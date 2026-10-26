"""Validated, non-sensitive application preferences."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from platformdirs import PlatformDirs

SETTINGS_VERSION = 5
ALLOWED_THEMES = frozenset({"system", "light", "dark"})
ALLOWED_SORTS = frozenset({"name", "type", "size", "created", "modified"})
ALLOWED_DENSITIES = frozenset({"comfortable", "compact"})


@dataclass(frozen=True)
class AppSettings:
    """Preferences safe to persist outside the encrypted vault."""

    theme: str = "system"
    auto_lock_minutes: int = 15
    setup_complete: bool = False
    vault_path: str | None = None
    default_sort_by: str = "name"
    confirm_permanent_delete: bool = True
    density: str = "comfortable"

    def __post_init__(self) -> None:
        if self.theme not in ALLOWED_THEMES:
            raise ValueError("Unsupported theme")
        if type(self.auto_lock_minutes) is not int or not 1 <= self.auto_lock_minutes <= 480:
            raise ValueError("Auto-lock timeout must be between 1 and 480 minutes")
        if type(self.setup_complete) is not bool:
            raise ValueError("Setup completion must be a boolean")
        if not isinstance(self.default_sort_by, str) or self.default_sort_by not in ALLOWED_SORTS:
            raise ValueError("Unsupported default file sort")
        if type(self.confirm_permanent_delete) is not bool:
            raise ValueError("Delete confirmation preference must be a boolean")
        if self.density not in ALLOWED_DENSITIES:
            raise ValueError("Unsupported interface density")
        if self.vault_path is not None:
            if (
                not isinstance(self.vault_path, str)
                or not self.vault_path
                or "\x00" in self.vault_path
                or len(self.vault_path) > 32767
                or not Path(self.vault_path).is_absolute()
            ):
                raise ValueError("Vault location must be an absolute path")


def default_settings_path() -> Path:
    """Return the current user's app configuration path."""

    return PlatformDirs("Frivault", appauthor=False).user_config_path / "settings.json"


class SettingsStore:
    """Load and atomically save validated non-secret preferences."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_settings_path()

    def load(self) -> AppSettings:
        try:
            raw = self.path.read_text(encoding="utf-8")
            payload = json.loads(raw, object_pairs_hook=_unique_object)
            if not isinstance(payload, dict):
                raise ValueError("Unexpected settings fields")
            version = payload.get("version")
            if type(version) is not int:
                raise ValueError("Unsupported settings version")
            density = "comfortable"
            if version == 1 and set(payload) == {"version", "theme", "auto_lock_minutes"}:
                setup_complete = True
                vault_path = None
                default_sort_by = "name"
                confirm_permanent_delete = True
            elif version == 2 and set(payload) == {
                "version",
                "theme",
                "auto_lock_minutes",
                "setup_complete",
            }:
                setup_complete = payload["setup_complete"]
                vault_path = None
                default_sort_by = "name"
                confirm_permanent_delete = True
            elif version == 3 and set(payload) == {
                "version",
                "theme",
                "auto_lock_minutes",
                "setup_complete",
                "vault_path",
            }:
                setup_complete = payload["setup_complete"]
                vault_path = payload["vault_path"]
                default_sort_by = "name"
                confirm_permanent_delete = True
                density = "comfortable"
            elif version == 4 and set(payload) == {
                "version",
                "theme",
                "auto_lock_minutes",
                "setup_complete",
                "vault_path",
                "default_sort_by",
                "confirm_permanent_delete",
            }:
                setup_complete = payload["setup_complete"]
                vault_path = payload["vault_path"]
                default_sort_by = payload["default_sort_by"]
                confirm_permanent_delete = payload["confirm_permanent_delete"]
                density = "comfortable"
            elif version == SETTINGS_VERSION and set(payload) == {
                "version",
                "theme",
                "auto_lock_minutes",
                "setup_complete",
                "vault_path",
                "default_sort_by",
                "confirm_permanent_delete",
                "density",
            }:
                setup_complete = payload["setup_complete"]
                vault_path = payload["vault_path"]
                default_sort_by = payload["default_sort_by"]
                confirm_permanent_delete = payload["confirm_permanent_delete"]
                density = payload["density"]
            else:
                raise ValueError("Unexpected settings fields or version")
            if not isinstance(payload["theme"], str):
                raise ValueError("Invalid theme value")
            return AppSettings(
                theme=payload["theme"],
                auto_lock_minutes=payload["auto_lock_minutes"],
                setup_complete=setup_complete,
                vault_path=vault_path,
                default_sort_by=default_sort_by,
                confirm_permanent_delete=confirm_permanent_delete,
                density=density,
            )
        except FileNotFoundError:
            return AppSettings()
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        if not isinstance(settings, AppSettings):
            raise TypeError("settings must be an AppSettings instance")
        payload = {"version": SETTINGS_VERSION, **asdict(settings)}
        encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".settings-", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, self.path)
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
            raise ValueError("Duplicate settings key")
        result[key] = value
    return result
