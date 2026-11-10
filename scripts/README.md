# scripts/ — 构建与许可证工具

本目录只有两个脚本，覆盖「打包发布」与「许可证签发」两件事。

| 文件 | 作用 |
|---|---|
| `build.ps1` | 唯一构建入口：PyInstaller 打包 → NSIS 安装包 → 代码签名 → 发布/便携版 zip |
| `license.py` | 许可证工具：`keypair` 生成密钥对、`issue` 签发、`verify` 校验 |

> 历史版本曾有 `build_windows.ps1`、`build_installer.ps1`、`make_release.ps1`、`package_portable.ps1`、`rebuild_release.ps1`、`sign_release.ps1`、`create_keypair.py`、`create_license.py`、`verify_license.py`、`create_test_pfx.ps1` 十个脚本，现已全部合并进上面两个文件。旧命令不再可用。

---

## 一、build.ps1

### 用法

```powershell
.\scripts\build.ps1 [-Target <exe|installer|release|portable|all>] [-SkipDeps] [-SkipSign]
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `-Target` | `release` | `exe` 只出 EXE；`installer` EXE+安装包；`release` EXE+安装包+发布 zip；`portable` EXE+便携版 zip；`all` 全部 |
| `-SkipDeps` | 关 | 跳过三条 pip 安装，依赖已就绪时用 |
| `-SkipSign` | 关 | 即使 `build_config.json` 里 `sign.enabled=true` 也不签名 |
| `-CreateTestCert` | 关 | 生成自签测试证书 `certs\code_sign.pfx` |
| `-TestCertPassword` | — | 配合 `-CreateTestCert`，PFX 导出密码，必填 |

### 执行步骤

顺序固定，任一步失败即抛出并退出（退出码非 0）：

1. **读 `build_config.json`**
   - 文件不存在 → 报错：`缺少 build_config.json。请先执行：copy build_config.json.example build_config.json`
   - 缺 `license` 段 → 报错终止（**没有**任何默认配置兜底）
2. **装依赖**（`-SkipDeps` 可跳过）：升级 pip、装 `requirements.txt`、装 `pyinstaller`，均走清华源
3. **生成 `dms_license_config.json`**：从配置的 `license` 段提取，`build_time` 为空则填当前本地时间；用 .NET 写 **UTF-8 无 BOM**（PowerShell 5.1 的 `Out-File -Encoding utf8` 会写 BOM，`json.load` 会因此失败）
4. **清理旧产物**：删掉 `releases\` 里的 `DMS_Client*.exe`，避免旧文件被误当成本次结果
5. **补目录**：`releases\`、`uploads\` 不存在时自动创建（`uploads\` 是 `--add-data` 的必需源目录，早期版本缺它会直接打包失败）
6. **PyInstaller**：`--onefile --noconfirm --distpath releases`，`windowed=true` 时加 `--windowed`；打入 `templates\`、`static\`、`uploads\`、`dms_license_config.json`，存在 `docs\` 时一并带上
7. **NSIS 安装包**（`installer|release|all`）：查找 `makensis`（PATH → `%ProgramFiles(x86)%\NSIS` → `%ProgramFiles%\NSIS`）。`-Target installer` 找不到就报错；其他目标只跳过并提示
8. **代码签名**（`sign.enabled=true` 且未 `-SkipSign`）：凭据优先级 PFX → 证书指纹 → 证书主题名，签 EXE 与安装包（存在时），随后 `signtool verify`
9. **发布 zip**（`release|all`）：先删 `releases\` 下历史 `DMS_Client_Release_*.zip`，再打包含 EXE、安装包、`README_WINDOWS_CLIENT.md`、`certs\license_public.pem`
10. **便携版 zip**（`portable|all`）：EXE + 自动生成的 `README.txt`
11. **汇总**：打印每个产物的名称、大小、SHA256

### 产物

| 文件 | 何时产生 |
|---|---|
| `releases\DMS_Client.exe` | 所有目标 |
| `releases\DMS_Client_Installer.exe` | `installer` / `release` / `all`（且装了 NSIS） |
| `releases\DMS_Client_Release_<yyyyMMdd_HHmmss>.zip` | `release` / `all` |
| `releases\DMS_Client_Portable.zip` | `portable` / `all` |
| `build\`、`DMS_Client.spec` | PyInstaller 中间产物，可随时删 |

### 常见用法

```powershell
.\scripts\build.ps1                                  # 完整发布
.\scripts\build.ps1 -Target exe                      # 只出 EXE，约 40 秒
.\scripts\build.ps1 -Target release -SkipDeps        # 依赖就绪，快十几秒
.\scripts\build.ps1 -Target installer -SkipDeps      # 只验证安装包
.\scripts\build.ps1 -CreateTestCert -TestCertPassword "Test@123" -Target release   # 顺带验证签名链路
```

### 实现约定（改之前请先读）

- **文件必须保存为 UTF-8 with BOM**。PowerShell 5.1 对无 BOM 的 `.ps1` 按 ANSI(GBK) 解析，中文字符串会乱码并把引号吃掉，直接报「字符串缺少终止符」。仓库里只有 `build.ps1` 带 BOM，就是因为这个。
- **调用外部命令一律走 `Invoke-Native`**。函数内部做了两件事：`2>&1` 把 stderr 并入管道，再逐行 `Write-Host` 转纯文本。漏掉任何一件都会出问题：
  - 不合并 stderr → PowerShell 5.1 在 `$ErrorActionPreference='Stop'` 下把 PyInstaller 的 INFO 日志包成 `NativeCommandError`，构建在 `Building executable...` 后直接中断；
  - 不转纯文本 → 原生命令输出混进函数返回值，调用方拿到的「退出码」是一堆日志行，判断逻辑失效。
- **删文件用 `[System.IO.File]::Delete`，不用 `Remove-Item`**。后者会被 shell 级删除守卫拦截并抛异常；构建已完成时的清理失败不应把成功报成失败。

---

## 二、license.py

### 三个子命令

```powershell
python scripts/license.py keypair [--out certs] [--password xxx] [--force]
python scripts/license.py issue <名称> [--days 365 | --expires 2026-12-31] [--out certs] [--password xxx]
python scripts/license.py verify [许可证文件] [--pubkey 公钥] [--out certs]
```

| 子命令 | 行为 |
|---|---|
| `keypair` | 生成 `certs\license_private.pem`（PKCS8、口令加密）与 `certs\license_public.pem`。已存在私钥时默认拒绝覆盖，需显式 `--force` |
| `issue` | 用私钥签 `{name, issued, expires}`，输出 `certs\license_<名称>.json`。`--days` 与 `--expires` 互斥，都不给则默认 30 天 |
| `verify` | 复用 `utils/license.py` 的校验函数，保证与客户端判定标准一致。不传文件则取 `certs` 下最新的 `license_*.json` |

退出码：`0` 成功、`1` 失败（含校验不通过、文件缺失）、`2` 参数错误。

### 私钥口令

优先级：`--password` > 环境变量 `DMS_LICENSE_KEY_PASS` > 内置默认值。

使用内置默认值时脚本会往 stderr 打一条 `[WARN]`。**生产环境请用环境变量**：

```powershell
$env:DMS_LICENSE_KEY_PASS = "换成你自己的强口令"
python scripts/license.py issue 某某制药 365
```

### 换密钥后必须做的一件事

`utils/license.py` 顶部有一个硬编码的 `EMBEDDED_PUBLIC_KEY_PEM`，是所有校验路径都失效时的兜底公钥。**重新生成密钥对后必须把它替换成新的 `license_public.pem` 内容**，否则打包出去的客户端仍用旧公钥验签，新签的许可证一律验不过。

### 校验不通过时的排查

| 提示 | 含义 |
|---|---|
| `signature invalid` | 许可证被改过，或签发用的私钥与校验用的公钥不是一对 |
| `expired` | 已到期，看 `payload.expires` |
| `公钥不存在` | 用 `--pubkey` 指定，或把 `license_public.pem` 放到许可证同目录 |
| `找不到私钥` | 先跑 `keypair` |

---

## 三、已知限制

| # | 限制 | 影响 | 规避 |
|---|---|---|---|
| 1 | `signtool` 只在三个固定位置查找：Windows Kits `10.0.18362.0` 的 x64/x86 目录、App Certification Kit 目录；之后才退到 PATH | 装了其他版本 SDK 可能找不到，签名被静默跳过 | 装 18362 版 SDK，或把 `signtool` 加进 PATH |
| 2 | 接口里没有暴露改名参数，`APP_NAME` / 输出名由 `build_config.json` 的 `output_name` 决定 | 改 `output_name` 后签名端、安装包文件名会一起变，需实测 | 保持 `output_name = DMS_Client` |
| 3 | `certs\` 不进 EXE。`utils/license.py` 在 frozen 模式下找许可证 JSON 只查 `_MEIPASS`，不查 exe 同级 | 授权版把 `license_xxx.json` 放 exe 旁边可能读不到；公钥另有 exe 同级兜底，于是出现「公钥找得到、许可证找不到」 | 发布授权版前实测；或在 `--add-data` 加 `certs`，并给 `license_search_paths()` 补 exe 同级路径 |
| 4 | `installer\dms_installer.nsi` 注释称支持开始菜单，实际只建桌面图标 | 开始菜单没有快捷方式 | 需要的话在 nsi 里补 `CreateShortCut "$SMPROGRAMS\..."` |
| 5 | 自签证书必然触发 SmartScreen 警告 | 客户首次运行会看到「未知发布者」 | 商用请购买正式代码签名证书 |

---

## 四、清场

```powershell
Remove-Item -Recurse -Force build, releases -ErrorAction SilentlyContinue
Remove-Item -Force DMS_Client.spec -ErrorAction SilentlyContinue
```

`build\`、`*.spec` 是 PyInstaller 中间产物，`releases\` 是输出目录，都不进版本库。清掉后重跑 `build.ps1` 即可，不影响 `%APPDATA%\DMS` 里的正式数据。
