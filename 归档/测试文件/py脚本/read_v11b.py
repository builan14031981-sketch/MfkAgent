import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT id, role, content FROM messages WHERE chat_id = 151 ORDER BY id ASC")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

scenarios = ["今天好累", "好累啊", "困死了", "嗯", "晚安", "今晚的月亮好亮"]

def count_actions(text):
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    real_actions = [p for p in parens if not re.match(r'[（(][\^v0-9a-zA-Z_~=]{1,6}[）)]', p)]
    stars = re.findall(r'\*[^*（(]+\*', text)
    return real_actions, stars

for i, (user, ai, msg_id) in enumerate(pairs):
    real_actions, stars = count_actions(ai)
    actions = len(real_actions) + len(stars)
    expected = "❌不该演" if i < 4 else "✅该演"
    sc = scenarios[i] if i < len(scenarios) else f"#{i+1}"
    print(f"\n[{expected}] {sc} ({len(ai)}字, 动作{actions}处)")
    print(f"  AI: {ai}")
    if real_actions: print(f"  括号: {real_actions}")
    if stars: print(f"  星号: {stars}")

conn.close()