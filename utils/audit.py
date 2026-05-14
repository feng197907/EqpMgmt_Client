# 审计日志工具
import json

from flask import has_request_context, request

from database import get_db
from utils.db_utils import commit_with_retry


def _to_json(value):
    """将值转换为 JSON 字符串"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def log_action_with_cursor(
    cur,
    user,
    action,
    target_type,
    target_id=None,
    details=None,
    before_value=None,
    after_value=None,
    reason=None,
    ip_address=None,
):
    """使用游标记录审计日志（内部使用）"""
    from utils.db_utils import execute_with_retry

    execute_with_retry(
        cur,
        """
        INSERT INTO audit_logs
        (user, action, target_type, target_id, details, before_value, after_value, reason, ip_address)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user,
            action,
            target_type,
            target_id,
            details,
            _to_json(before_value),
            _to_json(after_value),
            reason,
            ip_address,
        ),
    )


def log_action(
    user,
    action,
    target_type,
    target_id=None,
    details=None,
    before_value=None,
    after_value=None,
    reason=None,
    ip_address=None,
):
    """记录用户操作审计日志"""
    if ip_address is None and has_request_context():
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)

    conn = get_db()
    cur = conn.cursor()
    log_action_with_cursor(
        cur,
        user,
        action,
        target_type,
        target_id=target_id,
        details=details,
        before_value=before_value,
        after_value=after_value,
        reason=reason,
        ip_address=ip_address,
    )
    commit_with_retry(conn)
    conn.close()
