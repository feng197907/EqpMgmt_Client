import os
import sqlite3
from werkzeug.security import generate_password_hash

# SQLite 数据库文件位置。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "dms.db")


def get_db():
    """打开 SQLite 连接，启用行对象与外键约束。"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    """创建表结构，执行增量升级，并写入默认账号。"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_code TEXT UNIQUE NOT NULL,
            device_name TEXT NOT NULL,
            model TEXT,
            location TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            doc_name TEXT NOT NULL,
            version TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_by TEXT NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remarks TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            download_count INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            borrower TEXT NOT NULL,
            borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_date TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'borrowed',
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER,
            details TEXT,
            before_value TEXT,
            after_value TEXT,
            reason TEXT,
            ip_address TEXT,
            log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_step INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS approval_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            step_order INTEGER NOT NULL,
            approver_role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            decided_by TEXT,
            decided_at TIMESTAMP,
            comment TEXT,
            signature_id INTEGER,
            FOREIGN KEY (request_id) REFERENCES approval_requests(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            meaning TEXT NOT NULL,
            doc_id INTEGER NOT NULL,
            doc_version TEXT NOT NULL,
            doc_hash TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
        """
    )

    # 系统设置表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
        """
    )

    # 初始化默认设置
    _ensure_default_settings(conn)

    # 密码重置请求表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            processed_by TEXT,
            ip_address TEXT
        )
        """
    )

    # 维护计划表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            interval_days INTEGER NOT NULL,
            next_due_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """
    )

    # 维护记录表
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            device_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            content TEXT NOT NULL,
            result TEXT NOT NULL,
            performed_by TEXT NOT NULL,
            performed_at TEXT NOT NULL DEFAULT (datetime('now')),
            next_due_date TEXT NOT NULL,
            parts_used TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (plan_id) REFERENCES maintenance_plan(id),
            FOREIGN KEY (device_id) REFERENCES devices(id)
        )
        """
    )

    # 对旧数据库执行增量结构升级。
    conn.commit()

    ensure_column(
        conn,
        "documents",
        "download_count",
        "ALTER TABLE documents ADD COLUMN download_count INTEGER DEFAULT 0",
    )
    ensure_column(
        conn,
        "documents",
        "status",
        "ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'",
    )
    ensure_column(
        conn,
        "users",
        "status",
        "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
    )
    ensure_column(
        conn,
        "audit_logs",
        "before_value",
        "ALTER TABLE audit_logs ADD COLUMN before_value TEXT",
    )
    ensure_column(
        conn,
        "audit_logs",
        "after_value",
        "ALTER TABLE audit_logs ADD COLUMN after_value TEXT",
    )
    ensure_column(
        conn,
        "audit_logs",
        "reason",
        "ALTER TABLE audit_logs ADD COLUMN reason TEXT",
    )
    ensure_column(
        conn,
        "audit_logs",
        "ip_address",
        "ALTER TABLE audit_logs ADD COLUMN ip_address TEXT",
    )

    # 设备表可能需要软删除标记，若不存在则添加
    ensure_column(
        conn,
        "devices",
        "is_deleted",
        "ALTER TABLE devices ADD COLUMN is_deleted INTEGER DEFAULT 0",
    )

    _ensure_default_user(conn, "admin", "admin123", "admin")
    _ensure_default_user(conn, "user", "user123", "user")

    conn.commit()
    conn.close()


def ensure_column(conn, table_name, column_name, ddl_sql):
    """若字段不存在则添加（轻量迁移）。"""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = {row["name"] for row in cur.fetchall()}
    if column_name not in columns:
        cur.execute(ddl_sql)


def _ensure_default_user(conn, username, password, role):
    """默认用户不存在时才插入。"""
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone() is None:
        hashed = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed, role),
        )


def _ensure_default_settings(conn):
    """初始化默认系统设置"""
    cur = conn.cursor()
    default_settings = [
        ("approval_enabled", "true", "是否启用文档审批流程"),
        ("auto_approve_document", "false", "文档上传后是否自动生效（跳过审批）"),
    ]
    for key, value, description in default_settings:
        cur.execute(
            "INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
            (key, value, description),
        )


def get_system_setting(key, default=None):
    """获取系统设置值"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["setting_value"]
    return default


def get_all_system_settings():
    """获取所有系统设置"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM system_settings ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def update_system_setting(key, value, updated_by=None):
    """更新系统设置"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE system_settings SET setting_value = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?",
        (value, updated_by, key),
    )
    conn.commit()
    conn.close()
