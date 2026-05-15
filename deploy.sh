#!/bin/bash
# =============================================================================
# EquipmentManagement 自动化部署脚本
# 用法: ./deploy.sh [commit_message]
# 示例: ./deploy.sh "修复了用户登录bug"
# =============================================================================

set -e  # 遇到错误立即退出

# 配置
REMOTE_HOST="82.157.4.72"
REMOTE_USER="root"
REMOTE_PORT="22"
WEBHOOK_URL="http://82.157.4.72:5001/webhook"
PROJECT_DIR="/data/EquipmentManagement"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查参数
if [ -z "$1" ]; then
    COMMIT_MSG="Update: $(date '+%Y-%m-%d %H:%M:%S')"
else
    COMMIT_MSG="$1"
fi

echo ""
echo "=============================================="
echo "   EquipmentManagement 自动化部署脚本"
echo "=============================================="
echo ""

# 步骤 1: Git 状态检查
log_info "步骤 1/4: 检查 Git 状态..."
if [ -n "$(git status --porcelain)" ]; then
    log_info "发现未提交的更改，准备提交..."
else
    log_warning "没有检测到未提交的更改，将强制推送当前分支"
fi

# 步骤 2: Git 添加所有更改
log_info "步骤 2/4: 添加所有更改到暂存区..."
git add -A

# 步骤 3: Git 提交
log_info "步骤 3/4: 提交更改..."
log_info "提交信息: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

# 步骤 4: Git 推送
log_info "步骤 4/4: 推送到远程仓库..."
git push origin HEAD

# 等待 webhook 触发
log_info "等待远程服务器响应..."
sleep 3

# 触发远程 webhook（确保部署）
log_info "触发远程 Webhook 确认部署..."
curl -s -X POST "$WEBHOOK_URL" -m 10 || log_warning "Webhook 请求完成（可能已被 GitHub 触发）"

# 检查部署状态
echo ""
log_info "检查远程服务状态..."
ssh -p $REMOTE_PORT $REMOTE_USER@$REMOTE_HOST "systemctl is-active dms" 2>/dev/null && \
    log_success "主服务运行正常" || log_warning "主服务状态异常"

echo ""
echo "=============================================="
log_success "部署完成!"
echo "=============================================="
echo ""
log_info "访问地址:"
echo "  - 主站: http://$REMOTE_HOST:5000"
echo "  - Webhook: http://$REMOTE_HOST:5001/webhook"
echo ""
