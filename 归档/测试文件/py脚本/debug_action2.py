import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# Check ALL pianai chats for action descriptions
cur.execute("""
    SELECT c.id, c.title FROM chats 
    WHERE agent_id = 'pianai' 
    ORDER BY c.id ASC
""")
chats = cur.fetchall()

print("=== 所有偏爱聊天的动作描写统计 ===\n")

for chat in chats:
    chat_id = chat[0]
    cur.execute("""
        SELECT content FROM messages 
        WHERE chat_id = ? AND role = 'assistant'
        ORDER BY id ASC
    """, (chat_id,))
    ai_msgs = cur.fetchall()
    
    total_msgs = len(ai_msgs)
    msg_with_parens = 0
    total_parens = 0
    total_stars = 0
    
    for msg in ai_msgs:
        content = msg[0]
        parens = re.findall(r'[（(][^）)]+[）)]', content)
        stars = re.findall(r'\*[^*（(]+\*', content)
        if parens:
            msg_with_parens += 1
        total_parens += len(parens)
        total_stars += len(stars)
    
    if total_msgs > 0:
        print(f"Chat {chat_id} ({chat[1][:15]}):")
        print(f"  AI回复数: {total_msgs}")
        print(f"  含括号动作的消息: {msg_with_parens}/{total_msgs} ({100*msg_with_parens//total_msgs}%)")
        print(f"  括号动作总数: {total_parens}")
        print(f"  星号动作总数: {total_stars}")
        print()

# Now check: the V8 prompt examples contain action descriptions
print("=== V8 Prompt 中的动作描写示例 ===")
with open('Agent/Pianai.txt', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find all lines with parens
lines = content.split('\n')
for i, line in enumerate(lines):
    if '（' in line or '）' in line or '*' in line:
        if '例如' in line or '可以' in line or '禁止' in line or '不要' in line:
            print(f"  Line {i+1}: {line.strip()}")

conn.close()
