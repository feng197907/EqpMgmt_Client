Set-Location 'D:\EquipmentManagement_client'
$ErrorActionPreference = 'Stop'

$stamp = Get-Date -Format yyyyMMdd_HHmmss
$releaseDir = 'releases'
$out = "$releaseDir\DMS_Client_Release_$stamp.zip"
$dir = "$releaseDir\DMS_Client_$stamp"

New-Item -ItemType Directory -Path $dir -Force | Out-Null

# Find the latest built executable (with timestamp)
$latestExe = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_*.exe' |
	Where-Object { $_.Name -notmatch 'Installer' } |
	Sort-Object LastWriteTime -Descending |
	Select-Object -First 1

if ($latestExe) {
	Copy-Item $latestExe.FullName $dir -Force
	Write-Host "Copied: $($latestExe.Name)"
}

# Find the latest installer (with timestamp)
$latestInstaller = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_Installer_*.exe' |
	Sort-Object LastWriteTime -Descending |
	Select-Object -First 1

if ($latestInstaller) {
	Copy-Item $latestInstaller.FullName $dir -Force
	Write-Host "Copied: $($latestInstaller.Name)"
}

# Copy readme if exists
if (Test-Path 'README_WINDOWS_CLIENT.md') {
	Copy-Item 'README_WINDOWS_CLIENT.md' $dir -Force
}

# Copy public key for license verification
if (Test-Path 'certs\license_public.pem') {
	New-Item -ItemType Directory -Path (Join-Path $dir 'certs') -Force | Out-Null
	Copy-Item 'certs\license_public.pem' (Join-Path $dir 'certs') -Force
}

Compress-Archive -Path (Join-Path $dir '*') -DestinationPath $out -Force
Write-Host "Created: $out"
