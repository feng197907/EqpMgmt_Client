# Build script for Windows: creates a single-file executable using PyInstaller.
# Usage: Open an elevated PowerShell in repo root and run: .\scripts\build_windows.ps1

$ErrorActionPreference = 'Stop'

# Ensure virtualenv & packages
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Desktop launcher entry point (set DMS_ENTRY_SCRIPT=launcher.py to use browser mode)
$entryScript = $env:DMS_ENTRY_SCRIPT
if ([string]::IsNullOrWhiteSpace($entryScript)) {
	$entryScript = 'desktop_launcher.py'
}

# Prepare data arguments (PyInstaller on Windows uses semicolon as separator)
$add_templates = "templates;templates"
$add_static = "static;static"
$add_uploads = "uploads;uploads"

# Build single-file executable without a console window.
pyinstaller --noconfirm --onefile --windowed --add-data $add_templates --add-data $add_static --add-data $add_uploads --name DMS_Client $entryScript

$signScript = Join-Path $PSScriptRoot 'sign_release.ps1'
if (Test-Path $signScript) {
	& $signScript -DistDir (Join-Path $PSScriptRoot '..\dist')
} else {
	Write-Host "Skipping signing: scripts\sign_release.ps1 not found."
}

Write-Host "Build finished. Binary located in dist\DMS_Client.exe"