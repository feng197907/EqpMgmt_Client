# make_release.ps1 — Package release artifacts into a ZIP
# Usage: .\scripts\make_release.ps1
# Prerequisites: run build_windows.ps1 (and optionally build_installer.ps1) first

$ErrorActionPreference = 'Stop'

# Resolve repo root regardless of where the script is launched from
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

# ============================================================
# Locate release directory and artifacts
# ============================================================
$releaseDir = Join-Path $repoRoot 'releases'
if (-not (Test-Path $releaseDir)) {
    Write-Error "Release directory not found: $releaseDir — run build_windows.ps1 first."
    exit 1
}

# Find the main executable — prefer the fixed-name build output (DMS_Client.exe),
# fall back to timestamped names (DMS_Client_<timestamp>.exe)
$mainExe = $null
$fixedExe = Join-Path $releaseDir 'DMS_Client.exe'
if (Test-Path $fixedExe) {
    $mainExe = Get-Item $fixedExe
} else {
    $mainExe = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_*.exe' |
        Where-Object { $_.Name -notmatch 'Installer' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

# Find the installer — prefer fixed-name (DMS_Client_Installer.exe),
# fall back to timestamped names (DMS_Client_Installer_<timestamp>.exe)
$installerExe = $null
$fixedInstaller = Join-Path $releaseDir 'DMS_Client_Installer.exe'
if (Test-Path $fixedInstaller) {
    $installerExe = Get-Item $fixedInstaller
} else {
    $installerExe = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_Installer_*.exe' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

# Sanity check — at least the main exe must exist
if (-not $mainExe) {
    Write-Error "No DMS_Client executable found in $releaseDir — run build_windows.ps1 first."
    exit 1
}

# ============================================================
# Assemble staging directory
# ============================================================
$stamp = Get-Date -Format yyyyMMdd_HHmmss
$stagingDir = Join-Path $releaseDir "DMS_Client_$stamp"
$outZip = Join-Path $releaseDir "DMS_Client_Release_$stamp.zip"

if (Test-Path $stagingDir) { Remove-Item $stagingDir -Recurse -Force }
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null

try {
    # Copy main executable
    Copy-Item $mainExe.FullName $stagingDir -Force
    Write-Host "Copied: $($mainExe.Name)" -ForegroundColor Green

    # Copy installer (optional)
    if ($installerExe) {
        Copy-Item $installerExe.FullName $stagingDir -Force
        Write-Host "Copied: $($installerExe.Name)" -ForegroundColor Green
    } else {
        Write-Host "No installer found — skipping (build_installer.ps1 was not run)" -ForegroundColor Yellow
    }

    # Copy README if exists
    $readme = Join-Path $repoRoot 'README_WINDOWS_CLIENT.md'
    if (Test-Path $readme) {
        Copy-Item $readme $stagingDir -Force
    }

    # Copy public key for license verification
    $pubKey = Join-Path $repoRoot 'certs\license_public.pem'
    if (Test-Path $pubKey) {
        $certsDir = Join-Path $stagingDir 'certs'
        New-Item -ItemType Directory -Path $certsDir -Force | Out-Null
        Copy-Item $pubKey $certsDir -Force
    }

    # ============================================================
    # Compress
    # ============================================================
    if (Test-Path $outZip) { Remove-Item $outZip -Force }
    Compress-Archive -Path (Join-Path $stagingDir '*') -DestinationPath $outZip -Force

    # Show summary
    $zipSize = (Get-Item $outZip).Length / 1MB
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "Release package created successfully!" -ForegroundColor Green
    Write-Host "  ZIP:  $outZip" -ForegroundColor Cyan
    Write-Host "  Size: $([math]::Round($zipSize, 1)) MB" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Green
} finally {
    # Clean up staging directory
    if (Test-Path $stagingDir) {
        Remove-Item $stagingDir -Recurse -Force
    }
}
