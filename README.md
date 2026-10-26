# Frivault

**A local-first Windows desktop vault for keeping personal files encrypted on your device.**

Frivault is a Windows desktop app built with Python and a locally bundled HTML, CSS, and JavaScript interface. Create a password-protected vault, organize files and folders, and lock the vault when you are done. Vault use is local and does not require an account or cloud service.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Run Frivault from source](#run-frivault-from-source)
- [First-time setup](#first-time-setup)
- [Use your vault](#use-your-vault)
- [Back up and restore](#back-up-and-restore)
- [Security and privacy](#security-and-privacy)
- [Run checks](#run-checks)
- [Build a Windows package](#build-a-windows-package)
- [Troubleshooting](#troubleshooting)
- [Project layout](#project-layout)
- [Documentation](#documentation)
- [License](#license)

## Features

- Creates or opens a vault stored in a folder you choose on your computer.
- Encrypts file contents, filenames, folder hierarchy, and private vault metadata while stored in the vault.
- Lets you import files or folder trees, create folders, rename, copy, move, favorite, export, search, and sort items.
- Provides Recent, Favorites, and Trash views, with restore and permanent-delete actions.
- Shows import and other file-operation progress in the current file view so you can continue working in the vault.
- Locks the vault and asks for its password again when the app is started or the vault is locked. An inactivity auto-lock setting is available.
- Offers System, Light, and Dark appearance, comfortable or compact density, default sorting, and a permanent-delete confirmation preference.
- Keeps its interface assets bundled locally. Vault browsing and file management work locally on your device.

Frivault is designed for Windows 11. The current development and dependency lock files target Windows x64 with CPython 3.15.1. Use Python 3.15.1 on Windows x64 to follow the commands below.

## Requirements

- Windows 11 x64 (the development target).
- CPython 3.15.1 recommended for the pinned lock files and packaging scripts.
- Microsoft Edge WebView2 Evergreen Runtime. Windows 11 commonly includes it; if Frivault reports it is missing, install the [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) and restart the app.
- Internet access for the initial Python package installation. Normal vault use and the bundled interface are local; an internet connection is not needed to use the app.

## Run Frivault from source

Open PowerShell in the project folder. If you have Git installed, clone the public repository first:

```powershell
git clone https://github.com/orgo-talukder/Frivault.git
cd Frivault
```

Create a virtual environment, install the pinned runtime and development dependencies, and install Frivault in editable mode:

```powershell
py -3.15 -m venv .venv315
.venv315\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
```

Start the desktop app:

```powershell
python -m frivault
```

After the environment has been prepared, you can also double-click `run_frivault.bat` in File Explorer. That launcher expects the project-local `.venv315` environment created above. It keeps a status window open while the app runs and displays the log location if startup fails.

The project uses a `src` layout. Run the application from the project root with the virtual environment activated. Do not run files from inside an encrypted vault.

## First-time setup

1. Start Frivault. On the first launch, the **Create Frivault** setup screen asks for a vault name, password, and password confirmation.
2. Choose a strong, case-sensitive password of at least 12 characters and keep it in a safe place. Frivault does not store or reset your password; if it is lost, the vault cannot be unlocked.
3. Choose the parent folder where the new vault folder should be created. Keep the vault outside the app installation folder.
4. After creation, Frivault opens the vault for the current session. On later launches it asks for the password to unlock the remembered vault.
5. Keep an independent backup of the complete vault folder.

If Frivault cannot find the remembered vault folder—for example, if it was moved or its drive is disconnected—use **Locate existing vault** and choose the existing vault folder. Frivault will not create a replacement vault in its place.

## Use your vault

### Browse and organize files

- Open **My Vault** to browse the current folder. Use the breadcrumb and back/up controls to move through nested folders and return to the vault root.
- Double-click a folder to open it. Use **New folder** to add a folder at the current location.
- Use **Import files** or **Import folder** while viewing the destination folder. Imported items go into that folder; a progress/status area shows the running work and provides cancellation where supported.
- Select an item to access actions such as rename, favorite, copy, move, export, or move to Trash. Right-click an item for its context menu. Click empty space to clear the selection.
- Use **Search** to find encrypted names while the vault is unlocked.
- Use **Recent** and **Favorites** to find active items. Deleted items remain in **Trash** until restored or permanently deleted.

### Lock and settings

Choose **Lock vault** in the sidebar whenever you step away. Frivault also locks after the configured period of inactivity. Locking removes the active session from the app; unlocking requires the vault password again.

In **Settings**, you can change appearance, interface density, default file sorting, inactivity auto-lock time, and whether permanent deletion requires confirmation. Preferences are stored locally. Passwords and encryption keys are not stored in preferences.

### Exporting files

Export decrypts the selected item to a destination you choose. The exported copy is plaintext and is managed by Windows and other applications like any other file. Store it carefully and remove it yourself when it is no longer needed.

## Back up and restore

For a dependable backup, copy the **entire vault folder**, not just one file inside it:

1. Lock the vault and close Frivault.
2. Copy the complete vault folder to a separate drive or another safe location.
3. Keep the backup separate from the original device when possible.
4. Verify a backup by opening the copied vault in Frivault before relying on it.

To restore, copy the complete vault folder to a normal local folder and choose **Locate existing vault** in Frivault. Do not edit `vault.header`, `metadata.enc`, or files in `objects` manually.

## Security and privacy

Frivault encrypts vault file contents and private metadata at rest. The current format uses Argon2id for password-based key derivation and authenticated encryption primitives provided by maintained cryptographic libraries. File data is encrypted in authenticated chunks. The format details and parameters are documented in [Vault format v1](Frivault_Documentation/vault_format_v1.md). The cryptographic implementation has not received an independent third-party security audit.

Keep your device protected with a strong Windows sign-in password, choose a strong Frivault password, and keep a separate backup of the complete vault folder. Exported files are decrypted to the destination you choose and are then managed like other Windows files, so store those copies securely. The vault’s outer folder name, item count, and encrypted object sizes may be visible on disk.

## Run checks

From the project root with the development environment activated:

```powershell
python -m unittest discover -s tests -v
ruff check src tests
ruff format --check src tests
```

The repository includes unit, integration, and security-focused tests for the vault and application components.

## Build a Windows package

Building is optional; the source-run instructions above do not build an `.exe`. To create the project’s Windows x64 app package, prepare the pinned packaging dependencies and run the build script:

```powershell
python -m pip install -r requirements-packaging.lock
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/build_windows.ps1
```

The script requires the project’s `.venv315` environment with CPython 3.15.1. It creates `dist/Frivault-0.1.0-win-x64.zip`, containing an onedir app package and per-user install/uninstall scripts. The package is unsigned. The install script checks for WebView2 Runtime.

## Troubleshooting

### The app window does not appear or reports a WebView2 error

Install or repair the Microsoft Edge WebView2 Evergreen Runtime using the link in [Requirements](#requirements), then restart Frivault.

### `run_frivault.bat` says the Python environment is missing

Run the virtual-environment and dependency setup commands above from the project root. The launcher expects `.venv315\Scripts\python.exe`.

### PowerShell blocks virtual-environment activation

You can leave the environment inactive and call its Python executable directly:

```powershell
.venv315\Scripts\python.exe -m pip install -r requirements.lock
.venv315\Scripts\python.exe -m pip install -r requirements-dev.lock
.venv315\Scripts\python.exe -m pip install --no-deps -e .
.venv315\Scripts\python.exe -m frivault
```

### The remembered vault cannot be opened

Check that the original vault folder is still present and that its drive is connected. Use **Locate existing vault** to select that same folder. Do not create another vault over it or modify its internal files.

### Startup fails for another reason

The launcher points to `%LOCALAPPDATA%\Frivault\Logs\frivault.log`. Review the log locally before sharing it; diagnostic logs can contain environment details. Never share your password or vault files.

## Project layout

```text
Frivault/
├── src/frivault/                 # Python desktop shell, bridge, vault and crypto services
│   ├── bridge/                   # Allowlisted JavaScript-to-Python API
│   ├── crypto/                   # Versioned authenticated vault format
│   └── resources/ui/             # Bundled HTML, CSS, JavaScript and SVG assets
├── tests/                        # Unit, integration, UI smoke and security tests
├── icons/                        # Windows application icons
├── packaging/                    # Windows package and install scripts
├── Frivault_Documentation/       # Product, architecture, security and user docs
├── requirements*.lock            # Pinned Windows x64 dependency sets
├── pyproject.toml                # Package metadata and tool configuration
└── run_frivault.bat               # Local development launcher
```

## License

Frivault is distributed under the [MIT License](LICENSE). The project’s bundled dependencies and packaging materials may have separate license terms; see `packaging/licenses/` and the package’s `ThirdPartyLicenses` directory.
