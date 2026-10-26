# Vault Format v1 — Initial Security Prototype Notes

**Superseded:** `vault_format_v1.md` is the current format specification.
This file records the earlier prototype exploration only and is not the
implementation contract.

**Status:** frozen for the isolated prototype; not approved for production
vaults or valuable user data. The prototype has no migration or compatibility
commitment. A production format still requires security review, Windows
benchmarking, crash-recovery design, and release-gate tests.

## Decisions

- Password-derived key: Argon2id v1.3, 16-byte random salt, 32-byte output.
- V1 accepts a non-empty passphrase of at most 1,024 UTF-8 bytes.
- Baseline KDF parameters: 3 passes, 65,536 KiB memory, 4 lanes. This is
  RFC 9106's memory-constrained recommendation; it must be benchmarked on
  supported Windows devices before product use.
- KDF parser bounds: 1–6 passes, 65,536–262,144 KiB, 1–4 lanes. Enforce
  these bounds before running Argon2 on untrusted header fields.
- Key wrapping and per-object data-key wrapping: XChaCha20-Poly1305-IETF
  through PyNaCl/libsodium, with a fresh 24-byte random nonce per wrap.
- File content: libsodium `crypto_secretstream_xchacha20poly1305` through
  PyNaCl. Each stream uses a fresh random 32-byte data key and library-created
  stream header. Chunks are at most 1 MiB, each with the library's 17-byte
  authentication overhead.
- Maximum plaintext object size: `2^63 - 1` bytes; reject larger objects.
- Each file has a distinct 32-byte data key wrapped by the vault master key.
  The file object ID and stream header are authenticated as wrap associated
  data. Chunk associated data binds a domain label, object ID, and 64-bit
  sequence index.
- The library's final-message tag is mandatory. Reject missing final tags,
  data after the final tag, invalid tags, malformed frame lengths, and any
  authentication failure.

## Vault key header v1

All integers are unsigned big-endian. Header length is exactly 112 bytes.

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 8 | Magic `FRIVAULT` |
| 8 | 2 | Format version `1` |
| 10 | 1 | KDF ID `1` (Argon2id) |
| 11 | 1 | Argon2 version `19` (`0x13`) |
| 12 | 4 | Time cost |
| 16 | 4 | Memory in KiB |
| 20 | 4 | Parallelism |
| 24 | 16 | KDF salt |
| 40 | 24 | XChaCha20-Poly1305 nonce |
| 64 | 48 | Encrypted 32-byte master key plus 16-byte tag |

Bytes 0–63 are authenticated associated data for the encrypted master key.
Passphrases are interpreted as their exact UTF-8 encoding; v1 does not apply
Unicode normalization. The UI must disclose this behavior before production
use. A wrong passphrase and modified wrapped key produce the same safe
authentication error.

## File object v1

The fixed object header is 122 bytes:

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 8 | Magic `FRIVOBJ1` |
| 8 | 2 | Object format version `1` |
| 10 | 16 | Random opaque object ID |
| 26 | 24 | Data-key wrapping nonce |
| 50 | 24 | Secretstream header |
| 74 | 48 | Encrypted 32-byte data key plus tag |

The full 74-byte prefix is authenticated when wrapping the data key. The
object body is repeated records of a 4-byte big-endian ciphertext length and
one secretstream ciphertext chunk. The ciphertext length must be between 17
and 1,048,593 bytes. Empty input is represented by one authenticated empty
final chunk. No plaintext filename or folder name appears in this object
format. V1 does not pad records, so ciphertext lengths reveal the exact
plaintext object size; this metadata side-channel remains an accepted
prototype limitation and needs a product decision before production use.

## Streaming and failure behavior

Encryption uses one-chunk lookahead to identify the final chunk. Decryption
authenticates each chunk before writing that chunk to its destination, but
earlier chunks may already have been written when a later chunk fails. A file
operation must therefore decrypt only to a restricted temporary file, delete
that temporary output on any error, flush and verify it, then publish it
atomically without overwriting existing data. This safe file wrapper and the
vault metadata transaction are not implemented in the prototype.

The prototype exposes blocking binary stream functions only. It does not yet
define a vault directory layout, encrypted metadata schema, backups, recovery,
passphrase changes, object garbage collection, or migration. It has not been
reviewed as a complete cryptographic file format.

## Prototype checks

`tests/security/test_vault_format.py` covers key-header round trips, wrong
passphrases, header tampering, KDF bounds, empty and multi-chunk streams,
short reads, wrong keys, ciphertext tampering, truncation, reordered chunks,
trailing data, and oversized frame lengths. These are necessary prototype
checks, not a substitute for independent cryptographic review or full
application security tests.
