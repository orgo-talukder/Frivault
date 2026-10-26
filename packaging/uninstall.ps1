$ErrorActionPreference = 'Stop'
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Frivault'
if (Test-Path -LiteralPath $InstallRoot) {
    $ResolvedInstall = (Resolve-Path -LiteralPath $InstallRoot).Path
    $ExpectedRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd('\')
    if ($ResolvedInstall -ne $ExpectedRoot) { throw 'Refusing to remove an unexpected uninstall path.' }
    $VaultHeaders = Get-ChildItem -LiteralPath $ExpectedRoot -Filter 'vault.header' -File -Recurse -ErrorAction SilentlyContinue
    foreach ($Header in $VaultHeaders) {
        $VaultFolder = $Header.Directory
        if ((Test-Path -LiteralPath (Join-Path $VaultFolder.FullName 'metadata.enc')) -and
            (Test-Path -LiteralPath (Join-Path $VaultFolder.FullName 'objects') -PathType Container)) {
            throw "A vault was found inside the application folder. Move it elsewhere before uninstalling: $($VaultFolder.FullName)"
        }
    }
    Remove-Item -LiteralPath $ExpectedRoot -Recurse -Force
}
$Programs = [Environment]::GetFolderPath('Programs')
Remove-Item -LiteralPath (Join-Path $Programs 'Frivault.lnk') -Force -ErrorAction SilentlyContinue
$DesktopPath = [Environment]::GetFolderPath('Desktop')
Remove-Item -LiteralPath (Join-Path $DesktopPath 'Frivault.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Frivault' -Recurse -Force -ErrorAction SilentlyContinue
Write-Output 'Frivault was removed. Vault folders, settings and logs were left in place.'
