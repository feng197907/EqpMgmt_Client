#!/bin/bash
# =============================================================================
# EquipmentManagement 一键部署脚本（venv 版）
# 功能：创建/更新虚拟环境 + 拉取最新代码 + 安装依赖 + 重启服务
# 用法：./server_deploy.sh
# =============================================================================

set -e

PROJECT_DIR="/data/EquipmentManagement"
VENV_DIR="$PROJECT_DIR/venv"
cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "=============================================="
echo "   EquipmentManagement 部署脚本 (venv)"
echo "=============================================="
echo ""

# ── [0/7] 检查系统 Python（用于创建 venv）──────────────────────────────────
log_info "[0/7] 检查系统 Python..."

PYTHON_CANDIDATES=(
    "/usr/local/python3.11/bin/python3.11"
    "/usr/bin/python3.11"
    "/usr/local/bin/python3.11"
    "/usr/bin/python3"
    "/usr/local/bin/python3"
)

BASE_PYTHON=""
for candidate in "${PYTHON_CANDIDATES[@]}"; do
    if [ -x "$candidate" ]; then
        BASE_PYTHON="$candidate"
        break
    fi
done

if [ -z "$BASE_PYTHON" ]; then
    BASE_PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
fi

if [ -z "$BASE_PYTHON" ] || [ ! -x "$BASE_PYTHON" ]; then
    log_error "未找到 Python！请安装 Python 3.7+"
    exit 1
fi

log_info "系统 Python: $BASE_PYTHON"
$BASE_PYTHON --version

# 检查系统 Python SSL 支持（venv 会继承此特性）
SSL_OK=$($BASE_PYTHON -c "import ssl; print('ok')" 2>/dev/null || echo "fail")
if [ "$SSL_OK" != "ok" ]; then
    log_warning "系统 Python 缺少 SSL 模块"
    log_warning "  gunicorn 将无法使用，服务将以 python 直接运行方式启动"
    log_warning "  如需使用 gunicorn，请重编译 Python 并开启 SSL 支持"
fi

# ── [1/7] 创建/更新虚拟环境 ────────────────────────────────────────────────
log_info "[1/7] 检查虚拟环境..."

if [ ! -d "$VENV_DIR" ]; then
    log_info "创建虚拟环境: $VENV_DIR"
    $BASE_PYTHON -m venv "$VENV_DIR"
    log_success "虚拟环境创建成功"
else
    log_info "虚拟环境已存在: $VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

log_info "已激活虚拟环境"
log_info "  Python: $($VENV_PYTHON --version 2>&1)"
log_info "  Pip:    $($VENV_PIP --version 2>&1)"

# ── [2/7] 升级 pip ─────────────────────────────────────────────────────────
log_info "[2/7] 升级 pip..."
# 先尝试腾讯云镜像（HTTP，无 SSL 要求），失败则直连
$VENV_PYTHON -m pip install --upgrade pip \
    -i http://mirrors.tencentyun.com/pypi/simple \
    --trusted-host mirrors.tencentyun.com \
    --disable-pip-version-check 2>/dev/null \
    || $VENV_PYTHON -m pip install --upgrade pip --disable-pip-version-check 2>/dev/null \
    || true

# ── [3/7] 拉取最新代码 ────────────────────────────────────────────────────
log_info "[3/7] 拉取最新代码..."
OLD_REQ_HASH=$(md5sum "$PROJECT_DIR/requirements.txt" 2>/dev/null | awk '{print $1}')
git pull origin main
NEW_REQ_HASH=$(md5sum "$PROJECT_DIR/requirements.txt" 2>/dev/null | awk '{print $1}')

# ── [4/7] 安装/更新依赖（仅 requirements.txt 有变动时）────────────────────
if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then
    log_info "[4/7] requirements.txt 有变动，安装/更新依赖..."
    $VENV_PIP install -r "$PROJECT_DIR/requirements.txt" \
        -i http://mirrors.tencentyun.com/pypi/simple \
        --trusted-host mirrors.tencentyun.com \
        --disable-pip-version-check 2>&1 | grep -v "WARNING:" || true
    log_success "依赖安装完成"
else
    log_info "[4/7] requirements.txt 无变动，跳过依赖安装"
fi

# ── [5/7] 检查 gunicorn 是否可用 ───────────────────────────────────────────
USE_GUNICORN=false
GUNICORN_BIN=""

# 只有在 SSL 正常时 gunicorn 才能运行
if [ "$SSL_OK" = "ok" ]; then
    # 确保 gunicorn 已安装
    $VENV_PIP install gunicorn --disable-pip-version-check -q 2>/dev/null || true
    if $VENV_DIR/bin/gunicorn --version &>/dev/null; then
        USE_GUNICORN=true
        GUNICORN_BIN="$VENV_DIR/bin/gunicorn"
        log_info "gunicorn 可用: $($VENV_DIR/bin/gunicorn --version 2>&1)"
    fi
fi

if [ "$USE_GUNICORN" = false ]; then
    log_info "启动方式: python 直接运行（兼容性好）"
fi

# ── [6/7] 停止旧进程 ───────────────────────────────────────────────────────
log_info "[6/7] 停止旧进程..."

# 读取旧 PID 并停止
if [ -f "$PROJECT_DIR/gunicorn.pid" ]; then
    OLD_PID=$(cat "$PROJECT_DIR/gunicorn.pid" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" >/dev/null 2>&1; then
        log_info "停止 gunicorn 进程 $OLD_PID ..."
        kill -TERM "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
    rm -f "$PROJECT_DIR/gunicorn.pid"
fi

if [ -f "$PROJECT_DIR/app.pid" ]; then
    OLD_PID=$(cat "$PROJECT_DIR/app.pid" 2>/dev/null || echo "")
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" >/dev/null 2>&1; then
        log_info "停止 python 进程 $OLD_PID ..."
        kill -TERM "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
    rm -f "$PROJECT_DIR/app.pid"
fi

# pkill 兜底
pkill -f "gunicorn.*5000"            2>/dev/null || true
pkill -f "python.*app.py"            2>/dev/null || true
pkill -f "$VENV_DIR/bin/gunicorn"    2>/dev/null || true

# 杀掉占用 5000 端口的进程
fuser -k 5000/tcp 2>/dev/null || true

sleep 3

# 确认旧进程已停止
if pgrep -f "gunicorn.*5000" >/dev/null 2>&1 || pgrep -f "python.*app.py" >/dev/null 2>&1; then
    log_warning "旧进程仍在运行，强制杀死..."
    pkill -9 -f "gunicorn.*5000" 2>/dev/null || true
    pkill -9 -f "python.*app.py" 2>/dev/null || true
    sleep 2
fi

# ── [7/7] 启动服务 ─────────────────────────────────────────────────────────
log_info "[7/7] 启动服务..."
export PYTHONUNBUFFERED=1
mkdir -p "$PROJECT_DIR/logs"

if [ "$USE_GUNICORN" = true ]; then
    # ── 使用 gunicorn 启动 ──
    log_info "使用 gunicorn 启动..."
    PID_FILE="$PROJECT_DIR/gunicorn.pid"
    ACCESS_LOG="$PROJECT_DIR/logs/gunicorn_access.log"
    ERROR_LOG="$PROJECT_DIR/logs/gunicorn_error.log"

    $GUNICORN_BIN \
        --workers 2 \
        --bind 0.0.0.0:5000 \
        --pid "$PID_FILE" \
        --access-logfile "$ACCESS_LOG" \
        --error-logfile "$ERROR_LOG" \
        --log-level info \
        --daemon \
        "app:create_app()"

    SERVER_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
    log_info "gunicorn 已启动，PID: $SERVER_PID"
else
    # ── 使用 python 直接运行 ──
    log_info "使用 python 直接运行..."
    PID_FILE="$PROJECT_DIR/app.pid"

    # 切换到项目目录，激活虚拟环境，然后启动
    cd "$PROJECT_DIR"
    setsid nohup "$VENV_PYTHON" "$PROJECT_DIR/app.py" \
        > "$PROJECT_DIR/logs/app.log" 2>&1 &
    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"
    log_info "服务已启动，PID: $SERVER_PID"
fi

# ── 健康检查 ───────────────────────────────────────────────────────────────
log_info "等待服务启动..."
sleep 3

MAX_RETRIES=15
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))

    # 检查进程是否还在
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$PID" ] && ! ps -p "$PID" >/dev/null 2>&1; then
            log_error "进程已退出！查看日志："
            echo "----------------------------------------------"
            if [ "$USE_GUNICORN" = true ]; then
                tail -30 "$ERROR_LOG" 2>/dev/null || echo "  (无日志)"
            else
                tail -30 "$PROJECT_DIR/logs/app.log" 2>/dev/null || echo "  (无日志)"
                tail -30 "$PROJECT_DIR/logs/error.log" 2>/dev/null || echo "  (无日志)"
            fi
            echo "----------------------------------------------"
            exit 1
        fi
    fi

    # 检查端口监听
    if ss -tln 2>/dev/null | grep -q ':5000 '; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/login 2>/dev/null || echo "000")
        if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
            echo ""
            echo "=============================================="
            log_success "✅ 部署成功！服务正常运行"
            echo "=============================================="
            echo ""
            echo "  访问地址:  http://82.157.4.72:5000"
            echo "  虚拟环境:  $VENV_DIR"
            echo ""
            if [ "$USE_GUNICORN" = true ]; then
                echo "  服务类型:  gunicorn"
                echo "  进程 PID:  $SERVER_PID"
                echo "  日志:"
                echo "    - 访问日志: $ACCESS_LOG"
                echo "    - 错误日志: $ERROR_LOG"
            else
                echo "  服务类型:  python 直接运行"
                echo "  进程 PID:  $SERVER_PID"
                echo "  日志:"
                echo "    - $PROJECT_DIR/logs/app.log"
            fi
            echo "    - $PROJECT_DIR/logs/error.log"
            echo ""
            echo "  查看实时日志:  tail -f $PROJECT_DIR/logs/error.log"
            echo ""
            exit 0
        fi
    fi

    log_warning "等待服务启动... ($RETRY_COUNT/$MAX_RETRIES)"
done

# ── 部署失败，输出调试信息 ─────────────────────────────────────────────────
echo ""
log_error "❌ 部署失败：服务启动超时"
echo ""
echo "=============================================="
echo "  调试信息"
echo "=============================================="
echo ""
echo "1. 进程状态："
ps aux | grep -E "(gunicorn|python.*app.py)" | grep -v grep || echo "   无相关进程"
echo ""
echo "2. 端口监听状态："
ss -tlnp 2>/dev/null | grep ':5000' || echo "   端口 5000 未监听"
echo ""
echo "3. 应用日志（最后 30 行）："
echo "----------------------------------------------"
if [ "$USE_GUNICORN" = true ]; then
    tail -30 "$ERROR_LOG" 2>/dev/null || echo "   (无日志文件)"
else
    tail -30 "$PROJECT_DIR/logs/app.log" 2>/dev/null || echo "   (无日志文件)"
fi
echo "----------------------------------------------"
echo ""
echo "4. 错误日志（最后 20 行）："
echo "----------------------------------------------"
tail -20 "$PROJECT_DIR/logs/error.log" 2>/dev/null || echo "   (无日志文件)"
echo "----------------------------------------------"
echo ""
exit 1
