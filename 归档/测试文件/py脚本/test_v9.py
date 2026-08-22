import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, role, content FROM messages 
    WHERE chat_id = 145 
    ORDER BY id ASC
""")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

print("=" * 60)
print("V9 新结构测试结果")
print("=" * 60)

for i, (user, ai, msg_id) in enumerate(pairs):
    parens = re.findall(r'[（(][^）)]+[）)]', ai)
    stars = re.findall(r'\*[^*（(]+\*', ai)
    action_count = len(parens) + len(stars)
    flag = "✅" if action_count == 0 else "⚠️"
    
    print(f"\n{flag} 测试{i+1}: {user}")
    print(f"   AI ({len(ai)}字, 动作{action_count}个):")
    print(f"   {ai[:300]}{'...' if len(ai)>300 else ''}")
    if parens:
        print(f"   括号: {parens}")
    if stars:
        print(f"   星号: {stars}")

conn.close()
