#!/bin/bash
# =============================================================================
# EquipmentManagement 迁移脚本
# 从旧服务器迁移到新服务器
# 用法：./migrate.sh
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "=============================================="
echo "  EquipmentManagement 服务器迁移脚本"
echo "=============================================="

# ==================== 配置（迁移前请修改） ====================
NEW_HOST_IP="YOUR_NEW_SERVER_IP"  # 修改为新服务器 IP
APP_DIR="/data/EquipmentManagement"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 读取迁移环境配置（包含 MySQL 参数）
if [ -f "$SCRIPT_DIR/env.conf" ]; then
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/env.conf"
fi

# ==================== 步骤 1: 导出旧服务器数据 ====================
log "步骤 1/4: 准备迁移数据..."

# 创建迁移包
TEMP_DIR="/tmp/dms_migrate_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$TEMP_DIR"

# 复制配置文件和关键文件
log "打包配置文件..."
cp -r /data/EquipmentManagement/*.py "$TEMP_DIR/" 2>/dev/null || true
cp -r /data/EquipmentManagement/templates "$TEMP_DIR/" 2>/dev/null || true
cp -r /data/EquipmentManagement/static "$TEMP_DIR/" 2>/dev/null || true
cp /etc/systemd/system/dms.service "$TEMP_DIR/" 2>/dev/null || true
cp /etc/systemd/system/dms-webhook.service "$TEMP_DIR/" 2>/dev/null || true

# 导出环境变量
echo "# 迁移的环境变量" > "$TEMP_DIR/.env"
env | grep -E "^(SECRET_KEY|DB_|REDIS_)" >> "$TEMP_DIR/.env" 2>/dev/null || true

# 如果本地已有迁移配置，则补充 MySQL 连接参数
cat >> "$TEMP_DIR/.env" <<EOF
DB_TYPE=${DB_TYPE:-mysql}
MYSQL_HOST=${MYSQL_HOST:-127.0.0.1}
MYSQL_PORT=${MYSQL_PORT:-3306}
MYSQL_DATABASE=${MYSQL_DATABASE:-dms_db}
MYSQL_USER=${MYSQL_USER:-dms_user}
MYSQL_PASSWORD=${MYSQL_PASSWORD:-your_password}
EOF

log "迁移包已创建: $TEMP_DIR"

# ==================== 步骤 2: 在新服务器安装依赖 ====================
log "步骤 2/4: 安装依赖..."
ssh root@$NEW_HOST_IP "bash -s" << 'SSH_EOF'
    apt-get update -qq
    apt-get install -y python3 python3-pip git > /dev/null 2>&1
    pip3 install flask gunicorn paramiko --quiet
    mkdir -p /data
    echo "依赖安装完成"
SSH_EOF

# ==================== 步骤 3: 传输代码 ====================
log "步骤 3/4: 传输代码..."
rsync -az --exclude='.git' --exclude='__pycache__' \
    /data/EquipmentManagement/ root@$NEW_HOST_IP:/data/EquipmentManagement/

# 传输 MySQL 配置到新服务器的 .env
scp "$TEMP_DIR/.env" root@$NEW_HOST_IP:/data/EquipmentManagement/.env
log "代码传输完成"

# ==================== 步骤 4: 配置新服务器 ====================
log "步骤 4/4: 配置新服务器服务..."
ssh root@$NEW_HOST_IP "bash -s" << 'SSH_EOF'
    pip3 install -r /data/EquipmentManagement/requirements.txt --quiet

    # 复制 systemd 服务文件
    cp /tmp/dms_migrate_*/dms.service /etc/systemd/system/ 2>/dev/null || true
    
    # 重载 systemd
    systemctl daemon-reload
    systemctl enable dms
    systemctl restart dms
    
    # 验证
    sleep 2
    if systemctl is-active dms > /dev/null 2>&1; then
        echo "=============================================="
        echo -e "${GREEN}✅ 迁移成功！${NC}"
        echo "=============================================="
        echo "新服务器访问地址: http://$(hostname -I | awk '{print $1}'):5000"
    else
        echo -e "${RED}❌ 服务启动失败${NC}"
        journalctl -u dms -n 20
    fi
SSH_EOF

echo ""
echo "=============================================="
log "迁移完成！"
echo "=============================================="
echo ""
echo "迁移后检查清单:"
echo "  1. ✅ 确认新服务器服务正常运行"
echo "  2. 🔄 更新 GitHub Webhook URL（如有）"
echo "  3. 🔄 配置新服务器的防火墙 (开放 5000, 5001 端口)"
echo "  4. 🔄 配置域名解析（如有）"
echo "  5. 🔄 旧服务器可安全关机"
echo ""
