import os
import re
from contextlib import contextmanager

# 确保 .env 环境变量在模块初始化前加载
# （database.py 作为顶层模块被导入时，app.py 的 load_dotenv() 尚未执行）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# 数据库类型判断（优先级：环境变量 > MySQL可用性）
# ============================================================
_DB_TYPE = os.environ.get('DB_TYPE', '').lower().strip()

# 尝试验证 MySQL 是否真的可用
_MYSQL_AVAILABLE = False
_pymysql = None
try:
    import pymysql as _pymysql
    _pymysql.install_as_MySQLdb()
    from MySQLdb import Connection as _MySQLdbConn
    # 尝试建立连接验证是否可用
    _test_conn = _pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        port=int(os.environ.get('MYSQL_PORT', 3306)),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'dms_db'),
        charset='utf8mb4',
        connect_timeout=3,
    )
    _test_conn.close()
    _MYSQL_AVAILABLE = True
except Exception:
    _MYSQL_AVAILABLE = False
    _pymysql = None

# 最终 DB_TYPE 决策
if _DB_TYPE == 'mysql' and not _MYSQL_AVAILABLE:
    print("[WARN] DB_TYPE=mysql but MySQL unavailable, falling back to SQLite")
    DB_TYPE = 'sqlite'
elif _DB_TYPE == 'sqlite':
    DB_TYPE = 'sqlite'
elif _DB_TYPE == 'mysql' and _MYSQL_AVAILABLE:
    DB_TYPE = 'mysql'
else:
    # 默认：优先 MySQL，降级 SQLite
    DB_TYPE = 'mysql' if _MYSQL_AVAILABLE else 'sqlite'

MYSQL_AVAILABLE = (DB_TYPE == 'mysql')

# 兼容旧代码中的导入（蓝图文件可能引用）
if _pymysql:
    pymysql = _pymysql
else:
    import sqlite3
    from werkzeug.security import generate_password_hash

# ============================================================
# 数据库配置
# ============================================================

# SQLite 数据库路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'equipment.db')

# MySQL 配置
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'dms_db'),
    'charset': 'utf8mb4',
}

# ============================================================
# 兼容层：统一两种数据库的占位符和连接/游标行为
# ============================================================

def _convert_placeholder(sql):
    """统一占位符：
    - MySQL: %s
    - SQLite: ?
    调用方使用 %s 风格，本函数自动转换。
    """
    if DB_TYPE == 'mysql':
        # MySQL 源码用 %s，不转换
        return sql
    else:
        # SQLite 用 ?，把 %s 替换回 ?
        return sql.replace('%s', '?')


class _SQLiteRow(dict):
    """SQLite Row -> dict 兼容，兼容字典取值"""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)


class CompatibleCursor:
    """兼容两种数据库的游标封装。

    统一占位符风格：调用方始终用 %s，内部自动转成对应数据库的占位符。
    统一返回值：fetchone/fetchall 始终返回 dict list。
    """
    def __init__(self, cursor, is_sqlite=False):
        self._cur = cursor
        self._is_sqlite = is_sqlite

    def execute(self, sql, args=None):
        sql = _convert_placeholder(sql)
        if args is None:
            self._cur.execute(sql)
        else:
            self._cur.execute(sql, args)
        return self

    def executemany(self, sql, args=None):
        sql = _convert_placeholder(sql)
        if args is None:
            self._cur.executemany(sql)
        else:
            self._cur.executemany(sql, args)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if self._is_sqlite:
            return _SQLiteRow(row) if hasattr(row, 'keys') else dict(row)
        if hasattr(row, 'keys'):
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        if self._is_sqlite:
            return [_SQLiteRow(r) if hasattr(r, 'keys') else dict(r) for r in rows]
        return [dict(r) if hasattr(r, 'keys') else r for r in rows]

    def fetchmany(self, size=None):
        rows = self._cur.fetchmany(size)
        if not rows:
            return []
        if self._is_sqlite:
            return [_SQLiteRow(r) if hasattr(r, 'keys') else dict(r) for r in rows]
        return [dict(r) if hasattr(r, 'keys') else r for r in rows]

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount

    def __iter__(self):
        return iter(self.fetchall())

    def __getattr__(self, name):
        return getattr(self._cur, name)


class CompatibleConnection:
    """兼容两种数据库的连接封装，统一返回 dict 风格游标。"""
    def __init__(self, conn, is_sqlite=False):
        self._conn = conn
        self._is_sqlite = is_sqlite

    def cursor(self):
        raw = self._conn.cursor()
        return CompatibleCursor(raw, is_sqlite=self._is_sqlite)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


# ============================================================
# 核心连接函数
# ============================================================

def get_db():
    """获取数据库连接。
    - MySQL 模式：pymysql + DictCursor，封装为 CompatibleConnection
    - SQLite 模式：sqlite3 + dict Row，封装为 CompatibleConnection
    """
    if DB_TYPE == 'mysql' and MYSQL_AVAILABLE:
        conn = _pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            database=MYSQL_CONFIG['database'],
            charset='utf8mb4',
            cursorclass=_pymysql.cursors.DictCursor,
        )
        return CompatibleConnection(conn, is_sqlite=False)
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return CompatibleConnection(conn, is_sqlite=True)


def get_db_cursor():
    """获取兼容游标 + 连接（配套使用，用完记得 close）"""
    conn = get_db()
    return conn.cursor(), conn


@contextmanager
def get_db_context():
    """数据库连接上下文管理器，自动 commit/rollback + close。
    
    用法：
        with get_db_context() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
            rows = cur.fetchall()
    
    正常退出自动 commit，异常自动 rollback，finally 块自动 close。
    """
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# SQL 占位符辅助（给调用方参考）
# ============================================================

def sql(ph='%s'):
    """返回当前 DB_TYPE 对应的占位符字符串。

    用法示例（不再需要手动写死 ? 或 %s）：
        cur.execute("SELECT * FROM users WHERE username = " + sql(), (name,))
        cur.execute("INSERT INTO users (name) VALUES (" + sql() + ")", (name,))

    但更推荐：直接用 %s，内部自动转换。
    """
    return '%s' if DB_TYPE == 'mysql' else '?'


# ============================================================
# 数据库初始化
# ============================================================

def init_db():
    """创建表结构，执行增量升级，并写入默认账号。"""
    conn = get_db()
    cur = conn.cursor()

    if DB_TYPE == 'mysql':
        _init_mysql_tables(cur, conn)
    else:
        _init_sqlite_tables(cur, conn)

    conn.commit()
    conn.close()


def _migrate_mysql_columns(cur):
    """MySQL 增量升级：添加历史遗留列（安全，幂等）"""
    print("[DB] Running MySQL column migrations...")
    migrations = [
        ("documents", "calibration_due_date",
         "ALTER TABLE documents ADD COLUMN calibration_due_date DATE DEFAULT NULL"),
        # repair_record 表（增量创建）
        ("repair_record", "_table",
         "CREATE TABLE IF NOT EXISTS repair_record (id INT AUTO_INCREMENT PRIMARY KEY, device_id INT NOT NULL, content VARCHAR(2000) NOT NULL, result VARCHAR(50) NOT NULL, performed_by VARCHAR(255) NOT NULL, performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, parts_used VARCHAR(1000), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"),
        # maintenance_plan 新增列（增量）
        ("maintenance_plan", "is_closed",
         "ALTER TABLE maintenance_plan ADD COLUMN is_closed TINYINT NOT NULL DEFAULT 0"),
        ("maintenance_plan", "closed_at",
         "ALTER TABLE maintenance_plan ADD COLUMN closed_at TIMESTAMP NULL DEFAULT NULL"),
        ("maintenance_plan", "closed_by",
         "ALTER TABLE maintenance_plan ADD COLUMN closed_by VARCHAR(255) NULL DEFAULT NULL"),
        ("maintenance_plan", "close_reason",
         "ALTER TABLE maintenance_plan ADD COLUMN close_reason TEXT NULL DEFAULT NULL"),
        # spare_parts 系列表（增量创建）
        ("spare_parts", "_table",
         "CREATE TABLE IF NOT EXISTS spare_parts (id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(50) NOT NULL UNIQUE, name VARCHAR(200) NOT NULL, category VARCHAR(50) NOT NULL DEFAULT 'other', specification VARCHAR(200), unit VARCHAR(20) NOT NULL DEFAULT '个', brand VARCHAR(100), safety_stock_min INT NOT NULL DEFAULT 0, safety_stock_max INT NOT NULL DEFAULT 9999, current_stock INT NOT NULL DEFAULT 0, weighted_avg_price DECIMAL(10,2) DEFAULT 0, supplier_name VARCHAR(200), supplier_contact VARCHAR(100), supplier_phone VARCHAR(50), supplier_doc_path VARCHAR(500), remark TEXT, is_active TINYINT NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"),
        ("spare_part_inbounds", "_table",
         "CREATE TABLE IF NOT EXISTS spare_part_inbounds (id INT AUTO_INCREMENT PRIMARY KEY, spare_part_id INT NOT NULL, quantity INT NOT NULL, unit_price DECIMAL(10,2) NOT NULL DEFAULT 0, batch_no VARCHAR(50), inbound_date DATE NOT NULL, doc_path VARCHAR(500), remark TEXT, created_by VARCHAR(255) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"),
        ("spare_part_consumptions", "_table",
         "CREATE TABLE IF NOT EXISTS spare_part_consumptions (id INT AUTO_INCREMENT PRIMARY KEY, spare_part_id INT NOT NULL, maintenance_record_id INT, quantity INT NOT NULL, unit_price DECIMAL(10,2) NOT NULL DEFAULT 0, batch_no VARCHAR(50), consumed_by VARCHAR(255) NOT NULL, consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, remark TEXT, FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"),
        ("spare_part_alerts", "_table",
         "CREATE TABLE IF NOT EXISTS spare_part_alerts (id INT AUTO_INCREMENT PRIMARY KEY, spare_part_id INT NOT NULL, alert_type VARCHAR(50) NOT NULL, current_stock INT NOT NULL, threshold INT NOT NULL, is_resolved TINYINT NOT NULL DEFAULT 0, resolved_at TIMESTAMP NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"),
    ]
    for table, col, ddl in migrations:
        try:
            if col == "_table":
                cur.execute(ddl)
                print(f"[DB] Created table {table} (if not exists)")
            else:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
                    (table, col)
                )
                row = cur.fetchone()
                exists = row["cnt"] if isinstance(row, dict) else row[0]
                if not exists:
                    cur.execute(ddl)
                    print(f"[DB] Added column {table}.{col}")
                else:
                    print(f"[DB] Column {table}.{col} already exists, skipping")
        except Exception as e:
            import traceback
            print(f"[DB] Migration error for {table}.{col}: {e}")
            traceback.print_exc()
            raise


def _init_mysql_tables(cur, conn):
    """初始化 MySQL 表结构"""
    tables = [
        ("users", """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                permissions VARCHAR(500) DEFAULT '[]'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("devices", """
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
        """),
        ("documents", """
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
                calibration_due_date DATE DEFAULT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("borrow_records", """
            CREATE TABLE IF NOT EXISTS borrow_records (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT NOT NULL,
                borrower VARCHAR(255) NOT NULL,
                department VARCHAR(100),
                borrow_date DATE,
                expected_return_date DATE,
                actual_return_date DATE,
                status VARCHAR(20) NOT NULL DEFAULT 'borrowed',
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("audit_logs", """
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
        """),
        ("approval_requests", """
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_id INT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                created_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_step INT NOT NULL DEFAULT 1,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("approval_steps", """
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
        """),
        ("signatures", """
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
        """),
        ("system_settings", """
            CREATE TABLE IF NOT EXISTS system_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                setting_key VARCHAR(255) UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                description VARCHAR(500),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                updated_by VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("password_reset_requests", """
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
        """),
        ("maintenance_plan", """
            CREATE TABLE IF NOT EXISTS maintenance_plan (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id INT NOT NULL,
                maintenance_type VARCHAR(50) NOT NULL,
                interval_days INT NOT NULL,
                next_due_date VARCHAR(50) NOT NULL,
                is_active TINYINT NOT NULL DEFAULT 1,
                is_closed TINYINT NOT NULL DEFAULT 0,
                closed_at TIMESTAMP NULL DEFAULT NULL,
                closed_by VARCHAR(255) NULL DEFAULT NULL,
                close_reason TEXT NULL DEFAULT NULL,
                created_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("maintenance_record", """
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
        """),
        ("repair_record", """
            CREATE TABLE IF NOT EXISTS repair_record (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id INT NOT NULL,
                content VARCHAR(2000) NOT NULL,
                result VARCHAR(50) NOT NULL,
                performed_by VARCHAR(255) NOT NULL,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parts_used VARCHAR(1000),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("device_status_requests", """
            CREATE TABLE IF NOT EXISTS device_status_requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                device_id INT NOT NULL,
                new_status VARCHAR(50) NOT NULL,
                reason VARCHAR(1000),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                requested_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                decided_by VARCHAR(255),
                decided_at TIMESTAMP NULL,
                comment TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("electronic_signatures", """
            CREATE TABLE IF NOT EXISTS electronic_signatures (
                id INT AUTO_INCREMENT PRIMARY KEY,
                record_type VARCHAR(50) NOT NULL COMMENT '业务类型: maintenance_plan/document/device_change/maintenance_record',
                record_id INT NOT NULL COMMENT '关联业务记录ID',
                signed_by VARCHAR(255) NOT NULL COMMENT '签名人用户名',
                signed_by_display VARCHAR(100) NOT NULL COMMENT '签名人显示名',
                sign_meaning VARCHAR(50) NOT NULL COMMENT '签名含义: approved/reviewed/executed/released',
                sign_meaning_label VARCHAR(50) NOT NULL COMMENT '签名含义中文: 批准/审核/执行/放行',
                signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '签名时间(服务器时间)',
                ip_address VARCHAR(50) COMMENT '签名IP',
                remark TEXT COMMENT '备注',
                is_deleted TINYINT NOT NULL DEFAULT 0 COMMENT '软删除标记(审计要求不可物理删除)'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("spare_parts", """
            CREATE TABLE IF NOT EXISTS spare_parts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(200) NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'other',
                specification VARCHAR(200),
                unit VARCHAR(20) NOT NULL DEFAULT '个',
                brand VARCHAR(100),
                safety_stock_min INT NOT NULL DEFAULT 0,
                safety_stock_max INT NOT NULL DEFAULT 9999,
                current_stock INT NOT NULL DEFAULT 0,
                weighted_avg_price DECIMAL(10,2) DEFAULT 0,
                supplier_name VARCHAR(200),
                supplier_contact VARCHAR(100),
                supplier_phone VARCHAR(50),
                supplier_doc_path VARCHAR(500),
                remark TEXT,
                is_active TINYINT NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("spare_part_inbounds", """
            CREATE TABLE IF NOT EXISTS spare_part_inbounds (
                id INT AUTO_INCREMENT PRIMARY KEY,
                spare_part_id INT NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
                batch_no VARCHAR(50),
                inbound_date DATE NOT NULL,
                doc_path VARCHAR(500),
                remark TEXT,
                created_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("spare_part_consumptions", """
            CREATE TABLE IF NOT EXISTS spare_part_consumptions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                spare_part_id INT NOT NULL,
                maintenance_record_id INT,
                quantity INT NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL DEFAULT 0,
                batch_no VARCHAR(50),
                consumed_by VARCHAR(255) NOT NULL,
                consumed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                remark TEXT,
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
        ("spare_part_alerts", """
            CREATE TABLE IF NOT EXISTS spare_part_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                spare_part_id INT NOT NULL,
                alert_type VARCHAR(50) NOT NULL,
                current_stock INT NOT NULL,
                threshold INT NOT NULL,
                is_resolved TINYINT NOT NULL DEFAULT 0,
                resolved_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """),
    ]

    for _name, _ddl in tables:
        cur.execute(_ddl)

    _ensure_default_settings(cur, conn, db_type='mysql')
    _ensure_default_user(cur, "admin", "admin123", "admin", db_type='mysql')
    _ensure_default_user(cur, "user", "user123", "equipment_engineer", db_type='mysql')
    _migrate_mysql_columns(cur)


def _init_sqlite_tables(cur, conn):
    """初始化 SQLite 表结构"""
    tables = [
        ("users", """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                permissions TEXT DEFAULT '[]'
            )
        """),
        ("devices", """
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
        """),
        ("documents", """
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
                calibration_due_date DATE DEFAULT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """),
        ("borrow_records", """
            CREATE TABLE IF NOT EXISTS borrow_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                borrower TEXT NOT NULL,
                department TEXT,
                borrow_date DATE,
                expected_return_date DATE,
                actual_return_date DATE,
                status TEXT NOT NULL DEFAULT 'borrowed',
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(id)
            )
        """),
        ("audit_logs", """
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
        """),
        ("approval_requests", """
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_by TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                current_step INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (doc_id) REFERENCES documents(id)
            )
        """),
        ("approval_steps", """
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
        """),
        ("signatures", """
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
        """),
        ("system_settings", """
            CREATE TABLE IF NOT EXISTS system_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        """),
        ("password_reset_requests", """
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
        """),
        ("maintenance_plan", """
            CREATE TABLE IF NOT EXISTS maintenance_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                maintenance_type TEXT NOT NULL,
                interval_days INTEGER NOT NULL,
                next_due_date TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_closed INTEGER NOT NULL DEFAULT 0,
                closed_at TEXT NULL DEFAULT NULL,
                closed_by TEXT NULL DEFAULT NULL,
                close_reason TEXT NULL DEFAULT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """),
        ("maintenance_record", """
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
        """),
        ("repair_record", """
            CREATE TABLE IF NOT EXISTS repair_record (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                result TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                performed_at TEXT NOT NULL DEFAULT (datetime('now')),
                parts_used TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """),
        ("device_status_requests", """
            CREATE TABLE IF NOT EXISTS device_status_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                new_status TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                decided_by TEXT,
                decided_at TEXT,
                comment TEXT,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """),
        ("electronic_signatures", """
            CREATE TABLE IF NOT EXISTS electronic_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_type TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                signed_by TEXT NOT NULL,
                signed_by_display TEXT NOT NULL,
                sign_meaning TEXT NOT NULL,
                sign_meaning_label TEXT NOT NULL,
                signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                remark TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
        """),
        ("spare_parts", """
            CREATE TABLE IF NOT EXISTS spare_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                specification TEXT,
                unit TEXT NOT NULL DEFAULT '个',
                brand TEXT,
                safety_stock_min INTEGER NOT NULL DEFAULT 0,
                safety_stock_max INTEGER NOT NULL DEFAULT 9999,
                current_stock INTEGER NOT NULL DEFAULT 0,
                weighted_avg_price REAL DEFAULT 0,
                supplier_name TEXT,
                supplier_contact TEXT,
                supplier_phone TEXT,
                supplier_doc_path TEXT,
                remark TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """),
        ("spare_part_inbounds", """
            CREATE TABLE IF NOT EXISTS spare_part_inbounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spare_part_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL DEFAULT 0,
                batch_no TEXT,
                inbound_date TEXT NOT NULL,
                doc_path TEXT,
                remark TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            )
        """),
        ("spare_part_consumptions", """
            CREATE TABLE IF NOT EXISTS spare_part_consumptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spare_part_id INTEGER NOT NULL,
                maintenance_record_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL DEFAULT 0,
                batch_no TEXT,
                consumed_by TEXT NOT NULL,
                consumed_at TEXT NOT NULL DEFAULT (datetime('now')),
                remark TEXT,
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            )
        """),
        ("spare_part_alerts", """
            CREATE TABLE IF NOT EXISTS spare_part_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spare_part_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                current_stock INTEGER NOT NULL,
                threshold INTEGER NOT NULL,
                is_resolved INTEGER NOT NULL DEFAULT 0,
                resolved_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id)
            )
        """),
    ]

    for _name, _ddl in tables:
        cur.execute(_ddl)

    # SQLite 增量升级：新增列
    _migrate_sqlite_columns(cur)

    _ensure_default_settings(cur, conn, db_type='sqlite')
    _ensure_default_user(cur, "admin", "admin123", "admin", db_type='sqlite')
    _ensure_default_user(cur, "user", "user123", "equipment_engineer", db_type='sqlite')


def _migrate_sqlite_columns(cur):
    """SQLite 增量升级：添加历史遗留列"""
    migrations = [
        ("documents", "download_count", "ALTER TABLE documents ADD COLUMN download_count INTEGER DEFAULT 0"),
        ("documents", "status",         "ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'draft'"),
        ("documents", "is_deleted",     "ALTER TABLE documents ADD COLUMN is_deleted INTEGER DEFAULT 0"),
        ("users",     "status",         "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"),
        ("users",     "permissions",    "ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '[]'"),
        ("audit_logs","before_value",   "ALTER TABLE audit_logs ADD COLUMN before_value TEXT"),
        ("audit_logs","after_value",    "ALTER TABLE audit_logs ADD COLUMN after_value TEXT"),
        ("audit_logs","reason",         "ALTER TABLE audit_logs ADD COLUMN reason TEXT"),
        ("audit_logs","ip_address",     "ALTER TABLE audit_logs ADD COLUMN ip_address TEXT"),
        ("devices",   "is_deleted",     "ALTER TABLE devices ADD COLUMN is_deleted INTEGER DEFAULT 0"),
        # borrow_records 增量列
        ("borrow_records", "department",           "ALTER TABLE borrow_records ADD COLUMN department TEXT"),
        ("borrow_records", "borrow_date",          "ALTER TABLE borrow_records ADD COLUMN borrow_date DATE"),
        ("borrow_records", "expected_return_date", "ALTER TABLE borrow_records ADD COLUMN expected_return_date DATE"),
        ("borrow_records", "actual_return_date",   "ALTER TABLE borrow_records ADD COLUMN actual_return_date DATE"),
        ("borrow_records", "remarks",              "ALTER TABLE borrow_records ADD COLUMN remarks TEXT"),
        ("borrow_records", "created_at",           "ALTER TABLE borrow_records ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("documents",      "calibration_due_date", "ALTER TABLE documents ADD COLUMN calibration_due_date DATE DEFAULT NULL"),
        # repair_record 表（增量创建）
        ("repair_record", "_table", "CREATE TABLE IF NOT EXISTS repair_record (id INTEGER PRIMARY KEY AUTOINCREMENT, device_id INTEGER NOT NULL, content TEXT NOT NULL, result TEXT NOT NULL, performed_by TEXT NOT NULL, performed_at TEXT NOT NULL DEFAULT (datetime('now')), parts_used TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (device_id) REFERENCES devices(id))"),
        # maintenance_plan 新增列（增量）
        ("maintenance_plan", "is_closed",
         "ALTER TABLE maintenance_plan ADD COLUMN is_closed TINYINT NOT NULL DEFAULT 0"),
        ("maintenance_plan", "closed_at",
         "ALTER TABLE maintenance_plan ADD COLUMN closed_at TIMESTAMP NULL DEFAULT NULL"),
        ("maintenance_plan", "closed_by",
         "ALTER TABLE maintenance_plan ADD COLUMN closed_by VARCHAR(255) NULL DEFAULT NULL"),
        ("maintenance_plan", "close_reason",
         "ALTER TABLE maintenance_plan ADD COLUMN close_reason TEXT NULL DEFAULT NULL"),
        # spare_parts 系列表（增量创建）
        ("spare_parts", "_table", "CREATE TABLE IF NOT EXISTS spare_parts (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'other', specification TEXT, unit TEXT NOT NULL DEFAULT '个', brand TEXT, safety_stock_min INTEGER NOT NULL DEFAULT 0, safety_stock_max INTEGER NOT NULL DEFAULT 9999, current_stock INTEGER NOT NULL DEFAULT 0, weighted_avg_price REAL DEFAULT 0, supplier_name TEXT, supplier_contact TEXT, supplier_phone TEXT, supplier_doc_path TEXT, remark TEXT, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')))"),
        ("spare_part_inbounds", "_table", "CREATE TABLE IF NOT EXISTS spare_part_inbounds (id INTEGER PRIMARY KEY AUTOINCREMENT, spare_part_id INTEGER NOT NULL, quantity INTEGER NOT NULL, unit_price REAL NOT NULL DEFAULT 0, batch_no TEXT, inbound_date TEXT NOT NULL, doc_path TEXT, remark TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id))"),
        ("spare_part_consumptions", "_table", "CREATE TABLE IF NOT EXISTS spare_part_consumptions (id INTEGER PRIMARY KEY AUTOINCREMENT, spare_part_id INTEGER NOT NULL, maintenance_record_id INTEGER, quantity INTEGER NOT NULL, unit_price REAL NOT NULL DEFAULT 0, batch_no TEXT, consumed_by TEXT NOT NULL, consumed_at TEXT NOT NULL DEFAULT (datetime('now')), remark TEXT, FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id))"),
        ("spare_part_alerts", "_table", "CREATE TABLE IF NOT EXISTS spare_part_alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, spare_part_id INTEGER NOT NULL, alert_type TEXT NOT NULL, current_stock INTEGER NOT NULL, threshold INTEGER NOT NULL, is_resolved INTEGER NOT NULL DEFAULT 0, resolved_at TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (spare_part_id) REFERENCES spare_parts(id))"),
    ]
    for table, col, ddl in migrations:
        try:
            if col == "_table":
                cur.execute(ddl)
                print(f"[DB] Created table {table} (if not exists)")
            else:
                cur.execute(f"PRAGMA table_info({table})")
                cols = {row["name"] for row in cur.fetchall()}
                if col not in cols:
                    cur.execute(ddl)
                    print(f"[DB] Added column {table}.{col}")
        except Exception as e:
            import traceback
            print(f"[DB] Migration error for {table}.{col}: {e}")
            traceback.print_exc()


def ensure_column(cur, table_name, column_name, ddl_sql):
    """若字段不存在则添加（轻量迁移）。"""
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = {row["name"] for row in cur.fetchall()}
    if column_name not in columns:
        cur.execute(ddl_sql)


def _ensure_default_user(cur, username, password, role, db_type='mysql'):
    """默认用户不存在时才插入（同时兼容 MySQL/SQLite）。"""
    from werkzeug.security import generate_password_hash
    if db_type == 'mysql':
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    else:
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))

    if cur.fetchone() is None:
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        if db_type == 'mysql':
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, hashed, role),
            )
        else:
            cur.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, hashed, role),
            )


def _ensure_default_settings(cur, conn, db_type='mysql'):
    """初始化默认系统设置（同时兼容 MySQL/SQLite）。"""
    default_settings = [
        ("approval_enabled", "true",  "是否启用审批流程（设备变更、文档上传等）"),
        ("auto_approve_document", "false", "文档上传后是否自动生效"),
        ("borrowing_enabled", "true", "是否启用借阅功能（借阅、归还文档等）"),
    ]
    import time

    for key, value, description in default_settings:
        if db_type == 'mysql':
            # MySQL：用 INSERT IGNORE 防重
            cur.execute(
                "INSERT IGNORE INTO system_settings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
                (key, value, description),
            )
        else:
            # SQLite：用 INSERT OR IGNORE 防重（无 MySQL 的 INSERT IGNORE 语法）
            cur.execute(
                "INSERT OR IGNORE INTO system_settings (setting_key, setting_value, description) VALUES (?, ?, ?)",
                (key, value, description),
            )


def get_system_setting(key, default=None):
    """获取系统设置值"""
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == 'mysql':
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
    cur.execute("SELECT * FROM system_settings ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


def update_system_setting(key, value, updated_by=None):
    """更新系统设置"""
    conn = get_db()
    cur = conn.cursor()
    if DB_TYPE == 'mysql':
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
