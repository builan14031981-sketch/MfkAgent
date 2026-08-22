import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT id, role, content FROM messages WHERE chat_id = 147 ORDER BY id ASC")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

scenarios = ["今天好累","人生一直在证明别人错","你是不是不喜欢我了","你烦不烦","哦","被老板骂了","其实我也没做错什么","算了不说了","你觉得我是什么样的人","我们认识多久了"]

print("=" * 60)
print("修复后测试（expression_profile = NULL）")
print("=" * 60)

total_actions = 0
total_len = 0
clean_count = 0

for i, (user, ai, msg_id) in enumerate(pairs):
    parens = re.findall(r'[（(][^）)]+[）)]', ai)
    stars = re.findall(r'\*[^*（(]+\*', ai)
    actions = len(parens) + len(stars)
    total_actions += actions
    total_len += len(ai)
    if actions == 0:
        clean_count += 1
    flag = "✅" if actions == 0 else "⚠️"
    short = scenarios[i] if i < len(scenarios) else f"#{i+1}"
    print(f"\n{flag} {short}: {len(ai)}字, 动作{actions}个")
    print(f"   {ai[:280]}{'...' if len(ai)>280 else ''}")
    if parens: print(f"   括号: {parens}")
    if stars: print(f"   星号: {stars}")

print(f"\n{'='*60}")
print(f"总计: {total_actions}个动作, 平均{total_len//len(pairs)}字/轮")
print(f"干净轮数: {clean_count}/{len(pairs)}")

conn.close()
