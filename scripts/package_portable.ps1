# package_portable.ps1 — Package a portable ZIP containing the exe and a README
# Usage: .\scripts\package_portable.ps1

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

$releaseDir = Join-Path $repoRoot 'releases'
if (-not (Test-Path $releaseDir)) {
    Write-Error "Release directory not found: $releaseDir — run build_windows.ps1 first."
    exit 1
}

# Find the main executable
$exe = Join-Path $releaseDir 'DMS_Client.exe'
if (-not (Test-Path $exe)) {
    # Fallback: look for timestamped builds
    $timestamped = Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_*.exe' |
        Where-Object { $_.Name -notmatch 'Installer' } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($timestamped) {
        $exe = $timestamped.FullName
    } else {
        Write-Error "No DMS_Client executable found in $releaseDir"
        exit 1
    }
}

$zipPath = Join-Path $releaseDir 'DMS_Client_Portable.zip'
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$tempDir = Join-Path $env:TEMP "dms_portable_$(Get-Random)"
New-Item -Path $tempDir -ItemType Directory | Out-Null

try {
    Copy-Item $exe -Destination $tempDir

    $readme = @"
DMS Client (Portable)

说明:
- 双击 DMS_Client.exe 启动本地客户端，首次运行会触发配置向导并在浏览器中打开。
- 配置与数据存放在 %APPDATA%\DMS（Windows）

要创建安装程序，请安装 NSIS 并运行:
    .\scripts\build_installer.ps1

"@
    $readmePath = Join-Path $tempDir 'README.txt'
    [System.IO.File]::WriteAllText($readmePath, $readme, (New-Object System.Text.UTF8Encoding $false))

    Compress-Archive -Path (Join-Path $tempDir '*') -DestinationPath $zipPath -Force

    Write-Host "Created portable package: $zipPath" -ForegroundColor Green
} finally {
    if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
}
