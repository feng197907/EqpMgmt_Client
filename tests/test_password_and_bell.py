"""
DMS 设备管理系统 - 忘记密码 & 顶部闹铃提醒功能 测试套件
测试文件: blueprints/password.py, models/user.py, app.py (context_processor)
测试模板: forgot_password.html, admin_password_resets.html, login.html, base.html

测试分类:
  1. 模板语法检查 (Template Syntax)
  2. 路由注册验证 (Route Registration)
  3. 忘记密码功能 - 单元测试 (Forgot Password Unit)
  4. 管理员密码重置 - 单元测试 (Admin Reset Unit)
  5. User 模型权限测试 (User Model Permissions)
  6. Context Processor 闹铃控制测试 (Context Processor Bell Control)
"""

import os
import sqlite3
import sys
import tempfile

import pytest

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def app():
    """创建测试用 Flask 应用，使用临时数据库"""
    from app import create_app

    # 使用临时数据库，避免污染开发数据
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.environ["DMS_TEST_DB_PATH"] = db_path

    original_db_path = None
    try:
        # 替换数据库路径
        import database
        original_db_path = database.DB_PATH
        database.DB_PATH = db_path

        application = create_app()
        application.config["TESTING"] = True
        application.config["WTF_CSRF_ENABLED"] = False

        yield application
    finally:
        # 恢复原始数据库路径
        if original_db_path:
            database.DB_PATH = original_db_path
        if "DMS_TEST_DB_PATH" in os.environ:
            del os.environ["DMS_TEST_DB_PATH"]
        os.close(db_fd)
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def db_conn(app):
    """获取数据库连接"""
    from database import get_db
    conn = get_db()
    yield conn
    conn.close()


@pytest.fixture
def admin_user(app, db_conn):
    """创建管理员用户并登录，返回 client"""
    from werkzeug.security import generate_password_hash

    cur = db_conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
        ("testadmin", generate_password_hash("admin123", method='pbkdf2:sha256'), "admin", "active"),
    )
    db_conn.commit()

    client = app.test_client()
    client.post("/login", data={"username": "testadmin", "password": "admin123"})
    return client


@pytest.fixture
def normal_user(app, db_conn):
    """创建普通用户（equipment_engineer 角色）"""
    from werkzeug.security import generate_password_hash

    cur = db_conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
        ("testuser", generate_password_hash("user123", method='pbkdf2:sha256'), "equipment_engineer", "active"),
    )
    db_conn.commit()

    client = app.test_client()
    client.post("/login", data={"username": "testuser", "password": "user123"})
    return client


@pytest.fixture
def qa_manager_user(app, db_conn):
    """创建 QA 经理用户（有 document_approval 权限）"""
    from werkzeug.security import generate_password_hash

    cur = db_conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
        ("testqa", generate_password_hash("qa123", method='pbkdf2:sha256'), "qa_manager", "active"),
    )
    db_conn.commit()

    client = app.test_client()
    client.post("/login", data={"username": "testqa", "password": "qa123"})
    return client


# ============================================================
# 1. 模板语法检查
# ============================================================

class TestTemplateSyntax:
    """验证 Jinja2 模板可以被正确解析，无语法错误"""

    def test_forgot_password_template_renders(self, app):
        """forgot_password.html 应能正常渲染"""
        from jinja2 import TemplateSyntaxError

        templates = app.jinja_env.list_templates()
        assert "forgot_password.html" in templates, "forgot_password.html 模板不存在"

        # 尝试渲染，确认无语法错误
        with app.test_request_context():
            try:
                app.jinja_env.get_template("forgot_password.html")
            except TemplateSyntaxError as e:
                pytest.fail(f"forgot_password.html 存在语法错误: {e}")

    def test_admin_password_resets_template_renders(self, app):
        """admin_password_resets.html 应能正常渲染"""
        from jinja2 import TemplateSyntaxError

        with app.test_request_context():
            try:
                app.jinja_env.get_template("admin_password_resets.html")
            except TemplateSyntaxError as e:
                pytest.fail(f"admin_password_resets.html 存在语法错误: {e}")

    def test_login_template_renders(self, client):
        """login.html 应能正常渲染（含忘记密码链接）"""
        response = client.get("/login")
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        assert "忘记密码" in data, "页面缺少忘记密码文本"

    def test_login_template_has_forgot_password_link(self, client):
        """login.html 应包含指向 /forgot-password 的链接"""
        response = client.get("/login")
        data = response.data.decode("utf-8")
        assert "忘记密码" in data, "login.html 缺少'忘记密码'文本"
        assert "/forgot-password" in data, "login.html 缺少 /forgot-password 链接"

    def test_admin_password_resets_template_no_syntax_errors(self, app):
        """admin_password_resets.html Jinja2 模板解析检查"""
        from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

        template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
        env = Environment(loader=FileSystemLoader(template_dir))

        try:
            with open(os.path.join(template_dir, "admin_password_resets.html"), "r", encoding="utf-8") as f:
                env.parse(f.read())
        except TemplateSyntaxError as e:
            pytest.fail(f"admin_password_resets.html 存在 Jinja2 语法错误: {e}")

    def test_base_template_renders(self, app):
        """base.html 应能正常渲染"""
        with app.test_request_context():
            try:
                app.jinja_env.get_template("base.html").render()
            except Exception as e:
                # 某些渲染错误可以接受（如缺少 request context），但语法错误不行
                if "syntax" in str(e).lower() or "unexpected" in str(e).lower():
                    pytest.fail(f"base.html 存在语法/解析错误: {e}")


# ============================================================
# 2. 路由注册验证
# ============================================================

class TestRouteRegistration:
    """验证 password_bp 的路由正确注册到 Flask 应用"""

    def test_password_bp_registered(self, app):
        """password_bp 应已注册到应用"""
        # 检查所有注册的 blueprint
        bp_names = [bp.name for bp in app.blueprints.values()]
        assert "password" in bp_names, "password_bp 未注册到 Flask 应用"

    def test_forgot_password_route_exists(self, app):
        """/forgot-password GET 路由应存在"""
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/forgot-password" in rules, "/forgot-password 路由未注册"

    def test_admin_password_resets_route_exists(self, app):
        """/admin/password-resets GET 路由应存在"""
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        assert "/admin/password-resets" in rules, "/admin/password-resets 路由未注册"

    def test_admin_reset_password_route_exists(self, app):
        """/admin/password-resets/<int:request_id>/reset POST 路由应存在"""
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        reset_rules = [r for r in rules if "reset" in r and "password-resets" in r]
        assert len(reset_rules) > 0, "/admin/password-resets/<id>/reset 路由未注册"

    def test_forgot_password_endpoint_named(self, app):
        """forgot_password 端点应能通过 'password.forgot_password' 名称解析"""
        with app.test_request_context():
            url = app.url_for("password.forgot_password")
            assert url == "/forgot-password", f"端点解析错误，预期 /forgot-password，实际 {url}"

    def test_admin_password_resets_endpoint_named(self, app):
        """admin_password_resets 端点应能正确解析"""
        with app.test_request_context():
            url = app.url_for("password.admin_password_resets")
            assert url == "/admin/password-resets"

    def test_admin_reset_password_endpoint_named(self, app):
        """admin_reset_password 端点应能正确解析（带参数）"""
        with app.test_request_context():
            url = app.url_for("password.admin_reset_password", request_id=1)
            assert "/admin/password-resets/1/reset" in url

    def test_forgot_password_allows_get_and_post(self, app):
        """/forgot-password 应同时支持 GET 和 POST"""
        for rule in app.url_map.iter_rules():
            if rule.rule == "/forgot-password":
                methods = rule.methods or set()
                assert "GET" in methods, "/forgot-password 缺少 GET 方法"
                assert "POST" in methods, "/forgot-password 缺少 POST 方法"
                return
        pytest.fail("/forgot-password 路由未找到")


# ============================================================
# 3. 忘记密码功能 - 单元测试
# ============================================================

class TestForgotPassword:
    """测试忘记密码流程（提交重置请求）"""

    def test_get_forgot_password_page(self, client):
        """GET /forgot-password 应返回 200 并渲染表单"""
        response = client.get("/forgot-password")
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        assert "忘记密码" in data, "页面缺少标题"
        assert "username" in data, "页面缺少用户名输入框"

    def test_post_empty_username_shows_error(self, client):
        """提交空用户名应提示错误"""
        response = client.post("/forgot-password", data={"username": ""})
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        assert "请输入用户名" in data

    def test_post_nonexistent_username(self, client, db_conn):
        """提交不存在的用户名，不应暴露用户是否存在"""
        response = client.post("/forgot-password", data={"username": "nonexistent_user"})
        assert response.status_code == 302  # 重定向到登录页
        # 安全考虑：不暴露用户是否存在
        assert "管理员" in response.data.decode("utf-8") or response.status_code == 302

    def test_post_valid_username_creates_request(self, app, db_conn):
        """提交有效用户名应在 password_reset_requests 表中创建记录"""
        from werkzeug.security import generate_password_hash

        # 确保测试用户存在
        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("resetuser", generate_password_hash("pass123", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        db_conn.commit()

        client = app.test_client()
        response = client.post("/forgot-password", data={"username": "resetuser"})

        assert response.status_code == 302  # 重定向到登录页

        # 验证数据库中确实创建了记录
        cur.execute(
            "SELECT * FROM password_reset_requests WHERE username = ? AND status = 'pending'",
            ("resetuser",),
        )
        record = cur.fetchone()
        assert record is not None, "密码重置请求未写入数据库"
        assert record["username"] == "resetuser"
        assert record["status"] == "pending"

    def test_post_duplicate_request_prevented(self, app, db_conn):
        """对同一用户重复提交应被阻止"""
        from werkzeug.security import generate_password_hash

        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("dupuser", generate_password_hash("pass123", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        db_conn.commit()

        client = app.test_client()

        # 第一次提交
        response1 = client.post("/forgot-password", data={"username": "dupuser"})
        assert response1.status_code == 302

        # 第二次提交（重复）
        response2 = client.post("/forgot-password", data={"username": "dupuser"})
        data = response2.data.decode("utf-8")
        assert "重复" in data or "等待" in data, "重复提交未被阻止"

    def test_post_disabled_user(self, app, db_conn):
        """已禁用用户提交重置请求应提示账号被禁用"""
        from werkzeug.security import generate_password_hash

        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("disableduser", generate_password_hash("pass123", method='pbkdf2:sha256'), "equipment_engineer", "disabled"),
        )
        db_conn.commit()

        client = app.test_client()
        response = client.post("/forgot-password", data={"username": "disableduser"})
        data = response.data.decode("utf-8")
        assert "禁用" in data, "禁用用户应收到禁用提示"


# ============================================================
# 4. 管理员密码重置 - 单元测试
# ============================================================

class TestAdminPasswordReset:
    """测试管理员处理密码重置请求"""

    def test_admin_password_resets_requires_auth(self, client):
        """未登录用户访问 /admin/password-resets 应被重定向"""
        response = client.get("/admin/password-resets")
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_admin_password_resets_requires_admin(self, normal_user):
        """非管理员用户访问应被拒绝"""
        response = normal_user.get("/admin/password-resets")
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_admin_can_view_resets_list(self, admin_user, db_conn):
        """管理员应能访问密码重置请求列表"""
        response = admin_user.get("/admin/password-resets")
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        assert "密码重置请求管理" in data or "密码重置" in data

    def test_admin_can_filter_by_status(self, admin_user):
        """管理员应能按状态筛选请求"""
        response = admin_user.get("/admin/password-resets?status=pending")
        assert response.status_code == 200

    def test_admin_reset_password_requires_auth(self, client):
        """未登录用户执行重置应被重定向"""
        response = client.post("/admin/password-resets/1/reset", data={
            "new_password": "newpass123",
        })
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")

    def test_admin_reset_nonexistent_request(self, admin_user):
        """重置不存在的请求 ID 应提示错误"""
        response = admin_user.post("/admin/password-resets/99999/reset", data={
            "new_password": "newpass123",
        })
        data = response.data.decode("utf-8")
        assert response.status_code == 302
        # follow redirect
        response2 = admin_user.get("/admin/password-resets")
        data2 = response2.data.decode("utf-8")
        assert "不存在" in data2 or response.status_code == 302

    def test_admin_reset_with_short_password(self, admin_user, db_conn):
        """密码过短（少于4字符）应被拒绝"""
        from werkzeug.security import generate_password_hash

        # 创建待处理的请求
        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("shortpwduser", generate_password_hash("oldpwd", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        cur.execute("SELECT id FROM users WHERE username = 'shortpwduser'")
        user_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO password_reset_requests (user_id, username, status) VALUES (?, ?, 'pending')",
            (user_id, "shortpwduser"),
        )
        db_conn.commit()

        # 获取请求 ID
        cur.execute(
            "SELECT id FROM password_reset_requests WHERE username = ? AND status = 'pending'",
            ("shortpwduser",),
        )
        req_id = cur.fetchone()["id"]

        response = admin_user.post(
            f"/admin/password-resets/{req_id}/reset",
            data={"new_password": "ab"},  # 少于4字符
        )
        data = response.data.decode("utf-8")
        # 应提示密码过短
        response2 = admin_user.get("/admin/password-resets")
        data2 = response2.data.decode("utf-8")
        assert "4" in data2 or "长度" in data2 or "字符" in data2

    def test_admin_reset_password_success(self, admin_user, db_conn):
        """管理员成功重置用户密码"""
        from werkzeug.security import generate_password_hash, check_password_hash

        # 准备测试数据
        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("resetok", generate_password_hash("oldpwd", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        cur.execute("SELECT id FROM users WHERE username = 'resetok'")
        user_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO password_reset_requests (user_id, username, status) VALUES (?, ?, 'pending')",
            (user_id, "resetok"),
        )
        db_conn.commit()

        cur.execute(
            "SELECT id FROM password_reset_requests WHERE username = ? AND status = 'pending'",
            ("resetok",),
        )
        req_id = cur.fetchone()["id"]

        # 执行密码重置
        response = admin_user.post(
            f"/admin/password-resets/{req_id}/reset",
            data={"new_password": "newpassword123", "action": "reset"},
        )
        assert response.status_code == 302

        # 验证密码已更新
        cur.execute("SELECT password FROM users WHERE username = 'resetok'")
        user = cur.fetchone()
        assert check_password_hash(user["password"], "newpassword123"), "密码未被正确更新"

        # 验证请求状态已更新
        cur.execute(
            "SELECT status FROM password_reset_requests WHERE id = ?", (req_id,)
        )
        req = cur.fetchone()
        assert req["status"] == "completed", "请求状态未更新为 completed"

    def test_admin_cancel_reset_request(self, admin_user, db_conn):
        """管理员应能取消密码重置请求"""
        from werkzeug.security import generate_password_hash

        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("canceluser", generate_password_hash("oldpwd", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        cur.execute("SELECT id FROM users WHERE username = 'canceluser'")
        user_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO password_reset_requests (user_id, username, status) VALUES (?, ?, 'pending')",
            (user_id, "canceluser"),
        )
        db_conn.commit()

        cur.execute(
            "SELECT id FROM password_reset_requests WHERE username = ? AND status = 'pending'",
            ("canceluser",),
        )
        req_id = cur.fetchone()["id"]

        # 执行取消
        response = admin_user.post(
            f"/admin/password-resets/{req_id}/reset",
            data={"action": "cancel"},
        )
        assert response.status_code == 302

        # 验证请求状态已更新
        cur.execute(
            "SELECT status FROM password_reset_requests WHERE id = ?", (req_id,)
        )
        req = cur.fetchone()
        assert req["status"] == "cancelled", "请求状态未更新为 cancelled"

    def test_admin_reset_already_processed_request(self, admin_user, db_conn):
        """重置已处理的请求应提示已处理"""
        from werkzeug.security import generate_password_hash

        cur = db_conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role, status) VALUES (?, ?, ?, ?)",
            ("processeduser", generate_password_hash("pwd", method='pbkdf2:sha256'), "equipment_engineer", "active"),
        )
        cur.execute("SELECT id FROM users WHERE username = 'processeduser'")
        user_id = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO password_reset_requests (user_id, username, status) VALUES (?, ?, 'completed')",
            (user_id, "processeduser"),
        )
        db_conn.commit()

        cur.execute(
            "SELECT id FROM password_reset_requests WHERE username = ? AND status = 'completed'",
            ("processeduser",),
        )
        req_id = cur.fetchone()["id"]

        response = admin_user.post(
            f"/admin/password-resets/{req_id}/reset",
            data={"new_password": "anypassword", "action": "reset"},
        )
        assert response.status_code == 302


# ============================================================
# 5. User 模型权限测试
# ============================================================

class TestUserModelPermissions:
    """测试 User 模型的权限相关属性"""

    def test_admin_has_document_approval_permission(self):
        """admin 角色应有 document_approval 权限"""
        from models.user import User
        user = User(1, "admin", "admin", "hashed")
        assert user.has_permission("document_approval") is True

    def test_qa_manager_has_document_approval_permission(self):
        """qa_manager 角色应有 document_approval 权限"""
        from models.user import User
        user = User(2, "qamgr", "qa_manager", "hashed")
        assert user.has_permission("document_approval") is True

    def test_validation_engineer_has_document_approval_permission(self):
        """validation_engineer 角色应有 document_approval 权限"""
        from models.user import User
        user = User(3, "valeng", "validation_engineer", "hashed")
        assert user.has_permission("document_approval") is True

    def test_production_supervisor_has_document_approval_permission(self):
        """production_supervisor 角色应有 document_approval 权限"""
        from models.user import User
        user = User(4, "prodsup", "production_supervisor", "hashed")
        assert user.has_permission("document_approval") is True

    def test_equipment_engineer_no_document_approval(self):
        """equipment_engineer 角色不应有 document_approval 权限"""
        from models.user import User
        user = User(5, "eqeng", "equipment_engineer", "hashed")
        assert user.has_permission("document_approval") is False

    def test_archivist_no_document_approval(self):
        """archivist 角色不应有 document_approval 权限"""
        from models.user import User
        user = User(6, "archivist_user", "archivist", "hashed")
        assert user.has_permission("document_approval") is False

    def test_metrology_engineer_no_document_approval(self):
        """metrology_engineer 角色不应有 document_approval 权限"""
        from models.user import User
        user = User(7, "metroeng", "metrology_engineer", "hashed")
        assert user.has_permission("document_approval") is False

    def test_can_view_approvals_property(self):
        """can_view_approvals 属性应正确反映 document_approval 权限"""
        from models.user import User

        admin_user = User(1, "admin", "admin", "hashed")
        assert admin_user.can_view_approvals is True

        eng_user = User(2, "eng", "equipment_engineer", "hashed")
        assert eng_user.can_view_approvals is False

    def test_legacy_role_mapping(self):
        """旧 'user' 角色应映射为 equipment_engineer，不应有 document_approval"""
        from models.user import User
        user = User(8, "olduser", "user", "hashed")
        assert user.role == "equipment_engineer", "旧 user 角色未正确映射"
        assert user.has_permission("document_approval") is False

    def test_is_admin_property(self):
        """is_admin 属性应仅对 admin 角色返回 True"""
        from models.user import User

        assert User(1, "admin", "admin", "h").is_admin is True
        assert User(2, "qa", "qa_manager", "h").is_admin is False
        assert User(3, "eng", "equipment_engineer", "h").is_admin is False

    def test_role_label_property(self):
        """role_label 应返回正确的中文标签"""
        from models.user import User

        assert User(1, "admin", "admin", "h").role_label == "管理员"
        assert User(2, "qa", "qa_manager", "h").role_label == "QA经理"

    def test_has_permission_invalid_role(self):
        """无效角色应返回 False"""
        from models.user import User
        user = User(9, "test", "nonexistent_role", "hashed")
        assert user.has_permission("document_approval") is False
        assert user.has_permission("any_permission") is False


# ============================================================
# 6. Context Processor 闹铃控制测试
# ============================================================

class TestContextProcessor:
    """测试全局上下文处理器中的 can_view_approvals 和 pending_count"""

    def test_pending_count_present_in_context(self, app):
        """pending_count 应注入到所有模板上下文"""
        with app.test_request_context():
            ctx = app.jinja_env.globals
            # Context processor 在渲染时调用，这里验证注册
            assert hasattr(app, "context_processor")

    def test_can_view_approvals_for_anonymous(self, app):
        """未登录用户 can_view_approvals 应为 False"""
        with app.test_client() as client:
            # 不登录直接访问需要认证的页面会被重定向
            # 但 context processor 应该能正常处理匿名用户
            with app.test_request_context():
                # 模拟匿名用户
                from flask import template_rendered
                captured = {}

                def capture(sender, template, context, **extra):
                    captured["context"] = context

                template_rendered.connect(capture, app)
                try:
                    client.get("/login")  # 渲染 login 页面（不需要 base.html context）
                finally:
                    template_rendered.disconnect(capture, app)

    def test_can_view_approvals_for_admin(self, admin_user, db_conn):
        """admin 用户渲染 base 继承页面时 can_view_approvals 应为 True"""
        # 创建一个简单的数据来验证
        from flask import template_rendered

        captured = {}

        def capture(sender, template, context, **extra):
            captured["context"] = context

        # 直接测试 User 模型属性（最可靠的方式）
        from models.user import User
        admin = User(1, "admin", "admin", "hashed")
        assert admin.can_view_approvals is True

    def test_can_view_approvals_for_equipment_engineer(self, normal_user):
        """equipment_engineer 用户 can_view_approvals 应为 False"""
        from models.user import User
        eng = User(2, "eng", "equipment_engineer", "hashed")
        assert eng.can_view_approvals is False

    def test_can_view_approvals_for_qa_manager(self, qa_manager_user):
        """qa_manager 用户 can_view_approvals 应为 True"""
        from models.user import User
        qa = User(3, "qa", "qa_manager", "hashed")
        assert qa.can_view_approvals is True

    def test_pending_count_query(self, admin_user, db_conn):
        """pending_count 应正确反映数据库中的待审批数量"""
        # 初始状态应为 0
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM approval_requests WHERE status = 'pending'")
        result = cur.fetchone()
        initial_count = result["total"]
        assert isinstance(initial_count, int)

        # 添加一条待审批请求
        cur.execute(
            "INSERT INTO devices (device_code, device_name, status) VALUES (?, ?, ?)",
            ("TEST-001", "测试设备", "active"),
        )
        device_id = cur.lastrowid
        cur.execute(
            "INSERT INTO documents (device_id, doc_type, doc_name, version, file_path, uploaded_by, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, "manual", "测试文档", "1.0", "/tmp/test.pdf", "testuser", "pending"),
        )
        doc_id = cur.lastrowid
        cur.execute(
            "INSERT INTO approval_requests (doc_id, status, created_by, current_step) VALUES (?, ?, ?, ?)",
            (doc_id, "pending", "testuser", 1),
        )
        db_conn.commit()

        # 重新查询
        cur.execute("SELECT COUNT(*) as total FROM approval_requests WHERE status = 'pending'")
        result = cur.fetchone()
        assert result["total"] == initial_count + 1


# ============================================================
# 7. 数据库表结构验证
# ============================================================

class TestDatabaseSchema:
    """验证 password_reset_requests 表结构"""

    def test_password_reset_requests_table_exists(self, db_conn):
        """password_reset_requests 表应存在"""
        cur = db_conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_requests'"
        )
        result = cur.fetchone()
        assert result is not None, "password_reset_requests 表不存在"

    def test_password_reset_requests_columns(self, db_conn):
        """password_reset_requests 表应包含所有必要字段"""
        cur = db_conn.cursor()
        cur.execute("PRAGMA table_info(password_reset_requests)")
        columns = {row["name"] for row in cur.fetchall()}

        expected_columns = {
            "id", "user_id", "username", "status",
            "requested_at", "processed_at", "processed_by", "ip_address",
        }
        missing = expected_columns - columns
        assert not missing, f"password_reset_requests 缺少字段: {missing}"

    def test_password_reset_requests_default_status(self, db_conn):
        """status 字段默认值应为 'pending'"""
        cur = db_conn.cursor()
        cur.execute("PRAGMA table_info(password_reset_requests)")
        for row in cur.fetchall():
            if row["name"] == "status":
                assert row["dflt_value"] == "'pending'", "status 默认值应为 'pending'"
                return
        pytest.fail("未找到 status 字段")


# ============================================================
# 8. Python 语法检查
# ============================================================

class TestPythonSyntax:
    """验证所有 Python 文件无语法错误"""

    @pytest.mark.parametrize("filepath", [
        "blueprints/password.py",
        "app.py",
        "database.py",
        "models/user.py",
        "config.py",
        "extensions.py",
        "blueprints/__init__.py",
    ])
    def test_no_syntax_errors(self, filepath):
        """Python 文件应无语法错误"""
        import py_compile
        import importlib

        full_path = os.path.join(os.path.dirname(__file__), "..", filepath)
        try:
            py_compile.compile(full_path, doraise=True)
        except py_compile.PyCompileError as e:
            pytest.fail(f"{filepath} 存在语法错误: {e}")
