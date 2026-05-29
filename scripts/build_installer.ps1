$ErrorActionPreference = 'Stop'

# Run from the repo root so the build can find releases/ and installer/
$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

# Locate makensis
$makensis = Get-Command makensis -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $makensis) {
    $candidate = 'C:\Program Files (x86)\NSIS\makensis.exe'
    if (Test-Path $candidate) { $makensis = $candidate }
}
if (-not $makensis) {
    Write-Error 'makensis not found. Please install NSIS or add makensis to PATH.'
    exit 1
}
Write-Host "Using makensis: $makensis"

# Build the Windows client first so the installer always uses the current
# config and the releases folder starts clean.
$env:DMS_SKIP_NSIS = '1'
& "$PSScriptRoot\build_windows.ps1"
$env:DMS_SKIP_NSIS = ''
if ($LASTEXITCODE -ne 0) { Write-Error "build_windows.ps1 failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }

$releaseDir = Join-Path $repoRoot 'releases'

# Prefer the stable fixed-name executable, but keep a fallback for older timestamped builds.
$latestExe = $null
$fixedExe = Join-Path $releaseDir 'DMS_Client.exe'
if (Test-Path $fixedExe) {
    $latestExe = Get-Item $fixedExe
} else {
    $latestExe = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_*.exe' |
        Where-Object { $_.Name -notmatch 'Installer' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

if (-not $latestExe) {
    Write-Error "No DMS_Client executable found in $releaseDir/ after running build_windows.ps1."
    exit 1
}

$exeName = $latestExe.Name
$installerName = "DMS_Client_Installer.exe"
$installerPath = Join-Path $releaseDir $installerName

Write-Host "Building installer: $exeName"

& "$makensis" "/DAPP_EXE=$exeName" "/DAPP_EXE_PATH=$($latestExe.FullName)" "/DOUTFILE=$installerPath" "/DAPP_NAME=DMS_Client" "installer\dms_installer.nsi"
if ($LASTEXITCODE -ne 0) { Write-Error "makensis failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }
Write-Host "Installer written to: $installerPath"
