import sqlite3

db_path = r'C:\Users\jm-wtf\AppData\Roaming\DMS\equipment.db'
conn = sqlite3.connect(db_path)

# 修复 doc_id=1 的坏路径
conn.execute(
    "UPDATE documents SET file_path = 'uploads\\device_1\\equipment_history_1.0_.docx' WHERE id = 1"
)
conn.commit()

# 验证修复结果
# cur = conn.execute("SELECT id, file_name, file_path FROM documents WHERE id = 1")
cur = conn.execute("SELECT id, file_path FROM documents WHERE id = 1")
row = cur.fetchone()
# print(f"id={row[0]}, file_name={row[1]}, file_path={row[2]}")
print(f"id={row[0]}, file_path={row[1]}")

conn.close()
print("Done ✓")