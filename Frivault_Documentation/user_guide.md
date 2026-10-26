# Frivault user guide

## Install on Windows

1. Extract `Frivault-0.1.0-win-x64.zip` to a normal folder such as Downloads.
2. Run `install.ps1` from the extracted folder in PowerShell. It checks for
   Microsoft Edge WebView2 Runtime and installs Frivault under your per-user
   Programs folder.
3. Start Frivault from the Start menu or desktop shortcut.

Frivault is not code-signed in this build. Windows may show an unsigned-app
warning. The project does not publish this package as a production release.

## Create and unlock a vault

Choose **Create a vault**, select a parent folder, then enter the vault name
and a long passphrase. The selected parent contains a folder with the vault
name. Remember the exact passphrase: capitalization and spaces matter, and
there is no password reset or recovery key. Choose a location outside the
application install folder and keep an independent backup of the whole vault
folder.

To open a vault, choose **My Vaults → Open existing vault**, select its folder,
and enter the passphrase. Use **Lock vault** before leaving the computer.
Automatic lock runs after the configured period without app activity.

## Work with files

- **My Vault:** import files or a folder tree, create folders, rename, copy,
  move, favorite, export, and sort items.
- **Search:** searches encrypted metadata while the vault is unlocked.
- **Recent / Favorites:** browse active items.
- **Trash:** restore items or permanently remove them from the vault.
- **Operations:** monitor and cancel file imports, exports, and copies.
- Export writes a temporary file in the destination folder and publishes it
  only after every encrypted chunk authenticates.

Vault encryption protects the data while the vault is closed. Exported files
are ordinary plaintext files in the destination you choose. Frivault does not
promise forensic secure deletion from SSDs, backups, or filesystem journals.

## Backups and recovery

With the vault locked and the app closed, copy the entire vault folder to a
separate storage device. To restore, copy the folder back to a normal local
directory and open it in Frivault. Do not back up only `metadata.enc` or only
the `objects` folder. Verify the copy by opening it with the passphrase before
you rely on it. This build has no built-in backup scheduler or recovery key.

## Remove Frivault

Run `uninstall.ps1` from the installed application folder. It removes the app
and shortcuts while leaving the user's vault folders, settings, and logs in
place. Vaults should be stored outside the application folder.

## Security status

The local format has automated integrity and regression tests, but it has not
received an independent cryptographic audit or broad clean-machine review.
Do not use this build as the only copy of valuable data. See
`Frivault_Documentation/security.md` for the threat model and known limits.
