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

# 4. 启动新服务（使用 python3 直接运行，兼容无 gunicorn 环境）
echo "[4/4] 启动服务..."
export FLASK_APP=app.py
export FLASK_ENV=production

# 优先使用 gunicorn，如果不存在则使用 python3
if command -v gunicorn &> /dev/null; then
    nohup gunicorn --bind 0.0.0.0:5000 --workers 2 app:app > gunicorn.log 2>&1 &
    SERVER_TYPE="gunicorn"
else
    nohup python3 app.py > app.log 2>&1 &
    SERVER_TYPE="python3"
fi

sleep 3

# 检查状态
if pgrep -f "gunicorn.*5000|python3.*app.py" > /dev/null; then
    echo "=============================================="
    echo "✅ 部署成功！"
    echo "=============================================="
    echo "访问地址: http://82.157.4.72:5000"
    if [ "$SERVER_TYPE" = "gunicorn" ]; then
        echo "服务类型: gunicorn"
        echo "日志文件: $PROJECT_DIR/gunicorn.log"
    else
        echo "服务类型: python3"
        echo "日志文件: $PROJECT_DIR/app.log"
    fi
    echo ""
    echo "查看实时日志："
    echo "  tail -f $PROJECT_DIR/logs/error.log"
else
    echo "=============================================="
    echo "❌ 部署失败，请检查日志"
    echo "=============================================="
    echo "查看错误日志："
    echo "  tail -f $PROJECT_DIR/logs/error.log"
    echo "  tail -f $PROJECT_DIR/gunicorn.log"
    exit 1
fi
