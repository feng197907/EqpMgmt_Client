# 数据库工具
import sqlite3
import time


def execute_with_retry(cur, sql, params=(), retries=5, base_delay=0.2):
    """带重试的 SQL 执行"""
    for attempt in range(retries):
        try:
            cur.execute(sql, params)
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise


def commit_with_retry(conn, retries=5, base_delay=0.2):
    """带重试的事务提交"""
    for attempt in range(retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(base_delay * (attempt + 1))
                continue
            raise


def get_next_version(conn, device_id, doc_type):
    """获取文档下一个版本号"""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT version FROM documents
        WHERE device_id = %s AND doc_type = %s AND is_deleted = 0
        ORDER BY id DESC LIMIT 1
        """,
        (device_id, doc_type),
    )
    row = cur.fetchone()
    if row is None:
        return "1.0"
    parts = row["version"].split(".")
    if len(parts) != 2 or not parts[1].isdigit() or not parts[0].isdigit():
        return "1.0"
    major = int(parts[0])
    minor = int(parts[1]) + 1
    return f"{major}.{minor}"
