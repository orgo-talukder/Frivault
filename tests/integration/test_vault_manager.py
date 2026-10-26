from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frivault.crypto.format_v1 import KdfParams
from frivault.vault_manager import VaultBusyError, VaultError, VaultIntegrityError, VaultManager

TEST_KDF = KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)


class VaultManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.parent = Path(self.temporary_directory.name)
        self.manager = VaultManager(kdf_params=TEST_KDF)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_lock_reopen_unlock_and_lock(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Private Vault", "correct horse")
        path = self.parent / "Private Vault"
        self.assertTrue((path / "vault.header").is_file())
        self.assertTrue((path / "metadata.enc").is_file())
        self.assertTrue((path / "objects").is_dir())
        self.assertEqual("UNLOCKED", self.manager.get_status(vault_id)["state"])
        self.assertEqual("Private Vault", self.manager.get_status(vault_id)["name"])

        self.manager.lock_vault(vault_id)
        self.assertEqual("LOCKED", self.manager.get_status(vault_id)["state"])
        self.assertIsNone(self.manager.get_status(vault_id)["name"])
        reopened_id = self.manager.open_vault(path)
        self.assertEqual("LOCKED", self.manager.get_status(reopened_id)["state"])
        metadata = self.manager.unlock_vault(reopened_id, "correct horse")
        self.assertEqual("Private Vault", metadata["vault_name"])
        self.manager.lock_all()
        self.assertEqual("LOCKED", self.manager.get_status(reopened_id)["state"])

    def test_wrong_passphrase_does_not_unlock_or_return_private_metadata(self) -> None:
        path = self.parent / "Vault"
        self.manager.create_vault(self.parent, "Vault", "correct horse")
        self.manager.lock_all()
        vault_id = self.manager.open_vault(path)
        with self.assertRaisesRegex(
            VaultIntegrityError, "Passphrase is incorrect or vault data is damaged"
        ):
            self.manager.unlock_vault(vault_id, "wrong")
        self.assertEqual("LOCKED", self.manager.get_status(vault_id)["state"])
        self.assertIsNone(self.manager.get_status(vault_id)["name"])

    def test_change_passphrase_rewraps_key_without_changing_encrypted_metadata(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Vault", "correct horse")
        vault_path = self.parent / "Vault"
        old_header = (vault_path / "vault.header").read_bytes()
        encrypted_metadata = (vault_path / "metadata.enc").read_bytes()

        self.manager.change_passphrase(
            vault_id, "correct horse", "a much stronger new passphrase"
        )

        self.assertNotEqual(old_header, (vault_path / "vault.header").read_bytes())
        self.assertEqual(encrypted_metadata, (vault_path / "metadata.enc").read_bytes())
        self.assertEqual("UNLOCKED", self.manager.get_status(vault_id)["state"])
        self.manager.lock_vault(vault_id)
        reopened_id = self.manager.open_vault(vault_path)
        with self.assertRaises(VaultIntegrityError):
            self.manager.unlock_vault(reopened_id, "correct horse")
        metadata = self.manager.unlock_vault(reopened_id, "a much stronger new passphrase")
        self.assertEqual("Vault", metadata["vault_name"])

    def test_wrong_current_passphrase_does_not_change_header(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Vault", "correct horse")
        header_path = self.parent / "Vault" / "vault.header"
        before = header_path.read_bytes()
        with self.assertRaises(VaultIntegrityError):
            self.manager.change_passphrase(vault_id, "wrong horse", "a new strong passphrase")
        self.assertEqual(before, header_path.read_bytes())

    def test_password_change_waits_for_active_file_operations(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Vault", "correct horse")
        with self.manager.operation_lease(vault_id):
            with self.assertRaises(VaultBusyError):
                self.manager.change_passphrase(
                    vault_id, "correct horse", "a new strong passphrase"
                )

    def test_metadata_ciphertext_does_not_contain_vault_name(self) -> None:
        self.manager.create_vault(self.parent, "Private Name", "correct horse")
        encrypted = (self.parent / "Private Name" / "metadata.enc").read_bytes()
        self.assertNotIn(b"Private Name", encrypted)

    def test_corrupt_metadata_fails_unlock(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Vault", "correct horse")
        self.manager.lock_vault(vault_id)
        path = self.parent / "Vault" / "metadata.enc"
        encrypted = bytearray(path.read_bytes())
        encrypted[-1] ^= 1
        path.write_bytes(encrypted)
        reopened_id = self.manager.open_vault(path.parent)
        with self.assertRaises(VaultIntegrityError):
            self.manager.unlock_vault(reopened_id, "correct horse")

    def test_create_does_not_overwrite_an_existing_folder(self) -> None:
        existing = self.parent / "Existing"
        existing.mkdir()
        marker = existing / "keep.txt"
        marker.write_text("preserve", encoding="utf-8")
        with self.assertRaises(VaultError):
            self.manager.create_vault(self.parent, "Existing", "correct horse")
        self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_lock_is_rejected_while_an_operation_holds_a_key_lease(self) -> None:
        vault_id = self.manager.create_vault(self.parent, "Vault", "correct horse")
        with self.manager.operation_lease(vault_id):
            with self.assertRaises(VaultBusyError):
                self.manager.lock_vault(vault_id)
        self.manager.lock_vault(vault_id)


if __name__ == "__main__":
    unittest.main()
