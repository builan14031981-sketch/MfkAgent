import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# Get chat info
cur.execute("SELECT id, agent_id, personality_level, model FROM chats WHERE id = 142")
chat = cur.fetchone()
print(f"Chat: {chat[0]} | Agent: {chat[1]} | Personality: {chat[2]} | Model: {chat[3]}")

# Get all messages
cur.execute("""
    SELECT id, role, content, created_at 
    FROM messages 
    WHERE chat_id = 142 
    ORDER BY id ASC
""")
rows = cur.fetchall()

# Filter only meaningful test messages (ignore the first test with ???)
test_pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and rows[i][3] and '今天好累' in rows[i][2]:
        # Found the real test start
        for j in range(i, len(rows), 2):
            if j+1 < len(rows) and rows[j][1] == 'user' and rows[j+1][1] == 'assistant':
                test_pairs.append((rows[j][2], rows[j+1][2]))
        break

# Also get the first "今天好累" response specifically
print("\n" + "="*60)
print("RAW TEST DATA - ALL AI RESPONSES")
print("="*60)

for i, (user_msg, ai_msg) in enumerate(test_pairs):
    print(f"\n--- Test {i+1} ---")
    print(f"USER: {user_msg}")
    print(f"AI: {ai_msg}")
    print(f"[长度: {len(ai_msg)} 字符]")

conn.close()
