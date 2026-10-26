"""Tamper and streaming checks for the selected version 1 format."""

from __future__ import annotations

import io
import struct
import unittest

from frivault.crypto.format_v1 import (
    CHUNK_BYTES,
    MASTER_KEY_BYTES,
    OBJECT_HEADER_BYTES,
    FormatError,
    KdfParams,
    StreamIntegrityError,
    UnlockError,
    create_vault_header,
    decrypt_stream,
    encrypt_stream,
    rewrap_vault_header,
    unlock_vault_header,
)

TEST_KDF = KdfParams(time_cost=1, memory_kib=64 * 1024, parallelism=1)
TEST_MASTER_KEY = bytes(range(MASTER_KEY_BYTES))


class ShortReadStream(io.BytesIO):
    """A blocking source that deliberately returns short reads."""

    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.largest_request = 0

    def read(self, size: int = -1) -> bytes:
        self.largest_request = max(self.largest_request, size)
        if size < 0:
            size = len(self.getbuffer())
        return super().read(min(size, 8191))


def encrypt_bytes(plaintext: bytes) -> bytes:
    encrypted = io.BytesIO()
    encrypt_stream(io.BytesIO(plaintext), encrypted, TEST_MASTER_KEY)
    return encrypted.getvalue()


def decrypt_bytes(ciphertext: bytes, key: bytes = TEST_MASTER_KEY) -> bytes:
    plaintext = io.BytesIO()
    decrypt_stream(io.BytesIO(ciphertext), plaintext, key)
    return plaintext.getvalue()


def frame_spans(ciphertext: bytes) -> list[tuple[int, int]]:
    """Return start/end offsets for each length-prefixed encrypted chunk."""

    spans = []
    cursor = OBJECT_HEADER_BYTES
    while cursor < len(ciphertext):
        (length,) = struct.unpack_from(">I", ciphertext, cursor)
        end = cursor + 4 + length
        spans.append((cursor, end))
        cursor = end
    if cursor != len(ciphertext):
        raise AssertionError("test ciphertext has invalid chunk framing")
    return spans


class VaultHeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.header, cls.master_key = create_vault_header("test-only passphrase", params=TEST_KDF)

    def test_round_trip_and_header_has_no_plaintext_passphrase(self) -> None:
        recovered = unlock_vault_header(self.header, "test-only passphrase")
        self.assertEqual(recovered, self.master_key)
        self.assertNotIn(b"test-only passphrase", self.header)

    def test_documented_default_kdf_round_trip(self) -> None:
        header, expected_key = create_vault_header("default kdf check")
        self.assertEqual(unlock_vault_header(header, "default kdf check"), expected_key)

    def test_overlong_passphrase_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            create_vault_header("x" * 1025, params=TEST_KDF)

    def test_wrong_passphrase_fails_authentication(self) -> None:
        with self.assertRaises(UnlockError):
            unlock_vault_header(self.header, "a different passphrase")

    def test_rewrap_changes_passphrase_but_preserves_master_key(self) -> None:
        changed_header, changed_key = rewrap_vault_header(
            self.header,
            "test-only passphrase",
            "a different test passphrase",
        )
        self.assertNotEqual(self.header, changed_header)
        self.assertEqual(self.master_key, changed_key)
        self.assertEqual(
            self.master_key,
            unlock_vault_header(changed_header, "a different test passphrase"),
        )
        with self.assertRaises(UnlockError):
            unlock_vault_header(changed_header, "test-only passphrase")

    def test_rewrap_with_wrong_current_passphrase_fails(self) -> None:
        with self.assertRaises(UnlockError):
            rewrap_vault_header(self.header, "wrong current", "a new test passphrase")

    def test_rewrap_rejects_same_passphrase(self) -> None:
        with self.assertRaisesRegex(ValueError, "different"):
            rewrap_vault_header(
                self.header,
                "test-only passphrase",
                "test-only passphrase",
            )

    def test_salt_tampering_fails_authentication(self) -> None:
        changed = bytearray(self.header)
        changed[24] ^= 1
        with self.assertRaises(UnlockError):
            unlock_vault_header(bytes(changed), "test-only passphrase")

    def test_untrusted_kdf_memory_is_bounded_before_derivation(self) -> None:
        changed = bytearray(self.header)
        struct.pack_into(">I", changed, 16, 256 * 1024 + 1)
        with self.assertRaises(FormatError):
            unlock_vault_header(bytes(changed), "test-only passphrase")

    def test_wrong_header_size_is_rejected(self) -> None:
        with self.assertRaises(FormatError):
            unlock_vault_header(self.header[:-1], "test-only passphrase")


class FileStreamTests(unittest.TestCase):
    def test_empty_file_round_trip(self) -> None:
        self.assertEqual(decrypt_bytes(encrypt_bytes(b"")), b"")

    def test_multichunk_round_trip_with_short_reads(self) -> None:
        source_data = bytes(range(251)) * ((2 * CHUNK_BYTES + 997) // 251)
        source_data = source_data[: 2 * CHUNK_BYTES + 997]
        source = ShortReadStream(source_data)
        encrypted = io.BytesIO()
        encrypt_stream(source, encrypted, TEST_MASTER_KEY)
        self.assertLessEqual(source.largest_request, CHUNK_BYTES)
        self.assertEqual(decrypt_bytes(encrypted.getvalue()), source_data)

    def test_wrong_master_key_is_rejected(self) -> None:
        with self.assertRaises(StreamIntegrityError):
            decrypt_bytes(encrypt_bytes(b"private data"), bytes(reversed(TEST_MASTER_KEY)))

    def test_ciphertext_tampering_is_rejected_before_that_chunk_is_written(self) -> None:
        changed = bytearray(encrypt_bytes(b"secret data"))
        first_start, _ = frame_spans(changed)[0]
        changed[first_start + 4 + 1] ^= 0x40
        destination = io.BytesIO()
        with self.assertRaises(StreamIntegrityError):
            decrypt_stream(io.BytesIO(changed), destination, TEST_MASTER_KEY)
        self.assertEqual(destination.getvalue(), b"")

    def test_truncated_final_record_is_rejected(self) -> None:
        encrypted = encrypt_bytes(b"secret data")
        with self.assertRaises(StreamIntegrityError):
            decrypt_bytes(encrypted[:-1])

    def test_reordered_chunks_are_rejected(self) -> None:
        encrypted = encrypt_bytes(b"x" * (2 * CHUNK_BYTES + 1))
        spans = frame_spans(encrypted)
        self.assertGreaterEqual(len(spans), 3)
        chunks = [encrypted[start:end] for start, end in spans]
        reordered = encrypted[:OBJECT_HEADER_BYTES] + chunks[0] + chunks[2] + chunks[1]
        with self.assertRaises(StreamIntegrityError):
            decrypt_bytes(reordered)

    def test_trailing_data_after_authenticated_final_is_rejected(self) -> None:
        with self.assertRaises(StreamIntegrityError):
            decrypt_bytes(encrypt_bytes(b"valid") + b"extra")

    def test_oversized_frame_length_is_rejected_before_reading_body(self) -> None:
        encrypted = bytearray(encrypt_bytes(b"valid"))
        struct.pack_into(">I", encrypted, OBJECT_HEADER_BYTES, CHUNK_BYTES + 18)
        with self.assertRaises(StreamIntegrityError):
            decrypt_bytes(bytes(encrypted))


if __name__ == "__main__":
    unittest.main()
