import os
import re
from contextlib import contextmanager

# 尝试导入 MySQL 驱动，如果不可用则回退到 SQLite
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    from MySQLdb import Connection
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    import sqlite3
    from werkzeug.security import generate_password_hash

# ============================================================
# 数据库配置
# ============================================================

# 数据库类型：'mysql' 或 'sqlite'
DB_TYPE = os.environ.get('DB_TYPE', 'mysql')  # 默认使用 MySQL

# MySQL 配置
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'dms_db'),
    'charset': 'utf8mb4',
}


def _convert_placeholder(sql):
    """转换 SQL 占位符：SQLite 用 ?，MySQL 用 %s"""
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        return re.sub(r'\?', '%s', sql)
    return sql


def get_db():
    """获取数据库连接"""
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        return _get_mysql_db()
    else:
        return _get_sqlite_db()


def _get_mysql_db():
    """打开 MySQL 连接"""
    conn = pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        database=MYSQL_CONFIG['database'],
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        ssl_disabled=True  # 添加这行
    )
    return conn


def _get_sqlite_db():
    """打开 SQLite 连接（备用）"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


class CompatibleCursor:
    """兼容两种数据库的游标封装"""
    def __init__(self, cursor):
        self._cursor = cursor
    
    def execute(self, sql, args=None):
        sql = _convert_placeholder(sql)
        return self._cursor.execute(sql, args)
    
    def executemany(self, sql, args=None):
        sql = _convert_placeholder(sql)
        return self._cursor.executemany(sql, args)
    
    def fetchone(self):
        return self._cursor.fetchone()
    
    def fetchall(self):
        return self._cursor.fetchall()
    
    @property
    def row_factory(self):
        return self._cursor.row_factory
    
    def __getattr__(self, name):
        return getattr(self._cursor, name)


class CompatibleConnection:
    """兼容两种数据库的连接封装"""
    def __init__(self, conn):
        self._conn = conn
    
    def cursor(self):
        return CompatibleCursor(self._conn.cursor())
    
    def commit(self):
        return self._conn.commit()
    
    def rollback(self):
        return self._conn.rollback()
    
    def close(self):
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    """获取数据库连接（自动兼容占位符）"""
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        conn = _get_mysql_db()
    else:
        conn = _get_sqlite_db()
    return CompatibleConnection(conn)


def get_db_cursor():
    """获取带有兼容占位符的数据库游标"""
    conn = get_db()
    return conn.cursor(), conn


def init_db():
    """创建表结构，执行增量升级，并写入默认账号。"""
    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        _init_mysql_tables(cur, conn)
    else:
        _init_sqlite_tables(cur, conn)

    conn.commit()
    conn.close()


def _init_mysql_tables(cur, conn):
    """初始化 MySQL 表结构"""
    # 用户表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            permissions VARCHAR(500) DEFAULT '[]'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 设备表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_code VARCHAR(255) UNIQUE NOT NULL,
            device_name VARCHAR(255) NOT NULL,
            model VARCHAR(255),
            location VARCHAR(255),
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted TINYINT DEFAULT 0
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 文档表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id INT NOT NULL,
            doc_type VARCHAR(50) NOT NULL,
            doc_name VARCHAR(255) NOT NULL,
            version VARCHAR(50) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            uploaded_by VARCHAR(255) NOT NULL,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remarks VARCHAR(1000),
            status VARCHAR(50) NOT NULL DEFAULT 'draft',
            download_count INT DEFAULT 0,
            is_deleted TINYINT DEFAULT 0,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 借阅记录表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            doc_id INT NOT NULL,
            borrower VARCHAR(255) NOT NULL,
            borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_date TIMESTAMP NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'borrowed',
            FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 审计日志表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user VARCHAR(255) NOT NULL,
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id INT,
            details VARCHAR(2000),
            before_value VARCHAR(1000),
            after_value VARCHAR(1000),
            reason VARCHAR(1000),
            ip_address VARCHAR(50),
            log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 审批请求表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            doc_id INT NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_step INT NOT NULL DEFAULT 1,
            FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 审批步骤表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_steps (
            id INT AUTO_INCREMENT PRIMARY KEY,
            request_id INT NOT NULL,
            step_order INT NOT NULL,
            approver_role VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            decided_by VARCHAR(255),
            decided_at TIMESTAMP NULL,
            comment VARCHAR(1000),
            signature_id INT,
            FOREIGN KEY (request_id) REFERENCES approval_requests(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 签名表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS signatures (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user VARCHAR(255) NOT NULL,
            meaning VARCHAR(1000) NOT NULL,
            doc_id INT NOT NULL,
            doc_version VARCHAR(50) NOT NULL,
            doc_hash VARCHAR(255) NOT NULL,
            ip_address VARCHAR(50),
            user_agent VARCHAR(500),
            signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 系统设置表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(255) UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            description VARCHAR(500),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            updated_by VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 密码重置请求表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            username VARCHAR(255) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP NULL,
            processed_by VARCHAR(255),
            ip_address VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 维护计划表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_plan (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id INT NOT NULL,
            maintenance_type VARCHAR(50) NOT NULL,
            interval_days INT NOT NULL,
            next_due_date VARCHAR(50) NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            created_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 维护记录表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_record (
            id INT AUTO_INCREMENT PRIMARY KEY,
            plan_id INT NOT NULL,
            device_id INT NOT NULL,
            maintenance_type VARCHAR(50) NOT NULL,
            content VARCHAR(2000) NOT NULL,
            result VARCHAR(50) NOT NULL,
            performed_by VARCHAR(255) NOT NULL,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            next_due_date VARCHAR(50) NOT NULL,
            parts_used VARCHAR(1000),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES maintenance_plan(id) ON DELETE CASCADE,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 初始化默认设置
    _ensure_default_settings(cur, conn)

    # 设备状态变更请求表
    _ensure_mysql_table(cur, """
        CREATE TABLE IF NOT EXISTS device_status_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            device_id INT NOT NULL,
            new_status VARCHAR(50) NOT NULL,
            reason VARCHAR(1000),
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_by VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_by VARCHAR(255),
            processed_at TIMESTAMP NULL,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 初始化默认用户
    _ensure_default_user_mysql(cur, "admin", "admin123", "admin")
    _ensure_default_user_mysql(cur, "user", "user123", "equipment_engineer")


def _ensure_mysql_table(cur, create_sql):
    """确保 MySQL 表存在"""
    table_name = create_sql.split("CREATE TABLE IF NOT EXISTS ")[1].split(" ")[0]
    cur.execute(f"SHOW TABLES LIKE '{table_name}'")
    if not cur.fetchone():
        cur.execute(create_sql)


def _ensure_default_user_mysql(cur, username, password, role):
    """默认用户不存在时才插入（MySQL）"""
    from werkzeug.security import generate_password_hash
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cur.fetchone() is None:
        hashed = generate_password_hash(password)
        try:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, hashed, role),
            )
        except pymysql.err.IntegrityError:
            # 用户已存在，跳过
            pass


def _init_sqlite_tables(cur, conn):
    """初始化 SQLite 表结构（备用）"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            permissions TEXT DEFAULT '[]'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_code TEXT UNIQUE NOT NULL,
            device_name TEXT NOT NULL,
            model TEXT,
            location TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS borrow_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            borrower TEXT NOT NULL,
            borrow_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            return_date TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'borrowed',
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_by TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_step INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
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
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT UNIQUE NOT NULL,
            setting_value TEXT NOT NULL,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)

    cur.execute("""
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
    """)

    cur.execute("""
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
    """)

    cur.execute("""
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
    """)

    # 初始化默认设置
    _ensure_default_settings(cur, conn)

    # 初始化默认用户
    _ensure_default_user(conn, "admin", "admin123", "admin")
    _ensure_default_user(conn, "user", "user123", "equipment_engineer")

    # 执行增量升级
    _migrate_sqlite_columns(conn)


def _migrate_sqlite_columns(conn):
    """SQLite 增量升级"""
    cur = conn.cursor()
    ensure_column(cur, "documents", "download_count", "ALTER TABLE documents ADD COLUMN download_count INTEGER DEFAULT 0")
    ensure_column(cur, "documents", "status", "ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'")
    ensure_column(cur, "users", "status", "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
    ensure_column(cur, "users", "permissions", "ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '[]'")
    ensure_column(cur, "audit_logs", "before_value", "ALTER TABLE audit_logs ADD COLUMN before_value TEXT")
    ensure_column(cur, "audit_logs", "after_value", "ALTER TABLE audit_logs ADD COLUMN after_value TEXT")
    ensure_column(cur, "audit_logs", "reason", "ALTER TABLE audit_logs ADD COLUMN reason TEXT")
    ensure_column(cur, "audit_logs", "ip_address", "ALTER TABLE audit_logs ADD COLUMN ip_address TEXT")
    ensure_column(cur, "devices", "is_deleted", "ALTER TABLE devices ADD COLUMN is_deleted INTEGER DEFAULT 0")


def ensure_column(cur, table_name, column_name, ddl_sql):
    """若字段不存在则添加（轻量迁移）。"""
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = {row["name"] for row in cur.fetchall()}
    if column_name not in columns:
        cur.execute(ddl_sql)


def _ensure_default_user(conn, username, password, role):
    """默认用户不存在时才插入（SQLite）。"""
    from werkzeug.security import generate_password_hash
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone() is None:
        hashed = generate_password_hash(password)
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed, role),
        )


def _ensure_default_settings(cur, conn):
    """初始化默认系统设置"""
    default_settings = [
        ("approval_enabled", "true", "是否启用审批流程（设备变更、文档上传等）"),
        ("auto_approve_document", "false", "文档上传后是否自动生效"),
    ]
    for key, value, description in default_settings:
        cur.execute(
            "INSERT IGNORE INTO system_settings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
            (key, value, description),
        )


def get_system_setting(key, default=None):
    """获取系统设置值"""
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = %s", (key,))
    else:
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row.get('setting_value') if isinstance(row, dict) else row[0]
    return default


def get_all_system_settings():
    """获取所有系统设置"""
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        cur.execute("SELECT * FROM system_settings ORDER BY id")
    else:
        cur.execute("SELECT * FROM system_settings ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def update_system_setting(key, value, updated_by=None):
    """更新系统设置"""
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        cur.execute(
            "UPDATE system_settings SET setting_value = %s, updated_by = %s, updated_at = NOW() WHERE setting_key = %s",
            (value, updated_by, key),
        )
    else:
        cur.execute(
            "UPDATE system_settings SET setting_value = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?",
            (value, updated_by, key),
        )
    conn.commit()
    conn.close()
