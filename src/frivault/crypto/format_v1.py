"""Version 1 key envelope and authenticated file stream format.

This implementation has local unit and security coverage, but has not
received an independent cryptographic audit. Callers must decrypt only to a
private temporary destination and publish it after complete authentication.
"""

from __future__ import annotations

import secrets
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO

from argon2.low_level import Type, hash_secret_raw
from nacl.bindings import (
    crypto_aead_xchacha20poly1305_ietf_decrypt,
    crypto_aead_xchacha20poly1305_ietf_encrypt,
    crypto_secretstream_xchacha20poly1305_ABYTES,
    crypto_secretstream_xchacha20poly1305_init_pull,
    crypto_secretstream_xchacha20poly1305_init_push,
    crypto_secretstream_xchacha20poly1305_pull,
    crypto_secretstream_xchacha20poly1305_push,
    crypto_secretstream_xchacha20poly1305_state,
    crypto_secretstream_xchacha20poly1305_TAG_FINAL,
    crypto_secretstream_xchacha20poly1305_TAG_MESSAGE,
)
from nacl.exceptions import CryptoError

VAULT_MAGIC = b"FRIVAULT"
VAULT_VERSION = 1
KDF_ARGON2ID = 1
ARGON2_VERSION = 19
MASTER_KEY_BYTES = 32
SALT_BYTES = 16
AEAD_NONCE_BYTES = 24
AEAD_TAG_BYTES = 16

# A 64 MiB floor bounds the cost of valid v1 headers. The ceiling prevents
# attacker-controlled headers from requesting unbounded memory or CPU work.
MIN_MEMORY_KIB = 64 * 1024
MAX_MEMORY_KIB = 256 * 1024
MIN_TIME_COST = 1
MAX_TIME_COST = 6
MIN_PARALLELISM = 1
MAX_PARALLELISM = 4
MAX_PASSPHRASE_BYTES = 1024

DEFAULT_KDF_TIME_COST = 3
DEFAULT_KDF_MEMORY_KIB = 64 * 1024
DEFAULT_KDF_PARALLELISM = 4

_VAULT_PREFIX = struct.Struct(">8sHBBIII16s24s")
VAULT_HEADER_BYTES = _VAULT_PREFIX.size + MASTER_KEY_BYTES + AEAD_TAG_BYTES

OBJECT_MAGIC = b"FRIVOBJ1"
OBJECT_VERSION = 1
CHUNK_BYTES = 1024 * 1024
MAX_FILE_BYTES = 2**63 - 1
_OBJECT_PREFIX = struct.Struct(">8sH16s24s24s")
OBJECT_HEADER_BYTES = _OBJECT_PREFIX.size + MASTER_KEY_BYTES + AEAD_TAG_BYTES
_FRAME_LENGTH = struct.Struct(">I")
_CHUNK_AAD_DOMAIN = b"Frivault object chunk v1\x00"
_WRAP_AAD_DOMAIN = b"Frivault object key v1\x00"


class FormatError(ValueError):
    """The untrusted input is malformed or outside the v1 format bounds."""


class UnlockError(ValueError):
    """The passphrase is incorrect or authenticated vault data was changed."""


class StreamIntegrityError(ValueError):
    """An encrypted object is incomplete, corrupted, reordered, or invalid."""


class OperationCancelledError(Exception):
    """A streaming operation was cancelled before its output was published."""


@dataclass(frozen=True)
class KdfParams:
    time_cost: int = DEFAULT_KDF_TIME_COST
    memory_kib: int = DEFAULT_KDF_MEMORY_KIB
    parallelism: int = DEFAULT_KDF_PARALLELISM


def _validate_kdf(params: KdfParams) -> None:
    values = (params.time_cost, params.memory_kib, params.parallelism)
    if any(type(value) is not int for value in values):
        raise FormatError("KDF parameters must be integers")
    if not MIN_TIME_COST <= params.time_cost <= MAX_TIME_COST:
        raise FormatError("KDF time cost is outside supported bounds")
    if not MIN_MEMORY_KIB <= params.memory_kib <= MAX_MEMORY_KIB:
        raise FormatError("KDF memory cost is outside supported bounds")
    if not MIN_PARALLELISM <= params.parallelism <= MAX_PARALLELISM:
        raise FormatError("KDF parallelism is outside supported bounds")
    if params.memory_kib < 8 * params.parallelism:
        raise FormatError("KDF memory is too small for its parallelism")


def _passphrase_bytes(passphrase: str) -> bytes:
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("Passphrase must be a non-empty string")
    # V1 uses the exact UTF-8 bytes entered by the user; it does not normalize
    # Unicode. The UI must explain this before the format is used for real data.
    encoded = passphrase.encode("utf-8", errors="strict")
    if len(encoded) > MAX_PASSPHRASE_BYTES:
        raise ValueError("Passphrase exceeds the v1 input limit")
    return encoded


def _derive_kek(passphrase: str, salt: bytes, params: KdfParams) -> bytes:
    _validate_kdf(params)
    return hash_secret_raw(
        secret=_passphrase_bytes(passphrase),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_kib,
        parallelism=params.parallelism,
        hash_len=MASTER_KEY_BYTES,
        type=Type.ID,
        version=ARGON2_VERSION,
    )


def create_vault_header(
    passphrase: str,
    *,
    params: KdfParams | None = None,
) -> tuple[bytes, bytes]:
    """Create a v1 header and random master key for the prototype."""

    params = params or KdfParams()
    _validate_kdf(params)
    _passphrase_bytes(passphrase)
    master_key = secrets.token_bytes(MASTER_KEY_BYTES)
    return _wrap_master_key(master_key, passphrase, params), master_key


def unlock_vault_header(header: bytes, passphrase: str) -> bytes:
    """Authenticate a v1 header and return its master key."""

    if not isinstance(header, bytes) or len(header) != VAULT_HEADER_BYTES:
        raise FormatError("Invalid vault header length")
    fields = _VAULT_PREFIX.unpack_from(header)
    magic, version, kdf_id, kdf_version, time_cost, memory_kib, parallelism, salt, nonce = fields
    if magic != VAULT_MAGIC or version != VAULT_VERSION:
        raise FormatError("Unsupported vault format")
    if kdf_id != KDF_ARGON2ID or kdf_version != ARGON2_VERSION:
        raise FormatError("Unsupported vault key derivation parameters")
    params = KdfParams(time_cost, memory_kib, parallelism)
    _validate_kdf(params)  # Bounds-check untrusted values before Argon2 runs.
    kek = _derive_kek(passphrase, salt, params)
    try:
        return crypto_aead_xchacha20poly1305_ietf_decrypt(
            header[_VAULT_PREFIX.size :], header[: _VAULT_PREFIX.size], nonce, kek
        )
    except CryptoError as exc:
        raise UnlockError("Passphrase is incorrect or vault header is damaged") from exc


def rewrap_vault_header(
    header: bytes,
    current_passphrase: str,
    new_passphrase: str,
) -> tuple[bytes, bytes]:
    """Authenticate the current passphrase and wrap the same master key anew."""

    _passphrase_bytes(new_passphrase)
    if current_passphrase == new_passphrase:
        raise ValueError("The new passphrase must be different from the current one")
    master_key = unlock_vault_header(header, current_passphrase)
    fields = _VAULT_PREFIX.unpack_from(header)
    params = KdfParams(time_cost=fields[4], memory_kib=fields[5], parallelism=fields[6])
    return _wrap_master_key(master_key, new_passphrase, params), master_key


def _wrap_master_key(master_key: bytes, passphrase: str, params: KdfParams) -> bytes:
    _validate_kdf(params)
    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise ValueError("Invalid master key")
    _passphrase_bytes(passphrase)
    salt = secrets.token_bytes(SALT_BYTES)
    wrap_nonce = secrets.token_bytes(AEAD_NONCE_BYTES)
    prefix = _VAULT_PREFIX.pack(
        VAULT_MAGIC,
        VAULT_VERSION,
        KDF_ARGON2ID,
        ARGON2_VERSION,
        params.time_cost,
        params.memory_kib,
        params.parallelism,
        salt,
        wrap_nonce,
    )
    kek = _derive_kek(passphrase, salt, params)
    wrapped_master_key = crypto_aead_xchacha20poly1305_ietf_encrypt(
        master_key, prefix, wrap_nonce, kek
    )
    return prefix + wrapped_master_key


def _read_up_to(source: BinaryIO, limit: int) -> bytes:
    """Read up to limit bytes, tolerating short reads from binary streams."""

    chunks: list[bytes] = []
    remaining = limit
    while remaining:
        part = source.read(remaining)
        if part is None:
            raise OSError("Non-blocking source streams are not supported")
        if not part:
            break
        if not isinstance(part, bytes):
            raise TypeError("Source must be a binary stream")
        if len(part) > remaining:
            raise OSError("Source returned more bytes than requested")
        chunks.append(part)
        remaining -= len(part)
    return b"".join(chunks)


def _read_exact(source: BinaryIO, length: int) -> bytes:
    data = _read_up_to(source, length)
    if len(data) != length:
        raise StreamIntegrityError("Encrypted object ended unexpectedly")
    return data


def _write_all(destination: BinaryIO, data: bytes) -> None:
    view = memoryview(data)
    written = 0
    while written < len(view):
        count = destination.write(view[written:])
        if count is None or count <= 0:
            raise OSError("Destination stream did not accept the complete write")
        written += count


def _chunk_aad(object_id: bytes, chunk_index: int) -> bytes:
    if chunk_index >= 2**64:
        raise StreamIntegrityError("Object has too many chunks")
    return _CHUNK_AAD_DOMAIN + object_id + chunk_index.to_bytes(8, "big")


def encrypt_stream(
    source: BinaryIO,
    destination: BinaryIO,
    master_key: bytes,
    *,
    cancel_check: Callable[[], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    """Encrypt a blocking binary source into a v1 file-object stream.

    The caller must use a new private temporary destination and only publish
    it after this function returns successfully.
    """

    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise ValueError("Master key must be exactly 32 bytes")

    object_id = secrets.token_bytes(16)
    wrap_nonce = secrets.token_bytes(AEAD_NONCE_BYTES)
    data_key = secrets.token_bytes(MASTER_KEY_BYTES)
    state = crypto_secretstream_xchacha20poly1305_state()
    stream_header = crypto_secretstream_xchacha20poly1305_init_push(state, data_key)
    prefix = _OBJECT_PREFIX.pack(OBJECT_MAGIC, OBJECT_VERSION, object_id, wrap_nonce, stream_header)
    wrapped_data_key = crypto_aead_xchacha20poly1305_ietf_encrypt(
        data_key, _WRAP_AAD_DOMAIN + prefix, wrap_nonce, master_key
    )
    _write_all(destination, prefix + wrapped_data_key)

    pending = _read_up_to(source, CHUNK_BYTES)
    index = 0
    total_bytes = len(pending)
    while True:
        if cancel_check is not None:
            cancel_check()
        following = _read_up_to(source, CHUNK_BYTES)
        if total_bytes + len(following) > MAX_FILE_BYTES:
            raise StreamIntegrityError("File exceeds the v1 size limit")
        final = not following
        tag = (
            crypto_secretstream_xchacha20poly1305_TAG_FINAL
            if final
            else crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
        )
        ciphertext = crypto_secretstream_xchacha20poly1305_push(
            state, pending, _chunk_aad(object_id, index), tag
        )
        _write_all(destination, _FRAME_LENGTH.pack(len(ciphertext)))
        _write_all(destination, ciphertext)
        if on_progress is not None and not final:
            on_progress(total_bytes - len(following))
        if final:
            if on_progress is not None:
                on_progress(total_bytes)
            return total_bytes
        pending = following
        total_bytes += len(following)
        index += 1


def decrypt_stream(
    source: BinaryIO,
    destination: BinaryIO,
    master_key: bytes,
    *,
    cancel_check: Callable[[], None] | None = None,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    """Authenticate and decrypt a v1 object stream in bounded chunks.

    Earlier authenticated chunks can reach destination before a later chunk
    fails. A caller must keep destination private and temporary until complete
    success, then atomically publish it. On any exception, discard it.
    """

    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise ValueError("Master key must be exactly 32 bytes")

    prefix = _read_exact(source, _OBJECT_PREFIX.size)
    magic, version, object_id, wrap_nonce, stream_header = _OBJECT_PREFIX.unpack(prefix)
    if magic != OBJECT_MAGIC or version != OBJECT_VERSION:
        raise FormatError("Unsupported encrypted object format")
    wrapped_data_key = _read_exact(source, MASTER_KEY_BYTES + AEAD_TAG_BYTES)
    try:
        data_key = crypto_aead_xchacha20poly1305_ietf_decrypt(
            wrapped_data_key, _WRAP_AAD_DOMAIN + prefix, wrap_nonce, master_key
        )
    except CryptoError as exc:
        raise StreamIntegrityError("Encrypted object header authentication failed") from exc

    state = crypto_secretstream_xchacha20poly1305_state()
    try:
        crypto_secretstream_xchacha20poly1305_init_pull(state, stream_header, data_key)
    except (CryptoError, RuntimeError) as exc:
        raise StreamIntegrityError("Encrypted object stream header is invalid") from exc

    index = 0
    total_bytes = 0
    while True:
        if cancel_check is not None:
            cancel_check()
        length_bytes = source.read(_FRAME_LENGTH.size)
        if length_bytes is None:
            raise OSError("Non-blocking source streams are not supported")
        if not length_bytes:
            raise StreamIntegrityError("Encrypted object is missing its final chunk")
        if len(length_bytes) != _FRAME_LENGTH.size:
            length_bytes += _read_exact(source, _FRAME_LENGTH.size - len(length_bytes))
        (ciphertext_length,) = _FRAME_LENGTH.unpack(length_bytes)
        if (
            not crypto_secretstream_xchacha20poly1305_ABYTES
            <= ciphertext_length
            <= CHUNK_BYTES + crypto_secretstream_xchacha20poly1305_ABYTES
        ):
            raise StreamIntegrityError("Encrypted chunk length is outside supported bounds")
        ciphertext = _read_exact(source, ciphertext_length)
        try:
            plaintext, tag = crypto_secretstream_xchacha20poly1305_pull(
                state, ciphertext, _chunk_aad(object_id, index)
            )
        except (CryptoError, ValueError) as exc:
            raise StreamIntegrityError("Encrypted chunk authentication failed") from exc

        if tag not in (
            crypto_secretstream_xchacha20poly1305_TAG_MESSAGE,
            crypto_secretstream_xchacha20poly1305_TAG_FINAL,
        ):
            raise StreamIntegrityError("Unexpected encrypted chunk tag")
        if tag == crypto_secretstream_xchacha20poly1305_TAG_MESSAGE and not plaintext:
            raise StreamIntegrityError("Empty non-final chunks are invalid")
        if len(plaintext) > CHUNK_BYTES:
            raise StreamIntegrityError("Decrypted chunk exceeds the format limit")
        if total_bytes + len(plaintext) > MAX_FILE_BYTES:
            raise StreamIntegrityError("File exceeds the v1 size limit")
        _write_all(destination, plaintext)
        total_bytes += len(plaintext)
        if on_progress is not None:
            on_progress(total_bytes)

        if tag == crypto_secretstream_xchacha20poly1305_TAG_FINAL:
            if source.read(1):
                raise StreamIntegrityError("Unexpected data follows the final chunk")
            return total_bytes
        index += 1
