# EquipmentManagement 服务器迁移指南

## 迁移方案对比

| 方案 | 复杂度 | 速度 | 适用场景 |
|------|--------|------|----------|
| **一键脚本迁移** | ⭐ | 快 | 同架构 Linux 服务器 |
| 手动迁移 | ⭐⭐⭐ | 慢 | 不同环境、需要定制 |

---

## 推荐方案：一键脚本迁移（5分钟完成）

### 迁移前准备

1. **新服务器要求**
   - Ubuntu 20.04+ / Debian 11+
   - Root 权限
   - 已安装 Git

2. **获取迁移脚本**
   ```
   # 方式1: 从 GitHub 下载
   wget https://raw.githubusercontent.com/YOUR_USER/EquipmentManagement/main/migrate/quick_migrate.sh
   
   # 方式2: 直接复制脚本内容
   ```

### 迁移步骤

#### 步骤 1: 修改 Git 仓库地址

编辑 `quick_migrate.sh`，修改第 15 行：
```bash
GIT_REPO="https://github.com/YOUR_USERNAME/EquipmentManagement.git"
```
替换为你的实际 GitHub 仓库地址。

#### 步骤 2: 上传到新服务器

```bash
scp quick_migrate.sh root@YOUR_NEW_SERVER:/tmp/
```

#### 步骤 3: 执行迁移

```bash
ssh root@YOUR_NEW_SERVER
chmod +x /tmp/quick_migrate.sh
/tmp/quick_migrate.sh
```

#### 步骤 4: 验证

```
访问 http://新服务器IP:5000
```

---

## 迁移后检查清单

- [ ] 服务正常运行
- [ ] 数据库连接正常（如果有）
- [ ] GitHub Webhook URL 已更新为新服务器 IP
- [ ] 防火墙已开放 5000, 5001 端口
- [ ] 域名解析已更新（如果有）
- [ ] 原服务器可安全关机

## MySQL 配置说明

如果你在迁移后使用 MySQL，请先修改 [env.conf](env.conf) 中的数据库参数，再执行迁移脚本。脚本会把这些值写入新服务器项目根目录的 `.env` 文件。

需要关注的字段：

- `DB_TYPE="mysql"`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

如果暂时还想继续使用 SQLite，把 `DB_TYPE` 改成 `sqlite` 即可。

---

## 数据迁移（如有数据库）

### 导出旧服务器数据
```bash
mysqldump -u root -p equipment_db > equipment_db.sql
```

### 导入新服务器
```bash
scp equipment_db.sql root@新服务器:/tmp/
ssh root@新服务器
mysql -u root -p equipment_db < /tmp/equipment_db.sql
```

---

## 文件清单

```
migrate/
├── env.conf          # 环境配置文件
├── install.sh        # 全新安装脚本
├── migrate.sh        # 跨服务器迁移脚本
└── quick_migrate.sh  # 一键迁移脚本（推荐）
```
