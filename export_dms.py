# -*- coding: utf-8 -*-
"""
SQLite to MySQL Migration Script
读取 D:\EquipmentManagement\dms.db，生成 MySQL SQL 脚本

使用方法：
1. 把此脚本放到 D:\EquipmentManagement 目录
2. 双击运行 或 执行: python export_dms.py
3. 上传生成的 migrate_dms.sql 到服务器
4. 在服务器执行: mysql -u root -p dms_db < migrate_dms.sql
"""

import sqlite3
import os
import re
from datetime import datetime

# 配置
DB_PATH = '/data/EquipmentManagement/dms.db'
OUTPUT_PATH = '/data/EquipmentManagement/migrate_dms.sql'

def convert_sqlite_to_mysql_type(sqlite_type):
    """将 SQLite 类型转换为 MySQL 类型"""
    sqlite_type = sqlite_type.upper()

    if 'INT' in sqlite_type:
        return 'INT'
    elif 'TEXT' in sqlite_type or 'CLOB' in sqlite_type:
        return 'TEXT'
    elif 'REAL' in sqlite_type or 'FLOAT' in sqlite_type or 'DOUBLE' in sqlite_type:
        return 'DOUBLE'
    elif 'NUMERIC' in sqlite_type or 'DECIMAL' in sqlite_type:
        return 'DECIMAL(10,2)'
    elif 'BLOB' in sqlite_type:
        return 'BLOB'
    elif 'BOOLEAN' in sqlite_type:
        return 'TINYINT(1)'
    else:
        return 'VARCHAR(255)'

def parse_create_table(create_sql, table_name):
    """解析 CREATE TABLE 语句并转换为 MySQL 格式"""
    if 'WITHOUT ROWID' in create_sql:
        create_sql = create_sql.replace('WITHOUT ROWID', '')

    lines = create_sql.split('\n')
    columns = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('CREATE TABLE') or line.startswith(')'):
            continue

        parts = line.rstrip(',').split()
        if not parts:
            continue

        col_name = parts[0].strip('`"[]')
        col_type = ' '.join(parts[1:]) if len(parts) > 1 else 'TEXT'

        # 处理 PRIMARY KEY
        if 'PRIMARY KEY' in line.upper():
            if 'INTEGER' in col_type.upper():
                col_type = 'INT AUTO_INCREMENT PRIMARY KEY'
            else:
                col_type = convert_sqlite_to_mysql_type(col_type) + ' PRIMARY KEY'

        # 处理 NOT NULL
        if 'NOT NULL' in line.upper():
            if 'PRIMARY KEY' not in line.upper():
                col_type = convert_sqlite_to_mysql_type(col_type) + ' NOT NULL'

        # 处理 DEFAULT
        if 'DEFAULT' in line.upper():
            pass
        elif 'PRIMARY KEY' not in line.upper() and 'NOT NULL' not in line.upper():
            col_type = convert_sqlite_to_mysql_type(col_type)

        columns.append(f"  `{col_name}` {col_type}")

    sql = f"CREATE TABLE IF NOT EXISTS `{table_name}` (\n"
    sql += ',\n'.join(columns)
    sql += "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
    return sql

def escape_value(val):
    """转义 SQL 值"""
    if val is None:
        return 'NULL'
    elif isinstance(val, bool):
        return '1' if val else '0'
    elif isinstance(val, (int, float)):
        return str(val)
    else:
        val = str(val).replace('\\', '\\\\').replace("'", "\\'")
        return f"'{val}'"

def export_sqlite_to_mysql():
    """导出 SQLite 数据库为 MySQL SQL 文件"""
    print("=" * 60)
    print("SQLite (dms.db) to MySQL 迁移脚本")
    print("=" * 60)
    print(f"源数据库: {DB_PATH}")
    print(f"输出文件: {OUTPUT_PATH}")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"\n错误: 数据库文件不存在!")
        print(f"请确认文件位于: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("-- SQLite dms.db to MySQL Migration Script\n")
            f.write(f"-- Generated from: {DB_PATH}\n")
            f.write(f"-- Generated at: {datetime.now()}\n\n")
            f.write("SET NAMES utf8mb4;\n")
            f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

            # 获取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]

            print(f"\n找到 {len(tables)} 个表:")
            for t in tables:
                print(f"  - {t}")

            for table in tables:
                print(f"\n处理表: {table}")

                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
                create_sql = cursor.fetchone()[0]
                mysql_create = parse_create_table(create_sql, table)

                f.write("-- " + "=" * 60 + "\n")
                f.write(f"-- Table: {table}\n")
                f.write("-- " + "=" * 60 + "\n\n")
                f.write(f"DROP TABLE IF EXISTS `{table}`;\n\n")
                f.write(mysql_create + "\n\n")

                cursor.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]

                if not columns:
                    continue

                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                row_count = 0

                for row in rows:
                    values = [escape_value(val) for val in row]
                    cols = ', '.join(f'`{c}`' for c in columns)
                    vals = ', '.join(values)
                    f.write(f"INSERT INTO `{table}` ({cols}) VALUES ({vals});\n")
                    row_count += 1

                print(f"  导出 {row_count} 条记录")

                f.write("\n")

            f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

        conn.close()
        print(f"\n" + "=" * 60)
        print("完成!")
        print(f"=" * 60)
        print(f"SQL 文件已生成: {OUTPUT_PATH}")
        print(f"\n下一步:")
        print("1. 上传 migrate_dms.sql 到服务器")
        print("2. 在服务器执行:")
        print("   mysql -u root -p dms_db < migrate_dms.sql")
        return True

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = export_sqlite_to_mysql()
    if os.name == 'nt':
        input("\n按 Enter 键退出...")
