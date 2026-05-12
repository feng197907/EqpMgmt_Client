# 维护相关辅助函数
from datetime import datetime, date, timedelta

from config import MAINTENANCE_TYPE_LABELS
from database import get_db


def calc_next_due_date(performed_at, interval_days):
    """计算下次到期日

    Args:
        performed_at: 执行日期（date对象或'YYYY-MM-DD'字符串）
        interval_days: 周期天数

    Returns:
        'YYYY-MM-DD'格式的日期字符串
    """
    if isinstance(performed_at, str):
        performed_at = datetime.strptime(performed_at, "%Y-%m-%d").date()
    next_due = performed_at + timedelta(days=interval_days)
    return next_due.strftime("%Y-%m-%d")


def calc_urgency(due_date):
    """计算到期紧迫度

    Args:
        due_date: 到期日期（'YYYY-MM-DD'字符串）

    Returns:
        'danger' | 'warning' | 'info' | 'success'
    """
    if not due_date:
        return "info"
    due = datetime.strptime(due_date, "%Y-%m-%d").date()
    delta = (due - date.today()).days
    if delta < 0 or delta == 0:
        return "danger"
    elif delta <= 3:
        return "warning"
    elif delta <= 7:
        return "info"
    return "success"


def get_maintenance_type_label(mtype):
    """获取维护类型中文标签"""
    return MAINTENANCE_TYPE_LABELS.get(mtype, mtype)


def build_due_maintenance_reminders(conn, days=7, user=None):
    """构建到期维护提醒数据

    Args:
        conn: 数据库连接
        days: 提前提醒天数
        user: 如果指定，只返回该用户的设备提醒

    Returns:
        包含due_today, due_within_7days, overdue, summary的字典
    """
    cur = conn.cursor()

    # 构建用户设备过滤条件
    user_filter = ""
    params = []
    if user:
        # 假设用户只能看到自己负责的设备（这里需要根据实际业务逻辑调整）
        # 暂时返回所有设备的提醒
        pass

    # 查询所有激活的维护计划及其设备信息
    cur.execute(
        """SELECT mp.*, d.device_code, d.device_name
           FROM maintenance_plan mp
           JOIN devices d ON d.id = mp.device_id
           WHERE mp.is_active = 1
           AND (d.is_deleted IS NULL OR d.is_deleted = 0)
           ORDER BY mp.next_due_date"""
    )
    plans = cur.fetchall()

    due_today = []
    due_within_7days = []
    overdue = []

    today = date.today()
    seven_days_later = today + timedelta(days=7)

    for row in plans:
        due_date = datetime.strptime(row["next_due_date"], "%Y-%m-%d").date()
        delta = (due_date - today).days

        item = {
            "device_id": row["device_id"],
            "device_code": row["device_code"],
            "device_name": row["device_name"],
            "maintenance_type": row["maintenance_type"],
            "maintenance_type_label": get_maintenance_type_label(row["maintenance_type"]),
            "due_date": row["next_due_date"],
            "plan_id": row["id"],
            "overdue_days": delta if delta < 0 else 0,
        }

        if due_date < today:
            overdue.append(item)
        elif delta == 0:
            due_today.append(item)
        elif due_date <= seven_days_later:
            due_within_7days.append(item)

    return {
        "due_today": due_today,
        "due_within_7days": due_within_7days,
        "overdue": overdue,
        "summary": {
            "due_today_count": len(due_today),
            "due_7days_count": len(due_within_7days),
            "overdue_count": len(overdue),
        },
    }


def get_due_maintenance_for_dashboard(conn, days=7):
    """获取到期维护数据（供看板使用）

    Args:
        conn: 数据库连接
        days: 查询天数范围

    Returns:
        提醒数据字典
    """
    return build_due_maintenance_reminders(conn, days)
