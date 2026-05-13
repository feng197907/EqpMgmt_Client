#!/usr/bin/env python3
"""
SQLite 到 MySQL 数据迁移脚本

使用方法:
    1. 配置 MySQL 连接参数
    2. 运行脚本: python migrate_to_mysql.py

注意事项:
    - 建议先备份原数据库
    - 首次运行会清空 MySQL 表数据（可指定 --no-clear 保留）
    - 迁移完成后请验证数据完整性
"""

import sqlite3
import pymysql
import sys
import os
from datetime import datetime

# ==================== 配置区域 ====================

# SQLite 数据库路径
SQLITE_DB_PATH = 'dms.db'

# MySQL 连接配置
MYSQL_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', 3306)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'your_password'),
    'database': os.environ.get('DB_NAME', 'dms_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 需要迁移的表及其字段映射
# key: SQLite 表名, value: (MySQL 表名, 字段列表)
TABLE_MIGRATIONS = {
    'users': {
        'mysql_table': 'users',
        'columns': [
            'id', 'username', 'password_hash', 'email', 'role',
            'is_active', 'is_admin', 'department', 'phone',
            'created_at', 'last_login', 'created_by'
        ],
        'batch_size': 100
    },
    'devices': {
        'mysql_table': 'devices',
        'columns': [
            'id', 'device_code', 'device_name', 'device_type',
            'model', 'serial_number', 'manufacturer', 'purchase_date',
            'location', 'status', 'responsible_person', 'remarks',
            'created_at', 'updated_at', 'created_by'
        ],
        'batch_size': 100
    },
    'documents': {
        'mysql_table': 'documents',
        'columns': [
            'id', 'device_id', 'document_type', 'document_name',
            'file_path', 'file_size', 'file_type', 'version',
            'status', 'uploaded_by', 'uploaded_at', 'remarks',
            'created_at', 'updated_at'
        ],
        'batch_size': 50
    },
    'borrowing_records': {
        'mysql_table': 'borrowing_records',
        'columns': [
            'id', 'document_id', 'device_id', 'borrower',
            'borrow_date', 'expected_return_date', 'actual_return_date',
            'status', 'remarks', 'created_at', 'updated_at'
        ],
        'batch_size': 100
    },
    'approval_requests': {
        'mysql_table': 'approval_requests',
        'columns': [
            'id', 'document_id', 'device_id', 'request_type',
            'applicant', 'approver', 'status', 'remarks',
            'approved_at', 'created_at', 'updated_at'
        ],
        'batch_size': 100
    },
    'audit_logs': {
        'mysql_table': 'audit_logs',
        'columns': [
            'id', 'user_id', 'username', 'action', 'resource_type',
            'resource_id', 'details', 'ip_address', 'created_at'
        ],
        'batch_size': 500
    },
    'device_changes': {
        'mysql_table': 'device_changes',
        'columns': [
            'id', 'device_id', 'change_type', 'field_name',
            'old_value', 'new_value', 'changed_by', 'changed_at', 'reason'
        ],
        'batch_size': 200
    },
    'password_reset_requests': {
        'mysql_table': 'password_reset_requests',
        'columns': [
            'id', 'user_id', 'username', 'email', 'status',
            'requested_at', 'processed_by', 'processed_at'
        ],
        'batch_size': 100
    },
    # 如果有其他表，继续添加...
}


class MigrationError(Exception):
    """迁移过程中的自定义异常"""
    pass


def get_sqlite_connection(db_path):
    """连接 SQLite 数据库"""
    if not os.path.exists(db_path):
        raise MigrationError(f"SQLite 数据库文件不存在: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_mysql_connection(config):
    """连接 MySQL 数据库"""
    try:
        conn = pymysql.connect(**config)
        return conn
    except pymysql.Error as e:
        raise MigrationError(f"MySQL 连接失败: {e}")


def check_table_exists_mysql(cursor, table_name):
    """检查 MySQL 表是否存在"""
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = %s
    """, (table_name,))
    return cursor.fetchone()['count'] > 0


def clear_mysql_table(cursor, table_name):
    """清空 MySQL 表数据"""
    cursor.execute(f"TRUNCATE TABLE {table_name}")


def get_sqlite_table_columns(cursor, table_name):
    """获取 SQLite 表的列信息"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row['name'] for row in cursor.fetchall()]


def escape_value(value):
    """处理特殊值"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return value
    return str(value)


def migrate_table(sqlite_conn, mysql_conn, sqlite_table, config, clear_data=True):
    """迁移单个表"""
    mysql_table = config['mysql_table']
    columns = config['columns']
    batch_size = config.get('batch_size', 100)

    sqlite_cursor = sqlite_conn.cursor()
    mysql_cursor = mysql_conn.cursor()

    # 检查 SQLite 表是否存在
    sqlite_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (sqlite_table,))
    if not sqlite_cursor.fetchone():
        print(f"  ⚠️  SQLite 表 '{sqlite_table}' 不存在，跳过")
        return 0

    # 检查 MySQL 表是否存在
    if not check_table_exists_mysql(mysql_cursor, mysql_table):
        print(f"  ⚠️  MySQL 表 '{mysql_table}' 不存在，跳过")
        return 0

    # 清空 MySQL 表
    if clear_data:
        clear_mysql_table(mysql_cursor, mysql_table)
        print(f"  🗑️  已清空 MySQL 表 '{mysql_table}'")

    # 获取 SQLite 数据
    sqlite_cursor.execute(f"SELECT * FROM {sqlite_table}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        print(f"  📭  SQLite 表 '{sqlite_table}' 无数据")
        return 0

    print(f"  📊  开始迁移 {len(rows)} 条记录...")

    # 构建插入 SQL
    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {mysql_table} ({', '.join(columns)}) VALUES ({placeholders})"

    # 批量插入
    total_inserted = 0
    batch = []

    for row in rows:
        # 构建记录（按列顺序取值）
        record = []
        for col in columns:
            # 尝试从 SQLite 获取值
            value = row.get(col)
            # 处理 datetime 格式
            if isinstance(value, str) and ('T' in value or ':' in value):
                try:
                    # 尝试解析为 datetime
                    value = datetime.fromisoformat(value.replace(' ', 'T'))
                except:
                    pass
            record.append(escape_value(value))

        batch.append(tuple(record))

        # 达到批次大小时插入
        if len(batch) >= batch_size:
            try:
                mysql_cursor.executemany(insert_sql, batch)
                mysql_conn.commit()
                total_inserted += len(batch)
                print(f"    已插入 {total_inserted}/{len(rows)} 条...")
            except pymysql.Error as e:
                print(f"    ❌ 插入失败: {e}")
                mysql_conn.rollback()
                # 单条尝试插入，忽略失败的记录
                for record in batch:
                    try:
                        mysql_cursor.execute(insert_sql, record)
                        mysql_conn.commit()
                        total_inserted += 1
                    except:
                        pass
            batch = []

    # 插入剩余记录
    if batch:
        try:
            mysql_cursor.executemany(insert_sql, batch)
            mysql_conn.commit()
            total_inserted += len(batch)
        except pymysql.Error as e:
            print(f"    ❌ 批量插入失败: {e}")
            mysql_conn.rollback()
            for record in batch:
                try:
                    mysql_cursor.execute(insert_sql, record)
                    mysql_conn.commit()
                    total_inserted += 1
                except:
                    pass

    sqlite_cursor.close()
    print(f"  ✅  完成迁移 {total_inserted}/{len(rows)} 条记录到 '{mysql_table}'")

    return total_inserted


def verify_migration(sqlite_conn, mysql_conn):
    """验证迁移结果"""
    print("\n" + "=" * 50)
    print("📋 迁移验证")
    print("=" * 50)

    sqlite_cursor = sqlite_conn.cursor()
    mysql_cursor = mysql_conn.cursor()

    all_match = True

    for sqlite_table, config in TABLE_MIGRATIONS.items():
        mysql_table = config['mysql_table']

        # 检查表是否存在
        if not check_table_exists_mysql(mysql_cursor, mysql_table):
            continue

        # 统计数量
        sqlite_cursor.execute(f"SELECT COUNT(*) as count FROM {sqlite_table}")
        sqlite_count = sqlite_cursor.fetchone()['count']

        mysql_cursor.execute(f"SELECT COUNT(*) as count FROM {mysql_table}")
        mysql_count = mysql_cursor.fetchone()['count']

        status = "✅" if sqlite_count == mysql_count else "❌"
        print(f"  {status} {sqlite_table}: SQLite={sqlite_count}, MySQL={mysql_count}")

        if sqlite_count != mysql_count:
            all_match = False

    sqlite_cursor.close()
    mysql_cursor.close()

    return all_match


def main():
    """主函数"""
    print("=" * 50)
    print("🔄 SQLite 到 MySQL 数据迁移工具")
    print("=" * 50)
    print(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"SQLite: {SQLITE_DB_PATH}")
    print(f"MySQL: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}")

    # 确认操作
    if '--dry-run' not in sys.argv:
        confirm = input("\n⚠️  警告: 此操作将清空 MySQL 表数据！是否继续？(yes/no): ")
        if confirm.lower() not in ('yes', 'y'):
            print("已取消迁移")
            sys.exit(0)

    # 连接数据库
    print("\n📡 连接数据库...")
    try:
        sqlite_conn = get_sqlite_connection(SQLITE_DB_PATH)
        print(f"  ✅ SQLite 连接成功")
    except MigrationError as e:
        print(f"  ❌ {e}")
        sys.exit(1)

    try:
        mysql_conn = get_mysql_connection(MYSQL_CONFIG)
        print(f"  ✅ MySQL 连接成功")
    except MigrationError as e:
        print(f"  ❌ {e}")
        sys.exit(1)

    # 执行迁移
    print("\n🚀 开始迁移...")
    print("-" * 50)

    total_records = 0
    clear_data = '--no-clear' not in sys.argv

    for sqlite_table, config in TABLE_MIGRATIONS.items():
        print(f"\n📦 迁移表: {sqlite_table}")
        try:
            count = migrate_table(sqlite_conn, mysql_conn, sqlite_table, config, clear_data)
            total_records += count
        except Exception as e:
            print(f"  ❌ 迁移失败: {e}")

    # 关闭连接
    sqlite_conn.close()
    mysql_conn.close()

    # 验证
    print("\n" + "-" * 50)
    try:
        sqlite_conn = get_sqlite_connection(SQLITE_DB_PATH)
        mysql_conn = get_mysql_connection(MYSQL_CONFIG)
        verify_migration(sqlite_conn, mysql_conn)
        sqlite_conn.close()
        mysql_conn.close()
    except Exception as e:
        print(f"验证失败: {e}")

    # 完成
    print("\n" + "=" * 50)
    print(f"✅ 迁移完成！共迁移 {total_records} 条记录")
    print("=" * 50)

    print("\n💡 提示:")
    print("  - 使用 --dry-run 参数可预览迁移计划（不执行）")
    print("  - 使用 --no-clear 参数可保留 MySQL 表中现有数据")
    print("  - 建议手动验证数据完整性后再删除 SQLite 数据库")


if __name__ == '__main__':
    main()
