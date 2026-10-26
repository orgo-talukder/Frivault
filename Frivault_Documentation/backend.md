# Frivault Backend Specification

## 1. Purpose

The Python backend is the authority for all vault, encryption,
file-system, persistence and security decisions. The HTML/JavaScript
frontend is not trusted to enforce access control. Every operation must
verify the current vault state and validate all inputs on the Python
side.

## 2. Core service interfaces

Implement small, testable service classes with dependency injection
where practical.

### `VaultManager`

Responsibilities: - Create a vault. - List vault locations remembered by
the app without exposing private metadata unnecessarily. - Open an
existing vault. - Unlock, lock and lock all. - Validate vault version
and header. - Report safe vault status and storage usage. - Remove a
vault from the app without deleting its contents.

### `KeyService`

Responsibilities: - Generate a random master key using a
cryptographically secure source. - Derive a key-encryption key from the
passphrase using Argon2id. - Wrap/unwrap the master key using
authenticated encryption. - Change passphrase by re-wrapping the master
key, not by re-encrypting all data. - Generate and validate recovery
material if the recovery design is implemented. - Keep secrets out of
logs and persistent browser storage.

### `CryptoService`

Responsibilities: - Provide authenticated encrypt/decrypt operations
through a reviewed library. - Implement the approved, versioned
large-file chunk format. - Validate authentication tags and detect
truncation/reordering. - Reject malformed headers and unsafe
parameters. - Never silently return partial plaintext as a successful
export.

Do not implement a bespoke cipher, home-grown KDF, or unauthenticated
encryption format.

The maintained v1 implementation is in `src/frivault/crypto/format_v1.py`;
the old `vault_prototype` module is a compatibility import only. Vault
creation, open, unlock and lock use v1. `FileOperationService` implements
the tested local workflows; `OperationQueue` provides cooperative
cancellation and progress for imports, exports and copies. An independent
cryptographic audit, migration design and built-in encrypted backup are
still release work.

### `MetadataRepository`

Responsibilities: - Read/write encrypted metadata. - Manage folders,
files, tags, favorites, Trash and private timestamps. - Validate
metadata schema and version. - Commit changes atomically or through a
recoverable transaction. - Prevent path traversal and duplicate-ID
conflicts.

### `FileOperationService`

Responsibilities: - Import files/folders. - Export files. -
Copy/move/rename/delete/duplicate. - Trash/restore/permanent-delete. -
Multi-select/bulk operations. - Conflict handling. - Progress,
cancellation and safe retries. - Disk-space and permission error
handling.

### `SearchService`

Responsibilities: - Search names and metadata only while unlocked. -
Apply filters and sorting. - Avoid persistent plaintext indexes. - Clear
in-memory indexes and results when locking. - Do not index file contents
in MVP unless a separate privacy review approves it.

### `BackupRecoveryService`

Responsibilities: - Create encrypted backups. - Verify backups. -
Restore to a safe destination. - Report incomplete or corrupt backup
data. - Preserve versioning and migration support.

### `PreviewService`

Responsibilities: - Support approved preview types. - Decrypt to memory
or controlled temporary storage as appropriate. - Avoid rendering active
content in the privileged webview. - Avoid plaintext thumbnail caches by
default. - Require explicit consent for opening/exporting content in
external apps.

### `SettingsService`

Responsibilities: - Store non-sensitive preferences in an OS-appropriate
app data directory. - Store no passphrases, master keys or private
filenames in ordinary preferences. - Validate theme, auto-lock timeout,
keyboard shortcuts and paths.

`SettingsStore` has a versioned schema for theme and auto-lock timeout.
It writes atomically beneath the current user's app configuration
directory and is wired to the Settings screen. Local logs are rotated
and must not include passphrases, keys, private names or paths.

## 3. JavaScript bridge contract

Expose explicit methods only. Suggested initial methods:

-   `get_app_status()`
-   `create_vault(options)`
-   `select_vault_location()`
-   `unlock_vault(vault_id, passphrase)`
-   `lock_vault(vault_id)`
-   `lock_all_vaults()`
-   `get_dashboard_summary()`
-   `list_directory(folder_id, sort, view_options)`
-   `search_items(query, filters)`
-   `create_folder(parent_id, name)`
-   `rename_item(item_id, new_name)`
-   `copy_items(item_ids, destination_folder_id)`
-   `move_items(item_ids, destination_folder_id)`
-   `trash_items(item_ids)`
-   `restore_items(item_ids, destination_folder_id)`
-   `permanently_delete_items(item_ids, confirmation_token)`
-   `select_import_files()`
-   `select_import_folder()`
-   `export_items(item_ids, destination)`
-   `get_operation_queue()`
-   `cancel_operation(operation_id)`
-   `retry_operation(operation_id)`
-   `get_settings()`
-   `save_settings(settings)`
-   `create_encrypted_backup(vault_id, destination)`
-   `verify_vault(vault_id)`

The implemented allowlist lives in `bridge/api.py`. Native file dialogs
own file and folder selection; the bridge does not expose arbitrary
filesystem paths for import or export. Pause/resume and retry are not
implemented because operations do not have durable checkpoints.

### Bridge response shape

Use JSON-compatible values and safe exception messages:

``` json
{
  "ok": true,
  "data": {},
  "error": null
}
```

Failure example:

``` json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "VAULT_LOCKED",
    "message": "Unlock the vault before performing this action."
  }
}
```

Do not return stack traces, keys, raw OS exception text, or sensitive
local paths to normal UI messages.

## 4. File operation rules

### Import

-   Resolve selected paths through native dialogs.
-   Reject unsupported special files or handle them explicitly.
-   Stream input in bounded chunks.
-   Encrypt to a temporary object.
-   Verify completion.
-   Commit object and metadata transactionally.
-   Preserve original source unless the user separately requests
    deletion.

### Export

-   Show the selected destination and a privacy warning.
-   Decrypt to a temporary destination file.
-   Authenticate every chunk and finalization state.
-   Only rename into the final destination after verification.
-   If authentication fails, delete the incomplete output where possible
    and report an integrity error.

### Move and replace

-   Destination must be written and verified before source deletion.
-   Resolve collisions using Skip, Rename or Replace.
-   Replace must be explicit and recoverable.
-   Cross-vault move is a copy-verify-delete workflow, not a blind
    rename.

### Trash and permanent delete

-   Trash is a metadata state that allows restore.
-   Permanent deletion must require confirmation and clear wording.
-   Do not promise forensic secure erase. Filesystem snapshots, SSD wear
    levelling, backups and external copies can retain data.

## 5. Background operations

-   Use a task manager with bounded worker concurrency.
-   UI updates must be marshalled safely to the webview.
-   Workers must not manipulate UI directly.
-   Cancellation is cooperative and must leave a valid state.
-   Retry only operations known to be retry-safe.
-   Pause/resume must be implemented only for operations with durable
    checkpoint semantics.
-   On application shutdown, safely checkpoint or cancel tasks; do not
    silently abandon half-written vault transactions.

## 6. Persistence and logs

-   Private metadata belongs in the encrypted vault.
-   Preferences may include theme, auto-lock duration and non-sensitive
    UI choices.
-   Never log passphrases, keys, decrypted filenames, contents, search
    queries or recovery secrets.
-   Use structured error codes.
-   Diagnostics should be opt-in and previewable before export.

## 7. Backend acceptance tests

-   Wrong passphrase fails without revealing private metadata.
-   Tampered header, metadata or object is rejected.
-   Truncated file and invalid chunk order are rejected.
-   Large import/export does not consume memory proportional to file
    size.
-   Disk-full and permission failures preserve existing data.
-   Cancelled operations clean up partial outputs safely.
-   Lock clears active search and preview state.
-   Every bridge method rejects invalid IDs, invalid state and malformed
    parameters.
