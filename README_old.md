 # 设备档案与文档管理系统（DMS）

 一款基于 Flask 的轻量级设备档案与文档管理系统，默认使用 SQLite，适合中小型设备管理和文档归档场景。

 ## 精简说明

 - 快速搭建：开箱即用，首次运行会自动初始化数据库并创建默认管理员。
 - 核心功能：设备台账、文档版本与下载、借阅管理、审批流、审计日志与菜单权限。

 ## 主要特性

 - 设备管理：新增/编辑/停用/报废、状态与位置管理
 - 文档中心：上传、版本控制、下载统计
 - 借阅流程：借出/归还记录与审批
 - 审批与电子签名：支持多步骤审批与签名记录
 - 权限系统：7 类角色与菜单级权限控制
 - 审计日志：关键操作审计，便于追踪变更

 ## 环境要求

 - Python 3.10+
 - 建议在虚拟环境中运行（推荐使用项目自带 .venv）

 ## 快速开始

 1. 安装依赖（在项目根目录）：

 ```bash
 .venv\Scripts\python.exe -m pip install -r requirements.txt
 ```

 2. 启动服务：

 ```bash
 .venv\Scripts\python.exe app.py
 ```

 3. 打开浏览器访问：

 ```text
 http://127.0.0.1:5000
 ```

 ## 默认账号

 - admin / admin123 （管理员）
 - user / user123 （设备工程师）

 请首次登录后立即修改默认密码。

 ## 快速验证建议

 - 使用 `admin` 新建一个设备并进入详情页
 - 上传文档，检查版本号是否自增
 - 下载文档，查看下载次数统计
 - 创建并审批借阅记录，验证归还流程

 ## 项目结构（摘录）

 ```
 app.py
 config.py
 database.py
 blueprints/      # 路由模块
 models/          # 数据模型
 templates/       # Jinja2 模板
 static/          # 前端资源
 tests/           # 单元测试
 uploads/         # 上传文件
 ```

 ## 测试

 使用 `pytest` 运行自动化测试（测试会使用临时数据库）：

 ```bash
 .venv\Scripts\python.exe -m pytest
 ```

 ## 部署（简要）

 - 推荐在 Linux 服务器上使用 `gunicorn` + `systemd` 部署。
 - 例：

 ```bash
 pip3 install gunicorn
 nohup gunicorn --bind 0.0.0.0:5000 --workers 2 app:app &
```
 ## 手动重新部署

```bash
cd /data/EquipmentManagement
chmod +x server_deploy.sh
./server_deploy.sh
 ```

 ## 自动化部署（GitHub Webhook）

本项目支持 GitHub Webhook 自动化部署，当代码推送到 GitHub 仓库时，服务器会自动拉取最新代码并重启服务。

### 服务器端配置

Webhook 服务已配置在腾讯云服务器上：

- **Webhook 地址**：`http://82.157.4.72:5001/webhook`
- **服务端口**：5001
- **日志文件**：`/var/log/webhook-deploy.log`
- **Webhook Secret**：`6C1BFF08-CF1F-2813-907A-44B39B4D7FE5`

### 查看部署日志

```bash
# 实时查看部署日志
tail -f /var/log/webhook-deploy.log

# 查看最近10条日志
tail -10 /var/log/webhook-deploy.log
```

### 部署日志示例

当有代码推送时，日志会显示：

```
========================================
=== Starting deployment at 2026-05-15 10:32:08 ===
========================================
[BEFORE] Branch: main, Commit: dbd318a6
[BEFORE] Last commit: 重写README.md文件 (2026-05-15 10:26:25 +0800) by wangtiefeng
[REMOTE] origin  git@github.com:feng197907/EquipmentManagement.git
[GIT] Executing: git pull origin main...
[GIT] Fetch origin: OK
[GIT] Pull output:
  | Already up-to-date.
[CHANGE] No code changes (already up-to-date)
[SERVICE] Gunicorn reloaded successfully
========================================
=== Deployment completed at 2026-05-15 10:32:14 ===
========================================
```

### 管理 Webhook 服务

```bash
# SSH 登录服务器
ssh root@82.157.4.72

# 查看 webhook 服务状态
ps aux | grep webhook_server

# 重启 webhook 服务
cd /data/EquipmentManagement
pkill -f webhook_server
nohup python3 scripts/webhook_server.py > /tmp/webhook.log 2>&1 &

# 测试 webhook 服务
curl http://82.157.4.72:5001/health
```

### GitHub Webhook 配置步骤

1. 进入 GitHub 仓库 → Settings → Webhooks → Add webhook
2. 配置以下选项：
   - **Payload URL**：`http://82.157.4.72:5001/webhook`
   - **Content type**：`application/json`
   - **Secret**：`6C1BFF08-CF1F-2813-907A-44B39B4D7FE5`
   - **SSL verification**：`Disable`（因为使用 HTTP）
   - **Events**：选择 `Just the push event`
3. 点击 `Add webhook`

### 手动测试 Webhook

```bash
# 在服务器上手动触发一次部署
curl -X POST http://82.157.4.72:5001/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -d '{"ref":"refs/heads/main","repository":{"name":"EquipmentManagement"}}'
```

## 切换到 MySQL （可选）

 1. 安装客户端：

 ```bash
 pip install PyMySQL cryptography
 ```

 2. 创建数据库并修改 `database.py` 中的连接配置为 MySQL。

 ## 说明与注意事项

 - 上传文件保存在 `uploads/` 目录
 - 默认数据库文件：`dms.db`（SQLite）
 - 首次启动会自动建表，若遇旧库字段缺失，尝试重启应用触发迁移逻辑

 ## 常见问题

 - 登录后看不到内容：检查账号是否被停用或权限是否分配
 - 上传失败：请确认文件类型在允许范围（pdf/doc/docx/xls/xlsx/jpg/png）

 ## 参考文档

 - 使用手册： [使用手册](docs/使用手册.md)

 ## 需要我做什么？

 如果你希望我：

 - 进一步压缩成英文版 README；
 - 添加 CI / badges；
 - 或者基于此生成项目首页文档；

 请告诉我你的优先项，我会继续修改。
| reminder_center | 提醒中心 |       

