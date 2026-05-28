param(
	[Parameter(Mandatory = $true)]
	[string]$DistDir
)

$ErrorActionPreference = 'Stop'

function Get-SignToolPath {
	$candidates = @(
		'C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe',
		'C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x86\signtool.exe',
		'C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe'
	)
	foreach ($candidate in $candidates) {
		if (Test-Path $candidate) { return $candidate }
	}
	return $null
}

function Get-SigningInputs {
	$inputs = [ordered]@{
		TimestampUrl = $env:SIGN_TIMESTAMP_URL
		PfxPath      = $env:SIGN_CERT_PFX_PATH
		PfxPassword   = $env:SIGN_CERT_PFX_PASS
		Thumbprint    = $env:SIGN_CERT_THUMBPRINT
		Subject       = $env:SIGN_CERT_SUBJECT
	}

	if ([string]::IsNullOrWhiteSpace($inputs.TimestampUrl)) {
		$inputs.TimestampUrl = 'http://timestamp.digicert.com'
	}

	return $inputs
}

$signTool = Get-SignToolPath
if (-not $signTool) {
	Write-Host 'Skipping signing: signtool.exe not found.'
	exit 0
}

$inputs = Get-SigningInputs
$exePath = Join-Path $DistDir 'DMS_Client.exe'
$installerPath = Join-Path $DistDir 'DMS_Client_Installer.exe'

if (-not (Test-Path $exePath)) {
	throw "Missing binary: $exePath"
}
if (-not (Test-Path $installerPath)) {
	Write-Host "Installer not found yet, skipping: $installerPath"
}

function Invoke-SignTool {
	param(
		[string[]]$Arguments
	)
	& $signTool @Arguments
	if ($LASTEXITCODE -ne 0) {
		throw "signtool failed with exit code $LASTEXITCODE"
	}
}

if (-not [string]::IsNullOrWhiteSpace($inputs.PfxPath)) {
	if (-not (Test-Path $inputs.PfxPath)) {
		throw "PFX path not found: $($inputs.PfxPath)"
	}
	if ([string]::IsNullOrWhiteSpace($inputs.PfxPassword)) {
		throw 'SIGN_CERT_PFX_PASS is required when SIGN_CERT_PFX_PATH is used.'
	}
	Write-Host "Signing from PFX: $($inputs.PfxPath)"
	Invoke-SignTool @('sign', '/f', $inputs.PfxPath, '/p', $inputs.PfxPassword, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $exePath)
	if (Test-Path $installerPath) {
		Invoke-SignTool @('sign', '/f', $inputs.PfxPath, '/p', $inputs.PfxPassword, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $installerPath)
	}
}
elseif (-not [string]::IsNullOrWhiteSpace($inputs.Thumbprint)) {
	Write-Host "Signing from certificate store thumbprint: $($inputs.Thumbprint)"
	Invoke-SignTool @('sign', '/sha1', $inputs.Thumbprint, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $exePath)
	if (Test-Path $installerPath) {
		Invoke-SignTool @('sign', '/sha1', $inputs.Thumbprint, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $installerPath)
	}
}
elseif (-not [string]::IsNullOrWhiteSpace($inputs.Subject)) {
	Write-Host "Signing from certificate store subject: $($inputs.Subject)"
	Invoke-SignTool @('sign', '/n', $inputs.Subject, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $exePath)
	if (Test-Path $installerPath) {
		Invoke-SignTool @('sign', '/n', $inputs.Subject, '/tr', $inputs.TimestampUrl, '/td', 'sha256', '/fd', 'sha256', $installerPath)
	}
}
else {
	Write-Host 'Skipping signing: set SIGN_CERT_PFX_PATH + SIGN_CERT_PFX_PASS, SIGN_CERT_THUMBPRINT, or SIGN_CERT_SUBJECT.'
	exit 0
}

Write-Host 'Verifying signatures'
Invoke-SignTool @('verify', '/pa', '/v', $exePath)
if (Test-Path $installerPath) {
	Invoke-SignTool @('verify', '/pa', '/v', $installerPath)
}
