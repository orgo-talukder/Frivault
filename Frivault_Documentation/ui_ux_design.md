# Frivault UI/UX Design Specification

## 1. Brand identity

-   Product name: **Frivault**
-   Suggested Bangla pronunciation: **ফ্রিভল্ট** (ফ্রি-ভল্ট).
-   Product personality: private, calm, dependable, modern, premium,
    practical.
-   Brand colors:
    -   Emerald: `#10B981`
    -   Mint: `#6EE7B7`
    -   Deep Green: `#047857`
-   Icon direction: a unique abstract geometric brand symbol with a
    memorable silhouette. Do not use a literal locker, padlock, keyhole,
    shield, safe door, folder, cloud or generic cybersecurity icon.
-   The app icon should work at small sizes and in monochrome.

## 2. Design principles

1.  Professional Windows desktop experience.
2.  Clear hierarchy and generous spacing without wasting screen area.
3.  Familiar file-management behavior.
4.  Use brand color purposefully, not everywhere.
5.  Fast interactions and restrained animation.
6.  Strong keyboard accessibility.
7.  Privacy state must be obvious.
8.  No deceptive decorative controls or fake data.

## 3. Color tokens

### Brand

``` css
:root {
  --brand-emerald: #10B981;
  --brand-mint: #6EE7B7;
  --brand-deep-green: #047857;
}
```

### Suggested dark theme

-   Window background: `#151A18`
-   Sidebar: `#19211D`
-   Surface/card: `#202A25`
-   Elevated surface: `#27332D`
-   Primary text: `#F3F7F4`
-   Secondary text: `#B1C1B7`
-   Border: `#34433A`
-   Primary action: Emerald, with text contrast tested before use.

### Suggested light theme

-   Window background: `#F6F8F6`
-   Sidebar: `#FFFFFF`
-   Surface/card: `#FFFFFF`
-   Elevated surface: `#F0F5F1`
-   Primary text: `#17211B`
-   Secondary text: `#59685E`
-   Border: `#DCE5DE`
-   Primary action: Deep Green where white text is needed for contrast.

### Status colors

-   Success: green, not identical to every brand accent.
-   Warning: amber.
-   Error/destructive: red.
-   Information: blue or neutral. Always pair color with text/icon,
    never color alone.

## 4. Typography and spacing

-   Use a clear system UI font stack appropriate for Windows.
-   Page title: 24--28 px equivalent depending on window scale.
-   Section heading: 16--20 px.
-   Body: 13--15 px.
-   Metadata: 12--13 px, never too faint.
-   Use an 8 px spacing rhythm with consistent component padding.
-   Use compact but comfortable controls; avoid oversized web-style
    cards.
-   Respect Windows display scaling and high-DPI monitors.

## 5. Main window layout

-   Native title bar/window controls.
-   Left sidebar: roughly 220--250 px when expanded; icon-only when
    collapsed.
-   Main content: flexible width.
-   Top content toolbar: page title/breadcrumb, search, view/sort and
    contextual actions.
-   Optional details panel: closed by default, can open on selection.
-   Use native file dialogs for selecting source/destination paths.
-   Do not add heavy blur or glass effects that harm
    performance/readability.

## 6. Sidebar structure

Top: - Frivault brand symbol and product name. - Collapse/expand
control.

Main: - Home - My Vault / Files - Search - Recent - Favorites - Trash

Management: - My Vaults - Operations

Bottom: - Security & Privacy - Settings

Behavior: - Active item uses a restrained Emerald/Mint indicator. -
Hover/focus states are distinct. - Collapsed icons have tooltips and
accessible labels. - Locked state hides or disables navigation requiring
private metadata. - Avoid duplicate navigation labels in the main
content.

## 7. Screen specifications

### Home / Dashboard

-   Vault state card with clear Locked/Unlocked status.
-   Storage usage card with actual computed figures.
-   File/folder counts.
-   Quick actions: Import, New Folder, Lock Vault.
-   Recent activity only while unlocked.
-   Empty state for a new vault.
-   Never display stale private stats after locking.

### My Vault / Files

-   Breadcrumbs at top.
-   Toolbar: Import, New Folder, Sort, View mode, selection-dependent
    actions.
-   Search field.
-   List view as the default for desktop; optional grid.
-   Columns: Name, Type, Size, Modified (only if available and
    privacy-safe).
-   Right-click context menu and keyboard equivalents.
-   Multi-select with clear selection count and bulk action toolbar.
-   File/folder icons are simple vector assets; avoid emoji.
-   Large directories should remain responsive.

### Search

-   Search input and filters.
-   Results use the same file-row component.
-   Clear filters and no-results state.
-   Search terms/results are removed from the UI on lock.

### Recent / Favorites

-   Reuse the same visual list component.
-   Clear empty state.
-   Private names never remain visible when locked.

### Trash

-   Explain that Trash is restorable until permanently deleted.
-   Restore action.
-   Permanent delete requires a confirmation that clearly identifies the
    consequence.
-   Do not promise secure forensic erasure.

### My Vaults

-   Show vault label, state and storage summary.
-   Actions: Create, Open, Lock, Remove from app.
-   Separate "Remove from app" from "Delete vault data."
-   Do not show sensitive filenames in a vault card.

### Operations

-   Task queue with state, progress, elapsed time when reliable, and
    safe actions.
-   Show pause/resume only when truly supported.
-   Errors include retry guidance and a safe code.
-   Operation names and filenames disappear after locking.

### Security & Privacy

-   Auto-lock settings.
-   Change passphrase.
-   Recovery instructions.
-   Clipboard privacy setting with a clear limitation.
-   Plain-language export and preview warnings.
-   No exaggerated security badges or claims.

### Settings

-   Appearance: System, Light, Dark, optional Black.
-   Keyboard shortcuts.
-   Default folders.
-   Notifications and privacy.
-   Accessibility.
-   Diagnostics and update settings.
-   About and license information.

## 8. Dialog patterns

-   Use focused dialogs with one clear primary action and a secondary
    cancel action.
-   Destructive actions use explicit verbs, not vague "OK."
-   Avoid stacked modal dialogs.
-   Show field-specific validation.
-   Disable duplicate submission while an operation is starting.
-   Error dialogs must offer a practical next step.

## 9. Motion and feedback

-   Small transitions only when they clarify navigation or state.
-   Avoid continuous animations, animated backgrounds, and heavy blur.
-   Show real operation progress from the backend.
-   Use toast messages for non-destructive success; persistent inline
    errors for recoverable failures.
-   Respect reduced-motion preferences where feasible.

## 10. Accessibility

-   Keyboard navigation for all important features.
-   Visible focus indicator.
-   Accessible names for icon-only buttons.
-   Adequate text/background contrast.
-   Do not communicate status only with color.
-   Scalable text and high-DPI support.
-   Do not trap keyboard focus outside modal dialogs.

## 11. Design acceptance criteria

-   All 10 main screens share consistent spacing, typography and
    components.
-   Light and dark themes are readable and coherent.
-   Emerald/Mint is used as an accent, not as a full-page fill.
-   No placeholder actions masquerade as working features.
-   Locked state removes private metadata from the visible UI.
-   Layout adapts to narrower windows and high-DPI displays.
