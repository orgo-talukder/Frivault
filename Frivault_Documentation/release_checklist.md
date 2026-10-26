# Release readiness checklist

## Local engineering checks

- [ ] Run `ruff check src tests` and `ruff format --check src tests` in Python
  3.15.1.
- [ ] Run `python -m unittest discover -s tests -v` in Python 3.15.1.
- [ ] Run `python -m pip check` and dependency vulnerability audit.
- [ ] Build the Windows x64 onedir package on Windows using the pinned lock.
- [ ] Verify the executable icon and all bundled UI/runtime resources.
- [ ] Install from the ZIP into a clean Windows 11 user profile.
- [ ] Test create, unlock, import, copy, move, export, Trash, restore, and
  permanent deletion using disposable test data.
- [ ] Test light, dark, and system theme; close/reopen; inactivity lock.
- [ ] Verify uninstall removes app files and leaves vault, settings, and logs.
- [ ] Review generated third-party license inventory and notices.
- [ ] Resolve the upstream license-text discrepancy for `proxy_tools` before
  commercial redistribution.
- [ ] Sign the installer and executable with a trusted Windows code-signing
  certificate, then verify signatures.

## Security gates

- [ ] Independent review of vault format v1, key derivation, metadata format,
  streaming authentication, and implementation.
- [ ] Review crash recovery on interrupted writes and filesystem edge cases.
- [ ] Review passphrase handling, memory lifetime, local logs/settings, and
  Windows reparse-point handling.
- [ ] Confirm security and privacy behavior on clean machines and supported
  WebView2 Runtime versions.
- [ ] Do not claim production release readiness until all required gates pass.

The current build is an unsigned engineering preview. Local tests are not a
substitute for independent cryptographic review, signing, or clean-machine
installation verification.
