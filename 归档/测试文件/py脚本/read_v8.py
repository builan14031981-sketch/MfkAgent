import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, role, content, created_at 
    FROM messages 
    WHERE chat_id = 143 
    ORDER BY id ASC
""")
rows = cur.fetchall()

# Pair user + assistant messages
pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

print("=" * 60)
print("V8 测试结果")
print("=" * 60)

for i, (user, ai, msg_id) in enumerate(pairs):
    print(f"\n--- 测试 {i+1} ---")
    print(f"USER: {user}")
    print(f"AI (#{msg_id}): {ai}")
    print(f"[长度: {len(ai)} 字符]")

conn.close()
