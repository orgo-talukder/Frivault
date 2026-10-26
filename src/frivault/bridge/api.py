"""Explicit pywebview bridge for local vault workflows."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

from frivault import __version__
from frivault.file_operations import FileOperationService, OperationQueue
from frivault.metadata import ROOT_ID, validate_segment_name
from frivault.settings import AppSettings, SettingsStore
from frivault.vault_manager import VaultBusyError, VaultManager


class AppApi:
    """Only expose specific, validated actions needed by bundled UI."""

    def __init__(
        self,
        *,
        manager: VaultManager | None = None,
        files: FileOperationService | None = None,
        settings: SettingsStore | None = None,
    ) -> None:
        self._manager = manager or VaultManager()
        self._files = files or FileOperationService(self._manager)
        self._operations = OperationQueue()
        self._settings = settings or SettingsStore()
        self._prefs = self._settings.load()
        self._active_vault_id: str | None = None
        self._window: Any = None
        self._timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._restore_saved_vault()

    def _restore_saved_vault(self) -> None:
        """Register the last vault as locked without restoring any secret."""

        saved_path = self._prefs.vault_path
        if saved_path is None:
            return
        try:
            vault_id = self._manager.open_vault(Path(saved_path))
        except (OSError, ValueError):
            return
        with self._lock:
            self._active_vault_id = vault_id

    def _remember_vault_path(self, vault_id: str, *, setup_complete: bool | None = None) -> None:
        settings = AppSettings(
            theme=self._prefs.theme,
            auto_lock_minutes=self._prefs.auto_lock_minutes,
            setup_complete=(
                self._prefs.setup_complete if setup_complete is None else setup_complete
            ),
            vault_path=str(self._manager.get_vault_path(vault_id)),
            default_sort_by=self._prefs.default_sort_by,
            confirm_permanent_delete=self._prefs.confirm_permanent_delete,
        )
        self._settings.save(settings)
        self._prefs = settings

    def _attach_window(self, window: Any) -> None:
        self._window = window

    def _require_window(self) -> Any:
        if self._window is None:
            raise RuntimeError("Desktop window is not ready")
        return self._window

    def _require_vault(self) -> str:
        with self._lock:
            if self._active_vault_id is None:
                raise ValueError("Open and unlock a vault first")
            vault_id = self._active_vault_id
        self._touch()
        return vault_id

    def _cancel_timer(self) -> None:
        with self._lock:
            timer, self._timer = self._timer, None
        if timer is not None:
            timer.cancel()

    def _schedule_timer(self) -> None:
        self._cancel_timer()
        seconds = self._prefs.auto_lock_minutes * 60
        timer = threading.Timer(seconds, self._auto_lock)
        timer.daemon = True
        with self._lock:
            self._timer = timer
        timer.start()

    def _touch(self) -> None:
        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is not None and self._manager.get_status(vault_id)["state"] == "UNLOCKED":
            self._schedule_timer()

    def _auto_lock(self) -> None:
        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is None:
            return
        try:
            self._manager.lock_vault(vault_id)
        except VaultBusyError:
            # A long file operation owns a lock lease. Retry once it has
            # released the key rather than interrupting a committed write.
            timer = threading.Timer(5, self._auto_lock)
            timer.daemon = True
            with self._lock:
                self._timer = timer
            timer.start()
            return
        with self._lock:
            self._timer = None

    @staticmethod
    def _selection(result: Any) -> list[str]:
        return list(result or [])

    def get_app_status(self) -> dict[str, object]:
        """Return safe application and session state."""

        with self._lock:
            vault_id = self._active_vault_id
        vault = self._manager.get_status(vault_id) if vault_id else None
        return {
            "ok": True,
            "data": {
                "product": "Frivault",
                "version": __version__,
                "phase": "workflow",
                "vault": vault,
                "settings": {
                    "theme": self._prefs.theme,
                    "auto_lock_minutes": self._prefs.auto_lock_minutes,
                    "default_sort_by": self._prefs.default_sort_by,
                    "confirm_permanent_delete": self._prefs.confirm_permanent_delete,
                    "density": self._prefs.density,
                    "setup_complete": self._prefs.setup_complete,
                    "vault_configured": self._prefs.vault_path is not None,
                },
            },
            "error": None,
        }

    def get_settings(self) -> dict[str, Any]:
        return {
            "theme": self._prefs.theme,
            "auto_lock_minutes": self._prefs.auto_lock_minutes,
            "default_sort_by": self._prefs.default_sort_by,
            "confirm_permanent_delete": self._prefs.confirm_permanent_delete,
            "density": self._prefs.density,
            "setup_complete": self._prefs.setup_complete,
            "vault_configured": self._prefs.vault_path is not None,
        }

    def complete_first_run(self) -> dict[str, Any]:
        """Persist completion after a vault is created or an existing one is unlocked."""

        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is None or self._manager.get_status(vault_id)["state"] != "UNLOCKED":
            raise ValueError("Create or unlock a vault before finishing setup")
        self._remember_vault_path(vault_id, setup_complete=True)
        return self.get_settings()

    def save_settings(
        self,
        theme: str,
        auto_lock_minutes: int,
        default_sort_by: str = "name",
        confirm_permanent_delete: bool = True,
        density: str = "comfortable",
    ) -> dict[str, Any]:
        settings = AppSettings(
            theme=theme,
            auto_lock_minutes=auto_lock_minutes,
            setup_complete=self._prefs.setup_complete,
            vault_path=self._prefs.vault_path,
            default_sort_by=default_sort_by,
            confirm_permanent_delete=confirm_permanent_delete,
            density=density,
        )
        self._settings.save(settings)
        self._prefs = settings
        self._touch()
        return self.get_settings()

    def ping(self) -> bool:
        """Reset inactivity timeout while the user is active."""

        self._touch()
        return True

    def create_vault(self, name: str, passphrase: str) -> dict[str, Any] | None:
        """Create the single first-run vault under a native-selected location."""

        if self._prefs.vault_path is not None:
            raise ValueError("A vault is already set up. Create another vault is disabled.")
        validate_segment_name(name, max_bytes=120)
        _validate_new_passphrase(passphrase)

        import webview

        result = self._require_window().create_file_dialog(webview.FileDialog.FOLDER)
        selected = self._selection(result)
        if not selected:
            return None
        _assert_outside_install_directory(Path(selected[0]))
        self._lock_current_vault()
        vault_id = self._manager.create_vault(Path(selected[0]), name, passphrase)
        with self._lock:
            self._active_vault_id = vault_id
        self._remember_vault_path(vault_id)
        self._schedule_timer()
        return self._manager.get_status(vault_id)

    def _lock_current_vault(self) -> None:
        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is not None:
            self._manager.lock_vault(vault_id)
        self._cancel_timer()
        with self._lock:
            self._active_vault_id = None

    def open_vault_dialog(self) -> dict[str, Any] | None:
        """Open a vault selected through a native folder picker."""

        import webview

        result = self._require_window().create_file_dialog(webview.FileDialog.FOLDER)
        selected = self._selection(result)
        if not selected:
            return None
        _assert_outside_install_directory(Path(selected[0]))
        self._lock_current_vault()
        vault_id = self._manager.open_vault(Path(selected[0]))
        with self._lock:
            self._active_vault_id = vault_id
        self._remember_vault_path(vault_id)
        return self._manager.get_status(vault_id)

    def unlock_vault(self, passphrase: str) -> dict[str, Any]:
        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is None:
            raise ValueError("Open a vault first")
        self._manager.unlock_vault(vault_id, passphrase)
        self._schedule_timer()
        return self._manager.get_status(vault_id)

    def change_vault_passphrase(self, current_passphrase: str, new_passphrase: str) -> bool:
        """Change the passphrase by rewrapping the active vault master key."""

        if not isinstance(current_passphrase, str) or not current_passphrase:
            raise ValueError("Enter your current password")
        _validate_new_passphrase(new_passphrase)
        if current_passphrase == new_passphrase:
            raise ValueError("Choose a new password different from the current password")
        self._manager.change_passphrase(
            self._require_vault(), current_passphrase, new_passphrase
        )
        return True

    def lock_vault(self) -> bool:
        with self._lock:
            vault_id = self._active_vault_id
        if vault_id is None:
            return True
        self._manager.lock_vault(vault_id)
        self._cancel_timer()
        return True

    def _shutdown(self) -> bool:
        self._cancel_timer()
        self._operations.close(wait=True)
        try:
            self._manager.lock_all()
        except VaultBusyError:
            return False
        with self._lock:
            self._active_vault_id = None
        return True

    def list_items(
        self,
        view: str = "files",
        folder_id: str = "00000000000000000000000000000000",
        sort_by: str = "name",
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        vault_id = self._require_vault()
        if view == "files":
            return self._files.list_directory(
                vault_id, folder_id, sort_by=sort_by, descending=descending
            )
        if view == "search":
            return []
        if view == "recent":
            items = self._files.search(vault_id, "")
            return sorted(items, key=lambda item: item["modified_at_ns"], reverse=True)[:100]
        if view == "favorites":
            return [item for item in self._files.search(vault_id, "") if item["favorite"]]
        if view == "trash":
            return [
                item
                for item in self._files.search(vault_id, "", include_trashed=True)
                if item["trashed"]
            ]
        raise ValueError("Unsupported item view")

    def search_items(self, query: str) -> list[dict[str, Any]]:
        return self._files.search(self._require_vault(), query)

    def get_storage_summary(self) -> dict[str, int]:
        return self._files.storage_summary(self._require_vault())

    def create_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        return self._files.create_folder(self._require_vault(), parent_id, name)

    def rename_item(self, item_id: str, name: str) -> dict[str, Any]:
        return self._files.rename_item(self._require_vault(), item_id, name)

    def trash_items(self, item_ids: list[str]) -> int:
        return self._files.trash_items(self._require_vault(), item_ids)

    def restore_items(self, item_ids: list[str]) -> list[dict[str, Any]]:
        return self._files.restore_items(self._require_vault(), item_ids)

    def permanently_delete_items(self, item_ids: list[str]) -> int:
        return self._files.permanently_delete(self._require_vault(), item_ids)

    def set_favorites(self, item_ids: list[str], favorite: bool) -> int:
        return self._files.set_favorite(self._require_vault(), item_ids, favorite)

    def get_item_properties(self, item_id: str) -> dict[str, Any]:
        return self._files.properties(self._require_vault(), item_id)

    def list_folders(self) -> list[dict[str, str]]:
        items = self._files.search(self._require_vault(), "")
        by_id = {item["id"]: item for item in items if item["kind"] == "folder"}
        result: list[dict[str, str]] = []
        for folder in by_id.values():
            parts = [folder["name"]]
            parent_id = folder["parent_id"]
            while parent_id != "00000000000000000000000000000000":
                parent = by_id.get(parent_id)
                if parent is None:
                    break
                parts.append(parent["name"])
                parent_id = parent["parent_id"]
            result.append({"id": folder["id"], "path": "/".join(reversed(parts))})
        return sorted(result, key=lambda folder: folder["path"].casefold())

    def move_items(self, item_ids: list[str], destination_folder_id: str) -> list[dict[str, Any]]:
        return self._files.move_items(self._require_vault(), item_ids, destination_folder_id)

    def copy_items(self, item_ids: list[str], destination_folder_id: str) -> dict[str, str]:
        task = self._operations.submit(
            self._files.copy_items,
            self._require_vault(),
            item_ids,
            destination_folder_id,
        )
        return {"task_id": task.task_id}

    def get_operations(self) -> list[dict[str, Any]]:
        return self._operations.list()

    def cancel_operation(self, task_id: str) -> bool:
        return self._operations.get(task_id).cancel()

    def import_files_dialog(self, destination_folder_id: str = ROOT_ID) -> dict[str, list[str]]:
        import webview

        result = self._require_window().create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=True
        )
        return self._import_selected(result, destination_folder_id)

    def import_folder_dialog(self, destination_folder_id: str = ROOT_ID) -> dict[str, list[str]]:
        import webview

        result = self._require_window().create_file_dialog(webview.FileDialog.FOLDER)
        return self._import_selected(result, destination_folder_id)

    def _import_selected(self, result: Any, destination_folder_id: str = ROOT_ID) -> dict[str, list[str]]:
        vault_id = self._require_vault()
        selected = self._selection(result)
        task_ids = [
            self._operations.submit(
                self._files.import_path, vault_id, path, destination_folder_id
            ).task_id
            for path in selected
        ]
        return {"task_ids": task_ids}

    def export_file_dialog(self, item_id: str) -> dict[str, str] | None:
        import webview

        vault_id = self._require_vault()
        item = self._files.properties(vault_id, item_id)
        if item["kind"] != "file" or item["trashed"]:
            raise ValueError("Choose an active file to export")
        result = self._require_window().create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=item["name"],
        )
        selected = self._selection(result)
        if not selected:
            return None
        task = self._operations.submit(self._files.export_file, vault_id, item_id, selected[0])
        return {"task_id": task.task_id}


def _assert_outside_install_directory(path: Path) -> None:
    """Keep user vaults out of the folder removed by the app uninstaller."""

    if not getattr(sys, "frozen", False):
        return
    install_root = Path(sys.executable).resolve().parent
    selected = path.resolve(strict=True)
    if selected == install_root or install_root in selected.parents:
        raise ValueError("Choose a vault location outside the Frivault application folder")


def _validate_new_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or len(passphrase.strip()) < 12:
        raise ValueError("Use a password with at least 12 non-space characters")
    try:
        encoded = passphrase.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("Password contains unsupported Unicode characters") from exc
    if len(encoded) > 1024:
        raise ValueError("Password exceeds the supported 1,024-byte limit")
