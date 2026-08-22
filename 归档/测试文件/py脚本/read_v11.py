import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT id, role, content FROM messages WHERE chat_id = 150 ORDER BY id ASC")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

scenarios = [
    ("❌不该演", "今天好累"),
    ("❌不该演", "帮我写个Python爬虫"),
    ("❌不该演", "哦"),
    ("✅该演", "晚安"),
    ("✅该演", "外面下雨了，我在窗前发呆"),
    ("✅该演", "哄哄我"),
    ("✅该演", "我今天被老板骂了"),
    ("✅该演", "（靠在你肩头不说话）"),
    ("✅该演", "今天是我们的纪念日吗"),
]

def count_actions(text):
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    real_actions = [p for p in parens if not re.match(r'[（(][\^v0-9a-zA-Z_~=]{1,6}[）)]', p)]
    stars = re.findall(r'\*[^*（(]+\*', text)
    return real_actions, stars

print("=" * 70)
print("V11 表演分级测试（expression_profile=NULL + identity=V11）")
print("=" * 70)

for i, (user, ai, msg_id) in enumerate(pairs):
    real_actions, stars = count_actions(ai)
    actions = len(real_actions) + len(stars)
    expected, sc = scenarios[i] if i < len(scenarios) else ("?", f"#{i+1}")
    
    print(f"\n{'-'*70}")
    print(f"[{expected}] {sc} ({len(ai)}字, 动作{actions}处)")
    print(f"  AI: {ai}")
    if real_actions: print(f"  括号: {real_actions}")
    if stars: print(f"  星号: {stars}")

conn.close()