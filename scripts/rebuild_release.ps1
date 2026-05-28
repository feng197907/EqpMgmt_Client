Set-Location 'D:\EquipmentManagement_client'
$ErrorActionPreference = 'Stop'

Write-Host 'Step 1/3: build Windows EXE'
& "$PSScriptRoot\build_windows.ps1"
if ($LASTEXITCODE -ne 0) { throw "build_windows.ps1 failed with exit code $LASTEXITCODE" }

Write-Host 'Step 2/3: build installer'
& "$PSScriptRoot\build_installer.ps1"
if ($LASTEXITCODE -ne 0) { throw "build_installer.ps1 failed with exit code $LASTEXITCODE" }

Write-Host 'Step 3/3: create release ZIP'
& "$PSScriptRoot\make_release.ps1"
if ($LASTEXITCODE -ne 0) { throw "make_release.ps1 failed with exit code $LASTEXITCODE" }

Write-Host 'All release artifacts rebuilt successfully.'