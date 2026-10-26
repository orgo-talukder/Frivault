# Frivault Security Requirements and Threat Model

## 1. Purpose and security posture

Frivault is intended to protect local files at rest using a
passphrase-protected encrypted vault. It is not a substitute for
operating-system security, malware protection, encrypted backups, or
safe user behavior. Do not advertise absolute security.

Before any public release, perform a security-focused code review and
test the vault format, key lifecycle, recovery, crash handling and
dependency packaging. Consider an independent review before making
strong security claims.

## 2. Threat model

### Assets

-   File contents.
-   Original filenames and folder structure.
-   Tags, favorites, Recent/Trash state and other private metadata.
-   Master key, derived keys and recovery material.
-   Temporary decrypted content and thumbnails.
-   Backups and exported files.

### Threats in scope

-   Someone obtains a copy of the locked vault directory.
-   Someone reads files on disk without knowing the passphrase.
-   Vault header or encrypted objects are modified or truncated.
-   A file operation is interrupted by a crash or power loss.
-   Malformed vault data attempts to trigger parser errors or resource
    exhaustion.
-   Private filenames leak through logs, cache files, notifications,
    search indexes or crash reports.
-   A wrong or malformed path attempts to escape the selected vault.

### Threats not fully solved by this application

-   Malware or keyloggers running as the logged-in user.
-   An attacker controlling the desktop while the vault is unlocked.
-   Memory inspection by a sufficiently privileged attacker.
-   Plaintext exported or opened in another application.
-   Copies retained by Windows, external apps, backups, snapshots,
    filesystem journals or SSD wear levelling.
-   Weak passphrases or a user losing all recovery material.
-   Physical coercion or advanced forensic attacks.

## 3. Cryptographic design requirements

-   Use maintained, reviewed cryptographic libraries.
-   Use authenticated encryption. The selected v1 format uses libsodium
    secretstream through PyNaCl for large-file streaming and
    XChaCha20-Poly1305 for wrapping. See `vault_format_v1.md`. The format
    is implemented and locally tested, but not independently audited or
    approved for public release.
-   Use a random master key generated from a cryptographically secure
    random source.
-   Use Argon2id for passphrase-based key derivation, with per-vault
    random salt.
-   Benchmark KDF parameters on supported hardware; store the
    algorithm/version/parameters in the header and enforce strict safe
    limits before running them.
-   Wrap the random master key with the derived key-encryption key.
-   Use the master key to protect file content and private metadata
    through a documented key hierarchy.
-   Use unique nonces as required by the chosen algorithm and format.
    Never reuse a nonce with the same AEAD key.
-   Authenticate format/version/record identifiers as associated data
    where appropriate.
-   Detect tampering, truncation, reordered chunks and invalid
    finalization.
-   Never create custom ciphers or cryptographic primitives.
-   Never store a plaintext password or raw master key on disk.

## 4. Large-file encryption

The v1 chunk format, production limits, metadata envelope and failure
behavior are specified in `vault_format_v1.md`. V1 exposes exact object
sizes and has no recovery key; migrations and independent review remain
release requirements.

Do not treat repeated independent AES-GCM calls as safe streaming
encryption unless nonce uniqueness, per-chunk authentication, ordering
and truncation detection are formally specified and tested. Use an
established streaming AEAD construction or obtain expert review of the
format.

## 5. Metadata privacy

Encrypt: - original filenames; - folder names and hierarchy; - tags and
favorites; - Trash state; - private timestamps where they reveal
sensitive behavior; - search index and recent activity.

Use random opaque object IDs for on-disk object names. The outer vault
folder name and total size may reveal that a vault exists and how large
it is. Prototype v1 also reveals each file's exact size because it does
not pad encrypted chunks. Decide whether production objects need padding.

Never expose private metadata while locked in: - dashboard widgets; -
notifications; - application logs; - Windows Search; - crash reports; -
thumbnail caches; - Recent lists; - browser history or localStorage; -
file previews; - temporary export files.

## 6. Key lifecycle

-   Passphrases are used only for key derivation and must not be
    persisted.
-   Do not keep key material in JavaScript.
-   Keep keys in Python service scope only as long as necessary.
-   Clear references and lock state on explicit lock, idle timeout,
    session lock or shutdown when possible. Python cannot guarantee
    perfect memory zeroization; document this limitation.
-   Do not store a recovery secret in the same unprotected directory as
    the vault.
-   Changing the passphrase should re-wrap the master key, after careful
    verification, rather than re-encrypt all file contents.
-   A lost passphrase with no valid recovery mechanism may make data
    permanently unrecoverable; explain this before vault creation.
-   A local key cache protected only by an ordinary preference file is
    prohibited.

## 7. Bridge and UI security

-   Load only bundled trusted local UI.
-   Block or safely externalize arbitrary navigation.
-   No remote JavaScript, analytics, ad scripts or remote UI assets.
-   Expose a small allowlisted Python API.
-   Validate every bridge argument in Python.
-   Never expose shell execution, arbitrary filesystem access, `eval`,
    dynamic imports or generic Python method dispatch.
-   Treat filenames and file contents as untrusted input; render them as
    text, not HTML.
-   Do not render active HTML/SVG/JavaScript content inside the
    privileged application view.
-   Protect local bridge endpoints/tokens if an HTTP bridge is used.
-   Do not use the bridge as an authorization bypass.

## 8. Filesystem and operation safety

-   Normalize and validate paths at the Python boundary.
-   Prevent path traversal and symlink/reparse-point escapes.
-   Use temporary files in controlled locations with restrictive
    permissions where supported.
-   Verify destination data before removing the source.
-   Use atomic replace where supported and a transaction/recovery
    strategy otherwise.
-   Do not follow unexpected links or special files during recursive
    import without an explicit safe policy.
-   Do not silently overwrite.
-   On authentication failure, never report a partial decrypt as
    successful.
-   Do not execute files from the vault.
-   External opening requires an explicit export/open workflow and a
    warning about plaintext copies.

## 9. Lock behavior

When locking: - stop accepting new sensitive operations; - safely finish
or cancel active tasks according to documented policy; - clear
filenames, search results, selected items, previews and thumbnails from
the UI; - remove sensitive DOM elements and navigation state; - release
key references as practically possible; - hide private notification
text; - ensure returning to the app requires unlocking.

Auto-lock must be tested under idle, session lock and sleep/resume
scenarios.

## 10. Logging and diagnostics

Allowed by default: app version, non-sensitive error code, operation
type, duration and coarse performance data.

Forbidden by default: passphrases, keys, decrypted filenames, contents,
search terms, recovery material, full paths that expose personal data.

Diagnostics should be opt-in, previewable and redact sensitive values.
No telemetry by default.

## 11. Security test checklist

-   Wrong passphrase.
-   Empty/weak passphrase warning.
-   Malformed header and extreme KDF parameters.
-   Modified tag/ciphertext.
-   Truncated/reordered chunk.
-   Corrupt encrypted metadata.
-   Duplicate IDs and malformed names.
-   Path traversal and symlink/reparse-point tests.
-   Disk full, permission denied, process termination and power-loss
    simulation.
-   Lock during active operations.
-   Search/thumbnail/notification/log leak checks.
-   Recovery and backup verification.
-   Dependency vulnerability review and packaged-runtime inspection.

## 12. Release claims

Do not claim "unhackable," "100% secure," "military-grade,"
"bank-level," or "independently audited" without evidence. Describe
specific protections and limitations plainly.
