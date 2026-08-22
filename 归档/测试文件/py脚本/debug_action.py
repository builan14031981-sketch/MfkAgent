import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# Check all pianai chats
cur.execute("""
    SELECT c.id, c.title, c.created_at, c.personality_level
    FROM chats c
    WHERE c.agent_id = 'pianai'
    ORDER BY c.id DESC
    LIMIT 10
""")
chats = cur.fetchall()
print("=== 所有偏爱聊天 ===")
for ch in chats:
    print(f"  Chat {ch[0]}: {ch[1]} | personality={ch[3]} | {ch[2]}")

# Check first few messages of V8 test chat (143)
print("\n=== Chat 143 (V8测试) 前4条消息 ===")
cur.execute("""
    SELECT id, role, content FROM messages WHERE chat_id = 143 ORDER BY id ASC LIMIT 4
""")
for r in cur.fetchall():
    print(f"\n[{r[1]}] #{r[0]}")
    if r[1] == 'assistant':
        # Check for action descriptions in parentheses
        content = r[2]
        import re
        parens = re.findall(r'[（(][^）)]+[）)]', content)
        stars = re.findall(r'\*[^*]+\*', content)
        print(f"  内容: {content[:200]}")
        print(f"  括号动作: {parens}")
        print(f"  星号动作: {stars}")

# Now check if the ACTION descriptions existed from the FIRST response
print("\n\n=== 核心问题：第一条AI回复就有动作描写？ ===")
cur.execute("""
    SELECT id, content FROM messages 
    WHERE chat_id = 143 AND role = 'assistant' 
    ORDER BY id ASC LIMIT 1
""")
first_ai = cur.fetchone()
if first_ai:
    print(f"第一条AI回复 (msg #{first_ai[0]}):")
    print(first_ai[1])
    
    import re
    parens = re.findall(r'[（(][^）)]+[）)]', first_ai[1])
    stars = re.findall(r'\*[^*]+\*', first_ai[1])
    print(f"\n括号动作: {parens}")
    print(f"星号动作: {stars}")

conn.close()
