from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from frivault.bridge.api import AppApi
from frivault.crypto.format_v1 import KdfParams
from frivault.settings import AppSettings, SettingsStore
from frivault.vault_manager import VaultManager


class BridgeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.settings = SettingsStore(Path(self.temporary_directory.name) / "settings.json")
        self.api = AppApi(settings=self.settings)

    def tearDown(self) -> None:
        self.api._shutdown()
        self.temporary_directory.cleanup()

    def test_status_does_not_return_paths_or_private_metadata_when_closed(self) -> None:
        status = self.api.get_app_status()
        self.assertEqual("Frivault", status["data"]["product"])
        self.assertIsNone(status["data"]["vault"])
        self.assertFalse(status["data"]["settings"]["setup_complete"])
        self.assertFalse(status["data"]["settings"]["vault_configured"])
        self.assertNotIn("path", status["data"])
        self.assertNotIn("passphrase", status["data"])

    def test_only_validated_non_sensitive_settings_are_saved(self) -> None:
        saved = self.api.save_settings("dark", 5)
        self.assertEqual(
            {
                "theme": "dark",
                "auto_lock_minutes": 5,
                "default_sort_by": "name",
                "confirm_permanent_delete": True,
                "setup_complete": False,
                "vault_configured": False,
            },
            saved,
        )
        self.assertEqual("dark", self.settings.load().theme)
        self.assertIsNone(self.settings.load().vault_path)
        with self.assertRaises(ValueError):
            self.api.save_settings("remote", 5)

    def test_first_run_completion_requires_an_unlocked_vault(self) -> None:
        with self.assertRaises(ValueError):
            self.api.complete_first_run()

    def test_file_operation_bridge_methods_are_public(self) -> None:
        for method_name in (
            "import_files_dialog",
            "import_folder_dialog",
            "get_operations",
            "cancel_operation",
            "export_file_dialog",
        ):
            with self.subTest(method=method_name):
                self.assertTrue(callable(getattr(self.api, method_name, None)))

    def test_import_file_dialog_queues_each_selected_path(self) -> None:
        selected_path = str(Path(self.temporary_directory.name) / "sample.txt")
        window = Mock()
        window.create_file_dialog.return_value = [selected_path]
        self.api._attach_window(window)
        with (
            patch.object(self.api, "_require_vault", return_value="vault-id"),
            patch.object(
                self.api._operations,
                "submit",
                return_value=SimpleNamespace(task_id="operation-id"),
            ) as submit,
        ):
            result = self.api.import_files_dialog()
        self.assertEqual({"task_ids": ["operation-id"]}, result)
        self.assertIs(
            submit.call_args.args[0].__func__, self.api._files.import_path.__func__
        )
        self.assertEqual(("vault-id", selected_path), submit.call_args.args[1:])

    def test_first_run_completion_is_persisted_only_for_an_unlocked_vault(self) -> None:
        self.api._active_vault_id = "test-vault"
        with (
            patch.object(self.api._manager, "get_status", return_value={"state": "UNLOCKED"}),
            patch.object(
                self.api._manager,
                "get_vault_path",
                return_value=Path(self.temporary_directory.name) / "Frivault",
            ),
        ):
            saved = self.api.complete_first_run()
        self.assertTrue(saved["setup_complete"])
        self.assertTrue(self.settings.load().setup_complete)
        self.assertEqual(
            str(Path(self.temporary_directory.name) / "Frivault"),
            self.settings.load().vault_path,
        )

    def test_create_is_blocked_after_a_vault_has_been_configured(self) -> None:
        self.api._prefs = AppSettings(
            setup_complete=True,
            vault_path=str(Path(self.temporary_directory.name) / "Frivault"),
        )
        with self.assertRaisesRegex(ValueError, "already set up"):
            self.api.create_vault("Frivault", "a sufficiently long password")

    def test_saved_vault_is_registered_locked_at_startup(self) -> None:
        vault_parent = Path(self.temporary_directory.name) / "vaults"
        vault_parent.mkdir()
        manager = VaultManager(
            kdf_params=KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)
        )
        manager.create_vault(vault_parent, "Frivault", "correct horse battery staple")
        manager.lock_all()
        saved_settings = SettingsStore(Path(self.temporary_directory.name) / "saved.json")
        saved_settings.save(
            AppSettings(setup_complete=True, vault_path=str(vault_parent / "Frivault"))
        )

        restarted = AppApi(
            manager=VaultManager(
                kdf_params=KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)
            ),
            settings=saved_settings,
        )
        status = restarted.get_app_status()
        self.assertEqual("LOCKED", status["data"]["vault"]["state"])
        self.assertTrue(status["data"]["settings"]["vault_configured"])
        with self.assertRaises(ValueError):
            restarted.unlock_vault("this is the wrong password")
        self.assertEqual("LOCKED", restarted.get_app_status()["data"]["vault"]["state"])
        restarted._shutdown()


if __name__ == "__main__":
    unittest.main()
