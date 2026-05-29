# DMS 客户端构建配置说明

## 配置文件

项目使用 `build_config.json` 作为构建配置文件。你可以直接编辑这个文件来控制试用版、免费版和代码签名。

### 配置文件位置
- 配置文件: `build_config.json`，实际参与构建
- 配置模板: `build_config.json.example`，仅供复制参考

### 配置文件结构

```json
{
  "license": {
    "mode": "trial",
    "name": "Default",
    "days": 365,
    "expires": null,
    "required": false
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

## 配置项说明

### 1. license（授权配置）

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `mode` | string | 授权模式。`trial` 表示按天数或到期时间生成内嵌授权；`free` 表示不生成授权，长期免费使用 | `"trial"` / `"free"` |
| `name` | string | 许可证名称，通常是公司名或客户名 | `"MyCompany"` |
| `days` | integer | 试用天数，从构建时间算起 | `365` |
| `expires` | string/null | 指定过期时间，ISO 8601 格式。设置后优先于 `days` | `"2026-12-31T23:59:59"` |
| `required` | boolean | 是否强制授权。`trial` 模式下有效；`free` 模式下会被忽略 | `true` / `false` |

### 2. build（构建配置）

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `entry_script` | string | 入口脚本文件 | `"desktop_launcher.py"` |
| `output_name` | string | 输出程序基础名，不含 `.exe` | `"DMS_Client"` |
| `windowed` | boolean | 是否使用窗口模式。`true` 表示不显示控制台窗口 | `true` / `false` |

### 3. sign（代码签名配置）

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `enabled` | boolean | 是否启用代码签名 | `true` / `false` |
| `cert_thumbprint` | string | 证书指纹，证书安装在 Windows 证书存储时使用 | `"a909502dd82ae41433e6f83886b00d4277a32a7b"` |
| `cert_pfx_path` | string | PFX 证书文件路径 | `"C:\\certs\\code_sign.pfx"` |
| `cert_pfx_password` | string | PFX 证书密码 | `"your-password"` |
| `timestamp_url` | string | 时间戳服务器 URL | `"http://timestamp.digicert.com"` |

> `cert_thumbprint` 和 `cert_pfx_path` 二选一即可。

## 构建行为说明

### 1. 授权处理

当前构建流程只使用内嵌授权，不再依赖外部 `license_*.json` 文件：

1. `trial` 模式会根据 `days` 或 `expires` 生成授权。
2. 生成的授权会被打包进程序内部。
3. `free` 模式不会生成授权文件，程序按免费长期使用处理。
4. 已安装客户端启动时只检查内嵌授权，不依赖 `releases` 或安装目录里的外部授权文件。

### 2. 输出文件

构建后会生成固定名称的文件：

- `releases\DMS_Client.exe` - 主程序
- `releases\DMS_Client_Installer.exe` - 安装包

旧的时间戳文件会在下一次构建前自动清理。

## 使用方法

### 步骤 1: 编辑配置文件

打开 `build_config.json`，按需修改授权模式：

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 180,
    "expires": null,
    "required": true
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

如果你要长期免费使用，把授权模式改成：

```json
{
  "license": {
    "mode": "free",
    "name": "",
    "days": 0,
    "expires": null,
    "required": false
  }
}
```

### 步骤 2: 运行构建脚本

在 PowerShell 中运行：

```powershell
.\scripts\build_windows.ps1
```

如果你要同时构建安装包，运行：

```powershell
.\scripts\build_installer.ps1
```

### 步骤 3: 查看构建输出

构建完成后，可执行文件位于：

- `releases\DMS_Client.exe`
- `releases\DMS_Client_Installer.exe`

> 不再输出 `releases\license_<name>.json`。授权会被打包进程序内部。

## 授权功能说明

### 授权检查逻辑

1. 客户端启动时检查授权。
2. `trial` 模式下，如果授权过期，会弹出“授权过期，请联系管理员”。
3. `free` 模式下不生成授权文件，客户端按免费长期使用处理。

### 运行时日志

程序启动时会写入启动日志，位置为：

- `%APPDATA%\DMS\logs\startup.log`

日志会记录：

- 解析到的 license 文件路径
- 是否使用了内嵌授权回退

### 手动创建授权文件

如果你要更新试用授权，可以修改 `build_config.json` 后重新构建，构建脚本会重新生成并打包授权。

注意：当前版本不支持通过外部 `license.json` 热更新已安装客户端的授权。

### 验证授权文件

如果你需要验证生成的授权文件，可以使用：

```bash
python scripts/verify_license.py
```

## 常见问题

### Q1: 构建时提示 "Configuration file not found"

**A**: 确保 `build_config.json` 文件存在。如果不存在，复制 `build_config.json.example` 为 `build_config.json`。

### Q2: 如何禁用授权功能？

**A**: 把 `license.mode` 设为 `free`，然后重新构建。

### Q3: 授权到期后如何续期？

**A**: 修改 `license.days` 或 `license.expires` 后重新构建。

### Q4: 如何在不重新构建的情况下更新授权？

**A**: 当前版本不支持外部文件热更新授权，需要修改配置后重新构建。

### Q5: 代码签名失败

**A**: 检查以下事项：

1. 证书文件路径是否正确
2. 证书密码是否正确
3. 时间戳服务器是否可访问
4. 如果使用证书指纹，确保证书已安装到 Windows 证书存储

## 示例配置

### 示例 1: 试用版本，30 天

```json
{
  "license": {
    "mode": "trial",
    "name": "TestClient",
    "days": 30,
    "expires": null,
    "required": false
  }
}
```

### 示例 2: 试用版本，1 年

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 365,
    "expires": null,
    "required": true
  }
}
```

### 示例 3: 试用版本，到指定日期

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 365,
    "expires": "2026-12-31T23:59:59",
    "required": true
  }
}
```

### 示例 4: 免费版本，长期使用

```json
{
  "license": {
    "mode": "free",
    "name": "",
    "days": 0,
    "expires": null,
    "required": false
  }
}
```

### 示例 5: 启用代码签名

```json
{
  "license": {
    "mode": "trial",
    "name": "MyCompany",
    "days": 365,
    "expires": null,
    "required": true
  },
  "sign": {
    "enabled": true,
    "cert_thumbprint": "a909502dd82ae41433e6f83886b00d4277a32a7b",
    "cert_pfx_path": "",
    "cert_pfx_password": "",
    "timestamp_url": "http://timestamp.digicert.com"
  }
}
```
