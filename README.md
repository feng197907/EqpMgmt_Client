# DMS 设备管理系统

基于 Flask 的设备全生命周期管理系统，支持 Web 部署与 Windows 桌面客户端。适用于制药、实验室、学校等对设备文档合规性有要求的场景。

## 功能特性

### 核心模块

| 模块 | 说明 |
|------|------|
| 设备台账 | 设备录入 / 编辑 / 查询 / 状态跟踪（运行、维护、停用、报废、调试、待机、维修） |
| 文档管理 | 文档上传 / 下载 / 审批流程 / 版本历史 / 归档作废 |
| 借用管理 | 借用申请 → 审批 → 归还（可通过系统设置开关） |
| 维护管理 | 维护计划 / 维修记录 / 保养提醒（校准、保养、巡检） |
| 备件库存 | 备件入库 / 消耗 / 低库存预警 / 成本统计 |
| 审批流程 | 文档审批 + 设备状态变更审批，支持多步骤 |
| 电子签名 | 签名制作 / 验证 / 签名记录追溯 |
| 全局搜索 | 模糊搜索设备、文档、用户 |

### 权限与安全

- **7 种角色**：管理员、QA经理、设备工程师、验证工程师、档案管理员、生产主管、计量工程师
- **菜单级权限**：9 大菜单可按角色分配，管理员自动拥有全部
- **功能级权限**：每个角色细粒度控制（文档审批、设备校准、备件管理等 16+ 权限项）
- **审计日志**：全操作可追溯
- **密码管理**：修改密码 / 管理员重置 / 忘记密码自助申请
- **个人设置**：查看个人信息、修改密码

### 桌面客户端

- 基于 **pywebview** 将 Web 应用封装为 Windows 原生窗口
- **PyInstaller** 打包单文件 EXE + **NSIS** 制作安装程序
- 内置 **许可证系统**（试用期 / 授权期 / 免费模式），RSA 签名验证
- 详见 [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md) 和 [BUILD_CONFIG_README.md](BUILD_CONFIG_README.md)

## 技术架构

### 后端

| 项 | 说明 |
|----|------|
| 框架 | Flask 2.3+ |
| 数据库 | SQLite（默认）/ MySQL（可选，自动降级） |
| 认证 | Flask-Login |
| 数据访问 | 原生 SQL（sqlite3 / PyMySQL），自动兼容双库 |
| 加密 | cryptography（许可证 RSA 签名验证） |

### 前端

| 项 | 说明 |
|----|------|
| 模板 | Jinja2 |
| CSS | 自定义变量体系 + Bootstrap 5 |
| 图标 | Lucide Icons |
| JS | 原生 JS + Fetch API |

### 桌面客户端

| 项 | 说明 |
|----|------|
| 框架 | pywebview 5.0+ |
| 打包 | PyInstaller → 单 EXE |
| 安装程序 | NSIS（含许可证配置引导） |
| 代码签名 | signtool（可选） |

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/feng197907/EqpMgmt_Client.git
cd EqpMgmt_Client
```

2. **创建虚拟环境**（推荐）

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**（可选）

```bash
cp .env.example .env
# 编辑 .env，按需修改数据库连接、密钥等
```

5. **初始化并运行**

```bash
# 首次运行（自动创建数据库和配置文件）
python first_run.py

# 或直接启动
python launcher.py

# 或 Flask 开发服务器
python app.py
```

6. **访问应用**

浏览器打开 `http://localhost:5000`，默认管理员账号 `admin / admin123`。

### Windows 桌面客户端

**使用安装包**（推荐）

1. 从 [Releases](https://github.com/feng197907/EqpMgmt_Client/releases) 下载 `DMS_Client_Installer.exe`
2. 运行安装程序，按向导完成
3. 启动后自动打开独立窗口

**从源码构建**

```powershell
# 1. 构建 EXE
.\scripts\build_windows.ps1

# 2. 生成安装程序（需要 NSIS）
.\scripts\build_installer.ps1    # 此脚本会自动触发步骤 1

# 3. 便携版打包
.\scripts\package_portable.ps1
```

详细文档 → [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md) | [BUILD_CONFIG_README.md](BUILD_CONFIG_README.md)

## 配置说明

### 环境变量（.env）

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Flask session 加密密钥 | `dev-secret-key` |
| `DB_TYPE` | 数据库类型 `sqlite` / `mysql` | 自动检测（优先 MySQL） |
| `DB_PATH` | SQLite 数据库路径（`DB_TYPE=sqlite`） | `%APPDATA%\DMS\equipment.db` |
| `MYSQL_HOST` | MySQL 主机 | `localhost` |
| `MYSQL_PORT` | MySQL 端口 | `3306` |
| `MYSQL_USER` | MySQL 用户 | `root` |
| `MYSQL_PASSWORD` | MySQL 密码 | 空 |
| `MYSQL_DATABASE` | MySQL 库名 | `dms_db` |
| `UPLOAD_FOLDER` | 上传文件目录 | `%APPDATA%\DMS\uploads` |
| `PORT` | 应用端口 | `5000` |

### 用户数据位置

Windows 客户端将数据存放于用户目录：

| 路径 | 内容 |
|------|------|
| `%APPDATA%\DMS\equipment.db` | SQLite 数据库 |
| `%APPDATA%\DMS\uploads\` | 上传文件 |
| `%APPDATA%\DMS\logs\` | 运行日志 |

## 项目结构

```
EquipmentManagement_client/
├── app.py                    # Flask 应用工厂
├── config.py                 # 配置管理（角色、权限、文档类型、维护周期等）
├── database.py               # 数据库初始化 / 迁移 / 双库适配
├── extensions.py             # Flask 扩展（Login Manager）
├── launcher.py               # Web 启动脚本（生成配置 + 启动服务）
├── desktop_launcher.py       # Windows 桌面客户端入口
├── first_run.py              # 首次运行初始化
├── build_config.json         # 构建配置（许可证、签名等）
│
├── blueprints/               # Flask 蓝图（路由模块）
│   ├── __init__.py           #   蓝图注册与导出
│   ├── auth.py               #   登录 / 登出 / 首页
│   ├── dashboard.py          #   数据看板 / 提醒
│   ├── devices.py            #   设备管理
│   ├── documents.py          #   文档管理
│   ├── borrowing.py          #   借用管理
│   ├── approvals.py          #   审批流程
│   ├── device_changes.py     #   设备状态变更
│   ├── maintenance.py        #   维护管理
│   ├── spare_part.py         #   备件库存
│   ├── users.py              #   用户管理
│   ├── password.py           #   密码重置
│   ├── profile.py            #   个人设置
│   ├── settings.py           #   系统设置
│   ├── search.py             #   全局搜索
│   └── esign.py              #   电子签名
│
├── models/                   # 数据模型
│   ├── user.py               #   User 类（Flask-Login）
│   ├── electronic_signature.py
│   ├── maintenance.py
│   └── spare_part.py
│
├── utils/                    # 工具函数
│   ├── audit.py              #   审计日志记录
│   ├── db_utils.py           #   数据库辅助
│   ├── decorators.py         #   权限装饰器
│   ├── file_utils.py         #   文件操作
│   ├── helpers.py            #   通用辅助
│   ├── license.py            #   许可证验证
│   ├── logging_config.py     #   日志配置
│   ├── maintenance.py        #   维护提醒计算
│   └── request_logger.py     #   请求日志中间件
│
├── templates/                # Jinja2 模板
│   ├── base.html             #   基础布局（侧边栏 + 顶栏）
│   ├── components/           #   可复用模板组件
│   ├── login.html            #   登录页
│   ├── profile.html          #   个人设置页
│   ├── admin_settings.html   #   系统设置页
│   └── ...                   #   各功能页模板
│
├── static/                   # 静态资源
│   ├── css/
│   │   ├── variables.css     #   CSS 变量（主题色、间距）
│   │   ├── base.css          #   基础样式
│   │   ├── layout.css        #   布局
│   │   ├── components.css    #   组件样式
│   │   ├── pages.css         #   页面样式
│   │   └── login.css         #   登录页样式
│   ├── js/
│   │   └── main.js           #   全局交互脚本
│   └── vendor/               #   第三方库（Bootstrap、Lucide）
│
├── scripts/                  # 构建与发布脚本
│   ├── build_windows.ps1     #   PyInstaller 打包
│   ├── build_installer.ps1   #   NSIS 安装程序（含自动构建 EXE）
│   ├── create_keypair.py     #   生成 RSA 密钥对
│   ├── create_license.py     #   生成许可证文件
│   ├── verify_license.py     #   验证许可证
│   ├── make_release.ps1      #   发布打包
│   ├── package_portable.ps1  #   便携版打包
│   ├── rebuild_release.ps1   #   重新构建
│   └── sign_release.ps1      #   代码签名
│
├── installer/                # NSIS 安装脚本
│   └── dms_installer.nsi
│
├── certs/                    # 证书目录（RSA 公钥等）
├── docs/                     # 文档
├── migrations/               # 数据库迁移脚本
├── requirements.txt          # Python 依赖
└── DMS_Client.spec           # PyInstaller 规格文件
```

## 角色与权限

### 角色一览

| 分组 | 角色 | 核心权限 |
|------|------|---------|
| 管理类 | 管理员 (admin) | 全部权限 |
| 管理类 | QA经理 (qa_manager) | 质量审批、文档审批、报告查看 |
| 管理类 | 生产主管 (production_supervisor) | 生产审批、报告查看 |
| 技术类 | 设备工程师 (equipment_engineer) | 设备管理/校准/维护、备件库存 |
| 技术类 | 验证工程师 (validation_engineer) | IQ/OQ/PQ 管理、文档审批 |
| 技术类 | 计量工程师 (metrology_engineer) | 计量器具管理、校准记录 |
| 文档类 | 档案管理员 (archivist) | 文档上传、归档、管理 |

### 菜单权限

9 大菜单模块可在 `config.py` → `MENU_PERMISSIONS` 中按需分配：

`数据看板` · `设备管理` · `文档中心` · `用户管理` · `审计日志` · `电子签名` · `系统设置` · `提醒中心` · `备件库存管理`

管理员自动拥有全部菜单权限；普通用户默认拥有"数据看板、设备管理、文档中心、提醒中心"。

## 开发指南

### 开发模式

```bash
# 启用调试
export FLASK_DEBUG=1   # Linux / macOS
set FLASK_DEBUG=1      # Windows

python app.py
```

### 数据库迁移

应用启动时自动检测版本并迁移，无需手动操作。迁移逻辑位于 `database.py`。

### 添加新功能

1. 在 `blueprints/` 下创建蓝图文件
2. 在 `blueprints/__init__.py` 中导入并添加到 `__all__`
3. 在 `app.py` 中 `from blueprints import` 并 `register_blueprint`
4. 在 `templates/` 下创建对应模板
5. 如需新权限，在 `config.py` → `ROLE_PERMISSIONS` 中添加

## 生产部署

### Gunicorn（Linux）

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### systemd

```ini
[Unit]
Description=DMS Equipment Management System
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/DMS
Environment="PATH=/path/to/DMS/.venv/bin"
ExecStart=/path/to/DMS/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/DMS/static;
    }
}
```

## 常见问题

| 问题 | 排查方向 |
|------|---------|
| 启动后无法访问 | 端口 5000 是否被占、防火墙设置、查看 `%APPDATA%\DMS\logs\` |
| 数据库迁移失败 | 备份数据库 → 检查 `database.py` 迁移逻辑 → 查看错误日志 |
| 文件上传失败 | `UPLOAD_FOLDER` 目录权限、文件大小限制（50MB） |
| Windows 客户端无法启动 | 杀毒软件拦截 → 以管理员运行 → 事件查看器 |
| MySQL 连接失败 | 检查 `.env` 中 MySQL 配置 → 系统自动降级为 SQLite |

更多排查 → [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md)

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 联系方式

- 提交 Issue: [GitHub Issues](https://github.com/feng197907/EqpMgmt_Client/issues)
