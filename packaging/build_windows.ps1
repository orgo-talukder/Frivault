$ErrorActionPreference = 'Stop'

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $ProjectRoot '.venv315\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Create .venv315 with CPython 3.15.1 and install requirements.lock plus requirements-packaging.lock first.'
}
$PythonVersion = (& $Python -c 'import platform; print(platform.python_version())').Trim()
if ($PythonVersion -ne '3.15.1') { throw "Expected Python 3.15.1, found $PythonVersion" }

$BuildRoot = Join-Path $ProjectRoot 'build\windows'
$PyInstallerDist = Join-Path $BuildRoot 'pyinstaller-dist-0.1.0'
$PyInstallerWork = Join-Path $BuildRoot 'pyinstaller-work-0.1.0'
$SpecPath = Join-Path $BuildRoot 'spec-0.1.0'
$PackageRoot = Join-Path $BuildRoot 'package-v0.1.0\Frivault'
$FinalZip = Join-Path $ProjectRoot 'dist\Frivault-0.1.0-win-x64.zip'
New-Item -ItemType Directory -Force -Path $BuildRoot, $PyInstallerDist, $PyInstallerWork, $SpecPath | Out-Null

$PyInstallerArgs = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
    '--name', 'Frivault', '--icon', (Join-Path $ProjectRoot 'icons\frivault_icon.ico'),
    '--add-data', ((Join-Path $ProjectRoot 'src\frivault\resources') + ';frivault\resources'),
    '--collect-all', 'webview', '--collect-all', 'clr_loader',
    '--collect-all', 'pythonnet', '--collect-submodules', 'frivault',
    '--distpath', $PyInstallerDist, '--workpath', $PyInstallerWork,
    '--specpath', $SpecPath, (Join-Path $ProjectRoot 'src\frivault\__main__.py')
)
Push-Location $ProjectRoot
try { & $Python @PyInstallerArgs; if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" } }
finally { Pop-Location }

$BuiltApp = Join-Path $PyInstallerDist 'Frivault'
$BuiltExe = Join-Path $BuiltApp 'Frivault.exe'
if (-not (Test-Path -LiteralPath $BuiltExe -PathType Leaf)) { throw 'PyInstaller did not create Frivault.exe' }
if (Test-Path -LiteralPath $PackageRoot) {
    throw "Refusing to overwrite existing package folder: $PackageRoot. Move it aside before rebuilding."
}
New-Item -ItemType Directory -Force -Path (Split-Path $PackageRoot -Parent) | Out-Null
Copy-Item -LiteralPath $BuiltApp -Destination $PackageRoot -Recurse
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install.ps1') -Destination $PackageRoot
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $PackageRoot
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'README.md') -Destination $PackageRoot
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'Frivault_Documentation\user_guide.md') -Destination $PackageRoot
& $Python (Join-Path $PSScriptRoot 'copy_licenses.py') --project-root $ProjectRoot --output (Join-Path $PackageRoot 'ThirdPartyLicenses')
if ($LASTEXITCODE -ne 0) { throw 'Third-party license collection failed.' }
New-Item -ItemType Directory -Force -Path (Split-Path $FinalZip -Parent) | Out-Null
Compress-Archive -LiteralPath $PackageRoot -DestinationPath $FinalZip -CompressionLevel Optimal -Force
Write-Output "Package created: $FinalZip"
