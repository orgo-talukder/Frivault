# Frivault Testing and Quality Plan

## 1. Testing goals

Verify data confidentiality, integrity, recovery, UI behavior, operation
safety, performance and packaging. Passing ordinary UI tests is not
enough for an encrypted vault.

## 2. Test layers

### Unit tests

-   KDF configuration parsing and bounds.
-   Key wrapping/unwrapping behavior.
-   Vault header parser.
-   Chunk encryption/decryption.
-   Metadata schema validation.
-   Path validation.
-   State transitions.
-   Sort/filter behavior.
-   Settings validation.
-   Error-code mapping.
-   Foundation preference validation and atomic save/load behavior.
-   Local UI route containment, method handling and security headers.
-   Source and frozen resource path resolution.

### Integration tests

-   Create/unlock/lock/reopen vault.
-   Import/export arbitrary file types.
-   Nested folder import.
-   Rename/copy/move/duplicate.
-   Trash/restore/permanent delete.
-   Search, Favorites and Recent.
-   Encrypted backup and restore.
-   Passphrase change.
-   Crash-recovery journal.
-   Multi-vault operations.

### Security tests

-   Wrong passphrase.
-   Modified ciphertext/tag.
-   Truncated file.
-   Reordered or missing chunks.
-   Malformed headers and unreasonable KDF parameters.
-   Path traversal and symlink/reparse-point cases.
-   Private filename leakage in logs, caches, notifications and locked
    UI.
-   Bridge misuse and invalid operation IDs.
-   Active HTML/script file preview isolation.
-   Dependency and packaged binary inspection.

### UI tests

-   First-run setup.
-   Unlock and lock states.
-   Sidebar navigation and collapse.
-   Keyboard shortcuts.
-   Multi-select and context menu.
-   Dialog cancellation and validation.
-   Empty/loading/error states.
-   Light/dark/System themes.
-   Small window and high-DPI layouts.
-   Accessibility basics.

### Packaging tests

-   Clean Windows 11 install.
-   Missing WebView2 Runtime handling.
-   Offline launch after installation.
-   Upgrade while preserving vault data.
-   Uninstall without deleting vault data.
-   Windows Defender/SmartScreen behavior as applicable.
-   No development-only files or secrets in release package.

Current source checks: `python -m unittest discover -s tests -v`,
`ruff check src tests`, `ruff format --check src tests`, and
`node tests/ui/startup_smoke.cjs` for the local UI first-launch states.

### Local verification completed for the 0.1.0 preview (2026-10-24)

- Python 3.15.1: all 52 unit, integration and security tests passed.
- Ruff lint and format checks passed.
- `pip check` reported no broken requirements; `pip-audit` reported no
  known vulnerabilities for both runtime and packaging lock files.
- Bundled JavaScript syntax and Windows PowerShell script parsing passed.
- The UI startup smoke test verifies that locked and unlocked first launches
  both paint their page and navigation, and that a bridge failure shows a
  visible retry state instead of a blank screen.
- PyInstaller produced the Windows x64 onedir package and ZIP; the app
  executable started on the development Windows 11 machine.
- The local WebView2 Runtime was detected and the bundled app UI rendered.

Not verified: fresh Windows profile installation, upgrade/uninstall data
preservation, full manual click-through of every workflow, a second clean
machine, Authenticode signing/SmartScreen behavior, performance baselines,
and independent cryptographic review. These remain release gates; passing
the local checks above does not certify production security or release
readiness.

## 3. Test data

Use synthetic files only: - zero-byte file; - tiny text file; - binary
file with arbitrary bytes; - files larger than available RAM in test
environments when practical; - nested directories; - Unicode
filenames; - long names and reserved Windows names; - duplicate names; -
corrupted vault copies; - sparse files if supported.

Never use real personal files or passwords in automated fixtures.

## 4. Failure injection

Test: - disk full; - access denied; - destination disappears; - app
closes during import/export; - process termination between object write
and metadata commit; - corrupted metadata transaction; - lock requested
during operation; - cancellation at multiple points; - unavailable
destination drive; - backup interrupted midway.

Expected behavior: the app must either finish successfully or recover to
a known state. It must not silently report success or destroy the only
valid copy.

## 5. Performance benchmarks

Measure on a lower-spec Windows PC as well as a modern device: - cold
startup; - unlock latency; - listing a large directory; - search
latency; - importing/exporting a large file; - memory use during
large-file operations; - UI responsiveness during background work; -
idle CPU usage; - lock completion time.

Set measurable targets after establishing a baseline. Do not claim
performance without measurement.

## 6. Release gates

Do not publish a release if: - authentication failures can return
plaintext; - file corruption is silently accepted; - keys or passphrases
appear in logs; - locked UI exposes private names or thumbnails; -
destructive operations can silently delete the only valid copy; -
recovery/backup tests fail; - packaging fails on a clean Windows
machine; - a visible control is nonfunctional without being clearly
marked.
