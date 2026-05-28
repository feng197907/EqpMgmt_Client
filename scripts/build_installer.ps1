Set-Location 'D:\EquipmentManagement_client'
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
& "$makensis" "installer\dms_installer.nsi"
if ($LASTEXITCODE -ne 0) { Write-Error "makensis failed with exit code $LASTEXITCODE"; exit $LASTEXITCODE }
Write-Host 'NSIS build finished.'
