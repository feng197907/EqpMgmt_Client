#!/bin/bash
# =============================================================================
# EquipmentManagement 一键部署脚本
# 功能：拉取最新代码 + 重启服务 + 健康检查
# 用法：./server_deploy.sh
# =============================================================================

set -e  # 遇到错误立即退出

PROJECT_DIR="/data/EquipmentManagement"
cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=============================================="
echo "   EquipmentManagement 部署脚本"
echo "=============================================="
echo ""

# 0. 检查 Python 版本
log_info "[0/5] 检查 Python 版本..."

# 优先使用已知的 Python 3.11 路径
if [ -x "/usr/local/python3.11/bin/python3.11" ]; then
    PYTHON_BIN="/usr/local/python3.11/bin/python3.11"
elif [ -x "/usr/bin/python3.11" ]; then
    PYTHON_BIN="/usr/bin/python3.11"
else
    PYTHON_BIN=$(which python3.11 || which python3 || which python)
fi

if [ -z "$PYTHON_BIN" ] || [ ! -x "$PYTHON_BIN" ]; then
    log_error "未找到 Python！请安装 Python 3.7+"
    exit 1
fi
log_info "使用 Python: $PYTHON_BIN"
$PYTHON_BIN --version

# 验证 Python 版本 >= 3.7
PYTHON_VERSION=$($PYTHON_BIN -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 7 ]); then
    log_error "Python 版本过低 ($PYTHON_VERSION)，需要 3.7+"
    exit 1
fi
log_success "Python 版本检查通过: $PYTHON_VERSION"

# 1. 拉取最新代码
log_info "[1/5] 拉取最新代码..."
git pull origin main

# 2. 安装/更新依赖
log_info "[2/5] 检查依赖..."
$PYTHON_BIN -m pip install -r requirements.txt --quiet --disable-pip-version-check 2>&1 | grep -v "WARNING:" || true

# 3. 停止旧进程
log_info "[3/5] 停止旧进程..."
pkill -f "$PYTHON_BIN.*app.py" || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3

# 4. 启动新服务
log_info "[4/5] 启动服务..."
export FLASK_APP=app.py
export PYTHONUNBUFFERED=1

nohup $PYTHON_BIN app.py > app.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > app.pid
log_info "服务已启动，PID: $SERVER_PID"

# 5. 健康检查
log_info "[5/5] 健康检查（等待服务启动）..."
MAX_RETRIES=10
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
    
    # 检查进程是否存在
    if ! ps -p $SERVER_PID > /dev/null 2>&1; then
        log_error "服务进程已退出！查看日志："
        echo "----------------------------------------------"
        tail -30 app.log
        echo "----------------------------------------------"
        exit 1
    fi
    
    # 检查端口是否监听
    if ss -tln | grep -q ':5000 '; then
        # 尝试 HTTP 请求
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
            echo ""
            echo "=============================================="
            log_success "✅ 部署成功！服务正常运行"
            echo "=============================================="
            echo ""
            echo "  访问地址: http://82.157.4.72:5000"
            echo "  进程 PID: $SERVER_PID"
            echo "  日志文件:"
            echo "    - $PROJECT_DIR/app.log"
            echo "    - $PROJECT_DIR/logs/error.log"
            echo ""
            echo "  查看实时日志："
            echo "    tail -f $PROJECT_DIR/logs/error.log"
            echo ""
            exit 0
        fi
    fi
    
    log_warning "等待服务启动... ($RETRY_COUNT/$MAX_RETRIES)"
done

# 超时：服务启动但未响应
echo ""
log_error "❌ 部署失败：服务启动超时"
echo ""
echo "=============================================="
echo "  调试信息"
echo "=============================================="
echo ""
echo "1. 进程状态："
ps -p $SERVER_PID -o pid,cmd || echo "  进程不存在"
echo ""
echo "2. 端口监听状态："
ss -tlnp | grep ':5000' || echo "  端口 5000 未监听"
echo ""
echo "3. 应用日志（最后 30 行）："
echo "----------------------------------------------"
tail -30 app.log
echo "----------------------------------------------"
echo ""
echo "4. 错误日志（最后 20 行）："
echo "----------------------------------------------"
tail -20 logs/error.log 2>/dev/null || echo "  错误日志不存在"
echo "----------------------------------------------"
echo ""
exit 1
