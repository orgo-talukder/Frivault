# Frivault Architecture

## 1. High-level architecture

``` text
Windows 11
└── Frivault Desktop Process
    ├── pywebview native window
    │   └── Local UI: HTML + CSS + JavaScript
    │       └── Narrow, allowlisted JS/Python bridge
    ├── Application services (Python)
    │   ├── VaultManager
    │   ├── AuthenticationAndKeyService
    │   ├── CryptoService
    │   ├── MetadataRepository
    │   ├── FileOperationService
    │   ├── SearchService
    │   ├── PreviewService
    │   ├── BackupRecoveryService
    │   ├── SettingsService
    │   └── DiagnosticsService
    └── Local storage
        ├── Encrypted vault container
        ├── Non-sensitive app preferences
        └── Restricted temporary operation files
```

## 2. Proposed project structure

``` text
frivault/
├── README.md
├── pyproject.toml
├── requirements.lock
├── .gitignore
├── docs/
│   ├── PRD.md
│   ├── TRD.md
│   ├── architecture.md
│   ├── backend.md
│   ├── frontend.md
│   ├── security.md
│   ├── ui_ux_design.md
│   ├── testing.md
│   ├── roadmap.md
│   └── references.md
├── src/
│   └── frivault/
│       ├── __init__.py
│       ├── main.py
│       ├── app_config.py
│       ├── bridge/
│       │   ├── __init__.py
│       │   └── api.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── errors.py
│       │   └── policies.py
│       ├── services/
│       │   ├── vault_manager.py
│       │   ├── key_service.py
│       │   ├── crypto_service.py
│       │   ├── metadata_service.py
│       │   ├── file_operations.py
│       │   ├── search_service.py
│       │   ├── preview_service.py
│       │   ├── backup_service.py
│       │   └── settings_service.py
│       ├── storage/
│       │   ├── vault_format.py
│       │   ├── metadata_repository.py
│       │   ├── transaction_journal.py
│       │   └── paths.py
│       ├── workers/
│       │   ├── task_manager.py
│       │   └── operation_worker.py
│       ├── platform/
│       │   └── windows_integration.py
│       └── resources/
│           └── ui/
│               ├── index.html
│               ├── assets/
│               ├── css/
│               │   ├── tokens.css
│               │   ├── base.css
│               │   ├── layout.css
│               │   ├── components.css
│               │   └── themes.css
│               └── js/
│                   ├── app.js
│                   ├── router.js
│                   ├── bridge.js
│                   ├── state.js
│                   ├── components/
│                   └── screens/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── ui/
│   └── fixtures/
└── packaging/
    ├── pyinstaller.spec
    ├── installer/
    └── licenses/
```

This is a target structure. Create only modules needed by the current
phase; do not generate empty files for every future feature.

## Current implementation checkpoint

The initial source package lives under `src/frivault/`. The current
foundation includes the pywebview entry point, a small read-only bridge,
resource path resolution, and a static UI under
`src/frivault/resources/ui/`. The UI is served from a local WSGI app that
allows only existing bundled files and applies a restrictive Content
Security Policy. This is foundation code, not a completed vault or a
security review. The browser bridge currently exposes only
`get_app_status()`.

The supplied root icon remains unchanged. An identical copy is bundled
under the UI assets directory for local brand display; the original ICO
is still the source asset. Executable, shortcut, installer, and taskbar
icon integration are not configured yet.

## 3. Responsibility boundaries

### Frontend

-   Render screens and user interaction.
-   Maintain ephemeral view state.
-   Validate for user convenience.
-   Call only explicit bridge methods.
-   Never implement encryption in JavaScript.
-   Never read arbitrary local paths or hold the master key.

### Bridge

-   Narrow allowlisted API.
-   Validate types, sizes, paths and operation state.
-   Return safe structured responses.
-   Enforce vault state and authorization for every call.
-   Avoid generic `call(method_name, args)` designs.

### Services

-   Own business rules, key lifecycle, encryption, file operations,
    transactions and validation.
-   Keep UI concerns out of core vault logic.
-   Expose clear interfaces that can be tested without the UI.

### Storage

-   Own vault format, authenticated metadata, atomic updates,
    transaction recovery and migration.
-   Treat every file and header read from disk as untrusted input.

## 4. Key data flows

### Unlock

1.  User enters passphrase in the unlock screen.
2.  Frontend sends it only through the local bridge; do not log it or
    save it in browser storage.
3.  Python reads and bounds-checks the vault header.
4.  Derive the key-encryption key using recorded Argon2id parameters and
    per-vault salt.
5.  Authenticate/decrypt the wrapped random master key.
6.  Authenticate and decrypt metadata.
7.  Publish a safe metadata view to the frontend.
8.  Clear the passphrase from UI state and release temporary references
    as best as practical.

### Import

1.  User selects files through a native file picker.
2.  Backend validates paths and confirms the vault is unlocked.
3.  Operation queue creates a task.
4.  Source data is streamed and encrypted into a temporary object.
5.  Final integrity/authentication checks pass.
6.  Metadata is committed atomically.
7.  UI receives progress and final result.
8.  Failure removes partial output safely and preserves the original
    source.

### Lock

1.  Stop accepting new sensitive operations.
2.  Safely cancel or finish in-progress tasks according to policy.
3.  Clear UI metadata, previews, search results and sensitive selection
    state.
4.  Clear clipboard if user enabled this option, with a clear
    limitation.
5.  Release key references and lock the vault.
6.  Verify locked screens do not show names or thumbnails.

## 5. State model

Vault states: - `CLOSED`: no vault selected. - `LOCKED`: vault known,
keys unavailable. - `UNLOCKING`: authentication in progress. -
`UNLOCKED`: key material available to required services. - `LOCKING`:
sensitive operations being stopped and UI cleared. -
`ERROR_RECOVERY_REQUIRED`: vault cannot be safely opened or needs
repair.

Operation states: - `QUEUED`, `RUNNING`, `PAUSE_REQUESTED`, `PAUSED`,
`CANCEL_REQUESTED`, `CANCELLED`, `SUCCEEDED`, `FAILED`,
`NEEDS_ATTENTION`.

State transitions must be validated by backend services, not only the
frontend.

## 6. Data classification

-   **Secret:** passphrase, master key, derived keys, recovery secret.
-   **Private:** filenames, folder hierarchy, tags, file contents,
    thumbnails, search terms, operation names.
-   **Operational:** application version, non-sensitive settings, error
    codes, durations.
-   **Public:** product name, documentation and static UI assets.

Logs and crash reports may contain operational data only, unless the
user explicitly opts into a carefully reviewed diagnostic export.
