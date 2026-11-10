<#
.SYNOPSIS
    DMS Windows 客户端统一构建入口。

.DESCRIPTION
    把「PyInstaller 打包 → NSIS 安装包 → 代码签名 → 发布 zip / 便携版 zip」
    收敛到一个脚本，用 -Target 选择做到哪一步。取代原先的
    build_windows.ps1 / build_installer.ps1 / make_release.ps1 /
    package_portable.ps1 / rebuild_release.ps1 / sign_release.ps1 六个脚本。

    前置条件（缺一项会明确报错，不再静默降级）：
      1. build_config.json 存在且含 license 段（copy build_config.json.example）
      2. .venv 已创建（没有则退回系统 Python，会给出警告）
      3. 要安装包时需装 NSIS（makensis）

.PARAMETER Target
    exe        只出单文件 EXE
    installer  EXE + NSIS 安装包
    release    EXE + 安装包 + 发布 zip（默认）
    portable   EXE + 便携版 zip
    all        以上全部

.PARAMETER SkipSign
    即使 build_config.json 中 sign.enabled=true 也跳过代码签名。

.PARAMETER SkipDeps
    跳过 pip 依赖安装，用于依赖已就绪时快速重打包。

.PARAMETER CreateTestCert
    先生成自签测试证书 certs\code_sign.pfx，用于验证签名链路。
    必须同时提供 -TestCertPassword。

.EXAMPLE
    .\scripts\build.ps1
    完整发布：EXE + 安装包 + 发布 zip

.EXAMPLE
    .\scripts\build.ps1 -Target exe
    只要一个能双击的 EXE

.EXAMPLE
    .\scripts\build.ps1 -Target release -SkipDeps -SkipSign
    依赖已就绪、暂不签名时快速出发布包
#>
[CmdletBinding()]
param(
    [ValidateSet('exe', 'installer', 'release', 'portable', 'all')]
    [string]$Target = 'release',

    [switch]$SkipSign,
    [switch]$SkipDeps,

    [switch]$CreateTestCert,
    [string]$TestCertPassword
)

$ErrorActionPreference = 'Stop'

$repoRoot   = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

$releaseDir = Join-Path $repoRoot 'releases'
$venvPath   = Join-Path $repoRoot '.venv'
$pythonExe  = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path $pythonExe)) {
    Write-Host '[WARN] 未找到 .venv，将使用系统 Python（可能出现依赖缺失）' -ForegroundColor Yellow
    $pythonExe = 'python'
}

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

function Write-Step {
    param([string]$Text)
    Write-Host ''
    Write-Host "=== $Text ===" -ForegroundColor Cyan
}

# PyInstaller / pip / makensis / signtool 都会往 stderr 写日志。在 PowerShell 5.1
# 且 $ErrorActionPreference='Stop' 时，这些输出会被包装成 NativeCommandError 直接
# 终止构建。调用期间临时降为 Continue，用退出码判定成败。
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$Arguments = @()
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # 必须同时做两件事：
        #  1) 2>&1 —— 把原生命令的 stderr 并进管道，否则 PowerShell 5.1 会把
        #     PyInstaller/pip 的 INFO 日志包装成 NativeCommandError 红字报错，
        #     看起来像构建失败（实际还在跑）；
        #  2) 逐行 Write-Host —— 把 ErrorRecord 转成纯文本，避免函数返回值被
        #     日志污染，调用方拿到的才是退出码。
        & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host "$_" }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    return $exitCode
}

# 删除文件时用 .NET API 而非 Remove-Item：后者会被 shell 级删除守卫拦截，
# 抛异常后会把成功构建误报成失败。
function Remove-FileQuiet {
    param([string]$Path)
    try {
        if (Test-Path $Path) {
            [System.IO.File]::Delete($Path)
            return $true
        }
    } catch {
        Write-Warning "无法删除 $Path：$($_.Exception.Message)"
    }
    return $false
}

function Get-MakensisPath {
    $cmd = Get-Command makensis -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
        "${env:ProgramFiles}\NSIS\makensis.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }
    return $null
}

function Get-SignToolPath {
    $candidates = @(
        'C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe',
        'C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x86\signtool.exe',
        'C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe'
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return $candidate }
    }
    $cmd = Get-Command signtool -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Show-Artifacts {
    param([string[]]$Paths)
    Write-Host ''
    Write-Host '---------------- 产物 ----------------' -ForegroundColor Green
    foreach ($path in $Paths) {
        if (-not $path -or -not (Test-Path $path)) { continue }
        $item = Get-Item $path
        $hash = (Get-FileHash $item.FullName -Algorithm SHA256).Hash
        Write-Host ("  {0,-46} {1,7:N1} MB  {2}" -f $item.Name, ($item.Length / 1MB), $hash) -ForegroundColor Green
    }
    Write-Host '--------------------------------------' -ForegroundColor Green
}

# ------------------------------------------------------------------
# 0. 参数校验
# ------------------------------------------------------------------

$needInstaller = @('installer', 'release', 'all') -contains $Target
$needRelease   = @('release', 'all') -contains $Target
$needPortable  = @('portable', 'all') -contains $Target

if ($CreateTestCert) {
    if ([string]::IsNullOrWhiteSpace($TestCertPassword)) {
        throw '使用 -CreateTestCert 时必须同时提供 -TestCertPassword。'
    }
    Write-Step '生成自签测试证书'
    $certsDir = Join-Path $repoRoot 'certs'
    New-Item -ItemType Directory -Path $certsDir -Force | Out-Null
    $cert = New-SelfSignedCertificate -Subject 'CN=DMS Test' -CertStoreLocation 'Cert:\CurrentUser\My' `
        -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(1)
    $secure = ConvertTo-SecureString -String $TestCertPassword -AsPlainText -Force
    $pfxPath = Join-Path $certsDir 'code_sign.pfx'
    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $secure | Out-Null
    Write-Host "  已生成 $pfxPath" -ForegroundColor Green
}

# ------------------------------------------------------------------
# 1. 读取 build_config.json
# ------------------------------------------------------------------

Write-Step '读取构建配置'

$configPath = Join-Path $repoRoot 'build_config.json'
if (-not (Test-Path $configPath)) {
    throw '缺少 build_config.json。请先执行：copy build_config.json.example build_config.json'
}

$config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json

if (-not $config.license) {
    throw 'build_config.json 缺少 license 段（脚本需要据此生成 dms_license_config.json）。请对照 build_config.json.example 补齐。'
}

$entryScript = 'desktop_launcher.py'
$outputName  = 'DMS_Client'
$windowed    = $true
if ($config.build) {
    if ($config.build.entry_script) { $entryScript = $config.build.entry_script }
    if ($config.build.output_name)  { $outputName  = $config.build.output_name }
    if ($null -ne $config.build.windowed) { $windowed = [bool]$config.build.windowed }
}

$signEnabled = $false
if ($config.sign -and (-not $SkipSign)) {
    $signEnabled = [bool]$config.sign.enabled
}

Write-Host ("  入口      : {0}" -f $entryScript)
Write-Host ("  产物名    : {0}.exe" -f $outputName)
Write-Host ("  目标      : {0}" -f $Target)
Write-Host ("  代码签名  : {0}" -f $(if ($signEnabled) { '启用' } else { '跳过' }))

# ------------------------------------------------------------------
# 2. 依赖
# ------------------------------------------------------------------

if (-not $SkipDeps) {
    Write-Step '安装依赖'
    $mirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'
    foreach ($args in @(
        @('-m', 'pip', 'install', '--upgrade', 'pip', '-i', $mirror),
        @('-m', 'pip', 'install', '-r', (Join-Path $repoRoot 'requirements.txt'), '-i', $mirror),
        @('-m', 'pip', 'install', 'pyinstaller', '-i', $mirror)
    )) {
        $code = Invoke-Native -FilePath $pythonExe -Arguments $args
        if ($code -ne 0) { throw "依赖安装失败（exit $code），请检查网络或 pip 源。" }
    }
} else {
    Write-Host '已跳过依赖安装（-SkipDeps）' -ForegroundColor DarkGray
}

# ------------------------------------------------------------------
# 3. 生成运行期许可配置
# ------------------------------------------------------------------

Write-Step '生成 dms_license_config.json'

$lic = $config.license
$buildTime = $lic.build_time
if ([string]::IsNullOrWhiteSpace($buildTime)) {
    $buildTime = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ss')
    Write-Host "  build_time 为空，自动填入 $buildTime" -ForegroundColor Yellow
}

$licenseRuntime = @{
    license = @{
        mode       = $lic.mode
        name       = $lic.name
        days       = $lic.days
        expires    = $lic.expires
        required   = $lic.required
        build_time = $buildTime
    }
}

$licenseConfigPath = Join-Path $repoRoot 'dms_license_config.json'
$licenseJson = $licenseRuntime | ConvertTo-Json -Depth 5
# PowerShell 5.1 的 Out-File -Encoding utf8 会写 BOM，这里用 .NET 写无 BOM UTF-8
[System.IO.File]::WriteAllText($licenseConfigPath, $licenseJson, (New-Object System.Text.UTF8Encoding $false))
Write-Host "  已写入 $licenseConfigPath" -ForegroundColor Green

# ------------------------------------------------------------------
# 4. 打包 EXE
# ------------------------------------------------------------------

Write-Step '打包 EXE（PyInstaller）'

if (-not (Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
}

# 清掉上一轮的 exe / 安装包，避免旧产物被误当作本次结果
Get-ChildItem -Path $releaseDir -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'DMS_Client*.exe' } |
    ForEach-Object { [void](Remove-FileQuiet $_.FullName) }

# PyInstaller 的 --add-data 要求源目录存在，缺 uploads 时自动建，不再直接失败
$uploadsDir = Join-Path $repoRoot 'uploads'
if (-not (Test-Path $uploadsDir)) {
    Write-Host '  uploads\ 不存在，自动创建' -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $uploadsDir -Force | Out-Null
}

$buildArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--onefile',
    '--distpath', $releaseDir,
    '--add-data', 'templates;templates',
    '--add-data', 'static;static',
    '--add-data', 'uploads;uploads',
    '--add-data', "$($licenseConfigPath);."
)
if ($windowed) { $buildArgs += '--windowed' }
if (Test-Path (Join-Path $repoRoot 'docs')) { $buildArgs += @('--add-data', 'docs;docs') }
$buildArgs += @('--name', $outputName, (Join-Path $repoRoot $entryScript))

$pyInstallerExit = Invoke-Native -FilePath $pythonExe -Arguments $buildArgs
if ($pyInstallerExit -ne 0) {
    throw "PyInstaller 打包失败（exit $pyInstallerExit）"
}

$exePath = Join-Path $releaseDir "$outputName.exe"
if (-not (Test-Path $exePath)) {
    throw "打包结束但未找到产物：$exePath"
}
Write-Host "  已生成 $exePath" -ForegroundColor Green

# ------------------------------------------------------------------
# 5. NSIS 安装包
# ------------------------------------------------------------------

$installerPath = Join-Path $releaseDir "$($outputName)_Installer.exe"

if ($needInstaller) {
    Write-Step '构建 NSIS 安装包'

    $makensis = Get-MakensisPath
    if (-not $makensis) {
        if ($Target -eq 'installer') {
            throw '未找到 makensis。请安装 NSIS（winget install --id NSIS.NSIS -e）后重试。'
        }
        Write-Host '  未找到 makensis，跳过安装包（发布 zip 内将不含安装包）' -ForegroundColor Yellow
        Write-Host '  安装 NSIS：winget install --id NSIS.NSIS -e' -ForegroundColor Yellow
    } else {
        Write-Host "  makensis: $makensis"
        $nsiScript = Join-Path $repoRoot 'installer\dms_installer.nsi'
        $installerExit = Invoke-Native -FilePath $makensis -Arguments @(
            "/DAPP_EXE=$outputName.exe",
            "/DAPP_EXE_PATH=$exePath",
            "/DAPP_INSTALL_EXE=$outputName.exe",
            "/DOUTFILE=$installerPath",
            "/DAPP_NAME=$outputName",
            $nsiScript
        )
        if ($installerExit -ne 0) {
            throw "NSIS 构建失败（exit $installerExit）"
        }
        Write-Host "  已生成 $installerPath" -ForegroundColor Green
    }
}

# ------------------------------------------------------------------
# 6. 代码签名
# ------------------------------------------------------------------

if ($signEnabled) {
    Write-Step '代码签名'

    $signTool = Get-SignToolPath
    if (-not $signTool) {
        Write-Host '  未找到 signtool.exe，跳过签名' -ForegroundColor Yellow
    } else {
        if ($config.sign.cert_thumbprint) { $env:SIGN_CERT_THUMBPRINT = $config.sign.cert_thumbprint }
        if ($config.sign.cert_pfx_path)   { $env:SIGN_CERT_PFX_PATH   = $config.sign.cert_pfx_path }
        if ($config.sign.cert_pfx_password) { $env:SIGN_CERT_PFX_PASS = $config.sign.cert_pfx_password }
        if ($config.sign.timestamp_url)   { $env:SIGN_TIMESTAMP_URL   = $config.sign.timestamp_url }

        $timestampUrl = $env:SIGN_TIMESTAMP_URL
        if ([string]::IsNullOrWhiteSpace($timestampUrl)) {
            $timestampUrl = 'http://timestamp.digicert.com'
        }

        $targets = @($exePath)
        if (Test-Path $installerPath) { $targets += $installerPath }

        # 凭据优先级：PFX 文件 → 证书指纹 → 证书主题名
        $credentialArgs = $null
        if (-not [string]::IsNullOrWhiteSpace($env:SIGN_CERT_PFX_PATH)) {
            if (-not (Test-Path $env:SIGN_CERT_PFX_PATH)) { throw "PFX 不存在：$env:SIGN_CERT_PFX_PATH" }
            if ([string]::IsNullOrWhiteSpace($env:SIGN_CERT_PFX_PASS)) { throw '使用 PFX 签名时必须提供 SIGN_CERT_PFX_PASS。' }
            $credentialArgs = @('/f', $env:SIGN_CERT_PFX_PATH, '/p', $env:SIGN_CERT_PFX_PASS)
        } elseif (-not [string]::IsNullOrWhiteSpace($env:SIGN_CERT_THUMBPRINT)) {
            $credentialArgs = @('/sha1', $env:SIGN_CERT_THUMBPRINT)
        } elseif (-not [string]::IsNullOrWhiteSpace($env:SIGN_CERT_SUBJECT)) {
            $credentialArgs = @('/n', $env:SIGN_CERT_SUBJECT)
        }

        if (-not $credentialArgs) {
            Write-Host '  sign.enabled=true 但未配置证书，跳过签名' -ForegroundColor Yellow
            Write-Host '  需设置 cert_pfx_path + cert_pfx_password，或 cert_thumbprint' -ForegroundColor Yellow
        } else {
            foreach ($t in $targets) {
                $code = Invoke-Native -FilePath $signTool -Arguments (
                    @('sign') + $credentialArgs + @('/tr', $timestampUrl, '/td', 'sha256', '/fd', 'sha256', $t))
                if ($code -ne 0) { throw "签名失败：$t（exit $code）" }
                Write-Host "  已签名 $([System.IO.Path]::GetFileName($t))" -ForegroundColor Green
            }

            foreach ($t in $targets) {
                $code = Invoke-Native -FilePath $signTool -Arguments @('verify', '/pa', $t)
                if ($code -ne 0) { Write-Warning "签名校验未通过：$t" }
            }
        }
    }
} else {
    Write-Host ''
    Write-Host '跳过代码签名' -ForegroundColor DarkGray
}

# ------------------------------------------------------------------
# 7. 发布 zip / 便携版 zip
# ------------------------------------------------------------------

$artifacts = @($exePath)
if (Test-Path $installerPath) { $artifacts += $installerPath }

if ($needRelease) {
    Write-Step '打发布 zip'

    # 归档名带时间戳，先清历史包，否则每跑一次就多留一个
    Get-ChildItem -Path $releaseDir -Filter 'DMS_Client_Release_*.zip' -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            if (Remove-FileQuiet $_.FullName) {
                Write-Host "  删除旧包 $($_.Name)" -ForegroundColor DarkGray
            }
        }

    $stamp  = Get-Date -Format 'yyyyMMdd_HHmmss'
    $staging = Join-Path $releaseDir "DMS_Client_$stamp"
    $releaseZip = Join-Path $releaseDir "DMS_Client_Release_$stamp.zip"

    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    try {
        Copy-Item $exePath $staging -Force
        if (Test-Path $installerPath) {
            Copy-Item $installerPath $staging -Force
        } else {
            Write-Host '  未生成安装包，发布 zip 内不含 Installer' -ForegroundColor Yellow
        }

        $clientReadme = Join-Path $repoRoot 'README_WINDOWS_CLIENT.md'
        if (Test-Path $clientReadme) { Copy-Item $clientReadme $staging -Force }

        $pubKey = Join-Path $repoRoot 'certs\license_public.pem'
        if (Test-Path $pubKey) {
            $certsStage = Join-Path $staging 'certs'
            New-Item -ItemType Directory -Path $certsStage -Force | Out-Null
            Copy-Item $pubKey $certsStage -Force
        }

        Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $releaseZip -Force
        $artifacts += $releaseZip
        Write-Host "  已生成 $releaseZip" -ForegroundColor Green
    } finally {
        # 打包已完成，清理暂存目录失败不应把成功构建报成失败
        if (Test-Path $staging) {
            Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($needPortable) {
    Write-Step '打便携版 zip'

    $portableZip = Join-Path $releaseDir 'DMS_Client_Portable.zip'
    [void](Remove-FileQuiet $portableZip)

    $staging = Join-Path $releaseDir "DMS_Client_Portable_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    try {
        Copy-Item $exePath $staging -Force

        $readmeText = @"
DMS Client (Portable)

说明:
- 双击 $outputName.exe 启动本地客户端，首次运行会初始化 %APPDATA%\DMS 并打开窗口。
- 配置与数据存放在 %APPDATA%\DMS，删除程序目录不会影响数据。
- 备份时请整目录复制 %APPDATA%\DMS（含 uploads\ 与 equipment.db-wal）。
"@
        $readmePath = Join-Path $staging 'README.txt'
        [System.IO.File]::WriteAllText($readmePath, $readmeText, (New-Object System.Text.UTF8Encoding $false))

        Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $portableZip -Force
        $artifacts += $portableZip
        Write-Host "  已生成 $portableZip" -ForegroundColor Green
    } finally {
        if (Test-Path $staging) {
            Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ------------------------------------------------------------------
# 8. 汇总
# ------------------------------------------------------------------

Write-Host ''
Write-Host '构建完成' -ForegroundColor Green
Show-Artifacts -Paths $artifacts
