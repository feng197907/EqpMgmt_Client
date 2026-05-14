#!/usr/bin/env python3
"""
MySQL 数据导入脚本
从 sqlite_export.json 导入数据到 MySQL
"""
import json
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import pymysql

# MySQL 配置
MYSQL_CONFIG = {
    'host': os.environ.get('MYSQL_HOST', 'localhost'),
    'port': int(os.environ.get('MYSQL_PORT', 3306)),
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': os.environ.get('MYSQL_PASSWORD', ''),
    'database': os.environ.get('MYSQL_DATABASE', 'dms_db'),
    'charset': 'utf8mb4',
}

def get_mysql_connection():
    return pymysql.connect(**MYSQL_CONFIG)

def clear_tables(conn):
    """清空所有表数据（按外键依赖顺序）"""
    cur = conn.cursor()
    tables = [
        'maintenance_record',
        'maintenance_plan',
        'password_reset_requests',
        'signatures',
        'approval_steps',
        'approval_requests',
        'device_status_requests',
        'audit_logs',
        'borrow_records',
        'documents',
        'devices',
        'users',
    ]
    for table in tables:
        try:
            cur.execute(f"TRUNCATE TABLE {table}")
            print(f"已清空表: {table}")
        except Exception as e:
            print(f"清空表 {table} 失败: {e}")
    conn.commit()
    cur.close()

def import_data():
    # 读取导出数据
    export_path = os.path.join(os.path.dirname(__file__), 'sqlite_export.json')
    with open(export_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_mysql_connection()

    # 先清空表
    print("正在清空 MySQL 表数据...")
    clear_tables(conn)

    cur = conn.cursor()

    # 按依赖顺序导入
    tables_order = [
        'users',
        'devices',
        'documents',
        'borrow_records',
        'audit_logs',
        'approval_requests',
        'approval_steps',
        'signatures',
        'system_settings',
        'password_reset_requests',
        'maintenance_plan',
        'maintenance_record',
        'device_status_requests',
    ]

    for table in tables_order:
        if table not in data:
            continue

        rows = data[table]
        if not rows:
            print(f"表 {table} 无数据")
            continue

        print(f"导入表 {table} ({len(rows)} 行)...")

        for row in rows:
            try:
                # 处理字段
                fields = []
                values = []
                placeholders = []
                for key, value in row.items():
                    if key == 'sqlite_sequence':
                        continue
                    fields.append(key)
                    values.append(value)
                    placeholders.append('%s')

                sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                cur.execute(sql, values)
            except Exception as e:
                print(f"  导入 {table} 行失败: {e}")
                print(f"  数据: {row}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n数据导入完成！")

if __name__ == '__main__':
    import_data()
