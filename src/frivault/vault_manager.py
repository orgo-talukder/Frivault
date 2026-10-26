"""Vault creation, discovery, unlock and lock lifecycle."""

from __future__ import annotations

import copy
import hmac
import json
import os
import secrets
import shutil
import stat
import tempfile
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from frivault.crypto.format_v1 import (
    VAULT_HEADER_BYTES,
    KdfParams,
    UnlockError,
    create_vault_header,
    rewrap_vault_header,
    unlock_vault_header,
)
from frivault.metadata import empty_metadata, validate_metadata
from frivault.vault_crypto import (
    MAX_METADATA_BYTES,
    MetadataIntegrityError,
    decrypt_metadata,
    encrypt_metadata,
)

HEADER_FILENAME = "vault.header"
METADATA_FILENAME = "metadata.enc"
OBJECTS_DIRECTORY = "objects"
_MAX_ENVELOPE_SIZE = 34 + MAX_METADATA_BYTES + 16


class VaultError(ValueError):
    """Safe, expected vault lifecycle failure."""


class VaultNotUnlockedError(VaultError):
    """A sensitive action was requested for a locked vault."""


class VaultBusyError(VaultError):
    """A vault cannot be locked while a sensitive operation is active."""


class VaultIntegrityError(VaultError):
    """The selected vault is malformed or authenticated data is invalid."""


@dataclass
class _VaultSession:
    vault_id: str
    path: Path
    state: str = "LOCKED"
    master_key: bytes | None = None
    metadata: dict[str, Any] | None = None


class VaultManager:
    """Manage in-memory vault sessions and durable encrypted metadata."""

    def __init__(self, *, kdf_params: KdfParams | None = None) -> None:
        self._kdf_params = kdf_params or KdfParams()
        self._lock = threading.RLock()
        self._sessions: dict[str, _VaultSession] = {}
        self._active_operations: dict[str, int] = {}

    def create_vault(self, parent: Path | str, name: str, passphrase: str) -> str:
        """Create a new vault beside the chosen parent and unlock it."""

        metadata = empty_metadata(name)
        parent_path = _resolve_directory(parent)
        target = parent_path / name
        if target.exists() or target.is_symlink():
            raise VaultError("A file or folder with that vault name already exists")

        staging_path = parent_path / f".frivault-create-{secrets.token_hex(12)}"
        try:
            staging_path.mkdir(mode=0o700)
            (staging_path / OBJECTS_DIRECTORY).mkdir(mode=0o700)
            header, master_key = create_vault_header(passphrase, params=self._kdf_params)
            _write_new_file(staging_path / HEADER_FILENAME, header)
            _write_metadata(staging_path / METADATA_FILENAME, master_key, metadata)
            staging_path.rename(target)
        except BaseException:
            if staging_path.is_dir() and not staging_path.is_symlink():
                shutil.rmtree(staging_path, ignore_errors=True)
            raise

        with self._lock:
            vault_id = self._register(target)
            session = self._sessions[vault_id]
            session.state = "UNLOCKED"
            session.master_key = master_key
            session.metadata = metadata
            return vault_id

    def open_vault(self, path: Path | str) -> str:
        """Register a structurally valid vault in the locked state."""

        vault_path = _resolve_directory(path)
        header_path = vault_path / HEADER_FILENAME
        metadata_path = vault_path / METADATA_FILENAME
        objects_path = vault_path / OBJECTS_DIRECTORY
        _require_regular_file(header_path, expected_size=VAULT_HEADER_BYTES)
        _require_regular_file(metadata_path, max_size=_MAX_ENVELOPE_SIZE)
        _require_directory(objects_path)
        with self._lock:
            for session in self._sessions.values():
                if session.path == vault_path:
                    return session.vault_id
            return self._register(vault_path)

    def unlock_vault(self, vault_id: str, passphrase: str) -> dict[str, Any]:
        """Authenticate a vault and load its private metadata into memory."""

        with self._lock:
            session = self._get_session(vault_id)
            if session.state == "UNLOCKED":
                raise VaultError("Vault is already unlocked")
            header = _read_bounded(session.path / HEADER_FILENAME, VAULT_HEADER_BYTES)
            try:
                master_key = unlock_vault_header(header, passphrase)
                envelope = _read_bounded(session.path / METADATA_FILENAME, _MAX_ENVELOPE_SIZE)
                plaintext = decrypt_metadata(master_key, envelope)
                metadata = json.loads(plaintext, object_pairs_hook=_unique_object)
                validate_metadata(metadata)
            except (ValueError, OSError, json.JSONDecodeError, MetadataIntegrityError) as exc:
                raise VaultIntegrityError(
                    "Passphrase is incorrect or vault data is damaged"
                ) from exc

            session.master_key = master_key
            session.metadata = metadata
            session.state = "UNLOCKED"
            return _public_metadata(metadata)

    def lock_vault(self, vault_id: str) -> None:
        """Clear the manager's live references to the key and private metadata."""

        with self._lock:
            session = self._get_session(vault_id)
            if self._active_operations.get(vault_id, 0):
                raise VaultBusyError("Wait for active vault operations before locking")
            session.master_key = None
            session.metadata = None
            session.state = "LOCKED"

    def lock_all(self) -> None:
        """Lock every registered vault."""

        with self._lock:
            if any(self._active_operations.values()):
                raise VaultBusyError("Wait for active vault operations before locking")
            for session in self._sessions.values():
                session.master_key = None
                session.metadata = None
                session.state = "LOCKED"

    def get_status(self, vault_id: str) -> dict[str, str | None]:
        """Return only the state and private name when the vault is unlocked."""

        with self._lock:
            session = self._get_session(vault_id)
            name = session.metadata["vault_name"] if session.metadata is not None else None
            return {"vault_id": session.vault_id, "state": session.state, "name": name}

    def get_vault_path(self, vault_id: str) -> Path:
        """Return the local vault path to trusted application services."""

        with self._lock:
            return self._get_session(vault_id).path

    def change_passphrase(
        self,
        vault_id: str,
        current_passphrase: str,
        new_passphrase: str,
    ) -> None:
        """Atomically replace the password envelope without rewriting vault data."""

        with self._lock:
            session = self._require_unlocked(vault_id)
            if self._active_operations.get(vault_id, 0):
                raise VaultBusyError(
                    "Wait for active vault operations before changing the password"
                )
            assert session.master_key is not None
            header_path = session.path / HEADER_FILENAME
            header = _read_bounded(header_path, VAULT_HEADER_BYTES)
            try:
                updated_header, verified_master_key = rewrap_vault_header(
                    header, current_passphrase, new_passphrase
                )
            except UnlockError as exc:
                raise VaultIntegrityError(
                    "Current password is incorrect or vault header is damaged"
                ) from exc
            if not hmac.compare_digest(verified_master_key, session.master_key):
                raise VaultIntegrityError("Vault header changed after this session was unlocked")
            _replace_file_atomically(header_path, updated_header, ".header-")

    def get_unlocked_snapshot(self, vault_id: str) -> tuple[Path, bytes, dict[str, Any]]:
        """Return internal service inputs without exposing them through the bridge."""

        with self._lock:
            session = self._require_unlocked(vault_id)
            assert session.master_key is not None and session.metadata is not None
            return session.path, session.master_key, copy.deepcopy(session.metadata)

    def commit_metadata(self, vault_id: str, metadata: dict[str, Any]) -> None:
        """Validate and atomically commit a complete private metadata snapshot."""

        validated = validate_metadata(metadata)
        encoded = json.dumps(
            validated,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_METADATA_BYTES:
            raise VaultError("Vault metadata exceeds the supported size limit")
        with self._lock:
            session = self._require_unlocked(vault_id)
            assert session.master_key is not None
            _write_metadata(session.path / METADATA_FILENAME, session.master_key, validated)
            session.metadata = copy.deepcopy(validated)

    def mutate_metadata(
        self,
        vault_id: str,
        update: Callable[[dict[str, Any]], Any],
    ) -> Any:
        """Apply a serialized metadata transaction and return its safe result."""

        with self._lock:
            session = self._require_unlocked(vault_id)
            assert session.master_key is not None and session.metadata is not None
            updated = copy.deepcopy(session.metadata)
            result = update(updated)
            validate_metadata(updated)
            _write_metadata(session.path / METADATA_FILENAME, session.master_key, updated)
            session.metadata = updated
            return copy.deepcopy(result)

    @contextmanager
    def operation_lease(self, vault_id: str) -> Iterator[tuple[Path, bytes]]:
        """Keep a vault unlocked while one bounded file operation uses its key."""

        with self._lock:
            session = self._require_unlocked(vault_id)
            assert session.master_key is not None
            self._active_operations[vault_id] = self._active_operations.get(vault_id, 0) + 1
            path, master_key = session.path, session.master_key
        try:
            yield path, master_key
        finally:
            with self._lock:
                active = self._active_operations.get(vault_id, 0) - 1
                if active <= 0:
                    self._active_operations.pop(vault_id, None)
                else:
                    self._active_operations[vault_id] = active

    def _register(self, path: Path) -> str:
        vault_id = secrets.token_hex(16)
        self._sessions[vault_id] = _VaultSession(vault_id=vault_id, path=path)
        return vault_id

    def _get_session(self, vault_id: str) -> _VaultSession:
        if not isinstance(vault_id, str):
            raise VaultError("Invalid vault identifier")
        try:
            return self._sessions[vault_id]
        except KeyError as exc:
            raise VaultError("Vault is not open in this session") from exc

    def _require_unlocked(self, vault_id: str) -> _VaultSession:
        session = self._get_session(vault_id)
        if session.state != "UNLOCKED" or session.master_key is None or session.metadata is None:
            raise VaultNotUnlockedError("Unlock the vault before performing this action")
        return session


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Copy safe presentation metadata without exposing mutable manager state."""

    return copy.deepcopy(metadata)


def _resolve_directory(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    try:
        stat_result = candidate.lstat()
        if _is_reparse_point(stat_result) or not stat.S_ISDIR(stat_result.st_mode):
            raise VaultError("Selected location is not a normal directory")
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise VaultError("Selected directory is unavailable") from exc
    return resolved


def _is_reparse_point(result: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(result, "st_file_attributes", 0) & reparse_flag)


def _require_directory(path: Path) -> None:
    try:
        result = path.lstat()
    except OSError as exc:
        raise VaultIntegrityError("Vault directory structure is incomplete") from exc
    if _is_reparse_point(result) or not stat.S_ISDIR(result.st_mode):
        raise VaultIntegrityError("Vault directory structure is invalid")


def _require_regular_file(
    path: Path,
    *,
    expected_size: int | None = None,
    max_size: int | None = None,
) -> None:
    try:
        result = path.lstat()
    except OSError as exc:
        raise VaultIntegrityError("Vault file structure is incomplete") from exc
    if _is_reparse_point(result) or not stat.S_ISREG(result.st_mode):
        raise VaultIntegrityError("Vault file structure is invalid")
    if expected_size is not None and result.st_size != expected_size:
        raise VaultIntegrityError("Vault file structure is invalid")
    if max_size is not None and result.st_size > max_size:
        raise VaultIntegrityError("Vault file exceeds supported bounds")


def _read_bounded(path: Path, max_size: int) -> bytes:
    _require_regular_file(path, max_size=max_size)
    with path.open("rb") as source:
        data = source.read(max_size + 1)
    if len(data) > max_size:
        raise VaultIntegrityError("Vault file exceeds supported bounds")
    return data


def _write_new_file(path: Path, data: bytes) -> None:
    with path.open("xb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())


def _replace_file_atomically(path: Path, data: bytes, prefix: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _write_metadata(path: Path, master_key: bytes, metadata: dict[str, Any]) -> None:
    encoded = json.dumps(
        metadata,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_METADATA_BYTES:
        raise VaultError("Vault metadata exceeds the supported size limit")
    envelope = encrypt_metadata(master_key, encoded)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".metadata-", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(envelope)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata key")
        result[key] = value
    return result
