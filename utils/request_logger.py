"""
请求日志中间件 - 记录所有 HTTP 请求和响应
"""
import time
import logging
from flask import request, g

logger = logging.getLogger('app')

def log_request():
    """请求开始前记录"""
    g.start_time = time.time()
    logger.info(
        f"REQUEST: {request.method} {request.url} "
        f"[IP: {request.remote_addr}]"
    )

def log_response(response):
    """请求完成后记录"""
    duration = time.time() - getattr(g, 'start_time', time.time())
    logger.info(
        f"RESPONSE: {request.method} {request.url} "
        f"[Status: {response.status_code}] "
        f"[Duration: {duration:.3f}s]"
    )
    return response

def log_user_action(username, action, details=""):
    """记录用户操作"""
    logger.info(f"USER_ACTION: [{username}] {action} - {details}")

def log_security_event(event_type, details=""):
    """记录安全事件"""
    logger.warning(f"SECURITY: [{event_type}] {details}")

