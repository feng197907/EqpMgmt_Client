#!/bin/bash
# =============================================================================
# EquipmentManagement 一键部署脚本
# 功能：拉取最新代码 + 重启服务
# 用法：./deploy.sh
# =============================================================================

set -e  # 遇到错误立即退出

PROJECT_DIR="/data/EquipmentManagement"
cd "$PROJECT_DIR"

echo "=============================================="
echo "开始部署..."
echo "=============================================="

# 0. 检查 Python 版本
echo "[0/4] 检查 Python 版本..."
python3 --version

# 1. 拉取最新代码
echo "[1/4] 拉取最新代码..."
git pull origin main

# 2. 停止旧进程（兼容 gunicorn 和 python 直接运行）
echo "[2/4] 停止旧进程..."
pkill -f "gunicorn.*5000" || true
pkill -f "python.*app.py" || true
sleep 2

# 3. 安装/更新依赖
echo "[3/4] 检查依赖..."
python3 -m pip install -r requirements.txt --quiet

# 4. 启动新服务
echo "[4/4] 启动服务..."
export FLASK_APP=app.py
export FLASK_ENV=production

# 使用 python3.11 直接运行（兼容无 gunicorn 环境）
PYTHON_BIN=$(which python3.11 || which python3 || which python)
echo "使用 Python: $PYTHON_BIN"
$PYTHON_BIN --version

# 停止所有可能占用 5000 端口的进程
fuser -k 5000/tcp 2>/dev/null || true
sleep 2

# 使用 python 直接运行
nohup $PYTHON_BIN app.py > app.log 2>&1 &
SERVER_TYPE="python"

sleep 3

# 检查状态
sleep 3
if pgrep -f "$PYTHON_BIN.*app.py" > /dev/null; then
    echo "=============================================="
    echo "✅ 部署成功！"
    echo "=============================================="
    echo "访问地址: http://82.157.4.72:5000"
    echo "服务类型: python ($PYTHON_BIN)"
    echo "日志文件: $PROJECT_DIR/app.log"
    echo ""
    echo "查看实时日志："
    echo "  tail -f $PROJECT_DIR/logs/error.log"
    echo "  tail -f $PROJECT_DIR/app.log"
else
    echo "=============================================="
    echo "❌ 部署失败，请检查日志"
    echo "=============================================="
    echo "查看错误日志："
    echo "  tail -f $PROJECT_DIR/logs/error.log"
    echo "  cat $PROJECT_DIR/app.log"
    exit 1
fi
