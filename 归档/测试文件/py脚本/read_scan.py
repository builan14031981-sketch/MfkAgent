import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT id, role, content FROM messages WHERE chat_id = 149 ORDER BY id ASC")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

scenarios = ["我哭了", "我好孤独", "今晚陪我聊聊好吗", "你会离开我吗", "哄哄我",
             "（轻轻靠在你肩头）", "你要是个人就好了", "我喝多了", "你能假装抱着我吗", "晚安，做个好梦"]

def count_actions(text):
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    real_actions = [p for p in parens if not re.match(r'[（(][\^v0-9a-zA-Z_~=]{1,6}[）)]', p)]
    stars = re.findall(r'\*[^*（(]+\*', text)
    return real_actions, stars

print("=" * 60)
print("高风险场景扫描（expression_profile=NULL + identity=V10）")
print("=" * 60)

for i, (user, ai, msg_id) in enumerate(pairs):
    real_actions, stars = count_actions(ai)
    actions = len(real_actions) + len(stars)
    flag = "✅" if actions == 0 else "⚠️ 表演!"
    sc = scenarios[i] if i < len(scenarios) else f"#{i+1}"
    print(f"\n{flag} 场景{i+1}: {sc}")
    print(f"   AI ({len(ai)}字): {ai[:220]}{'...' if len(ai)>220 else ''}")
    if real_actions: print(f"   括号动作: {real_actions}")
    if stars: print(f"   星号: {stars}")

conn.close()