from __future__ import annotations

import unittest

from frivault.metadata import (
    ROOT_ID,
    MetadataValidationError,
    empty_metadata,
    validate_metadata,
)


class MetadataValidationTests(unittest.TestCase):
    def test_valid_empty_metadata(self) -> None:
        self.assertEqual({}, validate_metadata(empty_metadata("Research vault"))["items"])

    def test_windows_reserved_and_path_names_are_rejected(self) -> None:
        for name in ("CON", "folder/name", "trail.", "two  spaces?", ""):
            with self.subTest(name=name), self.assertRaises(MetadataValidationError):
                empty_metadata(name)

    def test_duplicate_sibling_names_are_rejected_case_insensitively(self) -> None:
        payload = empty_metadata("Vault")
        payload["items"] = {
            "1" * 32: _folder("1" * 32, ROOT_ID, "Notes"),
            "2" * 32: _folder("2" * 32, ROOT_ID, "notes"),
        }
        with self.assertRaises(MetadataValidationError):
            validate_metadata(payload)

    def test_folder_cycle_is_rejected(self) -> None:
        payload = empty_metadata("Vault")
        payload["items"] = {
            "1" * 32: _folder("1" * 32, "2" * 32, "One"),
            "2" * 32: _folder("2" * 32, "1" * 32, "Two"),
        }
        with self.assertRaises(MetadataValidationError):
            validate_metadata(payload)


def _folder(item_id: str, parent_id: str, name: str) -> dict[str, object]:
    return {
        "id": item_id,
        "parent_id": parent_id,
        "name": name,
        "kind": "folder",
        "object_id": None,
        "size_bytes": None,
        "created_at_ns": 1,
        "modified_at_ns": 1,
        "favorite": False,
        "trashed": False,
    }


if __name__ == "__main__":
    unittest.main()
