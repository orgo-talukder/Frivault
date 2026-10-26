# Frivault Development Roadmap

## Phase 0 --- Audit and planning

-   Review project documentation and the actual repository state.
-   Verify the supplied application icon and inspect existing build assets.
-   Record missing design decisions and agree on a phased implementation
    plan before making large changes.

**Exit criteria:** repository findings, security blockers, and the next
small implementation slice are documented.

## Phase 1 --- Desktop foundation

-   Establish the Python package and dependency metadata.
-   Launch a minimal pywebview window with bundled local HTML/CSS/JS.
-   Keep the JavaScript/Python bridge narrow and explicitly allowlisted.
-   Resolve resources in source and frozen modes.
-   Apply the supplied brand icon to the UI without changing the original.
-   Verify WebView2 runtime behavior on Windows 11.
-   Establish privacy-safe local logging, linting, foundation tests, and
    a non-sensitive settings store.

**Exit criteria:** source launch works with local UI assets, no remote UI
dependencies, and the packaging/resource approach is documented. Vault
actions remain unavailable until implemented.

## Phase 2 --- Vault format and security foundation

-   Review the documented local-at-rest threat model.
-   Specify and validate the vault header and encrypted metadata schema.
-   Define purpose-separated master-key subkeys and key wrapping.
-   Select and test authenticated large-file streaming encryption.
-   Implement create/open/unlock/lock without exposing secrets to UI storage.
-   Test wrong passphrase, tampering, truncation and KDF parameter limits.
-   Document recovery and lost-passphrase behavior.

The implemented format is specified in `vault_format_v1.md`. The earlier
prototype notes remain for history. V1 is not independently audited or
approved for public release.

**Exit criteria:** format documented, core cryptographic tests pass, no
custom crypto, and internal review checklist completed. The format is not
independently audited and must not be recommended as the sole copy of
valuable data.

## Phase 3 --- Core file operations

-   Import files and folders.
-   Export files.
-   Create folder, rename, copy, move, duplicate.
-   Safe conflict handling.
-   Search and sorting.
-   File properties.
-   Storage summary.
-   Operation progress and cancellation where safe.
-   Crash-safe metadata updates.

**Exit criteria:** small and large files round-trip correctly;
interrupted operations do not silently corrupt the vault.

## Phase 4 --- Frontend and user workflows

-   Dashboard.
-   My Vault / Files.
-   Search.
-   Recent.
-   Favorites.
-   Trash / Restore / Permanent Delete.
-   My Vaults.
-   Operations.
-   Security & Privacy.
-   Settings.
-   Auto-lock and session-lock behavior.
-   Clear private UI state on lock.
-   Light/Dark/System themes.
-   Approved previews, safe external-open flow, encrypted backup and
    recovery workflows after dependency and design review.

**Exit criteria:** all screens are wired to real backend behavior; no
private metadata leaks while locked.

## Phase 5 --- Windows integration and packaging

-   App icon and branding.
-   Installer/package.
-   Runtime checks.
-   Optional system tray and startup behavior only after
    privacy/performance review.
-   Keyboard shortcut settings.
-   License notices.
-   Upgrade/uninstall data-preservation checks.
-   Verify executable icon, shortcuts, window/taskbar icon, and installer
    entries where supported.
-   Preserve user vault data during uninstall.

**Exit criteria:** clean Windows 11 installation and launch, offline
startup, and user data preserved during upgrade/uninstall.

## Phase 6 --- Verification and release readiness

-   Security and regression checks.
-   Backup, recovery, and crash-recovery checks.
-   Dependency, license, and packaged-runtime review.
-   Security review and release checklist.
-   Documentation for users.

**Exit criteria:** all documented release gates pass; unverified security
and packaging claims are not made.

## Current implementation status (2026-10-24)

-   Phase 0 audit is complete.
-   Phase 1 is complete: Python 3.15.1 source launch, bundled local
    pywebview UI, narrow status bridge, TLS-enabled local UI server,
    source/frozen resource resolution, app icon asset, bounded local logs,
    validated non-sensitive settings persistence, Ruff checks and
    foundation tests are in place. WebView2 displays the UI on the
    development Windows 11 machine.
-   Phase 2 is implemented in the app: versioned encrypted metadata, the
    documented key hierarchy, create/open/unlock/lock, bounded schema
    validation and integrity handling. Internal security tests pass.
    Independent cryptographic review is still a release gate.
-   Phase 3 is partially implemented and wired to the UI: file/folder
    import, single-file export, folder creation, rename, copy/move,
    favorites, filename search, sorting, Trash/restore/permanent deletion,
    properties, storage summary and cancellable import/export/copy
    operations. Metadata commits and file publishing use temporary files
    and atomic rename. Remaining work includes conflict-resolution UI,
    duplicate/cut-paste/drag-drop, multi-file export, filters and broader
    crash-recovery testing.
-   Phase 4 is partially implemented in the bundled UI: Home, My Vault,
    Search, Recent, Favorites, Trash, My Vaults, Operations, Security &
    Privacy and Settings. The first-paint defect that left the page and
    sidebar empty on a fresh launch has been fixed; the sidebar now follows
    the grouped, collapsible design and the initial view has explicit
    loading/error states. Light/Dark/System themes and inactivity
    auto-lock exist. Remaining work includes a true multi-vault registry,
    change-passphrase/recovery/backup flows, previews, context menus,
    shortcuts, broader settings, and Windows workstation-lock handling.
-   Phase 5 has a Windows x64 onedir package, ZIP, WebView2 Runtime check,
    app icon, per-user install/uninstall scripts and third-party license
    files. The built executable starts on the development Windows 11
    machine. No clean-profile install, upgrade/uninstall preservation run,
    or code signing was performed.
-   Phase 6 local verification passes for the 0.1.0 preview: Python 3.15.1
    tests, Ruff, dependency checks and `pip-audit`; the UI startup smoke
    test also covers first launch and bridge failure. The package was
    built and launched. An independent crypto audit, clean machine review,
    complete manual UI workflow review, and signed release remain
    outstanding, so this is not release-ready.
-   The development environment is `.venv315`; Python 3.12 remains only in
    the older `.venv` and is not used by the current verification steps.

## Out of scope until separately approved

-   Cloud sync, accounts or remote telemetry.
-   AI content search.
-   Virtual drive mounting.
-   Automatic file execution.
-   Secure-delete guarantees.
-   Passwordless unlock or Windows Hello integration.
-   Any feature that increases attack surface without a clear user
    benefit.

## Working with Codex

At the start of each task: 1. Read relevant docs. 2. Inspect existing
code before editing. 3. State the exact files to change and the intended
behavior. 4. Implement a small coherent slice. 5. Add or update tests.
6. Run tests and report actual results. 7. Update docs when behavior or
architecture changes. 8. Never claim tests passed unless they were
actually run. 9. Never replace real functionality with mock behavior to
make a screen look complete. 10. Keep changes focused; avoid rewriting
unrelated modules.
