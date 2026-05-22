# 维护计划与记录模型
from datetime import datetime, date

from config import MAINTENANCE_RESULT_LABELS, MAINTENANCE_TYPE_LABELS
from database import get_db


def _normalize_date(value):
    """将日期值标准化为 date 对象，兼容 MySQL 返回的 datetime/date 对象和字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


class MaintenancePlan:
    """维护计划类"""

    def __init__(self, id=None, device_id=None, maintenance_type=None,
                 interval_days=None, next_due_date=None, is_active=1,
                 is_closed=0, closed_at=None, closed_by=None, close_reason=None,
                 created_by=None, created_at=None, updated_at=None):
        self.id = id
        self.device_id = device_id
        self.maintenance_type = maintenance_type
        self.interval_days = interval_days
        self.next_due_date = next_due_date
        self.is_active = is_active
        self.is_closed = is_closed
        self.closed_at = closed_at
        self.closed_by = closed_by
        self.close_reason = close_reason
        self.created_by = created_by
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def maintenance_type_label(self):
        """获取维护类型中文标签"""
        return MAINTENANCE_TYPE_LABELS.get(self.maintenance_type, self.maintenance_type)

    @property
    def status_label(self):
        """获取计划状态中文标签"""
        if self.is_closed:
            return "已关闭"
        if not self.is_active:
            return "已删除"
        if self.is_overdue:
            return "已逾期"
        return "正常"

    @property
    def status_class(self):
        """获取计划状态对应的 CSS 样式类"""
        if self.is_closed:
            return "secondary"
        if not self.is_active:
            return "muted"
        if self.is_overdue:
            return "danger"
        return "success"

    @property
    def is_overdue(self):
        """检查是否已逾期"""
        due_date = _normalize_date(self.next_due_date)
        if not due_date:
            return False
        return due_date < date.today()

    @property
    def overdue_days(self):
        """计算逾期天数"""
        due_date = _normalize_date(self.next_due_date)
        if not due_date:
            return 0
        delta = date.today() - due_date
        return delta.days

    @property
    def urgency(self):
        """计算紧迫度标签"""
        due_date = _normalize_date(self.next_due_date)
        if not due_date:
            return "info"
        delta = (due_date - date.today()).days
        if delta < 0 or delta == 0:
            return "danger"
        elif delta <= 3:
            return "warning"
        elif delta <= 7:
            return "info"
        return "success"

    @staticmethod
    def get_by_id(plan_id):
        """根据ID获取维护计划"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM maintenance_plan WHERE id = %s", (plan_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return MaintenancePlan(**dict(row))

    @staticmethod
    def get_by_device(device_id, active_only=True, include_closed=False):
        """获取设备的维护计划列表

        Args:
            active_only: 是否只返回 is_active=1 的记录
            include_closed: 是否包含已关闭的计划
        """
        conn = get_db()
        cur = conn.cursor()
        where = "device_id = %s"
        params = [device_id]
        if active_only:
            where += " AND is_active = 1"
        if not include_closed:
            where += " AND is_closed = 0"
        cur.execute(
            f"SELECT * FROM maintenance_plan WHERE {where} ORDER BY next_due_date ASC",
            params
        )
        rows = cur.fetchall()
        conn.close()
        return [MaintenancePlan(**dict(row)) for row in rows]

    @staticmethod
    def get_by_device_and_type(device_id, maintenance_type):
        """根据设备ID和维护类型获取激活的计划"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM maintenance_plan WHERE device_id = %s AND maintenance_type = %s AND is_active = 1",
            (device_id, maintenance_type)
        )
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return MaintenancePlan(**dict(row))

    def save(self):
        """保存维护计划（新增或更新）"""
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO maintenance_plan
                   (device_id, maintenance_type, interval_days, next_due_date,
                    is_active, is_closed, closed_at, closed_by, close_reason,
                    created_by, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())""",
                (self.device_id, self.maintenance_type, self.interval_days,
                 self.next_due_date, self.is_active, self.is_closed,
                 self.closed_at, self.closed_by, self.close_reason,
                 self.created_by)
            )
            self.id = cur.lastrowid
        else:
            cur.execute(
                """UPDATE maintenance_plan SET
                   maintenance_type = %s, interval_days = %s, next_due_date = %s,
                   is_active = %s, is_closed = %s, closed_at = %s,
                   closed_by = %s, close_reason = %s, updated_at = NOW()
                   WHERE id = %s""",
                (self.maintenance_type, self.interval_days, self.next_due_date,
                 self.is_active, self.is_closed, self.closed_at,
                 self.closed_by, self.close_reason, self.id)
            )
        conn.commit()
        conn.close()
        return self

    def close(self, closed_by, close_reason=""):
        """关闭维护计划（逾期计划可手动关闭）"""
        self.is_closed = 1
        self.closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.closed_by = closed_by
        self.close_reason = close_reason
        self.save()

    def delete(self):
        """软删除维护计划"""
        self.is_active = 0
        self.save()


class MaintenanceRecord:
    """维护记录类"""

    def __init__(self, id=None, plan_id=None, device_id=None,
                 maintenance_type=None, content=None, result=None,
                 performed_by=None, performed_at=None, next_due_date=None,
                 parts_used=None, created_at=None):
        self.id = id
        self.plan_id = plan_id
        self.device_id = device_id
        self.maintenance_type = maintenance_type
        self.content = content
        self.result = result
        self.performed_by = performed_by
        self.performed_at = performed_at
        self.next_due_date = next_due_date
        self.parts_used = parts_used
        self.created_at = created_at

    @property
    def maintenance_type_label(self):
        """获取维护类型中文标签"""
        return MAINTENANCE_TYPE_LABELS.get(self.maintenance_type, self.maintenance_type)

    @staticmethod
    def get_by_id(record_id):
        """根据ID获取维护记录"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM maintenance_record WHERE id = %s", (record_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return MaintenanceRecord(**dict(row))

    @staticmethod
    def get_by_device(device_id, maintenance_type=None, year=None, page=1, per_page=20):
        """获取设备的维护记录列表（支持分页和筛选）"""
        conn = get_db()
        cur = conn.cursor()
        where = "WHERE device_id = %s"
        params = [device_id]
        if maintenance_type:
            where += " AND maintenance_type = %s"
            params.append(maintenance_type)
        if year:
            where += " AND YEAR(performed_at) = %s"
            params.append(int(year))
        cur.execute(
            f"SELECT COUNT(*) as total FROM maintenance_record {where}",
            params
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        params_with_pagination = params + [per_page, offset]
        cur.execute(
            f"""SELECT * FROM maintenance_record {where}
                ORDER BY performed_at DESC LIMIT %s OFFSET %s""",
            params_with_pagination
        )
        rows = cur.fetchall()
        conn.close()
        records = [MaintenanceRecord(**dict(row)) for row in rows]
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
        return records, pagination

    @staticmethod
    def get_by_plan(plan_id):
        """根据计划ID获取维护记录列表"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM maintenance_record WHERE plan_id = %s ORDER BY performed_at DESC",
            (plan_id,)
        )
        rows = cur.fetchall()
        conn.close()
        return [MaintenanceRecord(**dict(row)) for row in rows]

    def save(self):
        """保存维护记录"""
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO maintenance_record
                   (plan_id, device_id, maintenance_type, content, result,
                    performed_by, performed_at, next_due_date, parts_used, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (self.plan_id, self.device_id, self.maintenance_type,
                 self.content, self.result, self.performed_by,
                 self.performed_at, self.next_due_date, self.parts_used)
            )
            self.id = cur.lastrowid
        conn.commit()
        conn.close()
        return self


class DeviceRepairRecord:
    """设备维修记录类（独立于维护计划的维修记录）"""

    def __init__(self, id=None, device_id=None, content=None,
                 result=None, performed_by=None, performed_at=None,
                 parts_used=None, created_at=None):
        self.id = id
        self.device_id = device_id
        self.content = content
        self.result = result
        self.performed_by = performed_by
        self.performed_at = performed_at
        self.parts_used = parts_used
        self.created_at = created_at

    @staticmethod
    def get_by_id(record_id):
        """根据ID获取维修记录"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM repair_record WHERE id = %s", (record_id,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            return None
        return DeviceRepairRecord(**dict(row))

    @staticmethod
    def get_by_device(device_id, page=1, per_page=20):
        """获取设备的维修记录列表（支持分页）"""
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) as total FROM repair_record WHERE device_id = %s",
            (device_id,)
        )
        total = cur.fetchone()["total"]
        offset = (page - 1) * per_page
        cur.execute(
            """SELECT * FROM repair_record WHERE device_id = %s
                ORDER BY performed_at DESC LIMIT %s OFFSET %s""",
            (device_id, per_page, offset)
        )
        rows = cur.fetchall()
        conn.close()
        records = [DeviceRepairRecord(**dict(row)) for row in rows]
        pagination = {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page
        }
        return records, pagination

    def save(self):
        """保存维修记录"""
        conn = get_db()
        cur = conn.cursor()
        if self.id is None:
            cur.execute(
                """INSERT INTO repair_record
                   (device_id, content, result, performed_by, performed_at, parts_used, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                (self.device_id, self.content, self.result,
                 self.performed_by, self.performed_at, self.parts_used)
            )
            self.id = cur.lastrowid
        conn.commit()
        conn.close()
        return self

    def delete(self):
        """删除维修记录"""
        if self.id is None:
            return False
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM repair_record WHERE id = %s", (self.id,))
        conn.commit()
        conn.close()
        return True
