# Build script for Windows: creates a single-file executable using PyInstaller.
# Usage: Open an elevated PowerShell in repo root and run: .\scripts\build_windows.ps1
#
# Configuration: Edit build_config.json (copy from build_config.json.example)

$ErrorActionPreference = 'Stop'

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
$configFile = Join-Path $PSScriptRoot '..\build_config.json'
$configExample = Join-Path $PSScriptRoot '..\build_config.json.example'

if (-not (Test-Path $configFile)) {
	Write-Host "Configuration file not found: $configFile" -ForegroundColor Yellow
	Write-Host "Please copy $configExample to build_config.json and edit it." -ForegroundColor Yellow
	Write-Host "Using default configuration..." -ForegroundColor Gray
	
	# Default configuration
	$config = @{
		license = @{
			name     = 'Default'
			days    = 365
			expires = $null
			required = $false
		}
		build   = @{
			entry_script = 'desktop_launcher.py'
			output_name = 'DMS_Client'
			windowed    = $true
		}
		sign    = @{
			enabled          = $false
			cert_thumbprint = ''
			cert_pfx_path   = ''
			cert_pfx_password = ''
			timestamp_url   = 'http://timestamp.digicert.com'
		}
	}
} else {
	Write-Host "Loading configuration from: $configFile" -ForegroundColor Cyan
	$config = Get-Content $configFile -Raw | ConvertFrom-Json
}

# Extract configuration
$licenseName = $config.license.name
$licenseDays = $config.license.days
$licenseExpires = $config.license.expires
$licenseRequired = $config.license.required

$entryScript = $config.build.entry_script
$outputName = $config.build.output_name
$windowed = $config.build.windowed

$signEnabled = $config.sign.enabled
$signThumbprint = $config.sign.cert_thumbprint
$signPfxPath = $config.sign.cert_pfx_path
$signPfxPass = $config.sign.cert_pfx_password
$signTimestampUrl = $config.sign.timestamp_url

# ============================================================
# Generate timestamp for output filename
# ============================================================
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputNameWithTimestamp = "$($outputName)_$timestamp"

# ============================================================
# Build process
# ============================================================

# Ensure virtualenv & packages
Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple

# ============================================================
# License generation (optional)
# ============================================================
if (-not [string]::IsNullOrWhiteSpace($licenseName)) {
	Write-Host "`nGenerating license for: $licenseName" -ForegroundColor Cyan
	
	# Build the command
	$licenseCmd = "python scripts/create_license.py `"$licenseName`""
	
	if (-not [string]::IsNullOrWhiteSpace($licenseExpires)) {
		# Use specific expiry date
		$licenseCmd += " `"$licenseExpires`""
		Write-Host "  Expiry date: $licenseExpires" -ForegroundColor Yellow
	} elseif ($licenseDays -and $licenseDays -gt 0) {
		# Use days
		$licenseCmd += " $licenseDays"
		Write-Host "  Valid for: $licenseDays days" -ForegroundColor Yellow
	} else {
		# Default: 365 days
		$licenseCmd += " 365"
		Write-Host "  Valid for: 365 days (default)" -ForegroundColor Yellow
	}
	
	# Execute license creation
	Invoke-Expression $licenseCmd
	
	# Copy license to dist folder (will be bundled with the executable)
	$licenseSrc = "certs/license_$licenseName.json"
	if (Test-Path $licenseSrc) {
		Write-Host "  License file: $licenseSrc" -ForegroundColor Green
	}
	
	# Set environment variable for license enforcement
	if ($licenseRequired) {
		$env:DMS_LICENSE_REQUIRED = '1'
		Write-Host "  License enforcement: ENABLED" -ForegroundColor Yellow
	} else {
		$env:DMS_LICENSE_REQUIRED = ''
		Write-Host "  License enforcement: OPTIONAL" -ForegroundColor Gray
	}
} else {
	Write-Host "`nNo license configuration found (set license.name in build_config.json)" -ForegroundColor Gray
}

# Prepare data arguments (PyInstaller on Windows uses semicolon as separator)
$add_templates = "templates;templates"
$add_static = "static;static"
$add_uploads = "uploads;uploads"

# Add license file if exists
$licenseFile = "certs/license_$licenseName.json"
if (Test-Path $licenseFile) {
	$add_license = "$licenseFile;$licenseFile"
} else {
	$add_license = $null
}

# ============================================================
# Generate license enforcement config file
# This file is used by the runtime to check if license is required
# ============================================================
$licenseConfigFile = "dms_license_config.json"
$licenseConfig = @{
	license = @{
		required = if ($licenseRequired) { $true } else { $false }
		name     = $licenseName
		days     = if ($licenseDays) { $licenseDays } else { 365 }
	}
}
$licenseConfig | ConvertTo-Json -Depth 3 | Out-File -FilePath $licenseConfigFile -Encoding utf8
Write-Host "License enforcement config: $licenseConfigFile" -ForegroundColor Green
if ($licenseRequired) {
	Write-Host "  Enforcement: ENABLED (written to config file)" -ForegroundColor Yellow
} else {
	Write-Host "  Enforcement: OPTIONAL (written to config file)" -ForegroundColor Gray
}

$add_license_config = "$licenseConfigFile;$licenseConfigFile"

# Add public key for license verification
$publicKeyFile = "certs/license_public.pem"
if (Test-Path $publicKeyFile) {
	$add_public_key = "$publicKeyFile;license_public.pem"
	Write-Host "Public key for verification: $publicKeyFile" -ForegroundColor Green
} else {
	$add_public_key = $null
	Write-Host "Warning: Public key not found at $publicKeyFile" -ForegroundColor Yellow
}

# Build single-file executable
Write-Host "`nBuilding executable..." -ForegroundColor Cyan

# Create releases directory if it doesn't exist
$releaseDir = "releases"
if (-not (Test-Path $releaseDir)) {
	New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
	Write-Host "Created release directory: $releaseDir/" -ForegroundColor Green
}

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

if ($add_public_key) {
	$buildArgs += @("--add-data", $add_public_key)
}

if ($add_license) {
	$buildArgs += @("--add-data", $add_license)
}

$buildArgs += @(
	"--name", $outputNameWithTimestamp,
	$entryScript
)

# Execute PyInstaller
pyinstaller @buildArgs

# Copy license to releases folder (for standalone use)
if (Test-Path $licenseFile) {
	Copy-Item $licenseFile -Destination "$releaseDir/" -Force
	Write-Host "License file copied to $releaseDir/" -ForegroundColor Green
}

# ============================================================
# Build NSIS installer (optional)
# ============================================================
$installerName = "$($outputName)_Installer_$timestamp.exe"
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
	Write-Host "`nBuilding NSIS installer..." -ForegroundColor Cyan
	Write-Host "  Installer: $installerName" -ForegroundColor Yellow
	
	$nsiScript = Join-Path $PSScriptRoot '..\installer\dms_installer.nsi'
	$nsisArgs = @(
		"/DAPP_EXE=$outputNameWithTimestamp.exe",
		"/DOUTFILE=$installerPath",
		"/DAPP_NAME=$outputName",
		$nsiScript
	)
	
	& $makensisPath @nsisArgs
	
	if ($LASTEXITCODE -eq 0) {
		Write-Host "  Installer built successfully: $installerPath" -ForegroundColor Green
	} else {
		Write-Host "  NSIS installer build failed (exit code: $LASTEXITCODE)" -ForegroundColor Red
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
		& $signScript -DistDir (Join-Path $PSScriptRoot "..\$releaseDir")
	} else {
		Write-Host "Signing script not found: $signScript" -ForegroundColor Yellow
	}
} else {
	Write-Host "`nSkipping code signing (disabled in config)" -ForegroundColor Gray
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "Build finished successfully!" -ForegroundColor Green
Write-Host "Binary located in: $releaseDir\$outputNameWithTimestamp.exe" -ForegroundColor Green
if (Test-Path $installerPath) {
	Write-Host "Installer located in: $releaseDir\$installerName" -ForegroundColor Green
}
Write-Host "============================================================" -ForegroundColor Green

# Display configuration summary
Write-Host "`nConfiguration Summary:" -ForegroundColor Cyan
Write-Host "  Entry script: $entryScript"
Write-Host "  Output name: $outputNameWithTimestamp"

if (-not [string]::IsNullOrWhiteSpace($licenseName)) {
	Write-Host "`n  License Configuration:" -ForegroundColor Cyan
	Write-Host "    Name: $licenseName"
	if (-not [string]::IsNullOrWhiteSpace($licenseExpires)) {
		Write-Host "    Expires: $licenseExpires"
	} else {
		$d = if (-not $licenseDays -or $licenseDays -le 0) { 365 } else { $licenseDays }
		Write-Host "    Valid for: $d days"
	}
	if ($licenseRequired) {
		Write-Host "    Enforcement: REQUIRED" -ForegroundColor Yellow
	} else {
		Write-Host "    Enforcement: OPTIONAL" -ForegroundColor Gray
	}
}

if ($signEnabled) {
	Write-Host "`n  Signing: ENABLED" -ForegroundColor Green
} else {
	Write-Host "`n  Signing: DISABLED" -ForegroundColor Gray
}