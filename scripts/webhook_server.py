#!/usr/bin/env python3
"""
Webhook 接收服务 - 用于自动部署
增强版：包含详细的 git 拉取日志
兼容 Python 3.6
"""

import hmac
import hashlib
import subprocess
import logging
import os
import signal
import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

GIT_DIR = "/data/EquipmentManagement"
WEBHOOK_SECRET = "6C1BFF08-CF1F-2813-907A-44B39B4D7FE5"
DEPLOY_LOG = "/var/log/webhook-deploy.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(DEPLOY_LOG),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def verify_signature(payload_body, signature_header):
    if not signature_header:
        return False
    try:
        sha_name, signature = signature_header.split('=')
        if sha_name != 'sha256':
            return False
        mac = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            payload_body,
            hashlib.sha256
        )
        return hmac.compare_digest(mac.hexdigest(), signature)
    except Exception as e:
        logger.error("Signature verification error: %s", e)
        return False


def run_command(cmd, cwd=None, timeout=60):
    """兼容 Python 3.6 的命令执行"""
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", "Timeout"


def get_git_info():
    """获取 git 仓库状态信息"""
    info = {}
    
    # 当前分支
    returncode, stdout, _ = run_command(["git", "branch", "--show-current"], cwd=GIT_DIR)
    info['branch'] = stdout.strip() if returncode == 0 else 'unknown'
    
    # 当前 commit
    returncode, stdout, _ = run_command(["git", "rev-parse", "HEAD"], cwd=GIT_DIR)
    info['commit'] = stdout.strip()[:8] if returncode == 0 else 'unknown'
    
    # 当前 commit message
    returncode, stdout, _ = run_command(["git", "log", "-1", "--pretty=%s"], cwd=GIT_DIR)
    info['commit_msg'] = stdout.strip() if returncode == 0 else 'unknown'
    
    # 提交时间
    returncode, stdout, _ = run_command(["git", "log", "-1", "--pretty=%ci"], cwd=GIT_DIR)
    info['commit_time'] = stdout.strip() if returncode == 0 else 'unknown'
    
    # 提交作者
    returncode, stdout, _ = run_command(["git", "log", "-1", "--pretty=%an"], cwd=GIT_DIR)
    info['commit_author'] = stdout.strip() if returncode == 0 else 'unknown'
    
    return info


def get_remote_info():
    """获取远程仓库信息"""
    returncode, stdout, stderr = run_command(["git", "remote", "-v"], cwd=GIT_DIR)
    if returncode == 0:
        return stdout.strip()
    return "No remote configured"


def deploy():
    try:
        logger.info("========================================")
        logger.info("=== Starting deployment at %s ===", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("========================================")
        
        # 记录部署前状态
        before_info = get_git_info()
        logger.info("[BEFORE] Branch: %s, Commit: %s", before_info['branch'], before_info['commit'])
        logger.info("[BEFORE] Last commit: %s (%s) by %s", 
                    before_info['commit_msg'], before_info['commit_time'], before_info['commit_author'])
        
        # 获取远程仓库信息
        remote_info = get_remote_info()
        logger.info("[REMOTE] %s", remote_info)
        
        # 检查是否有未提交的更改
        returncode, stdout, _ = run_command(["git", "status", "--porcelain"], cwd=GIT_DIR)
        if stdout.strip():
            logger.warning("[WARNING] Local changes exist, will stash before pull")
            run_command(["git", "stash"], cwd=GIT_DIR)
        
        # 执行 git pull
        logger.info("[GIT] Executing: git pull origin main...")
        returncode, stdout, stderr = run_command(
            ["git", "fetch", "origin"],
            cwd=GIT_DIR,
            timeout=30
        )
        
        if returncode == 0:
            logger.info("[GIT] Fetch origin: OK")
        else:
            logger.warning("[GIT] Fetch origin failed: %s", stderr.strip())
        
        # 执行 pull
        returncode, stdout, stderr = run_command(
            ["git", "pull", "origin", "main"],
            cwd=GIT_DIR,
            timeout=60
        )
        
        if returncode != 0:
            logger.error("[GIT] Pull failed with code %d: %s", returncode, stderr)
            return False, "Git pull failed: " + stderr
        
        logger.info("[GIT] Pull output:")
        for line in stdout.strip().split('\n'):
            if line.strip():
                logger.info("  | %s", line)
        
        # 记录部署后状态
        after_info = get_git_info()
        logger.info("[AFTER] Branch: %s, Commit: %s", after_info['branch'], after_info['commit'])
        logger.info("[AFTER] Latest commit: %s (%s) by %s",
                    after_info['commit_msg'], after_info['commit_time'], after_info['commit_author'])
        
        # 检查是否有代码变更
        if before_info['commit'] != after_info['commit']:
            logger.info("[CHANGE] Code has been updated!")
            
            # 获取变更的文件列表
            returncode, stdout, _ = run_command(
                ["git", "diff", "--stat", before_info['commit'], after_info['commit']],
                cwd=GIT_DIR
            )
            if returncode == 0 and stdout.strip():
                logger.info("[CHANGE] Changed files:")
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        logger.info("  | %s", line)
        else:
            logger.info("[CHANGE] No code changes (already up-to-date)")
        
        # 重启 gunicorn
        logger.info("[SERVICE] Restarting gunicorn...")
        
        returncode, stdout, stderr = run_command(["pgrep", "-f", "gunicorn.*5000"])
        
        if returncode == 0:
            pids = stdout.strip().splitlines()
            for pid in pids:
                if pid:
                    try:
                        os.kill(int(pid), signal.SIGHUP)
                        logger.info("[SERVICE] Sent SIGHUP to gunicorn PID %s", pid)
                    except (ProcessLookupError, ValueError):
                        logger.warning("[SERVICE] PID %s not found", pid)
            logger.info("[SERVICE] Gunicorn reloaded successfully")
        else:
            logger.warning("[SERVICE] No gunicorn found, starting new...")
            run_command(
                "cd /data/EquipmentManagement && nohup gunicorn -w 2 -b 0.0.0.0:5000 'app:create_app()' --daemon",
                shell=True
            )
        
        logger.info("========================================")
        logger.info("=== Deployment completed at %s ===", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("========================================")
        return True, "Deployment successful"
        
    except Exception as e:
        logger.error("[ERROR] Deployment error: %s", e)
        return False, str(e)


@app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("[WEBHOOK] Received from %s", request.remote_addr)
    
    event = request.headers.get('X-GitHub-Event', 'unknown')
    logger.info("[WEBHOOK] Event type: %s", event)
    
    if event != 'push':
        return jsonify({"status": "ignored", "event": event}), 200
    
    # 签名校验已禁用：不再强制验证 `WEBHOOK_SECRET`，仅记录签名存在与否
    signature = request.headers.get('X-Hub-Signature-256')
    if signature:
        logger.info("[WEBHOOK] Signature header present but verification is disabled")
    
    logger.info("[WEBHOOK] Starting deployment...")
    success, message = deploy()
    
    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "failed", "message": message}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "webhook"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
