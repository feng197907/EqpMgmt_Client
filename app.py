# DMS 设备管理系统 - Flask 应用工厂
import os

from flask import Flask

from config import (
    DOC_STATUS_LABELS,
    DEVICE_STATUS_LABELS,
    SECRET_KEY,
    UPLOAD_FOLDER,
)
from database import get_db, init_db
from blueprints import (
    approvals_bp,
    auth_bp,
    borrowing_bp,
    dashboard_bp,
    device_changes_bp,
    devices_bp,
    documents_bp,
    maintenance_bp,
    search_bp,
    users_bp,
)
from extensions import login_manager
from models.user import load_user


def create_app():
    """Flask 应用工厂函数"""
    app = Flask(__name__)

    # Flask 配置
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

    # 初始化 Flask-Login
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    # 注册用户加载回调
    login_manager.user_loader(load_user)

    # 注册 Blueprints
    app.register_blueprint(auth_bp)  # login, logout, index (保持原路径)
    app.register_blueprint(devices_bp)  # /device/<id> 等
    app.register_blueprint(documents_bp)  # upload_doc, download, documents 等
    app.register_blueprint(borrowing_bp)  # /borrow/<id>
    app.register_blueprint(approvals_bp)  # /approvals
    app.register_blueprint(device_changes_bp)  # /device_changes
    app.register_blueprint(users_bp)  # /users
    app.register_blueprint(dashboard_bp)  # dashboard, reminders, add_device 等
    app.register_blueprint(maintenance_bp)  # 维护计划相关路由
    app.register_blueprint(search_bp)  # 全局搜索

    # 确保上传目录存在
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # 初始化数据库
    init_db()

    # 全局上下文处理器 - 注入变量到所有模板
    @app.context_processor
    def inject_global_vars():
        """向所有模板注入全局变量"""
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as total FROM approval_requests WHERE status = 'pending'")
            result = cur.fetchone()
            pending_count = result["total"] if result else 0
            conn.close()
        except Exception:
            pending_count = 0
        return dict(
            pending_count=pending_count,
            doc_status_labels=DOC_STATUS_LABELS,
            device_status_labels=DEVICE_STATUS_LABELS,
        )

    return app


# 创建应用实例（用于测试和直接运行）
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
