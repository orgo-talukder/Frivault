from __future__ import annotations

import unittest

from frivault.crypto.format_v1 import MASTER_KEY_BYTES
from frivault.metadata import empty_metadata, validate_metadata
from frivault.vault_crypto import (
    MetadataIntegrityError,
    decrypt_metadata,
    derive_subkey,
    encrypt_metadata,
)


class MetadataEncryptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master_key = b"K" * MASTER_KEY_BYTES
        self.plaintext = b'{"vault_name":"Private name"}'

    def test_metadata_envelope_round_trip(self) -> None:
        encrypted = encrypt_metadata(self.master_key, self.plaintext)
        self.assertNotIn(b"Private name", encrypted)
        self.assertEqual(self.plaintext, decrypt_metadata(self.master_key, encrypted))

    def test_modified_metadata_is_rejected(self) -> None:
        encrypted = bytearray(encrypt_metadata(self.master_key, self.plaintext))
        encrypted[-1] ^= 1
        with self.assertRaises(MetadataIntegrityError):
            decrypt_metadata(self.master_key, bytes(encrypted))

    def test_truncated_or_oversized_metadata_is_rejected(self) -> None:
        with self.assertRaises(MetadataIntegrityError):
            decrypt_metadata(self.master_key, b"short")
        with self.assertRaises(ValueError):
            encrypt_metadata(self.master_key, b"x" * (64 * 1024 * 1024 + 1))

    def test_subkey_contexts_are_separated(self) -> None:
        self.assertNotEqual(
            derive_subkey(self.master_key, b"metadata"),
            derive_subkey(self.master_key, b"object wrap"),
        )

    def test_metadata_schema_starts_with_encrypted_private_name(self) -> None:
        metadata = empty_metadata("Private vault")
        self.assertEqual("Private vault", validate_metadata(metadata)["vault_name"])


if __name__ == "__main__":
    unittest.main()
