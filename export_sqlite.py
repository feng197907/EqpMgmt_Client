# -*- coding: utf-8 -*-
"""
SQLite 数据库导出为 MySQL 完整 SQL 脚本
包含建表语句 + 数据导入
"""

import sqlite3
import os
import re

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
    # 移除 sqlite 自动生成的 rowid
    if 'WITHOUT ROWID' in create_sql:
        create_sql = create_sql.replace('WITHOUT ROWID', '')

    # 提取列定义
    lines = create_sql.split('\n')
    columns = []
    primary_keys = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('CREATE TABLE') or line.startswith(')'):
            continue

        # 解析列定义
        parts = line.rstrip(',').split()
        if not parts:
            continue

        col_name = parts[0].strip('`"[]')
        col_type = ' '.join(parts[1:]) if len(parts) > 1 else 'TEXT'

        # 处理 PRIMARY KEY
        if 'PRIMARY KEY' in line.upper():
            primary_keys.append(col_name)
            # 如果是 INTEGER PRIMARY KEY，转换为 INT AUTO_INCREMENT
            if 'INTEGER' in col_type.upper():
                col_type = 'INT AUTO_INCREMENT PRIMARY KEY'
            else:
                col_type = convert_sqlite_to_mysql_type(col_type) + ' PRIMARY KEY'

        # 处理 NOT NULL
        if 'NOT NULL' in line.upper():
            col_type = convert_sqlite_to_mysql_type(col_type) + ' NOT NULL'

        # 处理 NULL（默认值）
        if 'DEFAULT NULL' in line.upper():
            col_type = convert_sqlite_to_mysql_type(col_type) + ' DEFAULT NULL'

        # 处理 DEFAULT 值
        default_match = re.search(r"DEFAULT\s+'([^']*)'", line, re.IGNORECASE)
        if default_match:
            default_val = default_match.group(1)
            col_type = col_type + f" DEFAULT '{default_val}'"
        elif 'DEFAULT' not in line.upper():
            col_type = convert_sqlite_to_mysql_type(col_type)

        # 处理 UNIQUE
        if 'UNIQUE' in line.upper():
            col_type = col_type + ' UNIQUE'

        columns.append(f"  `{col_name}` {col_type}")

    # 构建 MySQL 建表语句
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
        # 转义单引号和反斜杠
        val = str(val).replace('\\', '\\\\').replace("'", "\\'")
        return f"'{val}'"

def export_sqlite_to_mysql(db_path, output_path):
    """导出 SQLite 数据库为 MySQL SQL 文件"""
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    with open(output_path, 'w', encoding='utf-8') as f:
        # 写入文件头
        f.write("-- SQLite to MySQL Full Migration Script\n")
        f.write("-- Generated from: {}\n".format(db_path))
        f.write("-- Generated at: {}\n\n".format(__import__('datetime').datetime.now()))
        f.write("SET NAMES utf8mb4;\n")
        f.write("SET FOREIGN_KEY_CHECKS = 0;\n\n")

        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        print(f"找到 {len(tables)} 个表: {', '.join(tables)}")

        for table in tables:
            print(f"处理表: {table}")

            # 获取 CREATE TABLE 语句
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            create_sql = cursor.fetchone()[0]

            # 转换为 MySQL 语法
            mysql_create = parse_create_table(create_sql, table)

            f.write("-- " + "=" * 60 + "\n")
            f.write(f"-- Table: {table}\n")
            f.write("-- " + "=" * 60 + "\n\n")
            f.write(f"DROP TABLE IF EXISTS `{table}`;\n\n")
            f.write(mysql_create + "\n\n")

            # 获取列名
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]

            if not columns:
                continue

            # 获取所有数据
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()

            for row in rows:
                values = [escape_value(val) for val in row]
                cols = ', '.join(f'`{c}`' for c in columns)
                vals = ', '.join(values)
                f.write(f"INSERT INTO `{table}` ({cols}) VALUES ({vals});\n")

            f.write("\n")

        f.write("SET FOREIGN_KEY_CHECKS = 1;\n")

    conn.close()
    print(f"\n完成! SQL 文件已生成: {output_path}")
    return True

if __name__ == '__main__':
    # 配置路径
    db_path = 'equipment.db'
    output_path = 'migrate_full.sql'

    # 如果数据库不存在，尝试当前目录
    if not os.path.exists(db_path):
        # 尝试常见位置
        possible_paths = [
            'equipment.db',
            './equipment.db',
            '../equipment.db',
            '/root/EquipmentManagement/equipment.db',
            '/home/EquipmentManagement/equipment.db',
        ]
        for p in possible_paths:
            if os.path.exists(p):
                db_path = p
                break

    print("=" * 60)
    print("SQLite to MySQL 迁移脚本")
    print("=" * 60)
    print(f"源数据库: {db_path}")
    print(f"输出文件: {output_path}")
    print("=" * 60)

    if export_sqlite_to_mysql(db_path, output_path):
        print("\n请检查生成的 migrate_full.sql 文件，然后执行:")
        print("  mysql -u root -p dms_db < migrate_full.sql")
    else:
        print("\n请确认 equipment.db 文件存在，然后重新运行脚本")
