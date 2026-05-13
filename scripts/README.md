# 自动化部署指南

本文档介绍如何配置 GitHub Webhook 实现代码自动部署。

## 目录

- [方案一：Webhook 自动部署](#方案一webhook-自动部署)
- [方案二：systemd 服务管理（推荐）](#方案二systemd-服务管理推荐)

---

## 方案一：Webhook 自动部署

当代码 push 到 GitHub main 分支后，服务器自动拉取最新代码并重启服务。

### 1. 配置 webhook_server.py

编辑 `scripts/webhook_server.py`，修改以下配置：

```python
# 服务器项目路径
GIT_DIR = "/data/EquipmentManagement"

# 设置一个安全的密钥（随便写，之后 GitHub 要填同样的）
WEBHOOK_SECRET = "your-secret-key-here"

# 部署命令
DEPLOY_COMMAND = "cd /data/EquipmentManagement && git pull origin main"

# 重启命令
RESTART_COMMAND = "systemctl restart dms"
```

### 2. 上传到服务器

```bash
# 本地执行，上传到服务器
scp -r scripts/ root@你的服务器IP:/data/EquipmentManagement/
```

### 3. 服务器安装依赖并启动

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 安装依赖
pip3 install flask

# 启动 webhook 服务（监听 5001 端口）
cd /data/EquipmentManagement
nohup python3 scripts/webhook_server.py > webhook.log 2>&1 &

# 验证服务启动
curl http://localhost:5001/health
# 返回 {"status": "ok"} 表示成功
```

### 4. 开放端口

在腾讯云控制台 → 安全组 → 添加入站规则：

| 协议 | 端口 | 来源 |
|------|------|------|
| TCP | 5001 | 0.0.0.0/0 |

### 5. GitHub 配置 Webhook

1. 打开 GitHub 仓库 → **Settings** → **Webhooks** → **Add webhook**

2. 填写配置：

| 字段 | 值 |
|------|-----|
| Payload URL | `http://你的服务器IP:5001/webhook` |
| Content type | `application/json` |
| Secret | `your-secret-key-here`（与 webhook_server.py 一致） |
| Events | ✅ Just the `push` events |

3. 点击 **Add webhook**

### 6. 测试部署

```bash
# 本地修改代码后 push
git add .
git commit -m "测试自动部署"
git push origin main

# 服务器会自动执行：
# 1. git pull 拉取最新代码
# 2. systemctl restart dms 重启服务
```

### 7. 查看日志

```bash
# 服务器上查看 webhook 日志
tail -f /data/EquipmentManagement/webhook.log

# 查看部署日志
cat /var/log/webhook-deploy.log
```

---

## 方案二：systemd 服务管理（推荐）

使用 systemd 管理 Flask 应用，更简单可靠。

### 1. 创建服务文件

在服务器上执行：

```bash
cat > /etc/systemd/system/dms.service << 'EOF'
[Unit]
Description=DMS Equipment Management System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/data/EquipmentManagement
ExecStart=/usr/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
```

### 2. 启用并启动服务

```bash
systemctl daemon-reload
systemctl enable dms
systemctl start dms
```

### 3. 服务管理命令   

```bash
# 启动服务
systemctl start dms

# 停止服务
systemctl stop dms

# 重启服务
systemctl restart dms

# 查看状态
systemctl status dms

# 查看日志
journalctl -u dms -f
```

### 4. 部署更新

每次 push 后，手动在服务器执行：

```bash
cd /data/EquipmentManagement
git pull origin main
systemctl restart dms
```

---

## 方案三：systemd + Webhook（最完整）

结合 systemd 服务管理和 Webhook 自动化：

### 1. 修改 webhook_server.py

```python
GIT_DIR = "/data/EquipmentManagement"
WEBHOOK_SECRET = "your-secret-key"
RESTART_COMMAND = "systemctl restart dms"
```

### 2. 配置服务

按方案二的步骤配置 systemd 服务。

### 3. 启动 webhook 服务

```bash
nohup python3 /data/EquipmentManagement/scripts/webhook_server.py > webhook.log 2>&1 &
```

### 4. 验证

```bash
# 测试 webhook
curl -X POST http://localhost:5001/webhook

# 查看服务状态
systemctl status dms
```

---

## 常见问题

### Q1: webhook 服务启动失败

检查依赖是否安装：
```bash
pip3 install flask
```

检查端口是否被占用：
```bash
netstat -tlnp | grep 5001
```

### Q2: git pull 失败

检查服务器上的 git 配置：
```bash
cd /data/EquipmentManagement
git remote -v
git config --list
```

如果需要认证，建议使用 SSH 方式：
```bash
git remote set-url origin git@github.com:用户名/仓库名.git
```

### Q3: 服务重启后无法访问

检查端口是否开放：
```bash
# 腾讯云安全组添加 5000 端口
netstat -tlnp | grep 5000
```

检查防火墙：
```bash
systemctl status firewalld
firewall-cmd --list-ports
```

### Q4: 如何回滚到旧版本

```bash
cd /data/EquipmentManagement
git log --oneline     # 查看提交历史
git reset --hard <commit-id>   # 回滚到指定版本
systemctl restart dms
```

---

## 安全建议

1. **设置 WEBHOOK_SECRET**：防止他人恶意触发部署
2. **限制 IP 访问**：在云服务器安全组中限制 5001 端口来源 IP
3. **定期更新依赖**：`pip3 install --upgrade flask gunicorn`
4. **查看审计日志**：定期检查 webhook.log 和 git 操作日志
