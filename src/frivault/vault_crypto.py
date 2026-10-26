"""Versioned authenticated metadata encryption and vault subkey derivation."""

from __future__ import annotations

import secrets
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
)
from nacl.exceptions import CryptoError

from frivault.crypto.format_v1 import MASTER_KEY_BYTES

METADATA_MAGIC = b"FRIVMDT1"
METADATA_VERSION = 1
METADATA_NONCE_BYTES = 24
METADATA_TAG_BYTES = 16
MAX_METADATA_BYTES = 64 * 1024 * 1024
_METADATA_PREFIX = struct.Struct(">8sH24s")
_METADATA_AAD = b"Frivault encrypted metadata v1\x00"
_SUBKEY_AAD = b"Frivault key derivation v1\x00"
_METADATA_KEY_CONTEXT = b"metadata encryption key"
_OBJECT_WRAP_KEY_CONTEXT = b"file object key wrapping"


class MetadataIntegrityError(ValueError):
    """The metadata envelope is invalid or could not be authenticated."""


def derive_subkey(master_key: bytes, context: bytes) -> bytes:
    """Derive a purpose-separated 32-byte key from the random vault key."""

    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise ValueError("Master key must be exactly 32 bytes")
    if not isinstance(context, bytes) or not context or len(context) > 128:
        raise ValueError("Key context must be between 1 and 128 bytes")
    return HKDF(
        algorithm=hashes.SHA256(),
        length=MASTER_KEY_BYTES,
        salt=None,
        info=_SUBKEY_AAD + context,
    ).derive(master_key)


def object_wrapping_key(master_key: bytes) -> bytes:
    """Return the dedicated key used to wrap individual object keys."""

    return derive_subkey(master_key, _OBJECT_WRAP_KEY_CONTEXT)


def encrypt_metadata(master_key: bytes, plaintext: bytes) -> bytes:
    """Encrypt one bounded metadata snapshot with a fresh random nonce."""

    if not isinstance(plaintext, bytes) or len(plaintext) > MAX_METADATA_BYTES:
        raise ValueError("Metadata exceeds the supported size limit")
    nonce = secrets.token_bytes(METADATA_NONCE_BYTES)
    prefix = _METADATA_PREFIX.pack(METADATA_MAGIC, METADATA_VERSION, nonce)
    key = derive_subkey(master_key, _METADATA_KEY_CONTEXT)
    ciphertext = crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext,
        _METADATA_AAD + prefix,
        nonce,
        key,
    )
    return prefix + ciphertext


def decrypt_metadata(master_key: bytes, envelope: bytes) -> bytes:
    """Authenticate and decrypt a bounded metadata envelope."""

    minimum_size = _METADATA_PREFIX.size + METADATA_TAG_BYTES
    maximum_size = _METADATA_PREFIX.size + MAX_METADATA_BYTES + METADATA_TAG_BYTES
    if not isinstance(envelope, bytes) or not minimum_size <= len(envelope) <= maximum_size:
        raise MetadataIntegrityError("Encrypted metadata has an invalid size")
    prefix = envelope[: _METADATA_PREFIX.size]
    magic, version, nonce = _METADATA_PREFIX.unpack(prefix)
    if magic != METADATA_MAGIC or version != METADATA_VERSION:
        raise MetadataIntegrityError("Unsupported encrypted metadata format")
    key = derive_subkey(master_key, _METADATA_KEY_CONTEXT)
    try:
        return crypto_aead_xchacha20poly1305_ietf_decrypt(
            envelope[_METADATA_PREFIX.size :],
            _METADATA_AAD + prefix,
            nonce,
            key,
        )
    except CryptoError as exc:
        raise MetadataIntegrityError("Encrypted metadata authentication failed") from exc
