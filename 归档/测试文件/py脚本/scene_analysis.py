import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# 分析各版本测试聊天中，不同场景的动作描写分布
# chat 142 = V7测试, 143 = V8测试, 144 = V8.1, 145 = V9, 146 = V10, 147 = 修复后第一次, 148 = 完全修复

scenarios = ["今天好累", "证明别人错", "不喜欢我了", "你烦不烦", "哦", "被老板骂", "没做错什么", "算了不说了", "我是什么样的人", "认识多久了"]

def get_pairs(chat_id):
    cur.execute("SELECT id, role, content FROM messages WHERE chat_id = ? ORDER BY id ASC", (chat_id,))
    rows = cur.fetchall()
    pairs = []
    for i in range(len(rows)):
        if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
            pairs.append((rows[i][2], rows[i+1][2]))
    return pairs

def count_actions(text):
    # 排除颜文字
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    real_actions = [p for p in parens if not re.match(r'[（(][\^v0-9a-zA-Z_~=]{1,6}[）)]', p)]
    stars = re.findall(r'\*[^*（(]+\*', text)
    return len(real_actions), len(stars)

# 各版本聊天
versions = [
    ("V7", 142), ("V8", 143), ("V8.1", 144), ("V9", 145),
    ("V10", 146), ("修复后", 147), ("完全修复", 148),
]

print("=" * 80)
print("场景 × 版本 动作描写分布")
print("=" * 80)

# 收集每个版本每个场景的动作数
version_data = {}
for name, cid in versions:
    pairs = get_pairs(cid)
    version_data[name] = []
    for i, (user, ai) in enumerate(pairs):
        p, s = count_actions(ai)
        version_data[name].append(p + s)

# 打印表格
header = f"{'场景':<16}" + "".join(f"{name:>10}" for name, _ in versions)
print(header)
print("-" * 80)

for i, sc in enumerate(scenarios):
    row = f"{sc:<16}"
    for name, _ in versions:
        data = version_data[name]
        val = data[i] if i < len(data) else "N/A"
        row += f"{str(val):>10}"
    print(row)

print("-" * 80)
row = f"{'总计':<16}"
for name, _ in versions:
    row += f"{str(sum(version_data[name])):>10}"
print(row)

print("\n" + "=" * 80)
print("修复后（chat 148）各场景动作明细")
print("=" * 80)

pairs = get_pairs(148)
for i, (user, ai) in enumerate(pairs):
    p, s = count_actions(ai)
    sc = scenarios[i] if i < len(scenarios) else "?"
    print(f"  {sc}: 动作{p}+星号{s}")

conn.close()