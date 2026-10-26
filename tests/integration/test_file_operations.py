from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from frivault.crypto.format_v1 import KdfParams, OperationCancelledError, StreamIntegrityError
from frivault.file_operations import FileOperationService, NameConflictError, OperationQueue
from frivault.vault_manager import VaultManager

TEST_KDF = KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)


class FileOperationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.manager = VaultManager(kdf_params=TEST_KDF)
        self.vault_id = self.manager.create_vault(self.root, "Vault", "correct horse")
        self.files = FileOperationService(self.manager)

    def tearDown(self) -> None:
        self.manager.lock_all()
        self.temporary_directory.cleanup()

    def test_import_folder_encrypts_files_and_export_authenticates_before_publish(self) -> None:
        source = self.root / "source"
        (source / "nested").mkdir(parents=True)
        (source / "alpha.txt").write_bytes(b"private alpha")
        (source / "nested" / "beta.bin").write_bytes(bytes(range(256)) * 31)

        result = self.files.import_path(self.vault_id, source)
        self.assertEqual(2, result["imported_files"])
        self.assertEqual(2, result["imported_folders"])
        self.assertEqual(1, len(result["item_ids"]))

        vault_path = self.root / "Vault"
        encrypted_objects = list((vault_path / "objects").glob("*.frivo"))
        self.assertEqual(2, len(encrypted_objects))
        self.assertTrue(
            all(b"private alpha" not in path.read_bytes() for path in encrypted_objects)
        )

        alpha = self.files.search(self.vault_id, "ALPHA")[0]
        destination = self.root / "exported.txt"
        self.files.export_file(self.vault_id, alpha["id"], destination)
        self.assertEqual(b"private alpha", destination.read_bytes())
        self.assertEqual(2, self.files.storage_summary(self.vault_id)["file_count"])

    def test_mutations_trash_restore_and_permanent_delete(self) -> None:
        source = self.root / "note.txt"
        source.write_text("hello", encoding="utf-8")
        imported = self.files.import_path(self.vault_id, source)
        item_id = imported["item_ids"][0]
        self.files.rename_item(self.vault_id, item_id, "renamed.txt")
        self.assertEqual("renamed.txt", self.files.properties(self.vault_id, item_id)["name"])
        self.files.set_favorite(self.vault_id, [item_id], True)
        self.assertTrue(self.files.search(self.vault_id, "renamed")[0]["favorite"])

        self.assertEqual(1, self.files.trash_items(self.vault_id, [item_id]))
        self.assertEqual([], self.files.search(self.vault_id, "renamed"))
        restored = self.files.restore_items(self.vault_id, [item_id])
        self.assertEqual(item_id, restored[0]["id"])
        self.assertEqual(1, self.files.trash_items(self.vault_id, [item_id]))
        self.assertEqual(1, self.files.permanently_delete(self.vault_id, [item_id]))
        self.assertEqual([], self.files.search(self.vault_id, "renamed", include_trashed=True))
        self.assertEqual(0, self.files.storage_summary(self.vault_id)["encrypted_bytes"])

    def test_import_conflicts_are_explicit_and_failed_import_leaves_no_entry(self) -> None:
        source = self.root / "same.txt"
        source.write_text("first", encoding="utf-8")
        self.files.import_path(self.vault_id, source)
        source.write_text("second", encoding="utf-8")
        with self.assertRaises(NameConflictError):
            self.files.import_path(self.vault_id, source)
        result = self.files.import_path(self.vault_id, source, conflict="rename")
        self.assertEqual(2, len(self.files.search(self.vault_id, "same")))
        self.assertEqual(1, result["imported_files"])

    def test_cancelled_import_leaves_no_metadata_or_final_object(self) -> None:
        import threading

        source = self.root / "cancelled-import.bin"
        source.write_bytes(b"private bytes")
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(OperationCancelledError):
            self.files.import_path(self.vault_id, source, cancel=cancel)
        self.assertEqual([], self.files.search(self.vault_id, "cancelled-import"))
        vault_path, _, _ = self.manager.get_unlocked_snapshot(self.vault_id)
        self.assertEqual([], list((vault_path / "objects").glob("*.frivo")))

    def test_cancelled_export_does_not_publish_partial_destination(self) -> None:
        source = self.root / "large.bin"
        source.write_bytes(b"x" * (2 * 1024 * 1024))
        item_id = self.files.import_path(self.vault_id, source)["item_ids"][0]
        destination = self.root / "cancelled.bin"
        import threading

        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(OperationCancelledError):
            self.files.export_file(self.vault_id, item_id, destination, cancel=cancel)
        self.assertFalse(destination.exists())
        self.assertEqual([], list(self.root.glob(".frivault-export-*.tmp")))

    def test_multichunk_export_verifies_all_ciphertext_before_publish(self) -> None:
        source = self.root / "multichunk.dat"
        contents = bytes(range(251)) * 12_000
        source.write_bytes(contents)
        item_id = self.files.import_path(self.vault_id, source)["item_ids"][0]
        destination = self.root / "round-trip.dat"
        self.files.export_file(self.vault_id, item_id, destination)
        self.assertEqual(contents, destination.read_bytes())

        vault_path, _, metadata = self.manager.get_unlocked_snapshot(self.vault_id)
        object_id = metadata["items"][item_id]["object_id"]
        object_path = vault_path / "objects" / f"{object_id}.frivo"
        encrypted = bytearray(object_path.read_bytes())
        encrypted[-1] ^= 1
        object_path.write_bytes(encrypted)
        damaged_destination = self.root / "damaged-export.dat"
        with self.assertRaises(StreamIntegrityError):
            self.files.export_file(self.vault_id, item_id, damaged_destination)
        self.assertFalse(damaged_destination.exists())
        self.assertEqual([], list(self.root.glob(".frivault-export-*.tmp")))

    def test_operation_queue_tracks_cancellation_without_leaking_exception_paths(self) -> None:
        queue = OperationQueue(max_workers=1)

        def cancellable(*, cancel, progress):
            while not cancel.wait(0.01):
                progress(1, 10)
            raise OperationCancelledError("Operation cancelled")

        task = queue.submit(cancellable)
        task.cancel()
        task._future.result(timeout=2)
        details = queue.get(task.task_id)
        self.assertEqual("CANCELLED", details.state)
        self.assertIsNone(details.error)
        queue.close()


if __name__ == "__main__":
    unittest.main()
