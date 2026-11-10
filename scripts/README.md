# 打包与发布脚本说明

本目录的脚本负责把源码变成可交付的 Windows 客户端，链路是：

```
desktop_launcher.py ──PyInstaller──> releases\DMS_Client.exe
                                      └──NSIS──> releases\DMS_Client_Installer.exe
                                                    └──zip──> releases\DMS_Client_Release_<时间戳>.zip
```

本文只讲**怎么跑、跑出什么、会踩什么坑**。
配置字段含义见 [../BUILD_CONFIG_README.md](../BUILD_CONFIG_README.md)，最终用户的安装与使用见 [../README_WINDOWS_CLIENT.md](../README_WINDOWS_CLIENT.md)。

---

## 一、前置条件

| 项 | 要求 | 不满足会怎样 |
|---|---|---|
| 系统 | Windows 10/11 x64 | 脚本是 PowerShell + Windows API，Linux/macOS 跑不了 |
| Python | 3.10+，推荐仓库根目录存在 `.venv` | 无 `.venv` 时回退系统 Python，依赖可能不全 |
| 网络 | 能访问 `pypi.tuna.tsinghua.edu.cn` | 脚本每次构建都会强制 `pip install`，离线构建直接失败 |
| `build_config.json` | **必须存在**（从 `build_config.json.example` 复制） | 脚本报错退出，见「坑 1」 |
| `uploads\` 目录 | **必须存在** | `--add-data "uploads;uploads"` 找不到源目录，PyInstaller 中止，见「坑 4」 |
| NSIS（`makensis`） | 做安装包时必须 | 只出 EXE 可不装；`build_installer.ps1` 与 `rebuild_release.ps1` 会失败 |
| signtool | 可选，来自 Windows SDK | 仅签名需要，缺失时签名步骤静默跳过 |

`.venv` 和 `uploads\` 都在 `.gitignore` 里，**新克隆的仓库两者都没有**，第一次打包前先补上：

```powershell
python -m venv .venv
New-Item -ItemType Directory -Force uploads
Copy-Item build_config.json.example build_config.json
```

---

## 二、产物一览

| 产物 | 生成脚本 | 说明 |
|---|---|---|
| `releases\DMS_Client.exe` | `build_windows.ps1` | 单文件客户端，双击即用 |
| `releases\DMS_Client_Installer.exe` | `build_windows.ps1`（装了 NSIS 时自动生成）、`build_installer.ps1` | NSIS 安装程序 |
| `releases\DMS_Client_Release_<yyyyMMdd_HHmmss>.zip` | `make_release.ps1` | 对外发布包 |
| `releases\DMS_Client_Portable.zip` | `package_portable.ps1` | 便携版（EXE + 说明文件） |
| `dms_license_config.json`（仓库根目录） | `build_windows.ps1` | **构建产物**，每次构建按 `build_config.json` 重新生成，不要手改 |

`releases\`、`build\`、`*.spec`、`build_config.json`、`dms_license_config.json`、`certs\` 均已被 `.gitignore` 排除，不进版本库。

---

## 三、两条使用路径

### 3.1 一条命令走完全流程

```powershell
.\scripts\rebuild_release.ps1
```

依次执行 `build_windows.ps1` → `build_installer.ps1` → `make_release.ps1`，任一步非零退出即中断。

> ⚠️ 当前实现会**打包两次 EXE**（`build_installer.ps1` 内部又调了一次 `build_windows.ps1`），耗时约为单次的两倍。详见「坑 2」。

### 3.2 分步执行（推荐，便于定位失败点）

```powershell
.\scripts\build_windows.ps1      # 1. 出 EXE（装了 NSIS 的话连安装包一起出）
.\scripts\build_installer.ps1    # 2. 只补安装包（内部会重跑一次打包）
.\scripts\make_release.ps1       # 3. 组发布 zip
.\scripts\package_portable.ps1   # 4. 便携版 zip（可选）
```

只要 EXE、不要安装包的话，跳过第 2 步即可 —— `build_windows.ps1` 检测不到 `makensis` 时只打印一行提示，不算失败。

---

## 四、各脚本做了什么

### build_windows.ps1

1. 激活 `.venv`（不存在则用系统 Python）
2. **无条件**跑三条 pip 命令：升级 pip、装 `requirements.txt`、装 `pyinstaller`（均走清华源）
3. 读 `build_config.json` 的 `license` 段；`build_time` 为空则注入当前本地时间（`yyyy-MM-ddTHH:mm:ss`），写出 **UTF-8 无 BOM** 的 `dms_license_config.json`
4. 建 `releases\`，删掉里面旧的 `DMS_Client.exe` / `DMS_Client_*.exe` / `DMS_Client_Installer*.exe`（zip 不动）
5. 调用 PyInstaller：`--onefile --noconfirm --distpath releases`，`windowed=true` 时加 `--windowed`（无控制台窗口）；打包进 exe 的资源为 `templates\`、`static\`、`uploads\`、`dms_license_config.json`，存在 `docs\` 时一并带上
6. 检测到 `makensis` 就接着做安装包，传 `/DAPP_EXE`、`/DAPP_EXE_PATH`、`/DAPP_INSTALL_EXE`、`/DOUTFILE`、`/DAPP_NAME`；调用方设了环境变量 `DMS_SKIP_NSIS=1` 则跳过
7. `sign.enabled=true` 时写入 `SIGN_CERT_*` 环境变量并调用 `sign_release.ps1`

注意：**`certs\` 不在打包资源里**，公钥和许可证文件是 exe 的同级文件而非内置资源，详见「坑 3」。

### build_installer.ps1

先设 `DMS_SKIP_NSIS=1` 跑一遍 `build_windows.ps1`（拿到最新 EXE，且不重复生成安装包），再用 `makensis` 生成 `DMS_Client_Installer.exe`。`makensis` 查找顺序：PATH → `%ProgramFiles(x86)%\NSIS`，都没有就报错退出。

安装脚本 `installer\dms_installer.nsi` 的实际行为：

- 安装目录 `$PROGRAMFILES64\DMS_Client`
- 创建 `%APPDATA%\DMS` 与 `%APPDATA%\DMS\uploads`
- 可选组件：桌面图标、开机自启（写 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`）
- 卸载时删快捷方式、程序目录、自启注册表项；`%APPDATA%\DMS` 用 `RMDir`（只删空目录），所以**用户数据不会被误删**
- 界面语言只有 English

### make_release.ps1

把 `DMS_Client.exe`、`DMS_Client_Installer.exe`（有就带）、`README_WINDOWS_CLIENT.md`、`certs\license_public.pem`（有就带）打进 `DMS_Client_Release_<时间戳>.zip`，临时暂存目录用完即删。

### package_portable.ps1

把 `DMS_Client.exe` 和一份 `README.txt` 说明打成 `DMS_Client_Portable.zip`，适合「要发给别人但不想让他装东西」的场景。

### sign_release.ps1

对 `DMS_Client.exe` 和 `DMS_Client_Installer.exe` 做 SHA256 签名并 `signtool verify`。凭据三选一，优先级 PFX → 指纹 → 证书主题名：

| `build_config.json` → `sign` | 运行时环境变量 |
|---|---|
| `cert_pfx_path` + `cert_pfx_password` | `SIGN_CERT_PFX_PATH` + `SIGN_CERT_PFX_PASS` |
| `cert_thumbprint` | `SIGN_CERT_THUMBPRINT` |
| —（只支持环境变量） | `SIGN_CERT_SUBJECT` |

找不到 `signtool.exe` 时直接 `exit 0`（静默跳过），不会让构建失败。`signtool` 只在三个固定位置找：Windows Kits `10.0.18362.0` 的 x64 / x86 目录、App Certification Kit 目录。

### create_test_pfx.ps1

生成自签测试证书 `certs\code_sign.pfx`，用来验证签名链路是否通。自签证书在正式发布时会触发 SmartScreen 警告，只能用于测试。

```powershell
$env:SIGN_PFX_PASS = '你的测试口令'
.\scripts\create_test_pfx.ps1
```

---

## 五、许可证相关

客户端运行时读 `dms_license_config.json` 的 `license` 段决定是否强制校验（`mode=free` 永不强制），授权文件用 RSA-PSS + SHA256 签名。

```powershell
# 1. 生成密钥对（certs 目录要先存在；私钥口令在脚本内硬编码为 p@ssw0rd）
New-Item -ItemType Directory -Force certs
py -3 scripts/create_keypair.py      # → certs\license_private.pem / certs\license_public.pem

# 2. 签发授权
py -3 scripts/create_license.py 客户名称 365               # 365 天
py -3 scripts/create_license.py 客户名称 2026-12-31         # 指定日期
py -3 scripts/create_license.py 客户名称 2026-12-31T23:59:59  # 指定精确时间

# 3. 校验
py -3 scripts/verify_license.py
```

- `create_license.py` 输出 `certs\license_<客户名称>.json`
- `verify_license.py` 里的文件名是**写死的** `certs/license_TestUser.json` 加 `certs/license_public.pem`，验别的许可证需要改源码
- `certs\license_private.pem` 是签发私钥，**绝不能进发布包**（整个 `certs\` 已被 `.gitignore` 排除）

---

## 六、已知问题（均为当前代码的真实行为）

| # | 问题 | 影响 | 规避方式 |
|---|---|---|---|
| 1 | 没有 `build_config.json` 时，脚本虽然先打印「Using default configuration...」，但默认配置里**没有 `license` 段**，紧接着 `Write-Error` 并 `exit 1` | 报错看起来像配置错误，实际是「没配置文件就直接不干活」 | 必须先复制 `build_config.json.example` |
| 2 | `rebuild_release.ps1` 第 2 步调 `build_installer.ps1`，后者内部又完整跑一次 `build_windows.ps1`（含 PyInstaller） | 全流程打包两遍，耗时约两倍 | 用「3.2 分步执行」 |
| 3 | PyInstaller 只打包 `templates/static/uploads/docs/dms_license_config.json`，**不含 `certs\`**；而 `utils/license.py` 在 frozen 模式下找许可证 JSON 只查 `_MEIPASS`，不查 exe 同级目录 | 授权模式下把 `license_xxx.json` 放在 exe 旁边**不会被读取**；公钥另有 exe 同级 `certs\license_public.pem` 兜底，于是出现「公钥找得到、许可证找不到」 | 发布授权版前先实测；或把 `certs` 加进 `--add-data`，并给 `license_search_paths()` 补上 exe 同级路径 |
| 4 | `--add-data "uploads;uploads"` 依赖仓库根目录存在 `uploads\` | 目录不存在时 PyInstaller 报 `Unable to find` 并中止 | 打包前 `New-Item -ItemType Directory -Force uploads` |
| 5 | `sign_release.ps1` 里文件名硬编码 `DMS_Client.exe` / `DMS_Client_Installer.exe`，`signtool` 也只在 18362 版 SDK 目录下找 | 改了 `output_name` 或装了新版 SDK 后，签名会找不到文件或静默跳过 | 保持 `output_name = DMS_Client`；改了就同步改 `sign_release.ps1` |
| 6 | `installer\dms_installer.nsi` 注释声称支持开始菜单，实际只创建桌面图标 | 开始菜单没有快捷方式（卸载时仍会尝试删除，无副作用） | 需要就让用户勾桌面图标，或自行在 nsi 里补 `CreateShortCut "$SMPROGRAMS\..."` |

---

## 七、清理构建残留

```powershell
Remove-Item -Recurse -Force build, releases -ErrorAction SilentlyContinue
Remove-Item -Force *.spec -ErrorAction SilentlyContinue
```

`build\` 是 PyInstaller 的中间目录，`*.spec` 是它生成的规格文件，两者都不进版本库。清掉后重跑 `build_windows.ps1` 即可，不影响 `%APPDATA%\DMS` 里的正式数据。
