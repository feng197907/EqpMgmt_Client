#!/bin/bash
# =============================================================================
# EquipmentManagement 一键部署脚本
# 功能：拉取最新代码 + 重启服务
# 用法：./deploy.sh
# =============================================================================

cd /data/EquipmentManagement

echo "=============================================="
echo "开始部署..."
echo "=============================================="

# 1. 拉取最新代码
echo "[1/3] 拉取最新代码..."
git pull origin main

# 2. 停止旧进程
echo "[2/3] 停止旧进程..."
pkill -f gunicorn || true

# 3. 启动新服务
echo "[3/3] 启动服务..."
nohup gunicorn --bind 0.0.0.0:5000 --workers 2 app:app > gunicorn.log 2>&1 &

sleep 2

# 检查状态
if pgrep -f "gunicorn.*5000" > /dev/null; then
    echo "=============================================="
    echo "✅ 部署成功！"
    echo "=============================================="
    echo "访问地址: http://82.157.4.72:5000"
    echo "日志文件: /data/EquipmentManagement/gunicorn.log"
else
    echo "=============================================="
    echo "❌ 部署失败，请检查日志"
    echo "=============================================="
    echo "tail -f /data/EquipmentManagement/gunicorn.log"
    echo "实时查看应用日志"
    echo "tail -f /data/EquipmentManagement/logs/app.log"
    echo "查看错误日志"
    echo "tail -f /data/EquipmentManagement/logs/error.log"
fi
