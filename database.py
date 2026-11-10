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
# 数据库类型：本项目统一使用 SQLite
#
# 产品定位为单机客户端（Windows 桌面壳 / 本机浏览器访问），单写者足够；
# 历史上支持过的 MySQL 多用户部署已移除，需要多用户 Web 时走新架构。
# 保留 DB_TYPE 常量（恒为 'sqlite'），供历史代码中的方言判断引用。
# ============================================================
DB_TYPE = 'sqlite'

import sqlite3
from werkzeug.security import generate_password_hash

# ============================================================
# 数据库配置
# ============================================================

# SQLite 数据库路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 默认数据库路径：Windows 下放到 %APPDATA%/DMS，便于普通用户读写
if os.name == 'nt':
    _appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
    _default_db_dir = os.path.join(_appdata, 'DMS')
    _default_db_path = os.path.join(_default_db_dir, 'equipment.db')
else:
    _default_db_path = os.path.join(BASE_DIR, 'equipment.db')

DB_PATH = os.environ.get('DB_PATH', _default_db_path)

# 确保数据库目录存在（避免首次运行权限/路径异常）
try:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
except Exception:
    pass

# ============================================================
# 兼容层：统一两种数据库的占位符和连接/游标行为
# ============================================================

def _convert_placeholder(sql):
    """把业务代码里习惯写的 %s 转成 SQLite 的 ? 占位符。

    全项目有近 400 处 %s，逐个改成 ? 收益为零、风险不小，
    统一在这一层转换即可。
    """
    return sql.replace('%s', '?')


def _normalize_sql_for_sqlite(sql):
    """把少量常见 MySQL 语法改写成 SQLite 可执行语法。"""
    sql = sql.replace('NOW()', 'CURRENT_TIMESTAMP')
    sql = re.sub(r"DATE_FORMAT\(([^,]+),\s*'%%Y-%%m'\)", r"strftime('%Y-%m', \1)", sql)
    sql = re.sub(r"DATE_FORMAT\(([^,]+),\s*'%Y-%m'\)", r"strftime('%Y-%m', \1)", sql)
    sql = sql.replace('INT AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
    sql = sql.replace('BIGINT AUTO_INCREMENT PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
    sql = sql.replace(') ENGINE=InnoDB DEFAULT CHARSET=utf8mb4', ')')
    sql = sql.replace(') ENGINE=InnoDB', ')')
    return sql


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
        if self._is_sqlite and isinstance(sql, str):
            sql = _normalize_sql_for_sqlite(sql)
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
    """获取 SQLite 连接（封装为 CompatibleConnection，游标行为对上层统一）。"""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # 外键约束 SQLite 默认关闭，必须每个连接显式打开
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    # WAL：读写互不阻塞。桌面壳以 threaded=True 启动，看板一次并发 4-5 个请求，
    # 默认 DELETE 日志模式下写事务会阻塞全部读，表现是「点一下卡几秒」。
    # journal_mode 是持久化设置，写进数据库头后由后续连接继承，这里重复设置无副作用。
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
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
    return '?'


# ============================================================
# 数据库初始化
# ============================================================

def init_db():
    """创建表结构，执行增量升级，并写入默认账号。"""
    conn = get_db()
    cur = conn.cursor()

    _init_sqlite_tables(cur, conn)

    # 建表之后补业务索引：DDL 里只有主键和少数 UNIQUE，
    # 列表页/看板/提醒中心的过滤与排序列此前全部裸奔。
    _ensure_indexes(cur)

    conn.commit()
    conn.close()


# ============================================================
# 业务索引
#
# 依据实际查询语句确定，不是照着外键随便建：
#   - audit_logs：页面 ORDER BY log_time DESC LIMIT 500 + 按操作人/类型筛选
#   - documents ：设备详情按 device_id 查、看板统计待审数、列表按上传时间倒序
#   - devices   ：看板 WHERE is_deleted=0 GROUP BY status
#   - maintenance_plan：提醒中心 WHERE is_active/is_closed + ORDER BY next_due_date
# 覆盖各表规模差异：审计日志和文档会持续增长，其余表量小但查询频繁。
# ============================================================
_BUSINESS_INDEXES = [
    # (索引名, 表名, 列定义)
    ("ix_audit_logs_log_time", "audit_logs", "log_time"),
    ("ix_audit_logs_user_time", "audit_logs", "user, log_time"),
    ("ix_audit_logs_type_time", "audit_logs", "target_type, log_time"),
    ("ix_documents_device", "documents", "device_id, is_deleted"),
    ("ix_documents_deleted_status", "documents", "is_deleted, status"),
    ("ix_documents_deleted_upload", "documents", "is_deleted, upload_time"),
    ("ix_devices_deleted_status", "devices", "is_deleted, status"),
    ("ix_maintenance_plan_due", "maintenance_plan", "is_active, is_closed, next_due_date"),
    ("ix_maintenance_record_device", "maintenance_record", "device_id"),
    ("ix_approval_requests_status", "approval_requests", "status"),
    ("ix_borrow_records_status", "borrow_records", "status"),
    ("ix_spare_inbounds_part", "spare_part_inbounds", "spare_part_id"),
    ("ix_spare_consumptions_part", "spare_part_consumptions", "spare_part_id"),
]


def _index_exists(cur, table, name):
    """索引是否已存在（查 sqlite_master）。"""
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type = 'index' AND name = %s",
        (name,),
    )
    row = cur.fetchone()
    if row is None:
        return False
    return bool(row["cnt"] if isinstance(row, dict) or hasattr(row, "keys") else row[0])


def _ensure_indexes(cur):
    """幂等地补建业务索引。

    老库升级时表都已存在，直接 CREATE INDEX 即可；新建库在建表后执行，
    效果相同。任何一条失败（例如列不存在）只打日志，不阻断启动 ——
    索引是性能优化，不应该让整个应用起不来。
    """
    created = 0
    skipped = 0
    for name, table, columns in _BUSINESS_INDEXES:
        try:
            if _index_exists(cur, table, name):
                skipped += 1
                continue
            cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({columns})")
            created += 1
        except Exception as exc:
            print(f"[DB] 索引 {name} 跳过：{exc}")

    if created or skipped:
        print(f"[DB] 业务索引：新建 {created} 个，已存在 {skipped} 个")


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

    _ensure_default_settings(cur, conn)
    _ensure_default_user(cur, "admin", "admin123", "admin")
    _ensure_default_user(cur, "user", "user123", "equipment_engineer")


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


def _ensure_default_user(cur, username, password, role):
    """默认用户不存在时才插入。"""
    cur.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cur.fetchone() is None:
        hashed = generate_password_hash(password, method='pbkdf2:sha256')
        cur.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed, role),
        )


def _ensure_default_settings(cur, conn):
    """初始化默认系统设置。"""
    default_settings = [
        ("approval_enabled", "true",  "是否启用审批流程（设备变更、文档上传等）"),
        ("auto_approve_document", "false", "文档上传后是否自动生效"),
        ("borrowing_enabled", "true", "是否启用借阅功能（借阅、归还文档等）"),
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
    cur.execute(
        "UPDATE system_settings SET setting_value = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE setting_key = ?",
        (value, updated_by, key),
    )
    conn.commit()
    conn.close()
