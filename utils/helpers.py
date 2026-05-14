# 辅助函数工具
from datetime import datetime, timedelta, timezone


def get_document_rows(device_id):
    """获取设备的所有文档记录"""
    from database import get_db

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.*, br.id AS borrow_id, br.status AS borrow_status,
               br.borrower AS borrow_user, br.borrow_date AS borrow_date
        FROM documents d
        LEFT JOIN (
            SELECT b1.*
            FROM borrow_records b1
            JOIN (
                SELECT doc_id, MAX(id) AS max_id
                FROM borrow_records
                GROUP BY doc_id
            ) latest ON latest.max_id = b1.id
        ) br ON br.doc_id = d.id
        WHERE d.device_id = %s AND d.is_deleted = 0
        ORDER BY d.doc_type, d.upload_time DESC
        """,
        (device_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def parse_timestamp(value):
    """解析时间戳"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def build_calibration_reminders(rows, reminder_window_days=60, cycle_days=365):
    """构建校准提醒列表"""
    reminders = []
    today = datetime.now(timezone.utc).date()
    for row in rows:
        uploaded_at = parse_timestamp(row["upload_time"])
        if uploaded_at is None:
            continue
        due_date = uploaded_at.date() + timedelta(days=cycle_days)
        days_left = (due_date - today).days
        if days_left > reminder_window_days:
            continue
        if days_left < 0:
            severity = "danger"
            label = "已逾期"
        elif days_left <= 30:
            severity = "warning"
            label = "即将到期"
        else:
            severity = "info"
            label = "需关注"
        reminders.append(
            {
                "device_id": row["device_id"],
                "device_code": row["device_code"],
                "device_name": row["device_name"],
                "doc_id": row["id"],
                "doc_name": row["doc_name"],
                "version": row["version"],
                "uploaded_by": row["uploaded_by"],
                "upload_time": row["upload_time"],
                "due_date": due_date.isoformat(),
                "days_left": days_left,
                "severity": severity,
                "label": label,
            }
        )
    return reminders


def ensure_device_change_table(cur):
    """确保设备状态变更请求表存在"""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS device_status_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id INT NOT NULL,
            requested_by VARCHAR(255) NOT NULL,
            new_status VARCHAR(50) NOT NULL,
            reason TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            decided_by VARCHAR(255),
            decided_at TIMESTAMP NULL,
            comment TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
