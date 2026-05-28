# Package a portable ZIP containing the exe and a README
param()

$dist = Join-Path -Path $PSScriptRoot -ChildPath "..\dist"
$dist = (Resolve-Path $dist).ProviderPath
$exe = Join-Path $dist "DMS_Client.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Executable not found: $exe"
    exit 1
}

$zipPath = Join-Path $dist "DMS_Client_Portable.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$tempDir = Join-Path $env:TEMP "dms_portable_$(Get-Random)"
New-Item -Path $tempDir -ItemType Directory | Out-Null

Copy-Item $exe -Destination $tempDir

$readme = @"
DMS Client (Portable)

说明:
- 双击 DMS_Client.exe 启动本地客户端，首次运行会触发配置向导并在浏览器中打开。
- 配置与数据存放在 %APPDATA%\\DMS（Windows）

要创建安装程序，请安装 NSIS 并运行:
    makensis installer\dms_installer.nsi

"@
$readmePath = Join-Path $tempDir "README.txt"
Set-Content -Path $readmePath -Value $readme -Encoding UTF8

Compress-Archive -Path (Join-Path $tempDir '*') -DestinationPath $zipPath -Force

Remove-Item $tempDir -Recurse -Force

Write-Host "Created portable package: $zipPath"