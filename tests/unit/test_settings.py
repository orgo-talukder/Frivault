from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from frivault.settings import AppSettings, SettingsStore


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "config" / "settings.json"
        self.store = SettingsStore(self.path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_missing_file_returns_safe_defaults(self) -> None:
        self.assertEqual(AppSettings(), self.store.load())

    def test_save_and_load_round_trip(self) -> None:
        expected = AppSettings(theme="dark", auto_lock_minutes=30)
        self.store.save(expected)
        self.assertEqual(expected, self.store.load())

    def test_version_one_settings_are_treated_as_previously_configured(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"version":1,"theme":"dark","auto_lock_minutes":30}', "utf-8"
        )
        self.assertEqual(
            AppSettings(theme="dark", auto_lock_minutes=30, setup_complete=True),
            self.store.load(),
        )

    def test_version_two_migrates_setup_state_without_a_saved_location(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"version":2,"theme":"dark","auto_lock_minutes":30,"setup_complete":true}',
            "utf-8",
        )
        self.assertEqual(
            AppSettings(theme="dark", auto_lock_minutes=30, setup_complete=True),
            self.store.load(),
        )

    def test_version_three_migrates_preferences_with_safe_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        legacy_path = str(self.path.parent / "Vault")
        self.path.write_text(
            json.dumps(
                {
                    "version": 3,
                    "theme": "dark",
                    "auto_lock_minutes": 30,
                    "setup_complete": True,
                    "vault_path": legacy_path,
                }
            ),
            "utf-8",
        )
        self.assertEqual(
            AppSettings(
                theme="dark",
                auto_lock_minutes=30,
                setup_complete=True,
                vault_path=legacy_path,
            ),
            self.store.load(),
        )

    def test_malformed_or_unknown_fields_return_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"version":2,"theme":"dark","auto_lock_minutes":15,"extra":"secret"}',
            "utf-8",
        )
        self.assertEqual(AppSettings(), self.store.load())

    def test_duplicate_json_keys_return_defaults(self) -> None:
        self.path.parent.mkdir(parents=True)
        self.path.write_text(
            '{"version":2,"theme":"dark","theme":"light","auto_lock_minutes":15,"setup_complete":false}',
            "utf-8",
        )
        self.assertEqual(AppSettings(), self.store.load())

    def test_boolean_timeout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AppSettings(auto_lock_minutes=True)

    def test_non_boolean_setup_state_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AppSettings(setup_complete=1)

    def test_relative_vault_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AppSettings(vault_path="relative-vault")

    def test_save_does_not_persist_unrecognized_data(self) -> None:
        self.store.save(AppSettings())
        self.assertEqual(
            {
                "version": 4,
                "theme": "system",
                "auto_lock_minutes": 15,
                "setup_complete": False,
                "vault_path": None,
                "default_sort_by": "name",
                "confirm_permanent_delete": True,
            },
            json.loads(self.path.read_text("utf-8")),
        )


if __name__ == "__main__":
    unittest.main()
