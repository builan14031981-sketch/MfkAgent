import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# Check ALL pianai chats for action descriptions
cur.execute("""
    SELECT id, title FROM chats 
    WHERE agent_id = 'pianai' 
    ORDER BY id ASC
""")
chats = cur.fetchall()

print("=== All Pianai chats action description stats ===\n")

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
        content = msg[0] if msg[0] else ""
        parens = re.findall(r'[（(][^）)]+[）)]', content)
        stars = re.findall(r'\*[^*（(]+\*', content)
        if parens:
            msg_with_parens += 1
        total_parens += len(parens)
        total_stars += len(stars)
    
    if total_msgs > 0:
        pct = 100 * msg_with_parens // total_msgs
        print(f"Chat {chat_id} ({str(chat[1])[:15]}):")
        print(f"  AI msgs: {total_msgs}")
        print(f"  With parens: {msg_with_parens}/{total_msgs} ({pct}%)")
        print(f"  Total parens: {total_parens}")
        print(f"  Total stars: {total_stars}")
        print()

conn.close()
