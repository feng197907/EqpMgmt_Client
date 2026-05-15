#!/bin/bash
# =============================================================================
# EquipmentManagement 一键安装脚本
# 用于新服务器全新安装
# 用法：curl -sL https://raw.githubusercontent.com/YOUR_USER/repo/main/migrate/install.sh | bash
# =============================================================================

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 配置（可修改）
APP_DIR="/data/EquipmentManagement"
GIT_REPO="https://github.com/feng197907/EquipmentManagement"
GIT_BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 读取迁移环境配置（包含 MySQL 参数）
if [ -f "$SCRIPT_DIR/env.conf" ]; then
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/env.conf"
fi

echo "=============================================="
echo "  EquipmentManagement 一键安装脚本"
echo "=============================================="

# 1. 检查 root 权限
log "检查权限..."
[ "$EUID" -ne 0 ] && error "请使用 root 权限运行"

# 2. 安装依赖
log "安装系统依赖..."
apt-get update -qq
apt-get install -y python3 python3-pip git > /dev/null 2>&1

# 3. 安装 Python 依赖
log "安装 Python 依赖..."
echo "依赖将在拉取代码后从 requirements.txt 安装"

# 4. 拉取代码
log "拉取代码..."
mkdir -p /data
cd /data
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR && git pull origin $GIT_BRANCH
else
    git clone -b $GIT_BRANCH $GIT_REPO $APP_DIR
fi

# 安装项目依赖（包含 MySQL 驱动）
pip3 install -r "$APP_DIR/requirements.txt" --quiet

# 4.1 写入部署环境变量（包含 MySQL 配置）
log "写入 .env 配置..."
cat > "$APP_DIR/.env" <<EOF
DB_TYPE=${DB_TYPE:-mysql}
MYSQL_HOST=${MYSQL_HOST:-127.0.0.1}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_DATABASE=${MYSQL_DATABASE:-dms_db}
MYSQL_USER=${MYSQL_USER:-dms_user}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-your_password}
EOF

# 5. 配置 systemd 服务
log "配置系统服务..."
cat > /etc/systemd/system/dms.service << 'EOF'
[Unit]
Description=DMS Equipment Management System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/data/EquipmentManagement
ExecStart=/usr/local/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. 启动服务
log "启动服务..."
systemctl daemon-reload
systemctl enable dms
systemctl restart dms

# 7. 验证
sleep 2
if systemctl is-active dms > /dev/null 2>&1; then
    echo ""
    echo "=============================================="
    echo -e "${GREEN}✅ 安装成功！${NC}"
    echo "=============================================="
    echo "访问地址: http://$(hostname -I | awk '{print $1}'):5000"
else
    error "服务启动失败，请检查日志: journalctl -u dms -f"
fi
