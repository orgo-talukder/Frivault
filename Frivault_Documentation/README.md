# Frivault --- Project Documentation

**Product:** Frivault\
**Platform:** Windows 11 desktop (initial target)\
**Product type:** Offline-first local encrypted file vault\
**Brand palette:** Emerald `#10B981`, Mint `#6EE7B7`, Deep Green
`#047857`\
**Languages:** Python backend; HTML, CSS, JavaScript frontend

## How Codex should use this documentation

Read these documents in this order before changing code:

1.  `PRD.md` --- product goals, users, features, scope and acceptance
    criteria.
2.  `TRD.md` --- technical decisions, dependencies, runtime and
    constraints.
3.  `architecture.md` --- module boundaries, data flow and project
    structure.
4.  `security.md` --- mandatory security requirements and prohibited
    shortcuts.
5.  `backend.md` --- Python services and backend contracts.
6.  `frontend.md` --- UI modules and JavaScript-to-Python communication.
7.  `ui_ux_design.md` --- visual system, navigation and screen
    specifications.
8.  `testing.md` --- test strategy and release gates.
9.  `roadmap.md` --- implementation phases and definition of done.
10. `references.md` --- primary technical sources used during planning.

## Non-negotiable project rules

-   Frivault is a local-first, offline-capable Windows desktop
    application.
-   Core vault functions must not require an account, internet access,
    or cloud upload.
-   Use Python for application/backend logic and HTML/CSS/JavaScript for
    the UI.
-   Use maintained cryptographic libraries. Never invent cryptographic
    algorithms.
-   Never store plaintext passwords or plaintext encryption keys on
    disk.
-   Encrypt file contents and private vault metadata, including
    filenames and folder structure.
-   Never claim that Frivault is "unhackable," "100% secure," or
    independently audited unless that is demonstrably true.
-   Do not execute files or scripts directly from the vault.
-   Do not add telemetry, analytics, advertising, cloud sync, or network
    calls without explicit product approval.
-   Preserve user data. Destructive operations must be explicit and
    crash-safe.
-   Do not replace working code with mock data or decorative controls
    presented as functional features.
-   Every feature must have real backend behavior, error handling,
    tests, and clear loading/empty/error states.

## Proposed desktop shell

Use `pywebview` to host a locally bundled HTML/CSS/JavaScript interface
in a native window, with Python providing the application services. On
Windows, verify the Edge WebView2 runtime is available and provide a
documented installation/recovery path if it is missing. Keep the
JavaScript-to-Python API narrow and explicitly allowlisted.

This is a design decision, not proof that the final app is already
secure or production-ready. Validate dependency versions, licensing,
runtime behavior, packaging, and performance on supported Windows
systems before release.

## Current implementation status

The current source build uses Python 3.15.1, pywebview, a narrow
JavaScript/Python bridge, local UI resources, and a versioned encrypted
vault format. It supports vault create/open/unlock/lock and core file
operations such as import/export, folders, rename, copy/move, search,
favorites, Trash/restore and permanent delete. Settings currently store
only theme and inactivity auto-lock.

The desktop UI includes Home, My Vault, Search, Recent, Favorites, Trash,
My Vaults, Operations, Security & Privacy and Settings. It provides
Light/Dark/System themes, a grouped collapsible sidebar and an initial
loading/error state. Frontend and backend feature coverage is still
incomplete: see `roadmap.md` for the specific gaps. The Windows ZIP is an
unsigned engineering preview, not a production release. Independent
cryptographic review, clean-machine installation checks and signing are
still required; do not use this build as the only copy of valuable data.

## Important security boundary

Encryption at rest protects stored vault data while the vault is locked,
assuming keys are not exposed. It does not guarantee protection against
malware, keyloggers, an attacker controlling the logged-in desktop while
the vault is unlocked, or plaintext intentionally exported to other
applications.

## Documentation maintenance

When a decision changes, update all affected documents in the same
change. Keep security, architecture, backend contracts, UI behavior,
tests, and roadmap consistent.
