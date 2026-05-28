$ErrorActionPreference = 'Stop'

$certsDir = Join-Path $PSScriptRoot '..\certs'
New-Item -ItemType Directory -Force -Path $certsDir | Out-Null

$password = $env:SIGN_PFX_PASS
if ([string]::IsNullOrWhiteSpace($password)) {
    throw 'SIGN_PFX_PASS is not set in the current session.'
}

$cert = New-SelfSignedCertificate -Subject 'CN=DMS Test' -CertStoreLocation 'Cert:\CurrentUser\My' -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(1)
$securePassword = ConvertTo-SecureString -String $password -AsPlainText -Force
$pfxPath = Join-Path $certsDir 'code_sign.pfx'
Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null

Write-Host "PFX created: $pfxPath"
Write-Host ('Exists: ' + (Test-Path $pfxPath))