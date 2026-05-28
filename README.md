# DMS 设备管理系统

一个基于 Flask 的完整设备管理系统，支持 Web 部署和 Windows 桌面客户端。适用于企业、实验室、学校等场景的设备全生命周期管理。

## 📋 功能特性

### 核心功能
- **设备台账管理**：设备信息录入、编辑、查询、统计
- **设备状态管理**：在用、停用、维修、报废等状态跟踪
- **文档管理**：设备相关文档上传、下载、审批流程
- **借用管理**：设备借用申请、审批、归还管理
- **维护管理**：维护计划、维修记录、保养提醒
- **备件管理**：备件库存、出入库、低库存预警
- **审批流程**：文档审批、设备状态变更审批
- **用户权限**：基于角色的权限控制（管理类、技术类、普通用户）
- **电子签名**：支持电子签名功能
- **数据导出**：Excel 导出功能

### 高级特性
- 🔐 用户认证与权限管理
- 📊 仪表板和统计分析
- 🔍 全局搜索功能
- 📱 响应式设计
- 🖥️ Windows 桌面客户端支持
- 🔄 数据库自动迁移
- 📝 操作日志审计
- 🔑 许可证管理（企业版）

## 🛠️ 技术架构

### 后端
- **框架**: Flask 2.3+
- **数据库**: SQLite (默认) / MySQL (可选)
- **认证**: Flask-Login
- **ORM**: 原生 SQL (使用 sqlite3/PyMySQL)

### 前端
- **模板引擎**: Jinja2
- **CSS框架**: 自定义 CSS
- **JavaScript**: 原生 JS + Fetch API

### 桌面客户端
- **框架**: pywebview (将 Web 应用封装为桌面应用)
- **打包**: PyInstaller

## 📦 安装部署

### 方式一：Python 源码运行

#### 环境要求
- Python 3.10+
- pip

#### 安装步骤

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

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置环境变量**（可选）
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置数据库连接等参数
```

5. **初始化并运行**
```bash
# 首次运行（会自动创建数据库和配置文件）
python first_run.py

# 或直接启动
python launcher.py

# 或直接使用 Flask 开发服务器
python app.py
```

6. **访问应用**
打开浏览器访问 `http://localhost:5000`

### 方式二：Windows 桌面客户端

#### 快速使用（推荐）

1. **下载发布版本**
   - 从 [Releases](https://github.com/feng197907/EqpMgmt_Client/releases) 页面下载最新版本
   - 选择 `DMS_Client_Installer.exe`（安装版）或 `DMS_Client_Portable.zip`（便携版）

2. **安装或解压**
   - 安装版：运行安装程序，按提示完成安装
   - 便携版：解压 ZIP 文件，双击 `DMS_Client.exe` 运行

3. **启动应用**
   - 桌面客户端会自动打开独立窗口（基于 pywebview）
   - 后端仍然是本地 Flask 服务

#### 从源码构建 Windows 客户端

1. **安装依赖**
```powershell
pip install pyinstaller
```

2. **运行打包脚本**
```powershell
.\scripts\build_windows.ps1
```

3. **生成安装程序**（需要安装 NSIS）
```powershell
makensis installer\dms_installer.nsi
```

详细文档请参考 [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md)

## ⚙️ 配置说明

### 环境变量 (.env)

```bash
# Flask 密钥（用于 session 加密）
SECRET_KEY=your-secret-key-here

# 数据库类型 (sqlite 或 mysql)
DB_TYPE=sqlite

# SQLite 数据库路径（DB_TYPE=sqlite 时生效）
DB_PATH=%APPDATA%\DMS\equipment.db

# MySQL 配置（DB_TYPE=mysql 时生效）
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=dms

# 上传文件目录
UPLOAD_FOLDER=%APPDATA%\DMS\uploads

# 应用端口
PORT=5000
```

### 用户数据位置

Windows 客户端会在用户目录下创建配置和数据文件夹：
- 配置目录: `%APPDATA%\DMS`
- 数据库: `%APPDATA%\DMS\equipment.db` (SQLite)
- 上传文件: `%APPDATA%\DMS\uploads`
- 日志文件: `%APPDATA%\DMS\logs`

## 📁 项目结构

```
DMS/
├── app.py                  # Flask 应用工厂
├── config.py               # 配置管理
├── database.py             # 数据库初始化和迁移
├── launcher.py             # 启动脚本（生成配置 + 启动服务）
├── desktop_launcher.py     # Windows 桌面客户端启动器
├── first_run.py            # 首次运行初始化脚本
├── blueprints/             # Flask 蓝图（路由模块）
│   ├── auth.py             # 认证相关
│   ├── devices.py          # 设备管理
│   ├── documents.py        # 文档管理
│   ├── borrowing.py        # 借用管理
│   ├── approvals.py        # 审批流程
│   ├── maintenance.py      # 维护管理
│   ├── spare_part.py       # 备件管理
│   ├── users.py            # 用户管理
│   └── ...
├── models/                 # 数据模型
├── utils/                  # 工具函数
├── templates/              # Jinja2 模板
├── static/                 # 静态资源（CSS、JS）
├── scripts/                # 构建和发布脚本
├── installer/              # NSIS 安装脚本
└── requirements.txt        # Python 依赖
```

## 👥 用户角色与权限

系统内置以下角色分组：

### 管理类
- **系统管理员**：全部权限
- **设备管理员**：设备管理、用户管理、系统设置

### 技术类
- **技术员**：设备操作、维护记录、文档上传
- **审核员**：审批权限

### 普通用户
- **普通用户**：查看、借用申请、密码修改

权限细粒度控制，可在 `config.py` 中配置 `MENU_PERMISSIONS`。

## 🔧 开发指南

### 开发模式运行
```bash
# 启用调试模式
export FLASK_DEBUG=1  # Linux/Mac
set FLASK_DEBUG=1     # Windows

python app.py
```

### 数据库迁移
应用启动时会自动检测数据库版本并尝试迁移，无需手动操作。

### 添加新功能
1. 在 `blueprints/` 下创建新的蓝图文件
2. 在 `app.py` 中注册蓝图
3. 在 `templates/` 下创建对应的模板文件

## 📝 常见问题

### 1. 启动后无法访问
- 检查端口是否被占用（默认 5000）
- 检查防火墙设置
- 查看日志文件：`%APPDATA%\DMS\logs\error.log`

### 2. 数据库迁移失败
- 备份数据库文件
- 检查 `database.py` 中的迁移逻辑
- 查看错误日志获取详细信息

### 3. 文件上传失败
- 检查 `UPLOAD_FOLDER` 目录权限
- 检查文件大小限制（默认 50MB）

### 4. Windows 客户端无法启动
- 检查是否被杀毒软件拦截
- 以管理员身份运行
- 查看 Windows 事件查看器

更多问题请参考 [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md) 的故障排查部分。

## 🚀 生产部署

### 使用 Gunicorn (Linux)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

### 使用 systemd (Linux)

创建 `/etc/systemd/system/dms.service`:

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

### 使用 Nginx 反向代理

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

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📧 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue: [GitHub Issues](https://github.com/feng197907/EqpMgmt_Client/issues)
- 邮箱: [your-email@example.com]

## 🙏 致谢

感谢所有为本项目做出贡献的开发者！

---

**注意**: 本系统为开源项目，仅供学习和合法使用。请遵守相关法律法规，不得用于非法用途。
