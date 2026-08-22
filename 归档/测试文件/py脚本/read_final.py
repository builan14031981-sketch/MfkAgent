import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT id, role, content FROM messages WHERE chat_id = 148 ORDER BY id ASC")
rows = cur.fetchall()

pairs = []
for i in range(len(rows)):
    if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
        pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))

scenarios = ["今天好累","人生一直在证明别人错","你是不是不喜欢我了","你烦不烦","哦","被老板骂了","其实我也没做错什么","算了不说了","你觉得我是什么样的人","我们认识多久了"]

print("=" * 60)
print("完全修复后测试（expression_profile=NULL + identity=V10）")
print("=" * 60)
print(f"消息对数: {len(pairs)}")

total_actions = 0
total_len = 0
clean_count = 0

for i, (user, ai, msg_id) in enumerate(pairs):
    parens = re.findall(r'[（(][^）)]+[）)]', ai)
    stars = re.findall(r'\*[^*（(]+\*', ai)
    kaomoji = re.findall(r'[（(]\^.?[）)]', ai)
    # 排除颜文字形式的括号
    real_actions = [p for p in parens if not re.match(r'[（(]v?[0-9a-zA-Z_^]{1,5}[）)]', p)]
    actions = len(real_actions) + len(stars)
    total_actions += actions
    total_len += len(ai)
    if actions == 0:
        clean_count += 1
    flag = "✅" if actions == 0 else "⚠️"
    short = scenarios[i] if i < len(scenarios) else f"#{i+1}"
    print(f"\n{flag} {short}: {len(ai)}字, 动作{actions}个")
    print(f"   {ai[:300]}{'...' if len(ai)>300 else ''}")
    if real_actions: print(f"   括号动作: {real_actions}")
    if stars: print(f"   星号: {stars}")

print(f"\n{'='*60}")
print(f"总计: {total_actions}个动作, 平均{total_len//max(len(pairs),1)}字/轮")
print(f"干净轮数: {clean_count}/{len(pairs)}")

conn.close()