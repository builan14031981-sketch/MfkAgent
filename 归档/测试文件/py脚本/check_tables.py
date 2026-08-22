import sqlite3

conn = sqlite3.connect('mfkagent.db')
cur = conn.cursor()

# 列出所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('=== Tables ===')
for t in tables:
    print(t[0])

conn.close()
