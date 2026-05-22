# 电子签名模块测试 - 21 CFR Part 11 合规验证
import pytest

from app import create_app
from database import get_db


@pytest.fixture
def app():
    """创建测试用 Flask 应用"""
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """已登录的测试客户端（管理员）"""
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=True)
    return client


@pytest.fixture
def cleanup_esignatures():
    """清理测试产生的电子签名记录"""
    yield
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM electronic_signatures WHERE remark LIKE '%pytest%'")
    conn.commit()
    conn.close()


class TestEsignVerifyAPI:
    """电子签名验证接口测试"""

    def test_verify_success(self, auth_client, cleanup_esignatures):
        """正确用户名+密码 → 签名成功"""
        resp = auth_client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "admin123",
                "record_type": "document",
                "record_id": 1,
                "sign_meaning": "approved",
                "remark": "pytest: 签名成功测试",
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "signature_id" in data
        assert isinstance(data["signature_id"], int)

    def test_verify_wrong_password(self, auth_client):
        """错误密码 → 401"""
        resp = auth_client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "wrongpassword",
                "record_type": "document",
                "record_id": 1,
                "sign_meaning": "approved",
            },
        )
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["success"] is False
        assert "密码" in data["message"] or "失败" in data["message"]

    def test_verify_impersonation(self, auth_client):
        """代签检测：提交的用户名与当前登录用户不一致 → 403"""
        resp = auth_client.post(
            "/esign/api/verify",
            json={
                "username": "other_user",
                "password": "anypassword",
                "record_type": "document",
                "record_id": 1,
                "sign_meaning": "approved",
            },
        )
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        assert "代签" in data["message"] or "不一致" in data["message"]

    def test_verify_missing_fields(self, auth_client):
        """缺少必填字段 → 400"""
        resp = auth_client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "admin123",
                # 缺少 record_type, record_id, sign_meaning
            },
        )
        assert resp.status_code == 400

    def test_verify_invalid_meaning(self, auth_client):
        """签名含义无效 → 400"""
        resp = auth_client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "admin123",
                "record_type": "document",
                "record_id": 1,
                "sign_meaning": "invalid_meaning",
            },
        )
        assert resp.status_code == 400

    def test_verify_not_logged_in(self, client):
        """未登录 → 302 重定向到登录页"""
        resp = client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "admin123",
                "record_type": "document",
                "record_id": 1,
                "sign_meaning": "approved",
            },
        )
        # Flask-Login 未登录时重定向
        assert resp.status_code in (302, 401)


class TestEsignLockout:
    """签名失败锁定机制测试"""

    def test_lockout_after_3_failures(self, auth_client):
        """连续3次错误密码后锁定"""
        for i in range(3):
            resp = auth_client.post(
                "/esign/api/verify",
                json={
                    "username": "admin",
                    "password": "wrongpassword",
                    "record_type": "document",
                    "record_id": 1,
                    "sign_meaning": "approved",
                },
            )
        # 第3次应该返回429（锁定）
        assert resp.status_code == 429
        data = resp.get_json()
        assert data["success"] is False
        assert "锁定" in data["message"]


class TestEsignRecordsAPI:
    """签名记录 API 测试"""

    def test_get_record_signatures(self, auth_client, cleanup_esignatures):
        """查看某业务记录的签名历史"""
        # 先创建一条签名
        auth_client.post(
            "/esign/api/verify",
            json={
                "username": "admin",
                "password": "admin123",
                "record_type": "document",
                "record_id": 999,
                "sign_meaning": "reviewed",
                "remark": "pytest: 历史查询测试",
            },
        )
        # 查询签名历史
        resp = auth_client.get("/esign/records/document/999")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "signatures" in data
        assert len(data["signatures"]) >= 1
        sig = data["signatures"][0]
        assert sig["signed_by"] == "admin"
        assert sig["sign_meaning"] == "reviewed"


class TestEsignRecordsPage:
    """签名记录管理页面测试"""

    def test_records_page_admin(self, auth_client):
        """管理员可访问签名记录页面"""
        resp = auth_client.get("/esign/records")
        assert resp.status_code == 200
        assert "电子签名" in resp.data.decode("utf-8")

    def test_records_page_with_filter(self, auth_client):
        """筛选参数正确传递"""
        resp = auth_client.get("/esign/records?record_type=document&sign_meaning=approved")
        assert resp.status_code == 200

    def test_records_page_not_logged_in(self, client):
        """未登录无法访问签名记录页面"""
        resp = client.get("/esign/records", follow_redirects=False)
        assert resp.status_code in (302, 401)


class TestEsignModel:
    """电子签名 Model 测试"""

    def test_save_and_get(self, cleanup_esignatures):
        """新增签名记录并查询"""
        from models.electronic_signature import ElectronicSignature

        sig = ElectronicSignature(
            record_type="maintenance_plan",
            record_id=1,
            signed_by="pytest_user",
            signed_by_display="测试用户",
            sign_meaning="approved",
            sign_meaning_label="批准",
            ip_address="127.0.0.1",
            remark="pytest: Model测试",
        )
        result = sig.save()
        assert result.id is not None

        # 查询
        records = ElectronicSignature.get_by_record("maintenance_plan", 1)
        assert len(records) >= 1
        found = [r for r in records if r.remark == "pytest: Model测试"]
        assert len(found) == 1
        assert found[0].signed_by == "pytest_user"

    def test_model_no_update_method(self):
        """Model 没有 update 或 delete 方法（审计要求）"""
        from models.electronic_signature import ElectronicSignature

        assert not hasattr(ElectronicSignature, "update")
        assert not hasattr(ElectronicSignature, "delete")
        assert not hasattr(ElectronicSignature, "update_with_cursor")

    def test_get_all_pagination(self, cleanup_esignatures):
        """分页查询测试"""
        from models.electronic_signature import ElectronicSignature

        records, pagination = ElectronicSignature.get_all(page=1, per_page=5)
        assert pagination["page"] == 1
        assert pagination["per_page"] == 5
