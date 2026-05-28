Set-Location 'D:\EquipmentManagement_client'
$ErrorActionPreference = 'Stop'

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

# Find the latest built executable in releases/
$releaseDir = 'releases'
$latestExe = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_*.exe' |
    Where-Object { $_.Name -notmatch 'Installer' } |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $latestExe) {
    Write-Error "No DMS_Client executable found in $releaseDir/. Please run build_windows.ps1 first."
    exit 1
}

$exeName = $latestExe.Name
$exeBaseName = [System.IO.Path]::GetFileNameWithoutExtension($exeName)
$installerName = "$exeBaseName`_Installer.exe"
$installerPath = Join-Path $releaseDir $installerName

Write-Host "Building installer for: $exeName"
Write-Host "Output: $installerPath"

& "$makensis" "/DAPP_EXE=$exeName" "/DOUTFILE=$installerPath" "/DAPP_NAME=DMS_Client" "installer\dms_installer.nsi"
if ($LASTEXITCODE -ne 0) { Write-Error "makensis failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }
Write-Host "NSIS build finished: $installerPath"
