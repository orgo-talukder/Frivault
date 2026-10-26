"""Crash-aware encrypted file and folder operations for an unlocked vault."""

from __future__ import annotations

import os
import secrets
import stat
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable, Iterable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frivault.crypto.format_v1 import (
    MAX_FILE_BYTES,
    OperationCancelledError,
    decrypt_stream,
    encrypt_stream,
)
from frivault.metadata import MAX_ITEMS, ROOT_ID, MetadataValidationError, validate_segment_name
from frivault.vault_crypto import object_wrapping_key
from frivault.vault_manager import VaultManager

OBJECTS_DIRECTORY = "objects"
OBJECT_SUFFIX = ".frivo"
IO_CHUNK_BYTES = 1024 * 1024
MAX_IMPORT_ENTRIES = 100_000
ProgressCallback = Callable[[int, int], None]


@dataclass
class OperationTask:
    """Observable state for one queued operation."""

    task_id: str
    state: str = "PENDING"
    completed_bytes: int = 0
    total_bytes: int = 0
    error: str | None = None
    _cancel: threading.Event | None = None
    _future: Future[Any] | None = None

    def cancel(self) -> bool:
        if self.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return False
        if self._cancel is not None:
            self._cancel.set()
        return True


class OperationQueue:
    """Run cancellable file operations away from the UI thread."""

    def __init__(self, max_workers: int = 2) -> None:
        if type(max_workers) is not int or not 1 <= max_workers <= 4:
            raise ValueError("Operation worker count must be between 1 and 4")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="frivault")
        self._tasks: dict[str, OperationTask] = {}
        self._lock = threading.RLock()

    def submit(self, operation: Callable[..., Any], *args: Any, **kwargs: Any) -> OperationTask:
        if "cancel" in kwargs or "progress" in kwargs:
            raise ValueError("cancel and progress are managed by the operation queue")
        task = OperationTask(task_id=secrets.token_hex(16), _cancel=threading.Event())
        with self._lock:
            self._tasks[task.task_id] = task

        def report(current: int, total: int) -> None:
            with self._lock:
                task.completed_bytes = max(0, current)
                task.total_bytes = max(0, total)

        def run() -> Any:
            with self._lock:
                task.state = "RUNNING"
            try:
                operation(
                    *args,
                    cancel=task._cancel,
                    progress=report,
                    **kwargs,
                )
                with self._lock:
                    task.state = "SUCCEEDED"
                return None
            except OperationCancelledError:
                with self._lock:
                    task.state = "CANCELLED"
                return None
            except Exception as exc:
                with self._lock:
                    task.state = "FAILED"
                    if isinstance(exc, (FileOperationError, OperationCancelledError)):
                        task.error = str(exc)
                    else:
                        task.error = f"Unexpected error ({type(exc).__name__})"
                raise

        task._future = self._executor.submit(run)
        return task

    def get(self, task_id: str) -> OperationTask:
        with self._lock:
            try:
                return self._tasks[task_id]
            except KeyError as exc:
                raise FileOperationError("Operation task is unavailable") from exc

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            tasks = list(self._tasks.values())
            return [
                {
                    "task_id": task.task_id,
                    "state": task.state,
                    "completed_bytes": task.completed_bytes,
                    "total_bytes": task.total_bytes,
                    "error": task.error,
                }
                for task in tasks
            ]

    def has_active(self) -> bool:
        with self._lock:
            return any(task.state in {"PENDING", "RUNNING"} for task in self._tasks.values())

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            for task in self._tasks.values():
                if task.state in {"PENDING", "RUNNING"}:
                    task.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=not wait)


class FileOperationError(ValueError):
    """Expected, safe file-operation failure."""


class NameConflictError(FileOperationError):
    """A destination item already has the requested name."""


@dataclass(frozen=True)
class _ImportEntry:
    relative_parts: tuple[str, ...]
    source: Path
    kind: str


class _NullWriter:
    def write(self, data: bytes | memoryview) -> int:
        return len(data)


class FileOperationService:
    """Operate on vault entries while keeping all names in encrypted metadata."""

    def __init__(self, vaults: VaultManager) -> None:
        self._vaults = vaults
        self._operation_lock = threading.RLock()

    def create_folder(self, vault_id: str, parent_id: str, name: str) -> dict[str, Any]:
        item_id = secrets.token_hex(16)
        timestamp = time.time_ns()
        item = _new_item(
            item_id=item_id,
            parent_id=parent_id,
            name=name,
            kind="folder",
            object_id=None,
            size_bytes=None,
            timestamp=timestamp,
        )

        def update(metadata: dict[str, Any]) -> dict[str, Any]:
            _require_folder(metadata, parent_id, allow_root=True)
            _ensure_name_available(metadata, parent_id, name)
            metadata["items"][item_id] = item
            return _view_item(item)

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def import_path(
        self,
        vault_id: str,
        source: Path | str,
        parent_id: str = ROOT_ID,
        *,
        conflict: str = "error",
        cancel: threading.Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Import one file or a complete folder tree as one metadata transaction."""

        entries = _collect_import_entries(Path(source))
        if not entries:
            raise FileOperationError("The selected import contains no supported files or folders")
        total_bytes = sum(entry.source.stat().st_size for entry in entries if entry.kind == "file")
        if conflict not in {"error", "rename", "skip", "replace"}:
            raise ValueError("Unsupported conflict policy")

        with self._operation_lock, self._vaults.operation_lease(vault_id) as lease:
            vault_path, master_key = lease
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
            _require_folder(metadata, parent_id, allow_root=True)
            root_entry = entries[0]
            root_name = root_entry.relative_parts[-1]
            existing = _find_sibling(metadata, parent_id, root_name)
            replaced_item: dict[str, Any] | None = None
            if existing is not None:
                if conflict == "skip":
                    return {"imported_files": 0, "imported_folders": 0, "bytes": 0, "skipped": 1}
                if conflict == "rename":
                    root_name = _unique_name(metadata, parent_id, root_name)
                elif conflict == "replace":
                    if root_entry.kind != "file" or existing["kind"] != "file":
                        raise NameConflictError(
                            "Replace is supported only for a file with the same name"
                        )
                    replaced_item = existing
                else:
                    raise NameConflictError("An item with that name already exists")

            objects_path = vault_path / OBJECTS_DIRECTORY
            _require_normal_directory(objects_path)
            new_items: dict[str, dict[str, Any]] = {}
            staged_objects: list[tuple[Path, str]] = []
            committed_objects: list[Path] = []
            item_ids_by_relative: dict[tuple[str, ...], str] = {}
            processed_bytes = 0
            try:
                with tempfile.TemporaryDirectory(prefix=".import-", dir=objects_path) as temp_name:
                    staging = Path(temp_name)
                    for entry_index, entry in enumerate(entries):
                        _check_cancel(cancel)
                        item_id = secrets.token_hex(16)
                        item_ids_by_relative[entry.relative_parts] = item_id
                        parent_parts = entry.relative_parts[:-1]
                        if entry_index == 0:
                            destination_parent = parent_id
                            name = root_name
                        else:
                            destination_parent = item_ids_by_relative[parent_parts]
                            name = entry.relative_parts[-1]
                        timestamp = time.time_ns()
                        object_id: str | None = None
                        size_bytes: int | None = None
                        if entry.kind == "file":
                            before = _regular_source_stat(entry.source)
                            if before.st_size > MAX_FILE_BYTES:
                                raise FileOperationError(
                                    "A selected file exceeds the supported size"
                                )
                            object_id = secrets.token_hex(16)
                            staged_path = staging / f"{object_id}{OBJECT_SUFFIX}"
                            with (
                                entry.source.open("rb") as source_file,
                                staged_path.open("xb") as output,
                            ):
                                size_bytes = encrypt_stream(
                                    source_file,
                                    output,
                                    object_wrapping_key(master_key),
                                    cancel_check=lambda: _check_cancel(cancel),
                                    on_progress=lambda current, base=processed_bytes: (
                                        _report_progress(progress, base + current, total_bytes)
                                    ),
                                )
                                output.flush()
                                os.fsync(output.fileno())
                            after = _regular_source_stat(entry.source)
                            if (before.st_size, before.st_mtime_ns) != (
                                after.st_size,
                                after.st_mtime_ns,
                            ) or size_bytes != before.st_size:
                                raise FileOperationError("A selected source changed during import")
                            processed_bytes += size_bytes
                            staged_objects.append((staged_path, object_id))
                        new_items[item_id] = _new_item(
                            item_id=item_id,
                            parent_id=destination_parent,
                            name=name,
                            kind=entry.kind,
                            object_id=object_id,
                            size_bytes=size_bytes,
                            timestamp=timestamp,
                        )

                    _check_cancel(cancel)
                    for staged_path, object_id in staged_objects:
                        final_path = objects_path / f"{object_id}{OBJECT_SUFFIX}"
                        staged_path.rename(final_path)
                        committed_objects.append(final_path)

                    def update(current: dict[str, Any]) -> dict[str, Any]:
                        _require_folder(current, parent_id, allow_root=True)
                        collision = _find_sibling(current, parent_id, root_name)
                        if collision is not None and (
                            replaced_item is None or collision["id"] != replaced_item["id"]
                        ):
                            raise NameConflictError("An item with that name appeared during import")
                        if replaced_item is not None:
                            current["items"].pop(replaced_item["id"])
                        current["items"].update(new_items)
                        return {
                            "imported_files": sum(
                                item["kind"] == "file" for item in new_items.values()
                            ),
                            "imported_folders": sum(
                                item["kind"] == "folder" for item in new_items.values()
                            ),
                            "bytes": processed_bytes,
                            "skipped": 0,
                            "item_ids": [item_ids_by_relative[root_entry.relative_parts]],
                        }

                    result = self._vaults.mutate_metadata(vault_id, update)
                    if replaced_item is not None:
                        _remove_unreferenced_objects(
                            objects_path,
                            {replaced_item["object_id"]},
                            self._vaults.get_unlocked_snapshot(vault_id)[2],
                        )
                    if progress is not None:
                        progress(total_bytes, total_bytes)
                    return result
            except BaseException:
                for committed_path in committed_objects:
                    try:
                        committed_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise

    def export_file(
        self,
        vault_id: str,
        item_id: str,
        destination: Path | str,
        *,
        replace: bool = False,
        cancel: threading.Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> Path:
        """Authenticate to a same-directory temporary file before publishing."""

        target = _validate_export_target(destination)
        with self._operation_lock, self._vaults.operation_lease(vault_id) as lease:
            vault_path, master_key = lease
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
            item = _require_item(metadata, item_id)
            if item["kind"] != "file" or item["trashed"]:
                raise FileOperationError("Choose an active file to export")
            if target.exists() and not replace:
                raise NameConflictError("The destination already exists")
            object_path = _object_path(vault_path, item["object_id"])
            temporary_path: Path | None = None
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=".frivault-export-", suffix=".tmp", dir=target.parent
                )
                temporary_path = Path(temporary_name)
                with os.fdopen(descriptor, "wb") as output, object_path.open("rb") as source:
                    actual_size = decrypt_stream(
                        source,
                        output,
                        object_wrapping_key(master_key),
                        cancel_check=lambda: _check_cancel(cancel),
                        on_progress=lambda current: _report_progress(
                            progress, current, item["size_bytes"]
                        ),
                    )
                    if actual_size != item["size_bytes"]:
                        raise FileOperationError("Encrypted file size does not match its metadata")
                    output.flush()
                    os.fsync(output.fileno())
                _check_cancel(cancel)
                if replace:
                    os.replace(temporary_path, target)
                elif os.name == "nt":
                    os.rename(temporary_path, target)
                else:
                    os.link(temporary_path, target)
                    temporary_path.unlink()
                return target
            except BaseException:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise

    def create_folder_metadata(self, vault_id: str, parent_id: str, name: str) -> dict[str, Any]:
        """Alias retained for callers using the explicit metadata action name."""

        return self.create_folder(vault_id, parent_id, name)

    def rename_item(self, vault_id: str, item_id: str, new_name: str) -> dict[str, Any]:
        validate_segment_name(new_name)

        def update(metadata: dict[str, Any]) -> dict[str, Any]:
            item = _require_item(metadata, item_id)
            if item["trashed"]:
                raise FileOperationError("Restore an item before renaming it")
            _ensure_name_available(metadata, item["parent_id"], new_name, exclude_id=item_id)
            item["name"] = new_name
            item["modified_at_ns"] = time.time_ns()
            return _view_item(item)

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def move_items(
        self,
        vault_id: str,
        item_ids: Iterable[str],
        destination_folder_id: str,
        *,
        rename_conflicts: bool = False,
    ) -> list[dict[str, Any]]:
        ids = _unique_ids(item_ids)

        def update(metadata: dict[str, Any]) -> list[dict[str, Any]]:
            _require_folder(metadata, destination_folder_id, allow_root=True)
            move_ids = _collapse_selection(metadata, ids)
            items = [_require_item(metadata, item_id) for item_id in move_ids]
            selected = set(move_ids)
            if any(item["trashed"] for item in items):
                raise FileOperationError("Restore items before moving them")
            for item in items:
                if item["kind"] == "folder" and _is_descendant(
                    metadata, destination_folder_id, item["id"]
                ):
                    raise FileOperationError("A folder cannot be moved into itself")
                item["parent_id"] = destination_folder_id
                if _find_sibling(
                    metadata, destination_folder_id, item["name"], exclude_id=item["id"]
                ):
                    if not rename_conflicts:
                        raise NameConflictError("A destination item already has that name")
                    item["name"] = _unique_name(
                        metadata,
                        destination_folder_id,
                        item["name"],
                        exclude_ids=selected,
                    )
                item["modified_at_ns"] = time.time_ns()
            return [_view_item(item) for item in items]

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def copy_items(
        self,
        vault_id: str,
        item_ids: Iterable[str],
        destination_folder_id: str,
        *,
        rename_conflicts: bool = False,
        cancel: threading.Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> list[dict[str, Any]]:
        ids = _unique_ids(item_ids)
        with self._operation_lock, self._vaults.operation_lease(vault_id) as lease:
            vault_path, master_key = lease
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
            _require_folder(metadata, destination_folder_id, allow_root=True)
            ids = _collapse_selection(metadata, ids)
            sources = [_require_item(metadata, item_id) for item_id in ids]
            if any(item["trashed"] for item in sources):
                raise FileOperationError("Restore items before copying them")
            for item in sources:
                if item["kind"] == "folder" and _is_descendant(
                    metadata, destination_folder_id, item["id"]
                ):
                    raise FileOperationError("A folder cannot be copied into itself or its child")

            objects_path = vault_path / OBJECTS_DIRECTORY
            _require_normal_directory(objects_path)
            new_items: dict[str, dict[str, Any]] = {}
            staged_objects: list[tuple[Path, str]] = []
            committed_objects: list[Path] = []
            total_bytes = sum(
                item["size_bytes"]
                for item in _subtree_items(metadata, ids)
                if item["kind"] == "file" and not item["trashed"]
            )
            try:
                with tempfile.TemporaryDirectory(prefix=".copy-", dir=objects_path) as temp_name:
                    staging = Path(temp_name)
                    for source_item in sources:
                        root_name = source_item["name"]
                        if _find_sibling(metadata, destination_folder_id, root_name):
                            if not rename_conflicts:
                                raise NameConflictError("A destination item already has that name")
                            root_name = _unique_name(metadata, destination_folder_id, root_name)
                        _clone_subtree(
                            metadata,
                            source_item,
                            destination_folder_id,
                            root_name,
                            new_items,
                            staged_objects,
                            staging,
                            vault_path,
                            master_key,
                            cancel,
                            progress,
                            lambda count: _report_progress(
                                progress,
                                sum(
                                    item["size_bytes"] or 0
                                    for item in new_items.values()
                                    if item["kind"] == "file"
                                )
                                + count,
                                total_bytes,
                            ),
                        )
                    _check_cancel(cancel)
                    for staged_path, object_id in staged_objects:
                        final_path = objects_path / f"{object_id}{OBJECT_SUFFIX}"
                        staged_path.rename(final_path)
                        committed_objects.append(final_path)

                    def update(current: dict[str, Any]) -> list[dict[str, Any]]:
                        _require_folder(current, destination_folder_id, allow_root=True)
                        for source_item in sources:
                            if _require_item(current, source_item["id"])["trashed"]:
                                raise FileOperationError("A source item changed during copy")
                        for item in new_items.values():
                            _ensure_name_available(
                                current,
                                item["parent_id"],
                                item["name"],
                                exclude_id=item["id"],
                            )
                        current["items"].update(new_items)
                        return [
                            _view_item(new_items[item_id])
                            for item_id in _root_copy_ids(new_items, destination_folder_id)
                        ]

                    result = self._vaults.mutate_metadata(vault_id, update)
                    if progress is not None:
                        progress(total_bytes, total_bytes)
                    return result
            except BaseException:
                for committed_path in committed_objects:
                    try:
                        committed_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise

    def trash_items(self, vault_id: str, item_ids: Iterable[str]) -> int:
        ids = _top_level_selection(item_ids)

        def update(metadata: dict[str, Any]) -> int:
            selected_ids = _collapse_selection(metadata, ids)
            count = 0
            for item_id in selected_ids:
                item = _require_item(metadata, item_id)
                if item["trashed"]:
                    continue
                for child in _subtree_items(metadata, [item_id]):
                    child["trashed"] = True
                    child["modified_at_ns"] = time.time_ns()
                    count += 1
            return count

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def restore_items(self, vault_id: str, item_ids: Iterable[str]) -> list[dict[str, Any]]:
        ids = _top_level_selection(item_ids)

        def update(metadata: dict[str, Any]) -> list[dict[str, Any]]:
            restored: list[dict[str, Any]] = []
            for item_id in _collapse_selection(metadata, ids):
                item = _require_item(metadata, item_id)
                if not item["trashed"]:
                    continue
                parent_id = item["parent_id"]
                if parent_id != ROOT_ID and _require_item(metadata, parent_id)["trashed"]:
                    raise FileOperationError("Restore the parent folder before restoring this item")
                if _find_sibling(metadata, parent_id, item["name"], exclude_id=item_id):
                    item["name"] = _unique_name(
                        metadata, parent_id, item["name"], exclude_id=item_id
                    )
                for child in _subtree_items(metadata, [item_id]):
                    child["trashed"] = False
                    child["modified_at_ns"] = time.time_ns()
                restored.append(_view_item(item))
            return restored

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def permanently_delete(self, vault_id: str, item_ids: Iterable[str]) -> int:
        ids = _top_level_selection(item_ids)
        with self._operation_lock, self._vaults.operation_lease(vault_id) as lease:
            vault_path, _ = lease
            _, _, snapshot = self._vaults.get_unlocked_snapshot(vault_id)
            ids = _collapse_selection(snapshot, ids)
            removed = _subtree_items(snapshot, ids)
            removed_ids = {item["id"] for item in removed}
            object_ids = {item["object_id"] for item in removed if item["kind"] == "file"}

            def update(metadata: dict[str, Any]) -> int:
                if any(not _require_item(metadata, item_id)["trashed"] for item_id in ids):
                    raise FileOperationError("Move items to Trash before permanent deletion")
                for item_id in removed_ids:
                    metadata["items"].pop(item_id, None)
                return len(removed_ids)

            count = self._vaults.mutate_metadata(vault_id, update)
            _, _, current = self._vaults.get_unlocked_snapshot(vault_id)
            _remove_unreferenced_objects(vault_path / OBJECTS_DIRECTORY, object_ids, current)
            return count

    def set_favorite(self, vault_id: str, item_ids: Iterable[str], favorite: bool) -> int:
        ids = _unique_ids(item_ids)
        if type(favorite) is not bool:
            raise ValueError("favorite must be a boolean")

        def update(metadata: dict[str, Any]) -> int:
            for item_id in ids:
                item = _require_item(metadata, item_id)
                if item["trashed"]:
                    raise FileOperationError("Restore an item before changing its favorite state")
                item["favorite"] = favorite
            return len(ids)

        with self._operation_lock, self._vaults.operation_lease(vault_id):
            return self._vaults.mutate_metadata(vault_id, update)

    def list_directory(
        self,
        vault_id: str,
        folder_id: str = ROOT_ID,
        *,
        sort_by: str = "name",
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        if sort_by not in {"name", "type", "size", "created", "modified"}:
            raise ValueError("Unsupported sort field")
        if type(descending) is not bool:
            raise ValueError("descending must be a boolean")
        with self._vaults.operation_lease(vault_id):
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
        _require_folder(metadata, folder_id, allow_root=True)
        items = [
            item
            for item in metadata["items"].values()
            if item["parent_id"] == folder_id and not item["trashed"]
        ]
        items.sort(key=lambda item: _sort_key(item, sort_by), reverse=descending)
        return [_view_item(item) for item in items]

    def search(
        self, vault_id: str, query: str, *, include_trashed: bool = False
    ) -> list[dict[str, Any]]:
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError("Search query must be at most 200 characters")
        if type(include_trashed) is not bool:
            raise ValueError("include_trashed must be a boolean")
        normalized_query = unicodedata.normalize("NFC", query).casefold().strip()
        with self._vaults.operation_lease(vault_id):
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
        results = [
            item
            for item in metadata["items"].values()
            if (include_trashed or not item["trashed"])
            and normalized_query in unicodedata.normalize("NFC", item["name"]).casefold()
        ]
        results.sort(key=lambda item: (item["name"].casefold(), item["id"]))
        return [_view_item(item) for item in results]

    def properties(self, vault_id: str, item_id: str) -> dict[str, Any]:
        with self._vaults.operation_lease(vault_id):
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
        return _view_item(_require_item(metadata, item_id))

    def storage_summary(self, vault_id: str) -> dict[str, int]:
        with self._vaults.operation_lease(vault_id) as (vault_path, _):
            _, _, metadata = self._vaults.get_unlocked_snapshot(vault_id)
        files = [item for item in metadata["items"].values() if item["kind"] == "file"]
        active_files = [item for item in files if not item["trashed"]]
        object_directory = vault_path / OBJECTS_DIRECTORY
        _require_normal_directory(object_directory)
        encrypted_bytes = sum(
            path.stat().st_size
            for path in object_directory.glob(f"*{OBJECT_SUFFIX}")
            if path.is_file() and not path.is_symlink()
        )
        return {
            "file_count": len(active_files),
            "folder_count": sum(
                item["kind"] == "folder" and not item["trashed"]
                for item in metadata["items"].values()
            ),
            "trash_count": sum(item["trashed"] for item in metadata["items"].values()),
            "plaintext_bytes": sum(item["size_bytes"] for item in active_files),
            "encrypted_bytes": encrypted_bytes,
        }


def _collect_import_entries(source: Path) -> list[_ImportEntry]:
    try:
        result = source.lstat()
    except OSError as exc:
        raise FileOperationError("Selected source is unavailable") from exc
    _reject_reparse_or_link(result)
    try:
        source = source.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FileOperationError("Selected source is unavailable") from exc
    if stat.S_ISREG(result.st_mode):
        validate_segment_name(source.name)
        if result.st_size > MAX_FILE_BYTES:
            raise FileOperationError("Selected file exceeds the supported size")
        return [_ImportEntry((source.name,), source, "file")]
    if not stat.S_ISDIR(result.st_mode):
        raise FileOperationError("Only regular files and folders can be imported")

    entries: list[_ImportEntry] = []

    def visit(directory: Path, relative: tuple[str, ...], depth: int) -> None:
        if depth > 256:
            raise FileOperationError("Folder nesting exceeds the supported limit")
        if len(entries) >= MAX_IMPORT_ENTRIES:
            raise FileOperationError("Folder contains too many items")
        validate_segment_name(directory.name)
        entries.append(_ImportEntry(relative, directory, "folder"))
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise FileOperationError("A selected folder could not be read") from exc
        for child in children:
            try:
                child_stat = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise FileOperationError("A selected folder entry could not be read") from exc
            _reject_reparse_or_link(child_stat)
            child_path = Path(child.path)
            name = validate_segment_name(child.name)
            child_relative = relative + (name,)
            if stat.S_ISDIR(child_stat.st_mode):
                visit(child_path, child_relative, depth + 1)
            elif stat.S_ISREG(child_stat.st_mode):
                if len(entries) >= MAX_IMPORT_ENTRIES:
                    raise FileOperationError("Folder contains too many items")
                if child_stat.st_size > MAX_FILE_BYTES:
                    raise FileOperationError("A selected file exceeds the supported size")
                entries.append(_ImportEntry(child_relative, child_path, "file"))
            else:
                raise FileOperationError("Folder contains an unsupported special file")

    visit(source, (source.name,), 0)
    return entries


def _require_normal_directory(path: Path) -> None:
    try:
        result = path.lstat()
    except OSError as exc:
        raise FileOperationError("Vault object storage is unavailable") from exc
    _reject_reparse_or_link(result)
    if not stat.S_ISDIR(result.st_mode):
        raise FileOperationError("Vault object storage is invalid")


def _regular_source_stat(path: Path) -> os.stat_result:
    try:
        result = path.lstat()
    except OSError as exc:
        raise FileOperationError("Selected source is unavailable") from exc
    _reject_reparse_or_link(result)
    if not stat.S_ISREG(result.st_mode):
        raise FileOperationError("Selected source is not a regular file")
    return result


def _reject_reparse_or_link(result: os.stat_result) -> None:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(result.st_mode) or getattr(result, "st_file_attributes", 0) & reparse_flag:
        raise FileOperationError("Links and reparse points are not imported")


def _validate_export_target(destination: Path | str) -> Path:
    candidate = Path(destination).expanduser()
    try:
        parent = candidate.parent.resolve(strict=True)
        parent_stat = parent.lstat()
        _reject_reparse_or_link(parent_stat)
        if not stat.S_ISDIR(parent_stat.st_mode):
            raise FileOperationError("Export destination folder is unavailable")
        target = parent / validate_segment_name(candidate.name)
        if target.is_symlink():
            raise FileOperationError("Export destination cannot be a symbolic link")
        if target.exists() and not target.is_file():
            raise FileOperationError("Export destination is not a regular file")
        return target
    except OSError as exc:
        raise FileOperationError("Export destination folder is unavailable") from exc


def _object_path(vault_path: Path, object_id: str) -> Path:
    object_directory = vault_path / OBJECTS_DIRECTORY
    _require_normal_directory(object_directory)
    path = object_directory / f"{object_id}{OBJECT_SUFFIX}"
    try:
        result = path.lstat()
    except OSError as exc:
        raise FileOperationError("Encrypted file object is missing") from exc
    _reject_reparse_or_link(result)
    if not stat.S_ISREG(result.st_mode):
        raise FileOperationError("Encrypted file object is invalid")
    return path


def _require_item(metadata: dict[str, Any], item_id: str) -> dict[str, Any]:
    if not isinstance(item_id, str) or len(item_id) != 32:
        raise FileOperationError("Invalid item identifier")
    try:
        return metadata["items"][item_id]
    except KeyError as exc:
        raise FileOperationError("Item is unavailable") from exc


def _require_folder(metadata: dict[str, Any], folder_id: str, *, allow_root: bool) -> None:
    if allow_root and folder_id == ROOT_ID:
        return
    folder = _require_item(metadata, folder_id)
    if folder["kind"] != "folder" or folder["trashed"]:
        raise FileOperationError("Destination folder is unavailable")


def _new_item(
    *,
    item_id: str,
    parent_id: str,
    name: str,
    kind: str,
    object_id: str | None,
    size_bytes: int | None,
    timestamp: int,
) -> dict[str, Any]:
    try:
        validate_segment_name(name)
    except MetadataValidationError as exc:
        raise FileOperationError(str(exc)) from exc
    return {
        "id": item_id,
        "parent_id": parent_id,
        "name": name,
        "kind": kind,
        "object_id": object_id,
        "size_bytes": size_bytes,
        "created_at_ns": timestamp,
        "modified_at_ns": timestamp,
        "favorite": False,
        "trashed": False,
    }


def _name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()


def _find_sibling(
    metadata: dict[str, Any],
    parent_id: str,
    name: str,
    *,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    key = _name_key(name)
    for item in metadata["items"].values():
        if (
            item["id"] != exclude_id
            and item["parent_id"] == parent_id
            and _name_key(item["name"]) == key
        ):
            return item
    return None


def _ensure_name_available(
    metadata: dict[str, Any],
    parent_id: str,
    name: str,
    *,
    exclude_id: str | None = None,
) -> None:
    validate_segment_name(name)
    if _find_sibling(metadata, parent_id, name, exclude_id=exclude_id) is not None:
        raise NameConflictError("An item with that name already exists")


def _unique_name(
    metadata: dict[str, Any],
    parent_id: str,
    name: str,
    *,
    exclude_id: str | None = None,
    exclude_ids: set[str] | None = None,
) -> str:
    suffix = Path(name).suffix
    stem = name[: -len(suffix)] if suffix else name
    exclusions = exclude_ids or set()
    for number in range(2, 100_002):
        candidate = f"{stem} ({number}){suffix}"
        if _find_sibling(metadata, parent_id, candidate, exclude_id=exclude_id) is None and not any(
            item["id"] in exclusions
            and item["parent_id"] == parent_id
            and _name_key(item["name"]) == _name_key(candidate)
            for item in metadata["items"].values()
        ):
            return validate_segment_name(candidate)
    raise NameConflictError("Unable to create a unique destination name")


def _is_descendant(metadata: dict[str, Any], candidate_id: str, ancestor_id: str) -> bool:
    current = candidate_id
    while current != ROOT_ID:
        if current == ancestor_id:
            return True
        current = _require_item(metadata, current)["parent_id"]
    return False


def _subtree_items(metadata: dict[str, Any], root_ids: Iterable[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    stack = list(root_ids)
    while stack:
        item = _require_item(metadata, stack.pop())
        result.append(item)
        if item["kind"] == "folder":
            stack.extend(
                child["id"]
                for child in metadata["items"].values()
                if child["parent_id"] == item["id"]
            )
    return result


def _unique_ids(item_ids: Iterable[str]) -> list[str]:
    ids = list(item_ids)
    if not ids or len(ids) > MAX_ITEMS or any(not isinstance(value, str) for value in ids):
        raise ValueError("Select between 1 and the supported maximum number of items")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate item identifiers are not allowed")
    return ids


def _top_level_selection(item_ids: Iterable[str]) -> list[str]:
    return _unique_ids(item_ids)


def _collapse_selection(metadata: dict[str, Any], ids: list[str]) -> list[str]:
    selected = set(ids)
    roots: list[str] = []
    for item_id in ids:
        item = _require_item(metadata, item_id)
        parent_id = item["parent_id"]
        nested = False
        while parent_id != ROOT_ID:
            if parent_id in selected:
                nested = True
                break
            parent_id = _require_item(metadata, parent_id)["parent_id"]
        if not nested:
            roots.append(item_id)
    return roots


def _view_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "parent_id": item["parent_id"],
        "name": item["name"],
        "kind": item["kind"],
        "size_bytes": item["size_bytes"],
        "created_at_ns": item["created_at_ns"],
        "modified_at_ns": item["modified_at_ns"],
        "favorite": item["favorite"],
        "trashed": item["trashed"],
    }


def _sort_key(item: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    folder_rank = 0 if item["kind"] == "folder" else 1
    if sort_by == "name":
        return folder_rank, _name_key(item["name"]), item["id"]
    if sort_by == "type":
        return folder_rank, Path(item["name"]).suffix.casefold(), _name_key(item["name"])
    if sort_by == "size":
        return folder_rank, item["size_bytes"] or 0, _name_key(item["name"])
    if sort_by == "created":
        return folder_rank, item["created_at_ns"], _name_key(item["name"])
    return folder_rank, item["modified_at_ns"], _name_key(item["name"])


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise OperationCancelledError("Operation cancelled")


def _report_progress(callback: ProgressCallback | None, current: int, total: int) -> None:
    if callback is not None:
        callback(current, total)


def _remove_unreferenced_objects(
    object_directory: Path,
    object_ids: set[str],
    metadata: dict[str, Any],
) -> None:
    retained = {item["object_id"] for item in metadata["items"].values() if item["kind"] == "file"}
    for object_id in object_ids - retained:
        try:
            (object_directory / f"{object_id}{OBJECT_SUFFIX}").unlink(missing_ok=True)
        except OSError:
            # The object is already unreachable from encrypted metadata; cleanup
            # can be retried by a future vault verification/garbage collection.
            continue


def _clone_subtree(
    metadata: dict[str, Any],
    source_item: dict[str, Any],
    parent_id: str,
    name: str,
    new_items: dict[str, dict[str, Any]],
    staged_objects: list[tuple[Path, str]],
    staging: Path,
    vault_path: Path,
    master_key: bytes,
    cancel: threading.Event | None,
    progress: ProgressCallback | None,
    advance: Callable[[int], None],
) -> None:
    _check_cancel(cancel)
    new_id = secrets.token_hex(16)
    object_id: str | None = None
    size_bytes: int | None = None
    if source_item["kind"] == "file":
        object_id = secrets.token_hex(16)
        source_path = _object_path(vault_path, source_item["object_id"])
        staged_path = staging / f"{object_id}{OBJECT_SUFFIX}"
        with source_path.open("rb") as source:
            verified_size = decrypt_stream(
                source,
                _NullWriter(),  # type: ignore[arg-type]
                object_wrapping_key(master_key),
                cancel_check=lambda: _check_cancel(cancel),
                on_progress=lambda current: _report_progress(
                    progress,
                    advance(current),
                    max(source_item["size_bytes"], 1),
                ),
            )
        if verified_size != source_item["size_bytes"]:
            raise FileOperationError("Encrypted source object does not match its metadata")
        with source_path.open("rb") as source, staged_path.open("xb") as output:
            while True:
                _check_cancel(cancel)
                part = source.read(IO_CHUNK_BYTES)
                if not part:
                    break
                output.write(part)
            output.flush()
            os.fsync(output.fileno())
        size_bytes = source_item["size_bytes"]
        staged_objects.append((staged_path, object_id))

    new_item = _new_item(
        item_id=new_id,
        parent_id=parent_id,
        name=name,
        kind=source_item["kind"],
        object_id=object_id,
        size_bytes=size_bytes,
        timestamp=time.time_ns(),
    )
    new_item["favorite"] = source_item["favorite"]
    new_items[new_id] = new_item

    if source_item["kind"] == "folder":
        children = sorted(
            (
                item
                for item in metadata["items"].values()
                if item["parent_id"] == source_item["id"] and not item["trashed"]
            ),
            key=lambda item: _name_key(item["name"]),
        )
        for child in children:
            _clone_subtree(
                metadata,
                child,
                new_id,
                child["name"],
                new_items,
                staged_objects,
                staging,
                vault_path,
                master_key,
                cancel,
                progress,
                advance,
            )


def _advance_progress(count: int, total: int) -> int:
    return count


def _root_copy_ids(new_items: dict[str, dict[str, Any]], destination_id: str) -> list[str]:
    return [item_id for item_id, item in new_items.items() if item["parent_id"] == destination_id]
