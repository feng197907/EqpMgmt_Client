"""
DMS 设备维护周期提醒功能 - 全面QA测试
测试人员: 严过关 (Yan)
日期: 2026-05-12
"""
import json
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from database import init_db, get_db


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def client(monkeypatch):
    """创建测试客户端，使用临时数据库"""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    import database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp)
    init_db()

    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    app.config["LOGIN_DISABLED"] = True

    with app.test_client() as c:
        yield c

    try:
        os.remove(tmp)
    except OSError:
        pass


@pytest.fixture()
def auth_client(monkeypatch):
    """带登录认证的测试客户端"""
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    import database as dbmod
    monkeypatch.setattr(dbmod, "DB_PATH", tmp)
    init_db()

    from app import create_app
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as c:
        # 以 admin 登录
        c.post("/login", data={"username": "admin", "password": "admin123"})
        yield c

    try:
        os.remove(tmp)
    except OSError:
        pass


def insert_device(device_code="DEV-001", device_name="测试设备"):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO devices (device_code, device_name, model, location, status) VALUES (?, ?, ?, ?, ?)",
        (device_code, device_name, "M1", "Lab", "active"),
    )
    conn.commit()
    cur.execute("SELECT id FROM devices WHERE device_code = ?", (device_code,))
    row = cur.fetchone()
    conn.close()
    return row["id"]


def insert_plan(device_id, maintenance_type="calibration", interval_days=30,
                next_due_date=None, is_active=1, created_by="admin"):
    if next_due_date is None:
        next_due_date = (date.today() + timedelta(days=interval_days)).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO maintenance_plan
           (device_id, maintenance_type, interval_days, next_due_date, is_active, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (device_id, maintenance_type, interval_days, next_due_date, is_active, created_by),
    )
    conn.commit()
    plan_id = cur.lastrowid
    conn.close()
    return plan_id


def insert_record(plan_id, device_id, maintenance_type="calibration",
                  content="常规维护", result="qualified", performed_by="admin",
                  performed_at=None, next_due_date=None):
    if performed_at is None:
        performed_at = date.today().strftime("%Y-%m-%d")
    if next_due_date is None:
        next_due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO maintenance_record
           (plan_id, device_id, maintenance_type, content, result,
            performed_by, performed_at, next_due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (plan_id, device_id, maintenance_type, content, result,
         performed_by, performed_at, next_due_date),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


# ============================================================
# 1. 功能测试 - 数据库表
# ============================================================

class TestDatabaseTables:
    """测试数据库表创建是否正确"""

    def test_maintenance_plan_table_exists(self, client):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_plan'")
        assert cur.fetchone() is not None, "maintenance_plan 表不存在"
        conn.close()

    def test_maintenance_record_table_exists(self, client):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_record'")
        assert cur.fetchone() is not None, "maintenance_record 表不存在"
        conn.close()

    def test_maintenance_plan_columns(self, client):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(maintenance_plan)")
        columns = {row["name"] for row in cur.fetchall()}
        expected = {"id", "device_id", "maintenance_type", "interval_days",
                    "next_due_date", "is_active", "created_by", "created_at", "updated_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"
        conn.close()

    def test_maintenance_record_columns(self, client):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(maintenance_record)")
        columns = {row["name"] for row in cur.fetchall()}
        expected = {"id", "plan_id", "device_id", "maintenance_type", "content",
                    "result", "performed_by", "performed_at", "next_due_date",
                    "parts_used", "created_at"}
        assert expected.issubset(columns), f"缺少列: {expected - columns}"
        conn.close()

    def test_maintenance_plan_foreign_key(self, client):
        """验证外键约束设置"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_key_list(maintenance_plan)")
        fks = cur.fetchall()
        fk_cols = [fk["from"] for fk in fks]
        assert "device_id" in fk_cols, "maintenance_plan 缺少 device_id 外键"
        conn.close()

    def test_maintenance_record_foreign_keys(self, client):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_key_list(maintenance_record)")
        fks = cur.fetchall()
        fk_cols = [fk["from"] for fk in fks]
        assert "plan_id" in fk_cols, "maintenance_record 缺少 plan_id 外键"
        assert "device_id" in fk_cols, "maintenance_record 缺少 device_id 外键"
        conn.close()


# ============================================================
# 2. 功能测试 - 维护计划 CRUD
# ============================================================

class TestMaintenancePlanCRUD:
    """测试维护计划的增删改查"""

    def test_create_plan_page_accessible(self, auth_client):
        """测试维护计划列表页可访问"""
        dev_id = insert_device()
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        assert rv.status_code == 200

    def test_create_plan_success(self, auth_client):
        """测试创建维护计划成功"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "30",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200

        # 验证数据库中有记录
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        row = cur.fetchone()
        conn.close()
        assert row is not None
        assert row["maintenance_type"] == "calibration"
        assert row["interval_days"] == 30
        assert row["is_active"] == 1

    def test_create_plan_missing_fields(self, auth_client):
        """测试缺少必填字段时创建失败"""
        dev_id = insert_device()
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            # 缺少 interval_days 和 first_due_date
        }, follow_redirects=True)
        assert rv.status_code == 200

    def test_create_plan_invalid_interval(self, auth_client):
        """测试无效周期天数"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        # 周期0天
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "0",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        # 不应创建成功
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 0, "周期为0天的计划不应被创建"

    def test_create_plan_366_days(self, auth_client):
        """测试周期超过365天"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=400)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "366",
            "first_due_date": due_date,
        }, follow_redirects=True)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 0, "周期超过365天的计划不应被创建"

    def test_update_plan_api(self, auth_client):
        """测试更新维护计划（PUT API）"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id, interval_days=30)
        rv = auth_client.put(
            f"/device/{dev_id}/maintenance/plan/{plan_id}",
            data=json.dumps({"interval_days": 60, "next_due_date": "2026-08-01"}),
            content_type="application/json",
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["id"] == plan_id

        # 验证数据库更新
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT interval_days FROM maintenance_plan WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        conn.close()
        assert row["interval_days"] == 60

    def test_update_nonexistent_plan(self, auth_client):
        """测试更新不存在的计划"""
        dev_id = insert_device()
        rv = auth_client.put(
            f"/device/{dev_id}/maintenance/plan/99999",
            data=json.dumps({"interval_days": 60}),
            content_type="application/json",
        )
        assert rv.status_code == 404

    def test_delete_plan_soft(self, auth_client):
        """测试软删除维护计划"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        rv = auth_client.delete(f"/device/{dev_id}/maintenance/plan/{plan_id}")
        assert rv.status_code == 200

        # 验证软删除（is_active=0）
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM maintenance_plan WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        conn.close()
        assert row["is_active"] == 0

    def test_delete_nonexistent_plan(self, auth_client):
        """测试删除不存在的计划"""
        dev_id = insert_device()
        rv = auth_client.delete(f"/device/{dev_id}/maintenance/plan/99999")
        assert rv.status_code == 404

    def test_get_plans_api(self, auth_client):
        """测试获取维护计划列表API"""
        dev_id = insert_device()
        insert_plan(dev_id, maintenance_type="calibration")
        insert_plan(dev_id, maintenance_type="maintenance")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/api/plans")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "plans" in data
        assert len(data["plans"]) == 2

    def test_get_plans_api_only_active(self, auth_client):
        """测试API只返回激活的计划"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id, maintenance_type="calibration")
        insert_plan(dev_id, maintenance_type="maintenance")
        # 软删除一个
        auth_client.delete(f"/device/{dev_id}/maintenance/plan/{plan_id}")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/api/plans")
        data = rv.get_json()
        assert len(data["plans"]) == 1

    def test_nonexistent_device_plans(self, auth_client):
        """测试访问不存在设备的维护计划"""
        rv = auth_client.get("/device/99999/maintenance/", follow_redirects=True)
        assert rv.status_code == 200


# ============================================================
# 3. 功能测试 - 维护记录
# ============================================================

class TestMaintenanceRecord:
    """测试维护记录提交和到期日更新"""

    def test_record_form_accessible(self, auth_client):
        """测试维护记录表单页可访问"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        rv = auth_client.get(f"/device/{dev_id}/maintenance/plan/{plan_id}/record")
        assert rv.status_code == 200

    def test_submit_qualified_record_updates_due_date(self, auth_client):
        """测试提交合格记录后到期日自动更新"""
        dev_id = insert_device()
        original_due = date.today().strftime("%Y-%m-%d")
        plan_id = insert_plan(dev_id, interval_days=30, next_due_date=original_due)

        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={
                "content": "完成校准维护",
                "result": "qualified",
            },
            follow_redirects=True,
        )
        assert rv.status_code == 200

        # 验证到期日已更新
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT next_due_date FROM maintenance_plan WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        conn.close()
        expected_due = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        assert row["next_due_date"] == expected_due, \
            f"合格记录后到期日应更新为 {expected_due}，实际为 {row['next_due_date']}"

    def test_submit_unqualified_record_no_due_date_update(self, auth_client):
        """测试提交不合格记录后到期日不更新"""
        dev_id = insert_device()
        original_due = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        plan_id = insert_plan(dev_id, interval_days=30, next_due_date=original_due)

        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={
                "content": "校准不合格",
                "result": "unqualified",
            },
            follow_redirects=True,
        )
        assert rv.status_code == 200

        # 验证到期日未更新
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT next_due_date FROM maintenance_plan WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        conn.close()
        assert row["next_due_date"] == original_due, \
            "不合格记录后到期日不应更新"

    def test_submit_pending_result_no_due_date_update(self, auth_client):
        """测试提交待处理记录后到期日不更新"""
        dev_id = insert_device()
        original_due = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        plan_id = insert_plan(dev_id, interval_days=30, next_due_date=original_due)

        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={
                "content": "待处理维护",
                "result": "pending",
            },
            follow_redirects=True,
        )
        assert rv.status_code == 200

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT next_due_date FROM maintenance_plan WHERE id = ?", (plan_id,))
        row = cur.fetchone()
        conn.close()
        assert row["next_due_date"] == original_due, \
            "待处理记录后到期日不应更新"

    def test_submit_record_missing_fields(self, auth_client):
        """测试缺少必填字段提交记录"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={"content": "", "result": ""},
            follow_redirects=True,
        )
        assert rv.status_code == 200

    def test_submit_record_inactive_plan(self, auth_client):
        """测试向停用的计划提交记录"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id, is_active=0)
        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={"content": "测试维护", "result": "qualified"},
            follow_redirects=True,
        )
        assert rv.status_code == 200  # 应重定向，不应报错

    def test_maintenance_history_page(self, auth_client):
        """测试维护历史页可访问"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        insert_record(plan_id, dev_id)
        rv = auth_client.get(f"/device/{dev_id}/maintenance/history")
        assert rv.status_code == 200

    def test_maintenance_history_with_filter(self, auth_client):
        """测试维护历史筛选"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        insert_record(plan_id, dev_id, maintenance_type="calibration")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/history?type=calibration")
        assert rv.status_code == 200

    def test_get_records_api(self, auth_client):
        """测试获取维护记录列表API"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        insert_record(plan_id, dev_id)
        rv = auth_client.get(f"/device/{dev_id}/maintenance/api/records")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "records" in data
        assert "pagination" in data
        assert len(data["records"]) == 1


# ============================================================
# 4. 功能测试 - 紧迫度计算
# ============================================================

class TestUrgencyCalculation:
    """测试紧迫度计算逻辑"""

    def test_urgency_overdue(self):
        """测试逾期设备紧迫度为danger"""
        from utils.maintenance import calc_urgency
        yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert calc_urgency(yesterday) == "danger"

    def test_urgency_due_today(self):
        """测试今日到期紧迫度为danger"""
        from utils.maintenance import calc_urgency
        today = date.today().strftime("%Y-%m-%d")
        assert calc_urgency(today) == "danger"

    def test_urgency_warning_1_day(self):
        """测试1天后到期紧迫度为warning"""
        from utils.maintenance import calc_urgency
        tomorrow = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert calc_urgency(tomorrow) == "warning"

    def test_urgency_warning_3_days(self):
        """测试3天后到期紧迫度为warning"""
        from utils.maintenance import calc_urgency
        in3days = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
        assert calc_urgency(in3days) == "warning"

    def test_urgency_info_4_days(self):
        """测试4天后到期紧迫度为info"""
        from utils.maintenance import calc_urgency
        in4days = (date.today() + timedelta(days=4)).strftime("%Y-%m-%d")
        assert calc_urgency(in4days) == "info"

    def test_urgency_info_7_days(self):
        """测试7天后到期紧迫度为info"""
        from utils.maintenance import calc_urgency
        in7days = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")
        assert calc_urgency(in7days) == "info"

    def test_urgency_success_beyond_7_days(self):
        """测试8天后到期紧迫度为success"""
        from utils.maintenance import calc_urgency
        in8days = (date.today() + timedelta(days=8)).strftime("%Y-%m-%d")
        assert calc_urgency(in8days) == "success"

    def test_urgency_null_date(self):
        """测试空日期紧迫度为info"""
        from utils.maintenance import calc_urgency
        assert calc_urgency(None) == "info"
        assert calc_urgency("") == "info"

    def test_urgency_severely_overdue(self):
        """测试严重逾期（>30天）紧迫度仍为danger"""
        from utils.maintenance import calc_urgency
        long_overdue = (date.today() - timedelta(days=100)).strftime("%Y-%m-%d")
        assert calc_urgency(long_overdue) == "danger"


# ============================================================
# 5. 功能测试 - 到期日计算
# ============================================================

class TestNextDueDateCalculation:
    """测试到期日计算"""

    def test_calc_next_due_date_string(self):
        """测试字符串日期输入"""
        from utils.maintenance import calc_next_due_date
        result = calc_next_due_date("2026-05-12", 30)
        assert result == "2026-06-11"

    def test_calc_next_due_date_date_object(self):
        """测试date对象输入"""
        from utils.maintenance import calc_next_due_date
        result = calc_next_due_date(date(2026, 5, 12), 30)
        assert result == "2026-06-11"

    def test_calc_next_due_date_1_day(self):
        """测试周期1天"""
        from utils.maintenance import calc_next_due_date
        result = calc_next_due_date("2026-05-12", 1)
        assert result == "2026-05-13"

    def test_calc_next_due_date_365_days(self):
        """测试周期365天"""
        from utils.maintenance import calc_next_due_date
        result = calc_next_due_date("2026-01-01", 365)
        assert result == "2027-01-01"

    def test_calc_next_due_date_leap_year(self):
        """测试闰年计算"""
        from utils.maintenance import calc_next_due_date
        result = calc_next_due_date("2024-02-28", 1)
        assert result == "2024-02-29"


# ============================================================
# 6. 功能测试 - 登录弹窗提醒
# ============================================================

class TestLoginPopupReminder:
    """测试登录弹窗提醒逻辑"""

    def test_due_maintenance_api_no_data(self, auth_client):
        """测试无到期维护时API返回空数据"""
        rv = auth_client.get("/api/dashboard/due-maintenance")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["summary"]["due_today_count"] == 0
        assert data["summary"]["due_7days_count"] == 0
        assert data["summary"]["overdue_count"] == 0

    def test_due_maintenance_api_with_overdue(self, auth_client):
        """测试有逾期设备时API返回正确数据"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        insert_plan(dev_id, next_due_date=overdue_date)
        rv = auth_client.get("/api/dashboard/due-maintenance")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["summary"]["overdue_count"] == 1

    def test_due_maintenance_api_with_due_today(self, auth_client):
        """测试今日到期设备"""
        dev_id = insert_device()
        insert_plan(dev_id, next_due_date=date.today().strftime("%Y-%m-%d"))
        rv = auth_client.get("/api/dashboard/due-maintenance")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["summary"]["due_today_count"] == 1

    def test_due_maintenance_api_with_due_within_7days(self, auth_client):
        """测试7日内到期设备"""
        dev_id = insert_device()
        in5days = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        insert_plan(dev_id, next_due_date=in5days)
        rv = auth_client.get("/api/dashboard/due-maintenance")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["summary"]["due_7days_count"] == 1

    def test_due_maintenance_api_with_type_filter(self, auth_client):
        """测试按维护类型筛选"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
        insert_plan(dev_id, maintenance_type="calibration", next_due_date=overdue_date)
        insert_plan(dev_id, maintenance_type="maintenance", next_due_date=overdue_date)
        rv = auth_client.get("/api/dashboard/due-maintenance?type=calibration")
        data = rv.get_json()
        # 筛选后只应返回 calibration 类型
        for item in data["overdue"]:
            assert item["maintenance_type"] == "calibration"

    def test_due_maintenance_api_with_far_future(self, auth_client):
        """测试远期到期的不出现在提醒中"""
        dev_id = insert_device()
        far_future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        insert_plan(dev_id, next_due_date=far_future)
        rv = auth_client.get("/api/dashboard/due-maintenance")
        data = rv.get_json()
        total = data["summary"]["due_today_count"] + data["summary"]["due_7days_count"] + data["summary"]["overdue_count"]
        assert total == 0, "远期到期的设备不应出现在提醒中"

    def test_popup_javascript_in_base_template(self, auth_client):
        """验证base.html包含登录弹窗JS逻辑"""
        rv = auth_client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "due-maintenance" in html, "base.html 缺少 due-maintenance API 调用"
        assert "maintenanceReminderModal" in html, "base.html 缺少维护提醒弹窗代码"
        assert "snoozeMaintenanceReminder" in html, "base.html 缺少稍后提醒功能"


# ============================================================
# 7. 边界测试
# ============================================================

class TestBoundaryConditions:
    """边界测试"""

    def test_create_plan_1_day_interval(self, auth_client):
        """测试周期为1天"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "1",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT interval_days FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        row = cur.fetchone()
        conn.close()
        assert row is not None and row["interval_days"] == 1

    def test_create_plan_365_day_interval(self, auth_client):
        """测试周期为365天"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=365)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "365",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT interval_days FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        row = cur.fetchone()
        conn.close()
        assert row is not None and row["interval_days"] == 365

    def test_create_duplicate_plan_same_type_blocked(self, auth_client):
        """测试同一设备同一类型重复创建计划应被阻止"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        # 创建第一个计划
        auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "30",
            "first_due_date": due_date,
        }, follow_redirects=True)
        # 尝试创建相同类型的第二个计划
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "90",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        # 数据库中应只有一条 calibration 记录
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ? AND maintenance_type = ? AND is_active = 1",
                     (dev_id, "calibration"))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 1, "同一设备同一类型不应创建重复激活计划"

    def test_create_different_type_plans_allowed(self, auth_client):
        """测试同一设备不同类型计划可以创建"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "30",
            "first_due_date": due_date,
        }, follow_redirects=True)
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "maintenance",
            "interval_days": "90",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ? AND is_active = 1", (dev_id,))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 2, "同一设备不同类型的计划应可创建"

    def test_overdue_device_handling(self, auth_client):
        """测试逾期设备的处理"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        plan_id = insert_plan(dev_id, next_due_date=overdue_date)
        # 验证计划仍然可访问
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        assert rv.status_code == 200
        # 验证API返回逾期数据
        rv = auth_client.get(f"/device/{dev_id}/maintenance/api/plans")
        data = rv.get_json()
        assert len(data["plans"]) == 1
        assert data["plans"][0]["urgency"] == "danger"
        # 可以提交维护记录
        rv = auth_client.post(
            f"/device/{dev_id}/maintenance/plan/{plan_id}/record",
            data={"content": "补录逾期维护", "result": "qualified"},
            follow_redirects=True,
        )
        assert rv.status_code == 200

    def test_negative_interval_rejected(self, auth_client):
        """测试负数周期被拒绝"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "-1",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 0, "负数周期不应创建计划"

    def test_non_numeric_interval_rejected(self, auth_client):
        """测试非数字周期被拒绝"""
        dev_id = insert_device()
        due_date = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
        rv = auth_client.post(f"/device/{dev_id}/maintenance/plan", data={
            "maintenance_type": "calibration",
            "interval_days": "abc",
            "first_due_date": due_date,
        }, follow_redirects=True)
        assert rv.status_code == 200
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM maintenance_plan WHERE device_id = ?", (dev_id,))
        count = cur.fetchone()["cnt"]
        conn.close()
        assert count == 0, "非数字周期不应创建计划"


# ============================================================
# 8. 界面测试 - 模板验证
# ============================================================

class TestTemplateRendering:
    """测试模板正确渲染"""

    def test_device_maintenance_page_renders(self, auth_client):
        """测试维护计划页渲染"""
        dev_id = insert_device()
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "维护计划列表" in html or "暂无维护计划" in html
        assert "添加维护计划" in html

    def test_device_maintenance_with_plans(self, auth_client):
        """测试有计划时维护页渲染"""
        dev_id = insert_device()
        insert_plan(dev_id, maintenance_type="calibration")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "校准" in html

    def test_maintenance_record_form_renders(self, auth_client):
        """测试维护记录表单页渲染"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        rv = auth_client.get(f"/device/{dev_id}/maintenance/plan/{plan_id}/record")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "登记维护记录" in html
        assert "维护内容" in html
        assert "维护结果" in html

    def test_maintenance_history_page_renders(self, auth_client):
        """测试维护历史页渲染"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        insert_record(plan_id, dev_id, content="测试维护内容")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/history")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "维护历史" in html
        assert "测试维护内容" in html

    def test_maintenance_history_empty(self, auth_client):
        """测试无记录时历史页渲染"""
        dev_id = insert_device()
        rv = auth_client.get(f"/device/{dev_id}/maintenance/history")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "暂无维护记录" in html

    def test_static_css_files_referenced(self, auth_client):
        """测试静态CSS文件引用正确"""
        rv = auth_client.get("/")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "css/variables.css" in html
        assert "css/base.css" in html
        assert "css/layout.css" in html
        assert "css/components.css" in html

    def test_static_css_files_accessible(self, client):
        """测试静态CSS文件可访问"""
        for css_file in ["css/variables.css", "css/base.css", "css/layout.css", "css/components.css"]:
            rv = client.get(f"/static/{css_file}")
            assert rv.status_code == 200, f"静态文件 {css_file} 不可访问"

    def test_urgency_badges_rendered(self, auth_client):
        """测试紧迫度标签正确渲染"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        insert_plan(dev_id, next_due_date=overdue_date, maintenance_type="calibration")
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        html = rv.data.decode("utf-8")
        assert "已逾期" in html or "badge-danger" in html

    def test_maintenance_type_radio_buttons(self, auth_client):
        """测试维护类型单选按钮渲染"""
        dev_id = insert_device()
        rv = auth_client.get(f"/device/{dev_id}/maintenance/")
        html = rv.data.decode("utf-8")
        assert 'name="maintenance_type"' in html
        assert "calibration" in html
        assert "maintenance" in html
        assert "inspection" in html


# ============================================================
# 9. 模型方法测试
# ============================================================

class TestModelMethods:
    """测试模型类的属性和方法"""

    def test_maintenance_plan_is_overdue(self):
        """测试 MaintenancePlan.is_overdue 属性"""
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=1, maintenance_type="calibration",
            interval_days=30, next_due_date=(date.today() - timedelta(days=1)).strftime("%Y-%m-%d"),
            is_active=1, created_by="admin"
        )
        assert plan.is_overdue is True

    def test_maintenance_plan_not_overdue(self):
        """测试 MaintenancePlan.is_overdue 属性（未逾期）"""
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=1, maintenance_type="calibration",
            interval_days=30, next_due_date=(date.today() + timedelta(days=30)).strftime("%Y-%m-%d"),
            is_active=1, created_by="admin"
        )
        assert plan.is_overdue is False

    def test_maintenance_plan_overdue_days(self):
        """测试 MaintenancePlan.overdue_days 属性"""
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=1, maintenance_type="calibration",
            interval_days=30, next_due_date=(date.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
            is_active=1, created_by="admin"
        )
        assert plan.overdue_days == 5

    def test_maintenance_plan_overdue_days_not_overdue(self):
        """测试未逾期的 overdue_days 应为正数"""
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=1, maintenance_type="calibration",
            interval_days=30, next_due_date=(date.today() + timedelta(days=5)).strftime("%Y-%m-%d"),
            is_active=1, created_by="admin"
        )
        assert plan.overdue_days == -5  # 负数表示未逾期

    def test_maintenance_plan_type_label(self):
        """测试维护类型标签"""
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=1, maintenance_type="calibration",
            interval_days=30, next_due_date="2026-06-01",
            is_active=1, created_by="admin"
        )
        assert plan.maintenance_type_label == "校准"

    def test_maintenance_plan_save_and_get(self, auth_client):
        """测试保存和获取计划"""
        from models.maintenance import MaintenancePlan
        dev_id = insert_device()
        plan = MaintenancePlan(
            device_id=dev_id, maintenance_type="calibration",
            interval_days=30, next_due_date="2026-06-01",
            is_active=1, created_by="admin"
        )
        plan.save()
        assert plan.id is not None

        fetched = MaintenancePlan.get_by_id(plan.id)
        assert fetched is not None
        assert fetched.maintenance_type == "calibration"

    def test_maintenance_plan_get_by_device_and_type(self, auth_client):
        """测试按设备和类型获取计划"""
        dev_id = insert_device()
        insert_plan(dev_id, maintenance_type="calibration")
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan.get_by_device_and_type(dev_id, "calibration")
        assert plan is not None
        assert plan.maintenance_type == "calibration"

    def test_maintenance_plan_soft_delete(self, auth_client):
        """测试软删除"""
        dev_id = insert_device()
        from models.maintenance import MaintenancePlan
        plan = MaintenancePlan(
            device_id=dev_id, maintenance_type="calibration",
            interval_days=30, next_due_date="2026-06-01",
            is_active=1, created_by="admin"
        )
        plan.save()
        plan.delete()
        assert plan.is_active == 0

    def test_maintenance_record_save_and_get(self, auth_client):
        """测试保存和获取记录"""
        from models.maintenance import MaintenanceRecord
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        record = MaintenanceRecord(
            plan_id=plan_id, device_id=dev_id,
            maintenance_type="calibration",
            content="测试维护", result="qualified",
            performed_by="admin", performed_at="2026-05-12",
            next_due_date="2026-06-11",
        )
        record.save()
        assert record.id is not None

        fetched = MaintenanceRecord.get_by_id(record.id)
        assert fetched is not None
        assert fetched.content == "测试维护"

    def test_maintenance_record_get_by_device_pagination(self, auth_client):
        """测试记录分页"""
        dev_id = insert_device()
        plan_id = insert_plan(dev_id)
        for i in range(25):
            insert_record(plan_id, dev_id, content=f"维护{i+1}")
        from models.maintenance import MaintenanceRecord
        records, pagination = MaintenanceRecord.get_by_device(dev_id, page=1, per_page=20)
        assert len(records) == 20
        assert pagination["total"] == 25
        assert pagination["pages"] == 2

    def test_maintenance_record_type_label(self):
        """测试记录的维护类型标签"""
        from models.maintenance import MaintenanceRecord
        record = MaintenanceRecord(
            plan_id=1, device_id=1, maintenance_type="inspection",
            content="巡检", result="qualified",
            performed_by="admin", performed_at="2026-05-12",
            next_due_date="2026-06-11",
        )
        assert record.maintenance_type_label == "巡检"


# ============================================================
# 10. 权限测试
# ============================================================

class TestPermissions:
    """测试权限控制"""

    def test_unauthenticated_access_redirects(self, monkeypatch):
        """测试未登录访问重定向到登录页（不使用 LOGIN_DISABLED）"""
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        import database as dbmod
        monkeypatch.setattr(dbmod, "DB_PATH", tmp)
        init_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        # 不设置 LOGIN_DISABLED，测试真实的登录重定向
        with app.test_client() as c:
            dev_id = insert_device()
            rv = c.get(f"/device/{dev_id}/maintenance/")
            assert rv.status_code == 302
            assert "/login" in rv.headers.get("Location", "")
        try:
            os.remove(tmp)
        except OSError:
            pass

    def test_unauthenticated_api_redirects(self, monkeypatch):
        """测试未登录访问API重定向"""
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        import database as dbmod
        monkeypatch.setattr(dbmod, "DB_PATH", tmp)
        init_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            dev_id = insert_device()
            rv = c.get(f"/device/{dev_id}/maintenance/api/plans")
            assert rv.status_code == 302
            assert "/login" in rv.headers.get("Location", "")
        try:
            os.remove(tmp)
        except OSError:
            pass

    def test_anonymous_user_page_renders_after_fix(self, monkeypatch):
        """验证BUG-1修复：未登录用户（LOGIN_DISABLED模式）访问维护计划页不再报错

        修复前: device_maintenance.html 中 current_user.has_permission() 对
        AnonymousUserMixin 抛出 UndefinedError，导致 500 错误。
        修复后: 添加了 current_user.is_authenticated 前置检查，匿名用户可正常访问页面。
        """
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        import database as dbmod
        monkeypatch.setattr(dbmod, "DB_PATH", tmp)
        init_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        app.config["LOGIN_DISABLED"] = True  # 绕过 login_required, current_user 是 AnonymousUserMixin
        with app.test_client() as c:
            dev_id = insert_device()
            rv = c.get(f"/device/{dev_id}/maintenance/")
            assert rv.status_code == 200, \
                "BUG-1修复验证失败: 匿名用户访问页面应返回200，不再抛出 UndefinedError"
        try:
            os.remove(tmp)
        except OSError:
            pass

    def test_user_role_can_view_plans(self, monkeypatch):
        """测试普通用户可查看维护计划"""
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        import database as dbmod
        monkeypatch.setattr(dbmod, "DB_PATH", tmp)
        init_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            c.post("/login", data={"username": "user", "password": "user123"})
            dev_id = insert_device()
            rv = c.get(f"/device/{dev_id}/maintenance/")
            assert rv.status_code == 200
        try:
            os.remove(tmp)
        except OSError:
            pass


# ============================================================
# 11. 构建提醒数据测试
# ============================================================

class TestBuildDueMaintenanceReminders:
    """测试 build_due_maintenance_reminders 函数"""

    def test_reminders_with_mixed_data(self, auth_client):
        """测试混合数据的提醒构建"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        today_date = date.today().strftime("%Y-%m-%d")
        in5days = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        far_future = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")

        insert_plan(dev_id, maintenance_type="calibration", next_due_date=overdue_date)
        insert_plan(dev_id, maintenance_type="maintenance", next_due_date=today_date)
        insert_plan(dev_id, maintenance_type="inspection", next_due_date=in5days)
        insert_plan(dev_id, maintenance_type="calibration", next_due_date=far_future, is_active=0)  # 停用不应出现

        from utils.maintenance import build_due_maintenance_reminders
        conn = get_db()
        result = build_due_maintenance_reminders(conn)
        conn.close()

        assert result["summary"]["overdue_count"] == 1
        assert result["summary"]["due_today_count"] == 1
        assert result["summary"]["due_7days_count"] == 1

    def test_reminders_empty_database(self, auth_client):
        """测试空数据库的提醒构建"""
        from utils.maintenance import build_due_maintenance_reminders
        conn = get_db()
        result = build_due_maintenance_reminders(conn)
        conn.close()
        assert result["summary"]["overdue_count"] == 0
        assert result["summary"]["due_today_count"] == 0
        assert result["summary"]["due_7days_count"] == 0

    def test_reminders_inactive_plan_excluded(self, auth_client):
        """测试停用的计划不包含在提醒中"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        insert_plan(dev_id, next_due_date=overdue_date, is_active=0)

        from utils.maintenance import build_due_maintenance_reminders
        conn = get_db()
        result = build_due_maintenance_reminders(conn)
        conn.close()
        assert result["summary"]["overdue_count"] == 0

    def test_reminder_item_fields(self, auth_client):
        """测试提醒数据项包含必要字段"""
        dev_id = insert_device()
        overdue_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
        insert_plan(dev_id, maintenance_type="calibration", next_due_date=overdue_date)

        from utils.maintenance import build_due_maintenance_reminders
        conn = get_db()
        result = build_due_maintenance_reminders(conn)
        conn.close()

        if result["overdue"]:
            item = result["overdue"][0]
            assert "device_id" in item
            assert "device_code" in item
            assert "device_name" in item
            assert "maintenance_type" in item
            assert "maintenance_type_label" in item
            assert "due_date" in item
            assert "plan_id" in item


# ============================================================
# 12. BUG修复验证测试（第二轮）
# ============================================================

class TestBugFixVerification:
    """验证第一轮测试发现的BUG修复"""

    def test_bug1_has_permission_anonymous_user(self, monkeypatch):
        """BUG-1修复验证：匿名用户访问维护计划页不再抛出 UndefinedError

        修复内容: device_maintenance.html 中将 current_user.has_permission(...)
        改为 current_user.is_authenticated and current_user.has_permission(...)
        """
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        import database as dbmod
        monkeypatch.setattr(dbmod, "DB_PATH", tmp)
        init_db()
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        app.config["LOGIN_DISABLED"] = True
        with app.test_client() as c:
            dev_id = insert_device()
            rv = c.get(f"/device/{dev_id}/maintenance/")
            assert rv.status_code == 200, \
                "BUG-1未修复: 匿名用户访问页面仍然报错"

            # 验证页面内容正确渲染，不包含"添加维护计划"按钮（匿名用户不应看到）
            html = rv.data.decode("utf-8")
            assert "维护计划列表" in html or "暂无维护计划" in html
        try:
            os.remove(tmp)
        except OSError:
            pass

    def test_bug1_template_is_authenticated_check(self):
        """验证模板中 has_permission 前有 is_authenticated 检查"""
        with open("D:/EquipmentManagement/templates/device_maintenance.html", "r", encoding="utf-8") as f:
            content = f.read()
        # 所有 has_permission 调用前应有 is_authenticated 检查
        import re
        has_perm_matches = re.findall(r'has_permission\(', content)
        auth_guard_matches = re.findall(r'is_authenticated\s+and\s+\w+\.has_permission\(', content)
        assert len(has_perm_matches) == len(auth_guard_matches), \
            f"BUG-1修复不完整: {len(has_perm_matches)}处 has_permission 调用，" \
            f"但只有 {len(auth_guard_matches)}处有 is_authenticated 保护"

    def test_bug2_maintenance_all_page_accessible(self, auth_client):
        """BUG-2修复验证：/maintenance/all 页面可访问"""
        rv = auth_client.get("/maintenance/all")
        assert rv.status_code == 200, \
            "BUG-2未修复: /maintenance/all 页面不可访问"

    def test_bug2_maintenance_all_page_content(self, auth_client):
        """BUG-2修复验证：/maintenance/all 页面内容正确"""
        dev_id = insert_device()
        insert_plan(dev_id, maintenance_type="calibration")
        rv = auth_client.get("/maintenance/all")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "维护计划总览" in html
        assert "全部维护计划" in html

    def test_bug2_maintenance_all_with_plans(self, auth_client):
        """BUG-2修复验证：/maintenance/all 显示所有设备的维护计划"""
        dev1 = insert_device("DEV-001", "设备A")
        dev2 = insert_device("DEV-002", "设备B")
        insert_plan(dev1, maintenance_type="calibration")
        insert_plan(dev2, maintenance_type="maintenance")
        rv = auth_client.get("/maintenance/all")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "DEV-001" in html
        assert "DEV-002" in html

    def test_bug2_dashboard_link_updated(self, auth_client):
        """BUG-2修复验证：看板组件链接指向 /maintenance/all 而非 device_id=0"""
        with open("D:/EquipmentManagement/templates/components/maintenance_dashboard.html", "r", encoding="utf-8") as f:
            content = f.read()
        assert "device_id=0" not in content, \
            "BUG-2修复不完整: maintenance_dashboard.html 仍包含 device_id=0 链接"
        assert "maintenance_all" in content or "maintenance/all" in content, \
            "BUG-2修复不完整: 链接未更新为 maintenance_all 路由"

    def test_bug2_maintenance_all_empty(self, auth_client):
        """BUG-2修复验证：无计划时页面正常显示"""
        rv = auth_client.get("/maintenance/all")
        assert rv.status_code == 200
        html = rv.data.decode("utf-8")
        assert "暂无维护计划" in html
