# Product Requirements Document (PRD)

## 1. Product overview

Frivault is a professional Windows 11 desktop application for protecting
and managing personal files and folders inside a local encrypted vault.
The product is offline-first: creating, unlocking, browsing, importing,
organizing, and exporting vault content must work without a Frivault
account or cloud service.

Frivault should feel like a modern, polished desktop utility rather than
a web page in a window. Its identity uses Emerald `#10B981`, Mint
`#6EE7B7`, and Deep Green `#047857`. The icon direction is an original
abstract geometric brand symbol; avoid literal or generic padlocks,
shields, keyholes, safe doors, folders, clouds, and stock cybersecurity
imagery.

## 2. Problem statement

Users need a straightforward way to keep private files in an encrypted
container without uploading them to a service or depending on an online
account. Normal file-management actions should remain understandable and
reliable, while private filenames and metadata should not leak when the
vault is locked.

## 3. Product principles

1.  **Privacy first:** local storage and no mandatory cloud account.
2.  **Real encryption:** file content and private metadata are
    encrypted, not merely hidden or renamed.
3.  **Usable security:** lock, unlock, recovery, export warnings, and
    errors must be understandable.
4.  **Data integrity:** interrupted imports, moves, deletes, or app
    crashes must not silently corrupt user data.
5.  **Honest claims:** clearly state what the vault does and does not
    protect against.
6.  **Fast and restrained:** avoid needless animation, polling,
    background indexing, and heavy visual effects.
7.  **Accessible UI:** keyboard navigation, clear focus, adequate
    contrast, scalable text, and understandable labels.
8.  **No fake functionality:** every visible action must work or be
    explicitly marked as unavailable/coming later.

## 4. Target users and platform

-   Initial platform: Windows 11 x64 desktop.
-   Primary user: an individual who wants to keep personal documents,
    photos, code, archives, and other files locally encrypted.
-   Connectivity: core features must work offline.
-   Initial scope excludes multi-user cloud synchronization and
    server-side accounts.

## 5. Goals

-   Create and unlock a vault using a passphrase.
-   Store arbitrary file types encrypted at rest.
-   Encrypt filenames, folder hierarchy, tags, and other sensitive
    metadata.
-   Browse, search, organize, import, and export files.
-   Provide Trash/Restore and safe permanent deletion.
-   Show actual storage usage and operation progress.
-   Lock automatically after a configurable idle period or Windows
    session lock.
-   Package as a Windows desktop application with a clear
    installer/uninstaller path.
-   Provide recovery instructions and verified encrypted backups.

## 6. Non-goals for initial release

-   Cloud synchronization or online accounts.
-   Collaboration or sharing links.
-   AI/semantic content search.
-   Antivirus or malware scanning claims.
-   Secure deletion guarantees for SSDs, backups, filesystem journals,
    or external copies.
-   A virtual drive/mounted filesystem in MVP.
-   Automatically executing EXE, MSI, scripts, macros, or other active
    content from the vault.
-   A claim of certified, audited, or government-grade security without
    appropriate evidence.

## 7. Main navigation and screens

The primary application has 10 main screens:

1.  **Home / Dashboard:** vault status, file/folder counts, encrypted
    storage usage, quick actions, recent activity and security status.
2.  **My Vault / Files:** primary file manager with breadcrumbs, search,
    list/grid, sorting, selection, context menu, import and folder
    creation.
3.  **Search:** search by filename and available metadata while
    unlocked; filters for type, extension, date, size and folder.
4.  **Recent:** recently opened or modified items, stored privately and
    not exposed while locked.
5.  **Favorites:** starred files/folders.
6.  **Trash:** restore and permanent-delete workflow.
7.  **My Vaults:** create/open/lock/manage multiple vaults and inspect
    location/size.
8.  **Operations:** import/export/copy/move/delete task queue, progress,
    retry, cancellation and errors.
9.  **Security & Privacy:** change passphrase, recovery key guidance,
    auto-lock, clipboard privacy and privacy options.
10. **Settings:** appearance, keyboard shortcuts, default import/export
    folders, notifications, accessibility, diagnostics, updates and
    About.

Supporting dialogs/windows: - First-run setup and create-vault wizard. -
Unlock vault. - Recovery-key confirmation and recovery instructions. -
File preview and file properties. - Conflict resolution. - Export
confirmation. - Permanent-delete confirmation. - Error/recovery dialogs.

## 8. Functional requirements

### 8.1 Vault lifecycle

-   Create a new vault at a user-selected location.
-   Add/open an existing valid vault.
-   Unlock with a passphrase.
-   Lock the current vault and lock all vaults.
-   Automatically lock after configured idle time.
-   Lock on Windows session lock/sleep where reliably detectable.
-   Show explicit locked/unlocked state.
-   Allow removing a vault from the app without deleting its data.
-   Allow renaming a vault label without changing encrypted content.
-   Validate vault format/version and show recoverable errors.

### 8.2 File and folder management

The following actions are core requirements: 1. Create Folder. 2.
Rename. 3. Copy. 4. Move. 5. Cut & Paste. 6. Duplicate. 7. Delete. 8.
Trash / Recycle Bin. 9. Restore. 10. Permanent Delete. 11. Import Files.
12. Import Folders. 13. Export / Save As. 14. Drag & Drop. 15.
Multi-select. 16. Bulk Operations (Copy, Move, Delete, Export). 17.
Select All / Deselect All. 18. Open / Open With, only through an
explicit user action. 19. File Properties. 20. Copy File Contents for
supported text formats. 21. Sort Files. 22. Refresh.

Additional behavior: - Support arbitrary file extensions for encrypted
storage. - Use collision-safe rename and move operations. - Support
conflict choices such as Skip, Rename, or Replace, with clear
warnings. - Do not delete the source during a move until destination
writing and verification have succeeded. - Never execute a file directly
from the vault. - For external opening, export a temporary or
user-selected plaintext copy only after clear user consent, and explain
that the external app may retain copies.

### 8.3 Search and organization

-   Search filenames and supported metadata while unlocked.
-   Filters: file type, extension, size, date and folder.
-   Favorites, Recent, tags and custom labels.
-   Sort by name, type, size, modified date and created/imported date
    where available.
-   Keep sensitive indexes encrypted or reconstruct them only while
    unlocked.
-   Never leak private names to Windows Search, system notifications,
    logs, crash reports or telemetry.

### 8.4 Preview and edit

-   Initial previews: image, PDF where a maintained viewer is available,
    plain text, and common code formats.
-   Additional media previews may be added after dependency and
    licensing review.
-   Editing and saving must use safe temporary files and an explicit
    save workflow.
-   Minimize plaintext temporary files; clean them up after use, but do
    not claim that cleanup securely erases all storage remnants.
-   Do not render active HTML or execute scripts from vault content in
    the privileged app webview.

### 8.5 Operations

-   Queue imports, exports, copies, moves, and deletions.
-   Show item name only while unlocked and keep operation details
    private.
-   Show progress, current state, throughput when reliable, and errors.
-   Support cancellation where safe.
-   Pause/resume only where the operation format and state allow it; do
    not promise pause/resume for every operation.
-   Retry recoverable failures.
-   Limit concurrency to protect responsiveness and low-memory systems.
-   Clean up partial output safely after cancellation or failure.

### 8.6 Backup and recovery

-   Create a verified encrypted backup of a vault.
-   Restore a backup to a chosen destination.
-   Verify vault structure and encrypted object integrity.
-   Generate a recovery key or recovery mechanism with explicit user
    confirmation.
-   Explain that losing both the passphrase and recovery material may
    make data unrecoverable.
-   Version the vault format and document migrations.

### 8.7 Settings

-   Light, Dark, and System themes; optional Black theme.
-   Auto-lock timeout.
-   Default import/export location.
-   Clipboard clearing timer where practical, with a clear limitation
    that other apps or clipboard history may retain data.
-   Keyboard shortcuts.
-   Notifications with privacy-preserving text.
-   Accessibility preferences.
-   Cache/temp-file preferences.
-   Update, version, license and diagnostic settings.
-   Diagnostics must exclude plaintext contents, passphrases, keys, and
    private filenames.

## 9. UX requirements

-   Persistent collapsible left sidebar.
-   Clear page title, breadcrumb and contextual toolbar.
-   Familiar Windows keyboard shortcuts where appropriate.
-   List and grid views.
-   Right-click context menu and keyboard-accessible alternatives.
-   Consistent empty, loading, success, warning, error and disabled
    states.
-   Confirm destructive actions with meaningful wording.
-   Use Emerald/Mint for primary actions and active navigation, not
    every surface.
-   Avoid excessive animation, heavy blur and unnecessary polling.
-   Preserve current navigation and selection after safe operations when
    possible.

## 10. Non-functional requirements

-   Offline core workflow.
-   Reasonable responsiveness on low-memory Windows PCs.
-   Streaming encryption/decryption; never load an entire large file
    into RAM.
-   Background work must not block the UI thread.
-   Atomic or recoverable metadata writes.
-   No silent data loss on disk-full, permission failure or process
    termination.
-   Use signed release artifacts when feasible.
-   No analytics/telemetry by default.
-   Clear error messages that do not reveal secrets.

## 11. Acceptance criteria for MVP

-   A user can create, lock, unlock, and reopen a vault after restarting
    Windows.
-   A wrong passphrase does not reveal metadata or file contents.
-   File contents and sensitive metadata are encrypted at rest.
-   Import/export of arbitrary file types works for small and large
    files using streaming I/O.
-   Core file operations work with clear conflict handling.
-   Interrupted operations do not silently corrupt existing data.
-   Search, Favorites, Recent and Trash behave correctly and do not
    expose private data while locked.
-   Auto-lock works and clears sensitive UI state.
-   The app runs offline after installation.
-   A clean Windows test machine can install, launch, upgrade and
    uninstall the app.
-   Security and recovery tests pass before public release.
