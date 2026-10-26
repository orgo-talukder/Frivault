# Frivault Vault Format v1

**Status:** selected and implemented as the current local format. It has
internal design notes and automated tests, but no independent security audit
or release approval. Do not use this development build as the only copy of
valuable data.

## Threat model and scope

V1 protects file contents and private metadata when an attacker obtains a
closed vault directory but not its passphrase. It detects modification,
truncation, reordering, wrong passphrases and malformed records. It does not
protect against malware or keyloggers on the unlocked desktop, privileged
memory inspection, weak passphrases, or plaintext exported to other apps.

The format leaks that a vault exists, the container's total size, object
count, and each object's exact byte size through unpadded chunk lengths.
Names, folder hierarchy, private timestamps, favorites and Trash state are
inside authenticated encrypted metadata. Losing the passphrase makes the
vault unrecoverable: v1 has no recovery key or password reset mechanism.

## Container layout

```text
<user-selected vault directory>/
├── vault.header       # fixed 112-byte key envelope
├── metadata.enc       # authenticated encrypted JSON snapshot
└── objects/
    └── <32 lowercase hex chars>.frivo  # opaque ID, encrypted file stream
```

No plaintext names or hierarchy are used in object paths. Object IDs are 16
random bytes encoded as lowercase hexadecimal. The metadata JSON schema has
`schema_version`, `vault_name`, `root_id`, and an `items` map. Each item has
an ID, parent ID, name, kind, optional object ID and byte size, private
timestamps, favorite flag and Trash flag. The parser rejects unknown fields,
duplicate keys, duplicate case-insensitive sibling names, invalid Windows
path segments, missing/non-folder parents, cycles, nesting over 256 levels,
and more than 100,000 entries. Metadata is capped at 64 MiB.

## Key hierarchy

1. Creation generates a random 32-byte master key.
2. Argon2id v1.3 derives a 32-byte key-encryption key from the exact UTF-8
   passphrase and a random 16-byte salt. The default is 3 passes, 64 MiB,
   4 lanes; untrusted headers are bounded to 1–6 passes, 64–256 MiB and 1–4
   lanes before KDF execution.
3. XChaCha20-Poly1305 wraps the master key. Header bytes 0–63 are authenticated
   associated data. The fixed header is 112 bytes.
4. HKDF-SHA256 derives separate 32-byte metadata and file-object wrapping keys
   from the master key using distinct Frivault v1 context labels.
5. Each file object gets a random 32-byte data key. That key is wrapped by the
   object-wrapping subkey; libsodium secretstream XChaCha20-Poly1305 encrypts
   file content in 1 MiB authenticated chunks with sequence-bound associated
   data and a mandatory final tag.

Passphrases are not normalized; their exact UTF-8 bytes are used, with a
1,024-byte limit. Derived keys, master keys and passphrases are never
persisted or logged. Python cannot guarantee zeroization of immutable key
objects in memory; locking clears the application's live references.

## Metadata envelope

The encrypted metadata file starts with a 34-byte prefix: 8-byte magic
`FRIVMDT1`, 2-byte big-endian version `1`, and a fresh 24-byte random nonce.
The rest is XChaCha20-Poly1305 ciphertext and its 16-byte tag. A fixed domain
label plus the entire prefix is authenticated. Authentication failure,
unsupported versions and invalid sizes fail closed.

## Crash and recovery behavior

Creation builds a randomized staging directory beside the selected target,
flushes its header and encrypted metadata, then renames the completed
directory into place. Existing targets are never overwritten. Metadata
updates are written to a same-directory temporary file, flushed and atomically
replaced. During file imports, the encrypted object must be completed and
verified before metadata references it; a crash can leave an unreachable
encrypted object, which is safe to reclaim later. Permanent deletion removes
metadata references before deleting unreferenced object data. V1 does not
claim power-loss durability beyond the guarantees of the filesystem and
Windows rename/flush behavior.

Exports must decrypt to a private temporary file and become visible at the
chosen destination only after the final stream tag authenticates. Any error
discards the temporary output. Temporary cleanup is not secure erasure.

## Internal review checklist

- [x] Use maintained Argon2id, HKDF, XChaCha20-Poly1305 and secretstream
      implementations; no custom cipher or KDF.
- [x] Authenticate header, metadata envelope, object-key envelope and each
      ordered chunk.
- [x] Bound KDF, metadata, names, tree depth and file-object sizes before
      expensive or unbounded work.
- [x] Require a final stream tag and reject trailing bytes.
- [x] Keep names and folder hierarchy out of plaintext paths and logs.
- [x] Write new vaults and metadata snapshots through temporary paths.
- [ ] Independent cryptographic and implementation review before public
      release or valuable-data recommendation.
- [ ] Benchmark default Argon2id settings on supported low-memory Windows
      hardware and consider an explicit calibration flow.
- [ ] Clean-machine packaging, crash-injection, backup/restore and migration
      review in later roadmap phases.
