# Frivault Frontend Specification

## 1. Technology and boundaries

Use semantic HTML, modern CSS and plain JavaScript modules initially.
Avoid a heavy frontend framework until measured complexity justifies
one. The frontend runs inside a local `pywebview` window. Python remains
authoritative for filesystem access, encryption, permissions,
persistence and vault state.

The frontend must not: - Implement encryption or derive keys. - Save
passphrases or secrets in localStorage, sessionStorage, IndexedDB, URL
parameters or logs. - Access arbitrary filesystem paths. - invoke shell
commands or arbitrary Python functions. - load remote scripts, styles or
pages into the trusted app window. - display fake progress or
placeholder data as real results.

## 2. Suggested frontend structure

``` text
resources/ui/
├── index.html
├── assets/
│   ├── icons/
│   └── brand/
├── css/
│   ├── tokens.css
│   ├── reset.css
│   ├── typography.css
│   ├── layout.css
│   ├── components.css
│   ├── screens.css
│   └── themes.css
└── js/
    ├── app.js
    ├── router.js
    ├── bridge.js
    ├── state.js
    ├── formatters.js
    ├── components/
    │   ├── sidebar.js
    │   ├── toolbar.js
    │   ├── file-list.js
    │   ├── context-menu.js
    │   ├── dialog.js
    │   ├── toast.js
    │   └── operation-queue.js
    └── screens/
        ├── home.js
        ├── files.js
        ├── search.js
        ├── recent.js
        ├── favorites.js
        ├── trash.js
        ├── vaults.js
        ├── operations.js
        ├── security.js
        └── settings.js
```

## 3. UI state

Keep state explicit and minimal: - active route; - active vault status
(not key material); - current folder ID; - current view mode and sort; -
selected item IDs; - safe display metadata returned by Python; -
operation summaries; - theme and non-sensitive settings.

On lock: - clear item lists, filenames, thumbnails, search results,
selected items and preview content; - navigate to a locked state; -
ensure browser history cannot return to a stale sensitive screen; -
remove secret inputs from the DOM and clear their JavaScript references
as best as practical.

Never put passphrases or keys into global app state.

## 4. Bridge wrapper

Create a single `bridge.js` wrapper around `window.pywebview.api`. It
should: - check that the bridge exists before calling; - expose only
named, approved operations; - normalize error responses; - avoid logging
arguments; - handle cancellation and loading states; - reject unexpected
response shapes.

Do not create a generic method such as `invoke(name, arbitraryArgs)`
that exposes arbitrary Python methods.

## 5. Navigation and screens

### Sidebar

-   Brand icon and "Frivault" at top.
-   Main group: Home, My Vault / Files, Search, Recent, Favorites,
    Trash.
-   Management group: My Vaults, Operations.
-   Bottom group: Security & Privacy, Settings.
-   Active route highlighted with Emerald/Mint.
-   Collapsible to icon-only mode with tooltips and accessible labels.
-   In locked state, hide or disable routes that require private
    metadata.

### My Vault / Files

-   Page title and breadcrumbs.
-   Search field and toolbar actions.
-   List/grid toggle and sort control.
-   Main file list with icon, name, type, size and modified date where
    available.
-   Multi-select and keyboard operations.
-   Context menu with only valid actions for the selection.
-   Right-side details panel optional; closed by default on narrow
    windows.
-   Empty state with Import and New Folder actions.

### Dashboard

-   Current vault and lock state.
-   Storage used and available space, clearly identifying what the
    numbers mean.
-   File and folder counts.
-   Quick actions: Import, New Folder, Lock Vault.
-   Recent activity only while unlocked and stored privately.

### Search

-   Query and filter controls.
-   Results list with clear no-results state.
-   Search state cleared on lock.
-   Avoid storing queries in browser persistence.

### Recent and Favorites

-   Use the same list component as Files for consistency.
-   Show a clear empty state.
-   Private names must not remain visible after lock.

### Trash

-   Restore and permanent-delete actions.
-   Permanent deletion requires a confirmation dialog.
-   Explain that secure forensic erasure cannot be guaranteed.

### My Vaults

-   Cards/list with vault label, location if user chooses to display it,
    status and size.
-   Create, open, lock, remove from app.
-   "Remove from app" must be clearly different from deleting vault
    data.

### Operations

-   Queue list with status, progress, safe controls, error detail and
    retry.
-   Show pause/resume only when the backend supports it.
-   Keep item names hidden after locking.

### Security & Privacy

-   Auto-lock setting.
-   Change passphrase workflow.
-   Recovery instructions.
-   Clipboard privacy option with limitations.
-   Export/preview privacy explanations.

### Settings

-   Appearance: System, Light, Dark, optional Black.
-   Keyboard shortcuts.
-   Default import/export locations.
-   Notifications, accessibility, cache and diagnostics.
-   About, version and licenses.

## 6. Components and interaction rules

-   Use reusable dialog, toast, tooltip, button, file row, empty state,
    loading state and error state components.
-   Every icon-only control needs an accessible name and tooltip.
-   Keyboard focus must be visible.
-   Confirm destructive actions.
-   Avoid relying only on color to indicate status.
-   Use reduced motion and avoid non-essential animation.
-   Ensure keyboard equivalents for drag/drop and context-menu
    operations.

## 7. Responsive desktop layout

-   At wide sizes, show full sidebar and main content.
-   At narrower widths, collapse sidebar and hide optional details
    panel.
-   Do not let dialogs extend beyond the work area.
-   Maintain sensible minimum window size.
-   File list must not overflow horizontally without an intentional
    strategy.

## 8. Frontend quality gates

-   No console errors in release builds.
-   All buttons have real actions or are clearly disabled with
    explanation.
-   All API failures display useful safe messages.
-   Lock clears sensitive UI state.
-   No remote asset dependencies.
-   Test keyboard-only navigation, high DPI, light/dark themes and small
    window sizes.
