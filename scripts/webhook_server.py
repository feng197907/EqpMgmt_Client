#!/usr/bin/env python3
"""
Webhook 接收服务 - 用于自动部署
接收 GitHub Webhook 并自动执行 git pull
"""

import hmac
import hashlib
import subprocess
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# 配置
GIT_DIR = "/data/EquipmentManagement"
WEBHOOK_SECRET = "your_secret_token_here"  # 替换为您的 webhook 密钥
DEPLOY_COMMAND = "cd /data/EquipmentManagement && git pull origin main"
RESTART_COMMAND = "systemctl restart flask-app"  # 或其他重启命令

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/webhook-deploy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def verify_signature(payload_body, signature_header):
    """验证 GitHub webhook 签名"""
    if not WEBHOOK_SECRET or WEBHOOK_SECRET == "your_secret_token_here":
        logger.warning("Webhook secret not configured, skipping verification")
        return True
    
    if not signature_header:
        return False
    
    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload_body,
        hashlib.sha256
    )
    return hmac.compare_digest(mac.hexdigest(), signature)


def deploy():
    """执行部署"""
    try:
        # Git pull
        logger.info("Executing git pull...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=GIT_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"Git pull failed: {result.stderr}")
            return False, result.stderr
        
        logger.info(f"Git pull output: {result.stdout}")
        
        # 重启服务
        logger.info("Restarting service...")
        restart_result = subprocess.run(
            RESTART_COMMAND,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if restart_result.returncode == 0:
            logger.info("Service restarted successfully")
        else:
            logger.warning(f"Service restart returned: {restart_result.returncode}")
        
        return True, "Deployment successful"
        
    except subprocess.TimeoutExpired:
        logger.error("Deployment timeout")
        return False, "Deployment timeout"
    except Exception as e:
        logger.error(f"Deployment error: {e}")
        return False, str(e)


@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook 接收端点"""
    
    # 记录请求
    logger.info(f"Webhook received from {request.remote_addr}")
    logger.info(f"Event: {request.headers.get('X-GitHub-Event', 'unknown')}")
    
    # 只处理 push 事件
    event = request.headers.get('X-GitHub-Event', 'unknown')
    if event != 'push':
        logger.info(f"Ignoring event: {event}")
        return jsonify({"status": "ignored", "event": event}), 200
    
    # 验证签名
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        logger.warning("Invalid signature")
        return jsonify({"status": "unauthorized"}), 401
    
    # 执行部署
    logger.info("Starting deployment...")
    success, message = deploy()
    
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "failed", "message": message}), 500


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({"status": "ok"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
