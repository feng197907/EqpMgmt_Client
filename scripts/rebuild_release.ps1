# rebuild_release.ps1 — One-click release: build EXE + installer + package ZIP
# Usage: .\scripts\rebuild_release.ps1
# This orchestrates the full pipeline:
#   Step 1: build_windows.ps1  → DMS_Client.exe
#   Step 2: build_installer.ps1 → DMS_Client_Installer.exe
#   Step 3: make_release.ps1   → DMS_Client_Release_<timestamp>.zip

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

Write-Host ''
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host '  DMS Client — Full Release Build' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor Cyan
Write-Host ''

# Step 1: Build EXE (also handles NSIS installer + signing internally)
Write-Host '[1/3] Building Windows EXE...' -ForegroundColor Yellow
& "$PSScriptRoot\build_windows.ps1"
if ($LASTEXITCODE -ne 0) { throw "build_windows.ps1 failed with exit code $LASTEXITCODE" }

# Step 2: Build NSIS installer separately (in case build_windows skipped it)
Write-Host ''
Write-Host '[2/3] Building NSIS installer...' -ForegroundColor Yellow
& "$PSScriptRoot\build_installer.ps1"
if ($LASTEXITCODE -ne 0) { throw "build_installer.ps1 failed with exit code $LASTEXITCODE" }

# Step 3: Package into ZIP
Write-Host ''
Write-Host '[3/3] Packaging release ZIP...' -ForegroundColor Yellow
& "$PSScriptRoot\make_release.ps1"
if ($LASTEXITCODE -ne 0) { throw "make_release.ps1 failed with exit code $LASTEXITCODE" }

Write-Host ''
Write-Host '============================================================' -ForegroundColor Green
Write-Host '  All release artifacts rebuilt successfully!' -ForegroundColor Green
Write-Host '============================================================' -ForegroundColor Green
