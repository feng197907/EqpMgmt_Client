# DMS 设备档案管理系统

面向制药、医疗器械、实验室与科研院校等**对设备文档合规性有要求**的场景，覆盖设备台账、文档审批、维护校准、备件库存、电子签名与审计追溯的轻量级设备全生命周期管理系统。

一套代码，两种交付形态：**本机 Web 服务**或**Windows 桌面客户端**——数据全部留在本机，不上传任何第三方服务器。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-single--file-003B57?logo=sqlite&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-0078D6)

---

## 目录

- [交付形态](#交付形态)
- [功能模块](#功能模块)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [数据备份与版本升级](#数据备份与版本升级)
- [容量与性能实测](#容量与性能实测)
- [项目结构](#项目结构)
- [角色与权限](#角色与权限)
- [开发指南](#开发指南)
- [生产部署](#生产部署)
- [常见问题](#常见问题)
- [相关文档](#相关文档)

---

## 交付形态

| | Web 部署版 | Windows 桌面客户端 |
|---|---|---|
| 交互方式 | 浏览器访问 `http://<主机>:5000` | pywebview 独立窗口（内嵌 WebView2） |
| 适用场景 | 单机自用、局域网小团队共用 | 单机安装、交付给最终用户 |
| 数据库 | SQLite 单文件 | SQLite 单文件 |
| 数据位置 | 由 `DB_PATH` 指定，默认 `%APPDATA%\DMS` | `%APPDATA%\DMS` |
| 授权 | 无 | 内置许可证（试用 / 授权 / 免费） |
| 分发方式 | 源码 + Gunicorn | 单文件 EXE + NSIS 安装包 |

> **定位说明**：本仓库是**单机客户端版**。多用户、跨机协作的 Web 版走另一套架构（FastAPI + SQLAlchemy + Vue3），不在本仓库内实现。

---

## 功能模块

| 模块 | 说明 |
|------|------|
| 设备台账 | 录入 / 编辑 / 查询 / 状态跟踪（运行、待机、维护、维修、调试、停用、报废） |
| 文档管理 | 上传 / 下载 / 多步审批 / 版本历史 / 归档作废 |
| 借用管理 | 借用申请 → 审批 → 归还（可由系统设置整体开关） |
| 维护管理 | 维护计划、维修记录、保养/校准/巡检提醒与到期预警 |
| 备件库存 | 入库 / 消耗 / 低库存预警 / 成本统计 |
| 审批流程 | 文档审批 + 设备状态变更审批，支持多步骤审批链 |
| 电子签名 | 签名制作、签名验证、签名记录追溯（21 CFR Part 11 风格，连续 3 次密码错误锁定） |
| 审计日志 | 全操作留痕，支持按用户/类型/时间筛选并导出 Excel |
| 全局搜索 | 设备、文档、用户模糊检索 |
| 系统设置 | 角色菜单权限、功能开关、维护周期、文档类型等运行期配置 |

### 合规与安全

- **7 种角色 + 菜单级 / 功能级两层权限**
- **电子签名**：签名前校验登录密码，失败计数入库并限时锁定
- **审计留痕**：登录、审批、导出、删除、作废等关键动作全部记录操作人、IP、时间
- **密码管理**：自助改密、管理员主动重置、忘记密码申请与审批

---

## 技术架构

### 后端

| 项 | 说明 |
|----|------|
| 框架 | Flask 3.x（Flask-Login 会话认证） |
| 数据库 | SQLite 3，单文件、WAL 模式；**不再支持 MySQL** |
| 数据访问 | 原生 SQL，业务层统一写 `%s`，由兼容层自动转 `?` |
| 加密 | cryptography（许可证 RSA 签名验证） |
| 导出 | openpyxl 生成 xlsx |

### 前端

| 项 | 说明 |
|----|------|
| 模板 | Jinja2（`base.html` 统一布局 + 组件宏） |
| 样式 | Bootstrap 5 + 自定义 CSS 变量体系 |
| 图标 | Lucide Icons（本地 vendor，无 CDN 依赖） |
| 脚本 | 原生 JS，按页面拆分为 `static/js/pages/<page>.js` |

### 桌面客户端

| 项 | 说明 |
|----|------|
| 容器 | pywebview 5.x（Windows 上使用 Edge WebView2） |
| 打包 | PyInstaller → 单文件 EXE |
| 安装程序 | NSIS（含许可证配置引导） |
| 代码签名 | signtool（可选） |

### 关键设计（改代码前请先看这里）

多处重复实现已收敛为公共模块，新增功能请复用，不要另造一份：

| 能力 | 位置 | 约定 |
|------|------|------|
| Excel 导出 | `utils/excel_export.py` → `excel_response(wb, filename)` | 一处处理「浏览器下载」与「桌面壳落盘 + 唤起打开」两条分支 |
| 前端导出触发 | `static/js/main.js` → `DMS.doExport(btn, url)` | 桌面壳下带 `X-Desktop-Shell: 1`，后端返 JSON，前端调 `pywebview.api.open_file` |
| 列表分页 | `utils/pagination.py` + `templates/_pagination.html` | 默认 20 条/页，页码只渲染当前页 ±2 |
| 文件路径解析 | `utils/file_utils.py` → `get_upload_root()` / `resolve_doc_path()` | 上传、下载、审批、签名共用同一基准 |
| 审计留痕 | `utils/audit.py` → `log_action()` | 导出、审批、作废等动作都要调用 |
| 密码变更 | `utils/password_utils.py` | 唯一改密出口，改密后自动关闭该用户的待处理重置申请 |
| 业务索引 | `database.py` → `_BUSINESS_INDEXES` + `_ensure_indexes()` | 幂等创建，建表后自动补，失败只打日志不阻断启动 |

---

## 快速开始

### 环境要求

- Python **3.10+**（开发与验证环境为 3.12）
- pip
- Windows 桌面客户端另需 WebView2 运行时（Win10/11 通常已自带）

### 方式一：源码运行 Web 服务

```bash
git clone https://github.com/feng197907/EqpMgmt_Client.git
cd EqpMgmt_Client

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # Linux / macOS

pip install -r requirements.txt
python launcher.py                  # 首次运行自动生成配置和数据库，并打开浏览器
```

访问 `http://127.0.0.1:5000`，初始管理员账号 **`admin / admin123`**（首次登录后请立即修改）。

`launcher.py` 与 `app.py` 的区别：

| 入口 | 监听地址 | 调试 | 用途 |
|------|---------|------|------|
| `launcher.py` | `127.0.0.1:5000`（可由 `CLIENT_HOST` / `CLIENT_PORT` 覆盖） | 关闭 | 本机日常使用，启动后自动开浏览器 |
| `python app.py` | `0.0.0.0:$PORT`（默认 5000） | **开启** | 仅用于开发调试，**不要用于生产** |
| `desktop_launcher.py` | `127.0.0.1:5000` | 关闭 | 桌面客户端入口（需 pywebview） |

### 方式二：Windows 桌面客户端

**使用安装包（推荐）**

1. 从 [Releases](https://github.com/feng197907/EqpMgmt_Client/releases) 下载 `DMS_Client_Installer.exe`
2. 运行安装程序，按向导完成（许可证在安装时可一并配置）
3. 启动后打开独立窗口，不再依赖浏览器

**从源码构建**

一条命令走完全流程（EXE → 安装包 → 发布 zip，产物在 `releases\`）：

```powershell
.\scripts\rebuild_release.ps1
```

也可以按需分步执行：

```powershell
.\scripts\build_windows.ps1        # 1. PyInstaller 打包单文件 EXE → releases\DMS_Client.exe
.\scripts\build_installer.ps1      # 2. NSIS 安装程序（内部会自动触发步骤 1）→ releases\DMS_Client_Installer.exe
.\scripts\make_release.ps1         # 3. 打包成发布 zip
.\scripts\package_portable.ps1     # 4. 便携版（免安装 zip）
```

构建前需准备 `build_config.json`（参照 `build_config.json.example`）与 RSA 密钥对（`scripts/create_keypair.py`）。
打包与安装程序需要 PyInstaller、NSIS（`makensis`）已安装。

详细说明 → [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md) ｜ [BUILD_CONFIG_README.md](BUILD_CONFIG_README.md)

---

## 配置说明

配置来源有两处，优先级为 **环境变量 > `%APPDATA%\DMS\config.json` > 代码内默认值**。

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SECRET_KEY` | Flask session 加密密钥，**生产环境必须修改** | `dev-secret-key` |
| `DB_PATH` | SQLite 数据库文件路径 | `%APPDATA%\DMS\equipment.db` |
| `UPLOAD_FOLDER` | 上传文件目录 | 数据库同级的 `uploads/` |
| `PORT` | `app.py` 监听端口 | `5000` |
| `CLIENT_HOST` / `CLIENT_PORT` | `launcher.py` / 桌面壳监听地址与端口 | `127.0.0.1` / `5000` |

从源码运行时，可复制 `.env.example` 为 `.env` 后按需修改（`.env` 已在 `.gitignore` 中）。

### 数据位置

| 路径 | 内容 |
|------|------|
| `%APPDATA%\DMS\equipment.db` | SQLite 数据库（正式数据） |
| `%APPDATA%\DMS\equipment.db-wal`、`-shm` | WAL 日志与共享内存文件，**备份时必须一起处理** |
| `%APPDATA%\DMS\uploads\` | 上传的文档与附件 |
| `%APPDATA%\DMS\logs\` | 运行日志与错误日志 |
| `%APPDATA%\DMS\config.json` | 首次运行生成的配置 |

上传单文件大小上限 **50 MB**（`config.py` → `MAX_CONTENT_LENGTH`）。

---

## 数据备份与版本升级

### 备份

数据库启用了 WAL 模式，**直接复制 `equipment.db` 可能拿到不一致的快照**。两种正确做法：

```bash
# 做法 A（推荐）：先落盘再复制
sqlite3 "C:/Users/<user>/AppData/Roaming/DMS/equipment.db" "PRAGMA wal_checkpoint(TRUNCATE);"

# 做法 B：关闭程序后，整目录复制（含 -wal / -shm）
```

推荐直接用做法 B：停止客户端 → 复制整个 `%APPDATA%\DMS` 目录（含 `uploads\`）→ 归档。

### 升级

1. 停掉正在运行的程序
2. 备份上述目录
3. 替换程序文件（或安装新版本，安装包不会覆盖 `%APPDATA%\DMS` 下的数据）
4. 启动 → 自动补建表结构、自动补齐缺失索引，无需手工执行 SQL

> 从带 MySQL 支持的旧版本升级：`config.json` 里残留的 `"DB_TYPE": "mysql"` 会被忽略并在日志中告警，数据仍从 SQLite 读取。若发现「升级后数据是空的」，先确认程序读取的是哪个 `DB_PATH`。

---

## 容量与性能实测

本版本针对数据量做过实测与优化，结论：**单机场景下 SQLite 不是瓶颈，页面渲染才是**。

| 场景 | 数据量 | 优化前 | 优化后 |
|------|--------|--------|--------|
| 设备列表翻页 | 5,000 台 | 8.3 MB HTML | 45 KB / 39 ms |
| 文档检索 | 50,000 份 | 65 MB / 1.5 s | 40 KB / 27 ms |
| 审计日志首页 | 1,000,000 条 | 116.9 ms | 0.9 ms |
| 审计日志按操作人筛选 | 1,000,000 条 | 106 ms | 2.1 ms |
| 审计日志按类型 + 时间 | 1,000,000 条 | 122 ms | 2.6 ms |
| 并发读写（200 写 + 200 读） | — | 506 ms | 46 ms（WAL） |

按每天 200 次操作估算，100 万条审计日志需要约 **13 年**才能攒满。单机版建议数据量控制在此量级内；再往上应转向新的多用户架构。

---

## 项目结构

```
EqpMgmt_Client/
├── app.py                     # Flask 应用工厂（create_app）
├── config.py                  # 角色、权限、文档类型、维护周期等静态配置
├── database.py                # 建表 / 迁移 / 索引 / SQLite 兼容层
├── extensions.py              # Flask 扩展（LoginManager）
├── launcher.py                # Web 启动入口（生成配置 → 起服务 → 开浏览器）
├── desktop_launcher.py        # Windows 桌面客户端入口（pywebview 窗口）
├── first_run.py               # 首次运行初始化与非交互配置生成
├── build_config.json.example  # 构建配置样例（许可证、签名等）
├── requirements.txt
│
├── blueprints/                # 路由模块（16 个蓝图）
│   ├── auth.py                #   登录 / 登出 / 设备列表首页
│   ├── dashboard.py           #   数据看板 / 提醒中心 / 审计日志
│   ├── devices.py             #   设备台账
│   ├── documents.py           #   文档中心
│   ├── borrowing.py           #   借用管理
│   ├── approvals.py           #   审批流程
│   ├── device_changes.py      #   设备状态变更审批
│   ├── maintenance.py         #   维护计划与维修记录
│   ├── spare_part.py          #   备件库存
│   ├── users.py               #   用户管理
│   ├── password.py            #   密码重置与申请审批
│   ├── profile.py             #   个人设置
│   ├── settings.py            #   系统设置
│   ├── search.py              #   全局搜索
│   ├── esign.py               #   电子签名
│   └── log_bp.py              #   操作日志 / 错误日志查看
│
├── models/                    # 数据模型（非 ORM，封装原生 SQL）
│   ├── user.py                #   User（Flask-Login UserMixin）
│   ├── electronic_signature.py
│   ├── maintenance.py
│   └── spare_part.py
│
├── utils/                     # 公共工具
│   ├── audit.py               #   审计日志写入
│   ├── db_utils.py            #   数据库辅助
│   ├── decorators.py          #   权限装饰器（菜单级 / 功能级）
│   ├── excel_export.py        #   统一 Excel 导出出口
│   ├── file_utils.py          #   上传根目录与文档路径解析
│   ├── helpers.py             #   通用辅助
│   ├── license.py             #   许可证校验（RSA）
│   ├── logging_config.py      #   日志配置
│   ├── maintenance.py         #   维护/校准提醒计算
│   ├── pagination.py          #   列表分页
│   ├── password_utils.py      #   统一改密出口
│   └── request_logger.py      #   请求日志中间件
│
├── templates/                 # Jinja2 模板
│   ├── base.html              #   基础布局（侧边栏 + 顶栏）
│   ├── _pagination.html       #   分页组件宏
│   └── components/            #   可复用组件
│
├── static/
│   ├── css/                   # variables / base / layout / components / pages / login
│   ├── js/
│   │   ├── main.js            #   全局脚本（含 DMS.doExport）
│   │   └── pages/             #   按页面拆分（documents.js、audit-log.js…）
│   └── vendor/                #   Bootstrap、Lucide（本地化，无 CDN）
│
├── scripts/                   # 构建与许可工具（全流程入口：rebuild_release.ps1）
│   ├── build_windows.ps1      #   PyInstaller 打包
│   ├── build_installer.ps1    #   NSIS 安装程序
│   ├── package_portable.ps1   #   便携版打包
│   ├── make_release.ps1       #   发布打包
│   ├── rebuild_release.ps1    #   重新构建
│   ├── sign_release.ps1       #   代码签名
│   ├── create_keypair.py      #   生成 RSA 密钥对
│   ├── create_license.py      #   生成许可证文件
│   └── verify_license.py      #   校验许可证
│
├── installer/dms_installer.nsi  # NSIS 安装脚本
├── docs/使用手册.md              # 面向最终用户的操作手册
├── .env.example                 # 环境变量样例
├── README_WINDOWS_CLIENT.md     # 桌面客户端说明
└── BUILD_CONFIG_README.md       # 构建配置说明
```

> `.gitignore` 已排除 `certs/`、`build/`、`dist/`、`release/`、`*.spec`、`build_config.json`、`dms_license_config.json` 等本地/构建产物，克隆后不存在属于正常现象。

---

## 角色与权限

### 角色一览

| 分组 | 角色 | 核心权限 |
|------|------|---------|
| 管理类 | 管理员 `admin` | 全部权限，不受菜单权限限制 |
| 管理类 | QA经理 `qa_manager` | 质量审批、文档审批、报告查看 |
| 管理类 | 生产主管 `production_supervisor` | 生产审批、报告查看 |
| 技术类 | 设备工程师 `equipment_engineer` | 设备管理 / 校准 / 维护、备件库存 |
| 技术类 | 验证工程师 `validation_engineer` | IQ/OQ/PQ 管理、文档审批 |
| 技术类 | 计量工程师 `metrology_engineer` | 计量器具管理、校准记录 |
| 文档类 | 档案管理员 `archivist` | 文档上传、归档、文档管理 |

### 菜单权限

9 大菜单可在「系统设置 → 角色权限」中按角色分配，定义位于 `config.py` → `MENU_PERMISSIONS`：

`数据看板` · `设备管理` · `文档中心` · `用户管理` · `审计日志` · `电子签名` · `系统设置` · `提醒中心` · `备件库存管理`

管理员自动拥有全部菜单；其余角色默认拥有「数据看板、设备管理、文档中心、提醒中心」。

---

## 开发指南

### 新增一个功能模块

1. 在 `blueprints/` 下新建蓝图文件，按现有风格定义 `xxx_bp`
2. 在 `blueprints/__init__.py` 中 import 并加入 `__all__`
3. 在 `app.py` 的 `create_app()` 中 `register_blueprint`
4. 在 `templates/` 下创建页面模板（继承 `base.html`），脚本放 `static/js/pages/`
5. 需要新权限时，在 `config.py` → `ROLE_PERMISSIONS` 中登记，并在路由上挂 `utils/decorators.py` 的装饰器

### 代码约定（务必遵守）

- **导出**：一律走 `excel_response()`，前端一律调 `DMS.doExport()`，不要各自实现文件落盘
- **列表页**：必须分页，禁止全量查询 + 整表渲染（曾有 5 万文档渲染出 65 MB HTML 的事故）
- **文件路径**：一律经 `utils/file_utils.py` 解析，不要自己拼 `UPLOAD_FOLDER`
- **写操作**：审批、导出、作废、删除等动作调用 `log_action()` 留痕
- **静态资源改版**：更新 `templates/base.html` 里的 `?v=N` 以破缓存

### 数据库

- 建表与迁移在 `database.py` 中，**启动时自动执行**，无需手工跑 SQL
- 新增索引请加到 `_BUSINESS_INDEXES`，由 `_ensure_indexes()` 幂等创建
- 业务代码继续写 `%s` 占位符，兼容层负责转换；`NOW()`、`DATE_FORMAT()` 等函数也有归一化处理
- 迁移使用 `_migrate_sqlite_columns()` 做增量列补齐，改表结构时同步更新

---

## 生产部署

> 本项目定位为**单机客户端**，生产部署多用于「一台机器 + 局域网访问」。若需真正的多用户并发，请使用多用户架构版本。

### Gunicorn（Linux）

```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 "app:create_app()"
```

> 建议 **单 worker + 多线程**：SQLite 是单写者模型，多进程同时写入会触发 `database is locked`（虽有 `busy_timeout` 兜底，但会拖慢响应）。

### systemd

```ini
[Unit]
Description=DMS Equipment Management System
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/EqpMgmt_Client
Environment="PATH=/path/to/EqpMgmt_Client/.venv/bin"
Environment="SECRET_KEY=请替换为随机长字符串"
Environment="DB_PATH=/var/lib/dms/equipment.db"
Environment="UPLOAD_FOLDER=/var/lib/dms/uploads"
ExecStart=/path/to/EqpMgmt_Client/.venv/bin/gunicorn -w 1 --threads 4 -b 127.0.0.1:5000 "app:create_app()"
Restart=always

[Install]
WantedBy=multi-user.target
```

### Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50m;          # 与 MAX_CONTENT_LENGTH 保持一致

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/EqpMgmt_Client/static;
    }
}
```

---

## 常见问题

| 现象 | 排查方向 |
|------|---------|
| 启动后浏览器打不开 | 端口是否被占用（`netstat -ano \| findstr 5000`）、防火墙、`%APPDATA%\DMS\logs\` 里的启动错误 |
| 升级后数据是空的 | 检查实际生效的 `DB_PATH`；`config.json` 里若残留 `"DB_TYPE": "mysql"` 会被忽略并告警 |
| 文件上传失败 | `UPLOAD_FOLDER` 目录权限；单文件是否超过 50 MB |
| 导出按钮无反应 | 桌面壳需带 `X-Desktop-Shell: 1`，导出文件落在 `%TEMP%\DMS_Exports`；浏览器模式直接下载 |
| 电子签名提示锁定 | 连续 3 次密码错误后限时锁定，等待解锁或由管理员处理 |
| 备份后恢复数据不全 | 复制时漏了 `equipment.db-wal` / `-shm`，或在程序运行时直接复制了主库文件 |
| 桌面客户端无法启动 | 杀毒软件拦截 → 以管理员身份运行 → 检查事件查看器；确认 WebView2 已安装 |
| 页面样式错乱 | 静态资源缓存未失效，强制刷新或升 `?v=N` |
| 忘记管理员密码 | 停程序后用临时脚本调用 `utils/password_utils.py` 的哈希方法更新 `users` 表；不要直接改明文 |

更多排查 → [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md)

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [README_WINDOWS_CLIENT.md](README_WINDOWS_CLIENT.md) | 桌面客户端安装、许可、排障 |
| [BUILD_CONFIG_README.md](BUILD_CONFIG_README.md) | 构建配置（许可证、签名、版本信息）字段说明 |
| [docs/使用手册.md](docs/使用手册.md) | 面向最终用户的功能操作手册 |

---

## 许可证

本项目采用 MIT 许可证，详见根目录 `LICENSE` 文件。

## 反馈

- 提交 Issue：[GitHub Issues](https://github.com/feng197907/EqpMgmt_Client/issues)
