# DMS Windows 客户端 安装与使用说明

本文档针对将本项目打包为 Windows 客户端后的安装、首次运行、升级、卸载与常见故障排查场景。

## 1. 前提与依赖
- Windows 10/11
- Python 3.10+（仅在从源码构建时需要）
- 已安装 NSIS（若需生成安装程序）
- 推荐使用虚拟环境：`.venv`

## 2. 快速安装（已有二进制）
- 便携运行：解压 `dist/DMS_Client_Portable.zip`，双击 `DMS_Client.exe` 启动。
- 安装程序：运行 `dist/DMS_Client_Installer.exe` 按提示安装（支持选择是否创建桌面图标与开机自启）。

快速版客户端会直接弹出独立窗口（`pywebview`），不再先打开浏览器；窗口背后仍然是本地 Flask 服务。

## 3. 从源码构建可执行（开发者）
1. 创建并激活虚拟环境：
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
2. 安装依赖：
```powershell
pip install -r requirements.txt
pip install pyinstaller
```
3. 使用项目提供的打包脚本（会生成 `dist/DMS_Client.exe`）：
```powershell
.\scripts\build_windows.ps1
```
默认构建的是桌面壳版本；如需浏览器版，可先设置：
```powershell
$env:DMS_ENTRY_SCRIPT = 'launcher.py'
.\scripts\build_windows.ps1
```
4. 生成 NSIS 安装程序（需先安装 NSIS）：
```powershell
makensis installer\dms_installer.nsi
```

## 3.1 发布签名（正式 CA 证书）
正式发布请使用受信任的代码签名证书，不要使用仓库里的测试证书。推荐两种方式：

- 方式 A：证书安装在当前用户/本机证书存储中
  ```powershell
  $env:SIGN_CERT_THUMBPRINT = '你的证书指纹'
  $env:SIGN_TIMESTAMP_URL = 'http://timestamp.digicert.com'
  .\scripts\build_windows.ps1
  ```

- 方式 B：使用 PFX 文件
  ```powershell
  $env:SIGN_CERT_PFX_PATH = 'C:\path\to\release-code-sign.pfx'
  $env:SIGN_CERT_PFX_PASS = 'PFX密码'
  $env:SIGN_TIMESTAMP_URL = 'http://timestamp.digicert.com'
  .\scripts\build_windows.ps1
  ```

发布签名脚本会自动签名以下文件：
- `dist\DMS_Client.exe`
- `dist\DMS_Client_Installer.exe`

如果要只单独重签，可直接运行：
```powershell
.\scripts\sign_release.ps1 -DistDir .\dist
```

## 4. 首次运行行为
- 程序会在用户目录下创建配置与数据目录：`%APPDATA%\DMS`。
  - `config.json`：应用配置（DB_TYPE、DB_PATH、UPLOAD_FOLDER）。
  - `uploads/`：上传文件目录。
  - 默认采用 SQLite（`equipment.db`）放在 `%APPDATA%\DMS`。
- 如果以 GUI/安装器方式运行，程序会自动写入默认 `config.json`（无交互），并打开桌面窗口。
- 如果以命令行运行并需要自定义配置，可执行：
```powershell
python first_run.py
# 或
python launcher.py  # 先生成默认配置，再启动服务
```

## 5. 升级说明
- 以安装器升级：用新版本安装程序覆盖安装（会替换可执行文件，保留 `%APPDATA%\DMS` 数据）。
- 便携升级：停止正在运行的 `DMS_Client.exe`，替换二进制文件，重新启动。
- 若 schema 有变更，升级脚本会在应用启动时尝试逐步迁移（参见 `database.py` 中的迁移逻辑）。建议升级前备份 `%APPDATA%\DMS/equipment.db` 与 `uploads/`。

## 6. 卸载
- 使用安装程序生成的 `Uninstall`（控制面板 -> 卸载程序）进行卸载，会移除安装目录与开始菜单/桌面快捷方式；默认不会删除 `%APPDATA%\DMS`，以保留用户数据。
- 若需要完全清理（包括用户数据），可手动删除：
```powershell
Remove-Item -Recurse -Force "$env:APPDATA\DMS"
Remove-Item -Recurse -Force "C:\Program Files\DMS_Client"  # 如安装到此目录
```

## 7. 常见故障与排查
- 启动后页面打不开（连接被拒绝/超时）
  - 确认服务是否在运行：检查进程或运行 `netstat -ano | findstr 5000`。
  - 检查是否被防火墙或安全软件拦截（允许本地回环/端口访问）。
  - 确认 `config.json` 中 `DB_TYPE` 与 `DB_PATH` 设置正确。

- 首次运行没有生成 `config.json`
  - GUI 模式下程序会自动生成默认配置；若未生成，检查 `%APPDATA%` 的写权限。
  - 可手动运行：`.venv\Scripts\python.exe first_run.py` 来初始化配置。

- 数据库连接/迁移错误
  - 查看日志（应用会将日志写入 `logs/` 或在启动目录生成 `app.log`，参见 `utils/logging_config.py`）。
  - 若从 MySQL 回退到 SQLite，请检查 `DB_TYPE` 环境变量与 `database.py` 检测逻辑。

- 文件上传失败或权限错误
  - 确保 `UPLOAD_FOLDER` 可写；推荐使用 `%APPDATA%\DMS\uploads`。

## 8. 调试建议
- 以命令行方式运行，便于查看输出与交互：
```powershell
python launcher.py
# 或直接
python -m app
```
- 如要调试桌面壳，可运行：
```powershell
python desktop_launcher.py
```
- 查看日志：`logs/app.log` 或运行时控制台输出。

## 9. 联系与贡献
- 若需要企业级打包（MSI/企业签名/代码签名证书整合），当前流程已支持正式 CA 证书；我也可以继续协助添加 WiX、自动更新或 CI 签名。

---
文件位置：`README_WINDOWS_CLIENT.md`。需要我把这份内容合并回主 `README.md` 吗？
