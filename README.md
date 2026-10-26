# Frivault

Frivault is an offline-first Windows desktop vault engineering preview.
It supports local vault creation, lock/unlock, encrypted file and folder
operations, search, Trash, favorites, themes, settings and auto-lock.
Vault format v1 has not received an independent security audit; do not
use this build as the only copy of valuable data.

## Run from a source checkout

Requires Python 3.11–3.15 and the Microsoft Edge WebView2 Runtime on Windows.
The current Windows development environment uses Python 3.15.1.

```powershell
python -m venv .venv315
.venv315\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
frivault
```

The UI is bundled locally and does not connect to accounts, cloud services,
telemetry or remote UI assets. Passphrases are not saved. Vault filenames
and metadata are encrypted; the outer vault folder name and total/object
sizes may remain observable.

The current vault format and its limitations are documented in
`Frivault_Documentation/vault_format_v1.md`. It has not received an
independent security audit or release approval.

The unit, integration and security suite plus code-quality checks can be run
with:

```powershell
python -m unittest discover -s tests -v
ruff check src tests
ruff format --check src tests
```

## Build the Windows package

On Windows x64 with Python 3.15.1, install `requirements.lock`,
`requirements-dev.lock` and `requirements-packaging.lock`, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

The build creates `dist/Frivault-0.1.0-win-x64.zip`. Extract it and run
`install.ps1` to install per-user shortcuts. WebView2 Evergreen Runtime is
required. The package is unsigned and is an engineering preview; see the
release checklist before distributing it.

See `Frivault_Documentation/user_guide.md` for vault operation and backup
guidance, and `Frivault_Documentation/release_checklist.md` for remaining
release gates.

See [project documentation](Frivault_Documentation/README.md) for product,
architecture, security, and verification requirements.
