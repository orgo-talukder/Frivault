# Technical Requirements Document (TRD)

## 1. Technology decisions

### Required languages

-   Python: application services, vault logic, file operations,
    cryptography orchestration, persistence and OS integration.
-   HTML: semantic UI structure.
-   CSS: design system, layout, themes and responsive behavior.
-   JavaScript: navigation, rendering, user interaction and calls to the
    Python bridge.

### Desktop shell

Use `pywebview` as the first implementation candidate. It hosts bundled
local HTML/CSS/JavaScript in a native desktop window and exposes a
Python API to JavaScript. On Windows, prefer the Edge Chromium renderer.
The installer/startup check must verify WebView2 Runtime availability
and present a clear recovery path.

Do not load remote webpages in the privileged app window. Do not enable
arbitrary external navigation, remote scripts, or remote styles in the
trusted application UI.

### Python libraries (proposed; verify current versions and licensing)

-   `pywebview`: native webview shell and JS/Python bridge.
-   `PyNaCl`: maintained Python bindings to libsodium, including
    XChaCha20-Poly1305 and secretstream.
-   `argon2-cffi`: Argon2id password-based key derivation.
-   `platformdirs`: OS-appropriate app data/cache directories.
-   `pytest`: unit and integration tests.
-   `hypothesis`: property-based tests for parsers and operation
    invariants, if useful.
-   `ruff`: linting/format checks.
-   `mypy` or `pyright`: optional static analysis.
-   `PyInstaller`: Windows packaging candidate; verify pywebview
    runtime/backend dependencies and test on clean Windows machines.
-   SQLite via Python standard library for operational metadata only if
    the database is encrypted or contains no private information while
    locked. Prefer encrypted vault metadata for names and hierarchy.

Dependency versions must be pinned and updated through deliberate
security review. Do not install random packages at runtime.

### Foundation dependency selection

The initial source package pins `pywebview==6.2.1` and declares Python
3.11–3.15 support (`>=3.11,<3.16`). Its dependency set resolves and
installs in the Windows x64 CPython 3.15.1 development environment, and
the UI is displayed on the development Windows 11 machine. PyPI lists
pywebview 6.2.1 under the BSD 3-Clause license. Clean-machine runtime
verification and the complete transitive license inventory remain
release tasks. The frontend brand asset is a
byte-for-byte copy of the root `icons/frivault_icon.ico`.

The vault engine pins `PyNaCl==1.6.2` and
`argon2-cffi==25.1.0`, and the local pywebview static server uses
`cryptography==50.0.1` to enable TLS. PyNaCl is Apache-2.0 and argon2-cffi is MIT;
review the bundled libsodium and argon2-cffi-bindings notices as part of
the full release license inventory. These packages implement the selected
format; independent review remains required before release.

`platformdirs==4.11.10` provides per-user configuration and log
directories. Ruff `0.16.8` is pinned separately in
`requirements-dev.lock`; it is used for linting and formatting only.
Settings persist only theme and auto-lock timeout. Logs are bounded,
local and must contain operational codes only.

`requirements.lock` pins the resolved runtime dependencies in the
Windows x64 CPython 3.15.1 development environment. It has no artifact
hashes and is not a signed supply-chain lock; review and regenerate it
deliberately when updating dependencies.

## 2. Platform and packaging

-   Initial target: Windows 11 x64.
-   Build Windows artifacts on Windows; PyInstaller is not a
    cross-compiler.
-   Provide a signed installer when signing credentials and budget
    allow.
-   Verify Edge WebView2 Runtime on the target device.
-   Include license notices for Python packages and any frontend assets.
-   Package only required runtime files and bundled UI assets.
-   Test install, launch, update, uninstall, and data-preservation
    behavior.
-   Do not delete user vaults when uninstalling the app.
-   Never bundle private signing keys, test vaults with real personal
    data, or secrets.

## 3. Runtime architecture

-   UI process: pywebview window rendering local assets.
-   Frontend: static local HTML/CSS/JS.
-   Bridge: explicit Python API object with small, typed, validated
    methods.
-   Application services: vault manager, crypto service, metadata
    repository, file operation service, search service, preview service,
    settings service, recovery/backup service.
-   Persistence: encrypted vault container plus non-sensitive app
    preferences.
-   Background work: Python worker threads or a task manager with
    cancellation tokens/events; UI thread must remain responsive.
-   No cloud/backend server is required for core features.

## 4. Vault container format

Version 1 is implemented and documented in `vault_format_v1.md`:
`vault.header` wraps a random master key, `objects/` contains opaque
encrypted objects, and `metadata.enc` holds the encrypted file/folder
tree. V1 does not include an on-disk journal, encrypted backup manifest,
or recovery key. Creation and metadata commits use temporary files and
same-volume atomic rename; imports publish object files before committing
metadata, so interrupted imports can leave unreachable ciphertext that
can be cleaned up without losing committed entries.

This is a documented application format, not an independently reviewed
standard. Exact size leakage, version migration and recovery limits are
described in `vault_format_v1.md`.

## 5. Encryption requirements

-   Use a reviewed, maintained cryptographic library.
-   Use authenticated encryption. The selected v1 format uses
    XChaCha20-Poly1305 for key wrapping and libsodium secretstream for
    bounded file chunks. The format is specified in `vault_format_v1.md`
    and implemented, but awaits independent review before release.
-   Large files require a documented, reviewed chunked/streaming format
    with per-chunk authentication, unique nonces or a safe nonce
    derivation scheme, sequence binding, truncation detection and
    finalization/authentication. Do not invent a custom scheme casually.
-   Use `secrets` or the library's cryptographically secure random
    generator for keys, salts, IDs and nonces.
-   Generate a random vault master key; derive a key-encryption key from
    the passphrase using Argon2id and use it to protect the master key.
    This allows passphrase changes without re-encrypting all file
    contents.
-   Store the KDF identifier, salt and parameters with the vault header;
    treat these fields as untrusted and enforce safe upper bounds before
    expensive work.
-   Never log keys, passphrases, plaintext contents, or raw decrypted
    metadata.
-   Define a versioned, authenticated metadata format and robust parsing
    limits.

## 6. File operation invariants

-   Import: read source in bounded chunks, encrypt to a temporary
    object, verify finalization, then atomically commit metadata.
-   Export: decrypt to a temporary destination, verify every chunk and
    final authentication, then rename into the selected destination.
    Avoid exposing a partially verified file as final output.
-   Move within a vault: update metadata transactionally where possible.
-   Copy: create a new logical item/object according to the chosen
    storage model; preserve content integrity.
-   Move between vaults: write and verify destination first; remove
    source only after user-confirmed success.
-   Trash: update encrypted metadata and retain data until permanent
    deletion.
-   Permanent delete: remove object references and attempt file
    deletion; clearly explain that secure erasure cannot be guaranteed
    on SSDs, backups, journaling filesystems or copied data.
-   Disk full, permission errors and crashes must not silently destroy
    the only valid copy.

## 7. Performance and resource management

-   Stream large file reads/writes; do not read full files into memory.
-   Use bounded concurrency, especially on low-memory PCs.
-   Use virtualized or paginated UI lists for large vaults.
-   Avoid periodic polling when event-driven updates are possible.
-   Generate thumbnails only while unlocked and keep cache content
    private; do not persist plaintext thumbnails without explicit design
    review.
-   Measure cold startup, unlock latency, 1 GB import/export, large
    directory browsing, and memory use on a low-spec machine.

## 8. API and error contracts

-   Bridge methods use structured JSON-compatible values and return
    structured success/error objects.
-   Validate every argument at the Python boundary; UI validation is not
    a security boundary.
-   Never expose raw filesystem access, arbitrary Python evaluation,
    shell execution, arbitrary URL loading, or generic function
    invocation to JavaScript.
-   Errors should include a stable error code, safe user-facing message
    and optional non-sensitive diagnostic detail.
-   Sensitive details and filenames must be excluded from normal logs.

## 9. Definition of done

A feature is not done until: - backend implementation exists; - UI is
wired to real backend behavior; - input validation and error states
exist; - tests cover success, failure, interruption and boundary
conditions; - documentation is updated; - no plaintext metadata leak is
introduced; - packaging works on a clean Windows environment.
