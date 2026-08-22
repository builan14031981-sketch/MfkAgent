import sqlite3
conn = sqlite3.connect('mfkagent.db')
cur = conn.cursor()
cur.execute("UPDATE custom_providers SET name = ? WHERE name = ? AND is_builtin = 1",
            ("FreeLLMAPI（免费聚合）", "FreeLLMAPI（本地网关）"))
print(f"更新了 {cur.rowcount} 条记录")
conn.commit()
cur.execute("SELECT id, name, is_builtin FROM custom_providers")
for row in cur.fetchall():
    print(f"  id={row[0]}, name={row[1]}, builtin={row[2]}")
conn.close()
