"""
Flask 应用日志配置模块
"""
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, g

def setup_logging(app: Flask):
    """配置 Flask 应用的日志系统"""

    # 强制使用本地时区，避免容器默认 UTC 导致日志时间偏移
    formatter_converter = time.localtime
    if hasattr(time, "tzset"):
        try:
            time.tzset()
        except Exception:
            pass

    # 日志目录（项目根目录下的 logs/）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(project_root, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 日志文件路径
    app_log_file = os.path.join(log_dir, 'app.log')
    error_log_file = os.path.join(log_dir, 'error.log')

    # 日志格式（含精确时间）
    formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    formatter.converter = formatter_converter

    # 1. 应用日志 (INFO 级别)
    app_logger = logging.getLogger('app')
    app_logger.setLevel(logging.INFO)

    app_file_handler = RotatingFileHandler(
        app_log_file,
        maxBytes=10*1024*1024,
        backupCount=10
    )
    app_file_handler.setFormatter(formatter)
    app_file_handler.setLevel(logging.INFO)
    app_logger.addHandler(app_file_handler)

    # 控制台 Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    app_logger.addHandler(console_handler)

    # 2. 错误日志 (ERROR 级别)
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)

    error_file_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=10*1024*1024,
        backupCount=10
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)
    error_logger.addHandler(error_file_handler)

    # 3. 配置 Flask app logger
    app.logger.handlers.clear()
    app.logger.handlers.append(app_file_handler)
    app.logger.handlers.append(console_handler)
    app.logger.setLevel(logging.INFO)

    # 4. 禁用 Werkzeug 默认日志
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # 5. 请求日志中间件
    @app.before_request
    def log_request_info():
        g.start_time = time.time()
        app.logger.info(
            f">>> REQUEST: {request.method} {request.url} "
            f"[IP: {request.remote_addr}]"
        )

    @app.after_request
    def log_response_info(response):
        duration = time.time() - getattr(g, 'start_time', time.time())
        app.logger.info(
            f"<<< RESPONSE: {request.method} {request.url} "
            f"[Status: {response.status_code}] "
            f"[Duration: {duration:.3f}s]"
        )
        return response

    # 6. 全局错误处理器
    @app.errorhandler(404)
    def not_found(error):
        app.logger.error(f'[404] Not Found: {request.url} - {str(error)}')
        return {'error': '页面不存在'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        error_logger.error(f'[500] Internal Error: {str(error)}', exc_info=True)
        app.logger.error(f'[500] Error: {str(error)}')
        return {'error': '服务器内部错误'}, 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        error_logger.error(f'[EXCEPTION] Unhandled: {str(error)}', exc_info=True)
        app.logger.error(f'[ERROR] Unhandled: {str(error)}')
        return {'error': '发生未知错误'}, 500

    app.logger.info('日志系统初始化完成 (含请求中间件)')

    return app

def log_user_action(username, action, details=""):
    """记录用户操作"""
    logger = logging.getLogger('app')
    logger.info(f"USER_ACTION: [{username}] {action} - {details}")

def log_security_event(event_type, details=""):
    """记录安全事件"""
    logger = logging.getLogger('app')
    logger.warning(f"SECURITY: [{event_type}] {details}")

