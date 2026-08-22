import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

def extract_pairs(chat_id):
    cur.execute("SELECT id, role, content FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    rows = cur.fetchall()
    pairs = []
    for i in range(len(rows)):
        if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
            pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))
    return pairs

def count_actions(text):
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    stars = re.findall(r'\*[^*（(]+\*', text)
    return len(parens), len(stars), parens, stars

scenarios = ["今天好累","人生一直在证明别人错","你是不是不喜欢我了","你烦不烦","哦","被老板骂了","其实我也没做错什么","算了不说了","你觉得我是什么样的人","我们认识多久了"]

v10_pairs = extract_pairs(146)

print("=" * 60)
print("V10 关系型聊天陪伴 — 测试结果")
print("=" * 60)

total_actions = 0
total_len = 0

for i, (user, ai, msg_id) in enumerate(v10_pairs):
    p_count, s_count, p_list, s_list = count_actions(ai)
    actions = p_count + s_count
    total_actions += actions
    total_len += len(ai)
    flag = "✅" if actions == 0 else "⚠️"
    short = scenarios[i] if i < len(scenarios) else f"#{i+1}"
    print(f"\n{flag} {short}: {len(ai)}字, 动作{actions}个")
    print(f"   {ai[:250]}{'...' if len(ai)>250 else ''}")
    if p_list: print(f"   括号: {p_list}")
    if s_list: print(f"   星号: {s_list}")

print(f"\n总计: {total_actions}个动作, 平均{total_len//len(v10_pairs)}字/轮")

conn.close()
