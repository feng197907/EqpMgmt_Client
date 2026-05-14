#!/usr/bin/env python3
"""导出 SQLite 数据到 JSON"""
import sqlite3
import json
import sys
import os

db_path = os.path.join(os.path.dirname(__file__), 'dms.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 获取所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
print('Tables:', tables)

data = {}
for table in tables:
    cur.execute(f'SELECT * FROM {table}')
    rows = cur.fetchall()
    data[table] = [dict(row) for row in rows]
    print(f'{table}: {len(rows)} rows')

# 保存到 JSON 文件
output_path = os.path.join(os.path.dirname(__file__), 'sqlite_export.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2, default=str)

print(f'\n数据已导出到: {output_path}')
conn.close()
