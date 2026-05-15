#!/bin/bash
# =============================================================================
# EquipmentManagement 一键迁移脚本（目标服务器执行）
# 
# 使用方法（二选一）:
# 
# 方法1: 直接下载执行
# curl -sL https://raw.githubusercontent.com/YOUR_USER/repo/main/migrate/quick_migrate.sh | bash
#
# 方法2: 下载后执行
# wget -O quick_migrate.sh https://raw.githubusercontent.com/YOUR_USER/repo/main/migrate/quick_migrate.sh
# chmod +x quick_migrate.sh && ./quick_migrate.sh
#
# =============================================================================

set -e

# 配置
APP_DIR="/data/EquipmentManagement"
GIT_REPO="https://github.com/feng197907/EquipmentManagement"
GIT_BRANCH="main"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 读取迁移环境配置（包含 MySQL 参数）
if [ -f "$SCRIPT_DIR/env.conf" ]; then
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/env.conf"
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==============================================${NC}"
echo -e "${BLUE}    EquipmentManagement 一键迁移脚本${NC}"
echo -e "${BLUE}==============================================${NC}"
echo ""

# 检查 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}请使用 root 权限运行: sudo ./quick_migrate.sh${NC}"
    exit 1
fi

# 1. 安装依赖
echo -e "${GREEN}[1/5] 安装依赖...${NC}"
apt-get update -qq
apt-get install -y python3 python3-pip git > /dev/null 2>&1
echo "✅ 依赖安装完成"

# 2. 拉取代码
echo -e "${GREEN}[2/5] 拉取代码...${NC}"
mkdir -p /data
cd /data
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR
    git pull origin $GIT_BRANCH
else
    git clone -b $GIT_BRANCH $GIT_REPO $APP_DIR
fi
echo "✅ 代码拉取完成"

# 2.0 安装项目依赖（包含 MySQL 驱动）
echo -e "${GREEN}[2.0/5] 安装项目依赖...${NC}"
pip3 install -r "$APP_DIR/requirements.txt" --quiet
echo "✅ 项目依赖安装完成"

# 2.1 写入 .env 配置（MySQL）
echo -e "${GREEN}[2.1/5] 写入数据库配置...${NC}"
cat > "$APP_DIR/.env" <<EOF
DB_TYPE=${DB_TYPE:-mysql}
MYSQL_HOST=${MYSQL_HOST:-127.0.0.1}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_DATABASE=${MYSQL_DATABASE:-dms_db}
MYSQL_USER=${MYSQL_USER:-dms_user}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-your_password}
EOF
echo "✅ 数据库配置写入完成"

# 3. 配置服务
echo -e "${GREEN}[3/5] 配置 systemd 服务...${NC}"
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
echo "✅ 服务配置完成"

# 4. 启动服务
echo -e "${GREEN}[4/5] 启动服务...${NC}"
systemctl daemon-reload
systemctl enable dms
systemctl restart dms

# 5. 验证
echo -e "${GREEN}[5/5] 验证服务...${NC}"
sleep 2
SERVER_IP=$(hostname -I | awk '{print $1}')

if systemctl is-active dms > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}==============================================${NC}"
    echo -e "${GREEN}     ✅ 迁移成功！${NC}"
    echo -e "${GREEN}==============================================${NC}"
    echo ""
    echo -e "访问地址: ${BLUE}http://${SERVER_IP}:5000${NC}"
    echo ""
else
    echo -e "${RED}❌ 服务启动失败${NC}"
    echo "查看日志: journalctl -u dms -n 50"
    exit 1
fi
