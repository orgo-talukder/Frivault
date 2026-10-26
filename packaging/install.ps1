$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceExe = Join-Path $PackageRoot 'Frivault.exe'
if (-not (Test-Path -LiteralPath $SourceExe -PathType Leaf)) { throw 'Frivault.exe is missing from this package.' }

$RuntimeKey = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
$RuntimePaths = @(
    "HKCU:\Software\Microsoft\EdgeUpdate\Clients\$RuntimeKey",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$RuntimeKey",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$RuntimeKey"
)
$HasRuntime = $false
foreach ($RuntimePath in $RuntimePaths) {
    $Runtime = Get-ItemProperty -LiteralPath $RuntimePath -Name pv -ErrorAction SilentlyContinue
    if ($Runtime.pv -and $Runtime.pv -ne '0.0.0.0') { $HasRuntime = $true; break }
}
if (-not $HasRuntime) {
    throw 'Microsoft Edge WebView2 Runtime is required. Install the Evergreen Runtime from https://developer.microsoft.com/microsoft-edge/webview2/ and run this installer again.'
}

$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Frivault'
$UserDataRoot = Join-Path $env:LOCALAPPDATA 'Frivault'
if ($PackageRoot.StartsWith($InstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Run install.ps1 from the extracted package folder, not from the installed application folder.'
}
if (Test-Path -LiteralPath $InstallRoot) {
    $ResolvedInstall = (Resolve-Path -LiteralPath $InstallRoot).Path
    if ($ResolvedInstall -ne $InstallRoot) { throw 'Install target resolves outside the expected per-user application directory.' }
    $VaultHeaders = Get-ChildItem -LiteralPath $InstallRoot -Filter 'vault.header' -File -Recurse -ErrorAction SilentlyContinue
    foreach ($Header in $VaultHeaders) {
        $VaultFolder = $Header.Directory
        if ((Test-Path -LiteralPath (Join-Path $VaultFolder.FullName 'metadata.enc')) -and
            (Test-Path -LiteralPath (Join-Path $VaultFolder.FullName 'objects') -PathType Container)) {
            throw "A vault was found inside the application folder. Move it elsewhere before updating: $($VaultFolder.FullName)"
        }
    }
    Remove-Item -LiteralPath $InstallRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $InstallRoot, $UserDataRoot | Out-Null
Copy-Item -Path (Join-Path $PackageRoot '*') -Destination $InstallRoot -Recurse -Force

$Shell = New-Object -ComObject WScript.Shell
$Programs = [Environment]::GetFolderPath('Programs')
$StartMenuPath = Join-Path $Programs 'Frivault.lnk'
$Shortcut = $Shell.CreateShortcut($StartMenuPath)
$Shortcut.TargetPath = Join-Path $InstallRoot 'Frivault.exe'
$Shortcut.WorkingDirectory = $InstallRoot
$Shortcut.IconLocation = (Join-Path $InstallRoot 'Frivault.exe')
$Shortcut.Save()
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$DesktopShortcut = $Shell.CreateShortcut((Join-Path $DesktopPath 'Frivault.lnk'))
$DesktopShortcut.TargetPath = Join-Path $InstallRoot 'Frivault.exe'
$DesktopShortcut.WorkingDirectory = $InstallRoot
$DesktopShortcut.IconLocation = (Join-Path $InstallRoot 'Frivault.exe')
$DesktopShortcut.Save()

$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Frivault'
New-Item -Path $UninstallKey -Force | Out-Null
Set-ItemProperty -LiteralPath $UninstallKey -Name DisplayName -Value 'Frivault'
Set-ItemProperty -LiteralPath $UninstallKey -Name DisplayVersion -Value '0.1.0'
Set-ItemProperty -LiteralPath $UninstallKey -Name Publisher -Value 'Frivault'
Set-ItemProperty -LiteralPath $UninstallKey -Name InstallLocation -Value $InstallRoot
Set-ItemProperty -LiteralPath $UninstallKey -Name UninstallString -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $InstallRoot 'uninstall.ps1')`""
Write-Output "Frivault installed to $InstallRoot. Vault folders and local settings are kept outside the application install folder."
