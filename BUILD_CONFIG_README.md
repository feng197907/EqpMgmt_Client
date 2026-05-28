# DMS 客户端构建配置说明

## 配置文件

项目使用 `build_config.json` 作为构建配置文件。你可以直接编辑这个文件来配置构建选项。

### 配置文件位置
- **配置文件**: `build_config.json` （实际使用的配置）
- **配置模板**: `build_config.json.example` （模板文件，不会被使用）

### 配置文件结构

```json
{
  "license": {
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
| `name` | string | 许可证名称（通常是公司或用户名） | `"MyCompany"` |
| `days` | integer | 授权有效天数（从构建时间算起） | `365` |
| `expires` | string/null | 指定过期时间（ISO 8601 格式），设置此项会覆盖 `days` | `"2026-12-31T23:59:59"` |
| `required` | boolean | 是否强制要求授权（true: 无授权无法运行；false: 无授权会警告但可运行） | `true` / `false` |

**使用示例**：

```json
// 示例 1: 授权 365 天（从构建时间算起）
"license": {
  "name": "MyCompany",
  "days": 365,
  "expires": null,
  "required": true
}

// 示例 2: 授权到指定日期
"license": {
  "name": "MyCompany",
  "days": 365,  // 此值会被 expires 覆盖
  "expires": "2026-12-31T23:59:59",
  "required": true
}

// 示例 3: 不强制授权（软性提醒）
"license": {
  "name": "MyCompany",
  "days": 90,
  "expires": null,
  "required": false
}
```

### 2. build（构建配置）

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `entry_script` | string | 入口脚本文件 | `"desktop_launcher.py"` |
| `output_name` | string | 输出可执行文件名（不含 .exe） | `"DMS_Client"` |
| `windowed` | boolean | 是否使用窗口模式（true: 无控制台窗口；false: 显示控制台） | `true` / `false` |

### 3. sign（代码签名配置）

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `enabled` | boolean | 是否启用代码签名 | `true` / `false` |
| `cert_thumbprint` | string | 证书指纹（证书安装在 Windows 证书存储时使用） | `"a909502dd82ae41433e6f83886b00d4277a32a7b"` |
| `cert_pfx_path` | string | PFX 证书文件路径（使用 PFX 文件时使用） | `"C:\\certs\\code_sign.pfx"` |
| `cert_pfx_password` | string | PFX 证书密码 | `"your-password"` |
| `timestamp_url` | string | 时间戳服务器 URL | `"http://timestamp.digicert.com"` |

**注意**：`cert_thumbprint` 和 `cert_pfx_path` 只需要设置其中一个。

## 使用方法

### 步骤 1: 编辑配置文件

打开 `build_config.json`，修改配置项：

```json
{
  "license": {
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

### 步骤 2: 运行构建脚本

在 PowerShell 中运行：

```powershell
.\scripts\build_windows.ps1
```

### 步骤 3: 查看构建输出

构建完成后，可执行文件位于：
- `dist\DMS_Client.exe` - 主程序
- `dist\license_MyCompany.json` - 许可证文件（如果配置了）

## 授权功能说明

### 授权验证逻辑

1. **授权文件位置**（按优先级排序）：
   - `%APPDATA%\DMS\license.json`
   - 可执行文件所在目录的 `license.json`
   - 可执行文件所在目录的 `license_<name>.json`

2. **授权检查时机**：
   - 客户端启动时检查授权
   - 如果 `license.required = true` 且授权无效 → **阻止启动**，显示错误对话框
   - 如果 `license.required = false` 且授权无效 → **允许启动**，但记录警告日志

3. **授权过期处理**：
   - 授权过期后，客户端会拒绝启动（如果 `required = true`）
   - 用户需要联系管理员获取新的授权文件

### 手动创建授权文件

如果你想手动创建授权文件，可以使用 `create_license.py` 脚本：

```bash
# 授权 365 天
python scripts/create_license.py MyCompany 365

# 授权到指定日期
python scripts/create_license.py MyCompany 2026-12-31

# 授权到指定时间
python scripts/create_license.py MyCompany "2026-12-31T23:59:59"
```

生成的授权文件位于：`certs\license_<name>.json`

### 验证授权文件

使用 `verify_license.py` 脚本验证授权文件：

```bash
python scripts/verify_license.py
```

## 常见问题

### Q1: 构建时提示 "Configuration file not found"

**A**: 确保 `build_config.json` 文件存在。如果不存在，复制 `build_config.json.example` 为 `build_config.json`。

### Q2: 如何禁用授权功能？

**A**: 设置 `license.name` 为空字符串 `""` 或 `null`，或者不配置 `license` 部分。

### Q3: 授权到期后如何续期？

**A**: 重新构建客户端（修改 `license.days` 或 `license.expires`），或者联系管理员获取新的授权文件。

### Q4: 如何在不重新构建的情况下更新授权？

**A**: 将新的授权文件（`license.json`）放到以下任一位置：
- `%APPDATA%\DMS\license.json`
- 可执行文件所在目录的 `license.json`

### Q5: 代码签名失败

**A**: 检查以下事项：
1. 证书文件路径是否正确
2. 证书密码是否正确
3. 时间戳服务器是否可访问
4. 如果使用证书指纹，确保证书已安装到 Windows 证书存储

## 示例配置

### 示例 1: 测试版本（不强制授权）

```json
{
  "license": {
    "name": "TestClient",
    "days": 30,
    "expires": null,
    "required": false
  }
}
```

### 示例 2: 正式版本（强制授权，授权 1 年）

```json
{
  "license": {
    "name": "MyCompany",
    "days": 365,
    "expires": null,
    "required": true
  }
}
```

### 示例 3: 正式版本（强制授权，授权到指定日期）

```json
{
  "license": {
    "name": "MyCompany",
    "days": 365,
    "expires": "2026-12-31T23:59:59",
    "required": true
  }
}
```

### 示例 4: 启用代码签名

```json
{
  "license": {
    "name": "MyCompany",
    "days": 365,
    "expires": null,
    "required": true
  },
  "sign": {
    "enabled": true,
    "cert_pfx_path": "C:\\certs\\code_sign.pfx",
    "cert_pfx_password": "your-password",
    "timestamp_url": "http://timestamp.digicert.com"
  }
}
```

## 注意事项

1. **不要提交 `build_config.json` 到 Git**
   - 此文件包含敏感信息（如证书密码）
   - 已添加到 `.gitignore`

2. **`build_config.json.example` 可以提交到 Git**
   - 这是配置模板文件
   - 不包含敏感信息

3. **私钥安全**
   - `certs/license_private.pem` 是私钥文件，用于签名授权
   - 不要将此文件泄露给他人
   - 已添加到 `.gitignore`

4. **公钥可以公开**
   - `certs/license_public.pem` 是公钥文件，用于验证授权
   - 可以随客户端一起分发

## 相关文件

- `build_config.json` - 构建配置文件
- `build_config.json.example` - 配置模板文件
- `scripts/build_windows.ps1` - Windows 构建脚本
- `scripts/create_license.py` - 授权生成脚本
- `scripts/verify_license.py` - 授权验证脚本
- `utils/license.py` - 授权验证库
- `desktop_launcher.py` - 客户端启动器（包含授权检查逻辑）

## 技术支持

如有问题，请提交 Issue 或联系开发者。
