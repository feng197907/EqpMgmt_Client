# Build script for Windows: creates a single-file executable using PyInstaller.
# Usage: Open an elevated PowerShell in repo root and run: .\scripts\build_windows.ps1
#
# Configuration: Edit build_config.json (copy from build_config.json.example)

$ErrorActionPreference = 'Stop'

# Normalize all relative paths to the repository root so the script works
# whether it is launched from the repo root or from the scripts directory.
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

# ============================================================
# Activate virtual environment
# ============================================================
$venvPath = Join-Path $PSScriptRoot '..\.venv'
$activateScript = Join-Path $venvPath 'Scripts\Activate.ps1'
if (Test-Path $activateScript) {
	Write-Host "Activating virtual environment: $venvPath" -ForegroundColor Cyan
	& $activateScript
} else {
	Write-Host "Virtual environment not found at: $venvPath" -ForegroundColor Yellow
	Write-Host "Using system Python..." -ForegroundColor Yellow
}

# ============================================================
# Load configuration from build_config.json
# ============================================================
$configFile = Join-Path $repoRoot 'build_config.json'
$configExample = Join-Path $repoRoot 'build_config.json.example'

if (-not (Test-Path $configFile)) {
	Write-Host "Configuration file not found: $configFile" -ForegroundColor Yellow
	Write-Host "Please copy $configExample to build_config.json and edit it." -ForegroundColor Yellow
	Write-Host "Using default configuration..." -ForegroundColor Gray
	
	# Default configuration
	$config = @{
		build = @{
			entry_script = 'desktop_launcher.py'
			output_name = 'DMS_Client'
			windowed    = $true
		}
		sign  = @{
			enabled          = $false
			cert_thumbprint = ''
			cert_pfx_path   = ''
			cert_pfx_password = ''
			timestamp_url   = 'http://timestamp.digicert.com'
		}
	}
} else {
	Write-Host "Loading configuration from: $configFile" -ForegroundColor Cyan
	$config = Get-Content $configFile -Raw -Encoding UTF8 | ConvertFrom-Json
}

# Extract configuration
$entryScript = $config.build.entry_script
$outputName = $config.build.output_name
$windowed = $config.build.windowed

$entryScriptPath = Join-Path $repoRoot $entryScript

$signEnabled = $config.sign.enabled
$signThumbprint = $config.sign.cert_thumbprint
$signPfxPath = $config.sign.cert_pfx_path
$signPfxPass = $config.sign.cert_pfx_password
$signTimestampUrl = $config.sign.timestamp_url

# ============================================================
# Build process
# ============================================================

# Determine the python executable (prefer venv if activated)
$pythonExe = 'python'
if (Test-Path (Join-Path $venvPath 'Scripts\python.exe')) {
	$pythonExe = Join-Path $venvPath 'Scripts\python.exe'
}

# Ensure virtualenv & packages
Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $pythonExe -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
& $pythonExe -m pip install -r (Join-Path $repoRoot 'requirements.txt') -i https://pypi.tuna.tsinghua.edu.cn/simple
& $pythonExe -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

# Prepare data arguments (PyInstaller on Windows uses semicolon as separator)
$add_templates = "templates;templates"
$add_static = "static;static"
$add_uploads = "uploads;uploads"
$add_docs = if (Test-Path (Join-Path $repoRoot 'docs')) { "docs;docs" } else { $null }

# ============================================================
# License runtime config — auto-generated from build_config.json
# ============================================================
# The ``license`` section in build_config.json is the single source of truth.
# This script extracts it, injects build_time (if null), writes
# dms_license_config.json, and packages it into the executable.
# dms_license_config.json is a build artifact — do NOT edit it manually.

$licenseSection = $config.license
if (-not $licenseSection) {
	Write-Error "build_config.json is missing the 'license' section. Please add it (see build_config.json.example)."
	exit 1
}

# If build_time is null/empty, inject current build timestamp (local time, ISO 8601)
$buildTime = $licenseSection.build_time
if ([string]::IsNullOrWhiteSpace($buildTime)) {
	$buildTime = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
	Write-Host "License build_time not set — auto-injecting: $buildTime" -ForegroundColor Yellow
}

# Build the runtime license config JSON that utils/license.py expects
$licenseRuntime = @{
	license = @{
		mode       = $licenseSection.mode
		name       = $licenseSection.name
		days       = $licenseSection.days
		expires    = $licenseSection.expires
		required   = $licenseSection.required
		build_time = $buildTime
	}
}

$licenseConfigFile = 'dms_license_config.json'
$licenseConfigFilePath = Join-Path $repoRoot $licenseConfigFile

# Write dms_license_config.json (overwrite if exists)
# PowerShell 5.1 does not support UTF8NoBOM; use .NET to write UTF-8 without BOM
$licenseJson = $licenseRuntime | ConvertTo-Json -Depth 5
[System.IO.File]::WriteAllText($licenseConfigFilePath, $licenseJson, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Generated runtime license config: $licenseConfigFilePath" -ForegroundColor Green

$add_license_config = "$licenseConfigFile;."

# Build single-file executable
Write-Host "`nBuilding executable..." -ForegroundColor Cyan

# Create releases directory if it doesn't exist
$releaseDir = Join-Path $repoRoot 'releases'
if (-not (Test-Path $releaseDir)) {
	New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
	Write-Host "Created release directory: $releaseDir/" -ForegroundColor Green
}

# Remove stale packaged executables, installers, and license exports before building a fresh set.
Get-ChildItem -Path $releaseDir -File -ErrorAction SilentlyContinue |
	Where-Object {
		$_.Name -like 'DMS_Client.exe' -or
		$_.Name -like 'DMS_Client_*.exe' -or
		$_.Name -like 'DMS_Client_Installer.exe' -or
		$_.Name -like 'DMS_Client_Installer_*.exe'
	} |
	Remove-Item -Force -ErrorAction SilentlyContinue

$buildArgs = @(
	'--noconfirm',
	'--onefile',
	"--distpath", $releaseDir
)

if ($windowed) {
	$buildArgs += '--windowed'
}

$buildArgs += @(
	"--add-data", $add_templates,
	"--add-data", $add_static,
	"--add-data", $add_uploads,
	"--add-data", $add_license_config
)

if ($add_docs) {
	$buildArgs += @("--add-data", $add_docs)
}

$buildArgs += @(
	"--name", $outputName,
	$entryScriptPath
)


# Execute PyInstaller
& $pythonExe -m PyInstaller @buildArgs
if ($LASTEXITCODE -ne 0) {
	Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
	exit $LASTEXITCODE
}

$builtExePath = Join-Path $releaseDir "$outputName.exe"

# ============================================================
# Build NSIS installer (optional)
# ============================================================
$installerName = "$($outputName)_Installer.exe"
$installerPath = Join-Path $releaseDir $installerName

# Check if NSIS is installed (check PATH first, then common install locations)
$makensisPath = Get-Command makensis -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $makensisPath) {
	$makensisPath = @(
		"${env:ProgramFiles(x86)}\NSIS\makensis.exe",
		"${env:ProgramFiles}\NSIS\makensis.exe"
	) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if ($makensisPath) {
	if ($env:DMS_SKIP_NSIS -eq '1') {
		Write-Host "`nSkipping NSIS installer (requested by caller)" -ForegroundColor Gray
	} else {
	Write-Host "`nBuilding NSIS installer..." -ForegroundColor Cyan
	Write-Host "  Installer: $installerName" -ForegroundColor Yellow
	
	$nsiScript = Join-Path $PSScriptRoot '..\installer\dms_installer.nsi'
	$nsisArgs = @("/DAPP_EXE=$outputName.exe",
		"/DAPP_EXE_PATH=$builtExePath",
		"/DAPP_INSTALL_EXE=$outputName.exe",
		"/DOUTFILE=$installerPath",
		"/DAPP_NAME=$outputName",
		$nsiScript)
	
	& $makensisPath @nsisArgs
	
	if ($LASTEXITCODE -eq 0) {
		Write-Host "  Installer built successfully: $installerPath" -ForegroundColor Green
	} else {
		Write-Host "  NSIS installer build failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
		exit $LASTEXITCODE
	}
	}
} else {
	Write-Host "`nSkipping NSIS installer (makensis.exe not found)" -ForegroundColor Gray
	Write-Host "  Install NSIS from https://nsis.sourceforge.io/ to enable installer creation" -ForegroundColor Gray
}

# ============================================================
# Code signing (optional)
# ============================================================
if ($signEnabled) {
	Write-Host "`nSigning executable..." -ForegroundColor Cyan
	
	# Set environment variables for signing
	if (-not [string]::IsNullOrWhiteSpace($signThumbprint)) {
		$env:SIGN_CERT_THUMBPRINT = $signThumbprint
	}
	
	if (-not [string]::IsNullOrWhiteSpace($signPfxPath)) {
		$env:SIGN_CERT_PFX_PATH = $signPfxPath
	}
	
	if (-not [string]::IsNullOrWhiteSpace($signPfxPass)) {
		$env:SIGN_CERT_PFX_PASS = $signPfxPass
	}
	
	if (-not [string]::IsNullOrWhiteSpace($signTimestampUrl)) {
		$env:SIGN_TIMESTAMP_URL = $signTimestampUrl
	}
	
	# Run sign script
	$signScript = Join-Path $PSScriptRoot 'sign_release.ps1'
	if (Test-Path $signScript) {
		& $signScript -DistDir $releaseDir
	} else {
		Write-Host "Signing script not found: $signScript" -ForegroundColor Yellow
	}
} else {
	Write-Host "`nSkipping code signing (disabled in config)" -ForegroundColor Gray
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "Build finished successfully!" -ForegroundColor Green
Write-Host "Binary located in: $releaseDir\$outputName.exe" -ForegroundColor Green
if (Test-Path $installerPath) {
	Write-Host "Installer located in: $releaseDir\$installerName" -ForegroundColor Green
}
Write-Host "============================================================" -ForegroundColor Green

# Display configuration summary
Write-Host "`nConfiguration Summary:" -ForegroundColor Cyan
Write-Host "  Entry script: $entryScript"
Write-Host "  Output name: $outputName"

if ($signEnabled) {
	Write-Host "`n  Signing: ENABLED" -ForegroundColor Green
} else {
	Write-Host "`n  Signing: DISABLED" -ForegroundColor Gray
}