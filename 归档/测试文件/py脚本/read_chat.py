import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, chat_id, role, content, created_at 
    FROM messages 
    WHERE chat_id = 142 
    ORDER BY id ASC
""")
rows = cur.fetchall()
for r in rows:
    print(f'\n=== [{r[2]}] #{r[0]} @ {r[4]} ===')
    content = r[3][:1000] if r[3] else '(empty)'
    print(content)

conn.close()
