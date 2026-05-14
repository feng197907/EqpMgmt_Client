# -*- coding: utf-8 -*-
"""
SQLite to MySQL Migration Script - 修复版
正确解析 SQLite 的 CREATE TABLE 语句
"""

import sqlite3
import os
import re
from datetime import datetime

# 配置
DB_PATH = '/data/EquipmentManagement/dms.db'
OUTPUT_PATH = '/data/EquipmentManagement/migrate_dms_fixed.sql'

def convert_sqlite_type(sqlite_type):
    """转换 SQLite 类型到 MySQL 类型"""
    sqlite_type = sqlite_type.upper().strip()
    
    if not sqlite_type or sqlite_type == ',':
        return 'TEXT'
    
    # 关键字映射
    type_mapping = {
        'INTEGER': 'INT',
        'INT': 'INT',
        'BIGINT': 'BIGINT',
        'SMALLINT': 'SMALLINT',
        'TINYINT': 'TINYINT',
        'REAL': 'DOUBLE',
        'FLOAT': 'FLOAT',
        'DOUBLE': 'DOUBLE',
        'NUMERIC': 'DECIMAL(10,2)',
        'DECIMAL': 'DECIMAL(10,2)',
        'BOOLEAN': 'TINYINT(1)',
        'BLOB': 'BLOB',
    }
    
    for key, value in type_mapping.items():
        if key in sqlite_type:
            return value
    
    # 默认为 VARCHAR
    return 'VARCHAR(255)'

def parse_create_table(create_sql, table_name):
    """解析 CREATE TABLE 语句并转换为 MySQL 格式"""
    # 提取括号内的内容
    match = re.search(r'\(([\s\S]+)\)', create_sql)
    if not match:
        return None
    
    content = match.group(1)
    lines = content.split('\n')
    
    columns = []
    primary_keys = []
    
    for line in lines:
        line = line.strip().rstrip(',').strip()
        if not line:
            continue
        
        # 跳过 CREATE TABLE 和括号
        if line.upper().startswith('CREATE TABLE'):
            continue
        
        # 解析列定义: column_name TYPE [constraints]
        # 匹配列名（可能有引号或反引号）
        col_match = re.match(r'[`"\[]?(\w+)[`"\]]?\s+(.+?)(?:,|$)', line, re.IGNORECASE)
        if col_match:
            col_name = col_match.group(1)
            col_def = col_match.group(2).strip()
            
            # 跳过逗号列名
            if col_name == ',' or not col_name:
                continue
            
            # 检查约束
            is_primary = 'PRIMARY KEY' in col_def.upper()
            is_not_null = 'NOT NULL' in col_def.upper()
            has_default = 'DEFAULT' in col_def.upper()
            is_unique = 'UNIQUE' in col_def.upper()
            
            # 提取类型
            mysql_type = convert_sqlite_type(col_def)
            
            # 构建列定义
            col_sql = f"  `{col_name}` {mysql_type}"
            
            if is_primary and 'AUTOINCREMENT' in col_def.upper():
                col_sql = f"  `{col_name}` INT AUTO_INCREMENT PRIMARY KEY"
                primary_keys.append(col_name)
            else:
                if is_not_null:
                    col_sql += ' NOT NULL'
                if has_default:
                    # 保留 DEFAULT
                    pass
                if is_unique:
                    col_sql += ' UNIQUE'
            
            columns.append(col_sql)
    
    # 构建 CREATE TABLE 语句
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
    print("SQLite to MySQL Migration Script (Fixed)")
    print("=" * 60)
    print(f"源数据库: {DB_PATH}")
    print(f"输出文件: {OUTPUT_PATH}")
    print("=" * 60)

    if not os.path.exists(DB_PATH):
        print(f"\n错误: 数据库文件不存在!")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            f.write("-- SQLite to MySQL Migration Script\n")
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
                
                if not mysql_create:
                    print(f"  警告: 无法解析表结构，跳过")
                    continue

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
        return True

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    export_sqlite_to_mysql()
