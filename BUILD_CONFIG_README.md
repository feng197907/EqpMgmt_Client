# DMS 客户端构建配置说明

## 概述

项目使用 `build_config.json` 作为统一的构建配置文件，控制以下三个方面：

- **授权（license）**：试用模式 / 免费模式、到期时间、是否强制拦截
- **构建（build）**：入口脚本、输出文件名、是否显示控制台窗口
- **代码签名（sign）**：是否对可执行文件签名及签名方式

---

## 配置文件

| 文件 | 用途 |
|------|------|
| `build_config.json` | 实际参与构建的配置文件，包含敏感信息，不提交 Git |
| `build_config.json.example` | 参考模板，可复制为 `build_config.json` 后修改 |

### 完整结构

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 365,
    "expires": null,
    "required": true,
    "build_time": null
  },
  "build": {
    "entry_script": "desktop_launcher.py",
    "output_name": "DMS_Client",
    "windowed": true
  },
  "sign": {
    "enabled": false,
    "cert_thumbprint": "",
    "cert_pfx_path": "",
    "cert_pfx_password": "",
    "timestamp_url": "http://timestamp.digicert.com"
  }
}
```

---

## 配置项说明

### 1. `license`（授权配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| `mode` | string | `"trial"` 按天数或到期时间生成内嵌授权；`"free"` 不生成授权，长期免费使用 |
| `name` | string | 许可证名称，通常填写公司名或客户名，仅作标识用途 |
| `days` | integer | 试用天数，从 `build_time` 起算。`expires` 不为空时被忽略 |
| `expires` | string / null | 显式指定到期时间，ISO 8601 格式（如 `"2026-12-31T23:59:59"`）。**优先级高于 `days`** |
| `required` | boolean | `true` 表示到期后强制拦截启动；`false` 表示仅弹出警告，仍可继续使用。`mode: "free"` 时本字段被忽略 |
| `build_time` | string / null | 构建时间，ISO 8601 格式。构建脚本会在此字段为空时自动注入当前时间，一般**留 `null`** 即可 |

> **到期时间计算优先级**：`expires` > `build_time + days`

### 2. `build`（构建配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| `entry_script` | string | PyInstaller 打包入口文件，固定为 `"desktop_launcher.py"` |
| `output_name` | string | 输出程序的基础名称，不含 `.exe` 后缀，固定为 `"DMS_Client"` |
| `windowed` | boolean | `true` 不显示控制台黑窗口（生产环境使用）；`false` 显示控制台（调试使用） |

### 3. `sign`（代码签名配置）

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | `true` 启用代码签名，`false` 跳过 |
| `cert_thumbprint` | string | 证书指纹（证书已安装到 Windows 证书存储时使用） |
| `cert_pfx_path` | string | PFX 证书文件路径（如 `"C:\\certs\\code_sign.pfx"`） |
| `cert_pfx_password` | string | PFX 证书密码 |
| `timestamp_url` | string | 时间戳服务器地址，默认 `"http://timestamp.digicert.com"` |

> `cert_thumbprint` 和 `cert_pfx_path` 二选一即可，无需同时填写。

---

## 构建流程说明

### 授权处理流程

1. 构建脚本读取 `build_config.json` 中的 `license` 节。
2. 若 `build_time` 为空，自动注入当前时间（本地时间，ISO 8601）。
3. 生成运行时配置文件 `dms_license_config.json`（构建产物，**勿手动编辑**）。
4. `dms_license_config.json` 随 PyInstaller 一起打包进可执行文件内部。
5. 已安装的客户端启动时仅读取内嵌授权，**不依赖外部授权文件**。

### 客户端启动时的授权检查逻辑

```
读取内嵌 dms_license_config.json
  │
  ├─ mode = "free"  → 跳过所有授权检查，直接启动
  │
  └─ mode = "trial"
        │
        ├─ 未过期        → 记录"剩余 N 天"到启动日志，正常启动
        │
        └─ 已过期
              ├─ required = true  → 弹出错误框，拦截启动
              └─ required = false → 弹出警告框，仍可继续使用
```

### 输出文件

构建完成后，所有输出均在 `releases\` 目录：

| 文件 | 说明 |
|------|------|
| `releases\DMS_Client.exe` | 主程序（单文件可执行） |
| `releases\DMS_Client_Installer.exe` | NSIS 安装包（需安装 NSIS 才会生成） |

每次构建前会自动清理 `releases\` 目录中的旧版同名文件。

### 启动日志

程序启动时写入日志，路径为：

```
%APPDATA%\DMS\logs\startup.log
```

日志内容包括：授权模式检查结果、内嵌授权文件路径、试用剩余天数或过期原因。

---

## 使用方法

### 步骤 1：编辑配置文件

打开 `build_config.json`，按实际需求修改授权配置。

**试用版（180 天，强制到期拦截）：**

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 180,
    "expires": null,
    "required": true,
    "build_time": null
  }
}
```

**试用版（指定到期日期）：**

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 0,
    "expires": "2026-12-31T23:59:59",
    "required": true,
    "build_time": null
  }
}
```

**免费版（长期使用）：**

```json
{
  "license": {
    "mode": "free",
    "name": "",
    "days": 0,
    "expires": null,
    "required": false,
    "build_time": null
  }
}
```

### 步骤 2：运行构建脚本

在项目根目录的 PowerShell 中运行：

```powershell
# 仅构建主程序 .exe
.\scripts\build_windows.ps1

# 构建主程序 + NSIS 安装包（需已安装 NSIS）
.\scripts\build_installer.ps1
```

> `build_installer.ps1` 会先调用 `build_windows.ps1` 完成主程序构建，再生成安装包，**无需分两步运行**。

### 步骤 3：查看构建输出

```
releases\
  DMS_Client.exe           ← 主程序
  DMS_Client_Installer.exe ← 安装包（有 NSIS 时）
```

---

## 常见问题

### Q1：构建时提示 "Configuration file not found"

`build_config.json` 不存在。复制模板文件并重命名：

```powershell
Copy-Item build_config.json.example build_config.json
```

### Q2：如何彻底禁用授权功能？

将 `license.mode` 设为 `"free"` 后重新构建，所有授权检查均会跳过。

### Q3：授权到期后如何续期？

修改 `license.days` 或 `license.expires`，将 `build_time` 清为 `null`，然后重新构建。

### Q4：能否不重新构建就更新授权？

**不支持。** 当前版本不支持通过外部文件热更新已安装客户端的授权，必须修改配置后重新构建并重新分发。

### Q5：代码签名失败怎么办？

逐项排查：

1. `cert_pfx_path` 路径是否正确，文件是否存在
2. `cert_pfx_password` 密码是否正确
3. 若使用 `cert_thumbprint`，确认证书已安装到 Windows 证书存储
4. `timestamp_url` 时间戳服务器是否可访问（可尝试 `http://timestamp.sectigo.com`）

### Q6：构建后发现授权已经过期了

可能原因：`build_config.json` 中的 `expires` 日期早于当前时间，或上次构建写入的 `build_time` 加上 `days` 已超过当前时间。
解决方法：更新 `expires` 或增大 `days`，将 `build_time` 清为 `null`，重新构建。

---

## 辅助脚本说明

| 脚本 | 说明 |
|------|------|
| `scripts\build_windows.ps1` | 主构建脚本，生成单文件 `.exe`，可选调用 NSIS |
| `scripts\build_installer.ps1` | 安装包构建脚本，先触发主构建，再生成 NSIS 安装包 |
| `scripts\sign_release.ps1` | 代码签名脚本，由 `build_windows.ps1` 在 `sign.enabled=true` 时自动调用 |
| `scripts\create_keypair.py` | 生成 RSA 密钥对（`license_private.pem` / `license_public.pem`） |
| `scripts\create_license.py` | 用私钥签名生成 `license_<name>.json` 授权文件（标准 license 文件模式） |
| `scripts\verify_license.py` | 验证指定授权文件的签名是否有效 |
| `scripts\make_release.ps1` | 一键打包发布（构建 + 安装包 + 签名） |
| `scripts\rebuild_release.ps1` | 强制重新构建（清理 build 目录后重新运行） |
| `scripts\package_portable.ps1` | 打包便携版（免安装压缩包） |

---

## 示例配置速查

| 场景 | mode | days | expires | required |
|------|------|------|---------|----------|
| 30 天试用，到期可继续用 | `trial` | `30` | `null` | `false` |
| 1 年试用，到期强制拦截 | `trial` | `365` | `null` | `true` |
| 指定到 2026-12-31，强制 | `trial` | `0` | `"2026-12-31T23:59:59"` | `true` |
| 永久免费 | `free` | `0` | `null` | `false` |
