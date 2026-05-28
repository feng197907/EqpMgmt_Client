Set-Location 'D:\EquipmentManagement_client'
$stamp = Get-Date -Format yyyyMMdd_HHmmss
$out = "release\DMS_Client_Release_$stamp.zip"
$dir = "release\DMS_Client_$stamp"
New-Item -ItemType Directory -Path $dir | Out-Null
if (Test-Path 'dist\DMS_Client.exe') { Copy-Item 'dist\DMS_Client.exe' $dir -Force }
if (Test-Path 'dist\DMS_Client_Installer.exe') { Copy-Item 'dist\DMS_Client_Installer.exe' $dir -Force }
if (Test-Path 'README_WINDOWS_CLIENT.md') { Copy-Item 'README_WINDOWS_CLIENT.md' $dir -Force }
# Do not bundle private keys into the release ZIP.
# Only copy the public key if you want to distribute a test license verifier.
if (Test-Path 'certs\license_public.pem') {
	New-Item -ItemType Directory -Path (Join-Path $dir 'certs') -Force | Out-Null
	Copy-Item 'certs\license_public.pem' (Join-Path $dir 'certs') -Force
}
Compress-Archive -Path (Join-Path $dir '*') -DestinationPath $out -Force
Write-Host 'Created:' $out
