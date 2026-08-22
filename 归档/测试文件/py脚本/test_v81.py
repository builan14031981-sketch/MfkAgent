import sqlite3
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

def extract_pairs(chat_id):
    cur.execute("""
        SELECT id, role, content FROM messages 
        WHERE chat_id = ? ORDER BY id ASC
    """, (chat_id,))
    rows = cur.fetchall()
    pairs = []
    for i in range(len(rows)):
        if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
            pairs.append((rows[i][2], rows[i+1][2], rows[i+1][0]))
    return pairs

def count_actions(text):
    parens = re.findall(r'[（(][^）)]+[）)]', text)
    stars = re.findall(r'\*[^*（(]+\*', text)
    return len(parens), len(stars)

# Read all three versions
v7_pairs = extract_pairs(142)
v8_pairs = extract_pairs(143)
v81_pairs = extract_pairs(144)

scenarios = [
    "今天好累",
    "人生一直在证明别人错",
    "你是不是不喜欢我了",
    "你烦不烦",
    "哦",
    "被老板骂了",
    "其实我也没做错什么",
    "算了不说了",
    "你觉得我是什么样的人",
    "我们认识多久了",
]

print("=" * 70)
print("V8.1 修改后测试结果")
print("=" * 70)

print(f"\n{'#':<3} {'场景':<15} {'V7':>6} {'V8':>6} {'V8.1':>6} | V7动作 V8动作 V8.1动作")
print("-" * 75)

v7_total_parens = 0
v8_total_parens = 0
v81_total_parens = 0
v7_total_stars = 0
v8_total_stars = 0
v81_total_stars = 0

for i in range(min(len(v7_pairs), len(v8_pairs), len(v81_pairs))):
    v7_p, v7_s = count_actions(v7_pairs[i][1])
    v8_p, v8_s = count_actions(v8_pairs[i][1])
    v81_p, v81_s = count_actions(v81_pairs[i][1])
    
    v7_total_parens += v7_p
    v8_total_parens += v8_p
    v81_total_parens += v81_p
    v7_total_stars += v7_s
    v8_total_stars += v8_s
    v81_total_stars += v81_s
    
    v7_len = len(v7_pairs[i][1])
    v8_len = len(v8_pairs[i][1])
    v81_len = len(v81_pairs[i][1])
    
    short = scenarios[i][:14] if i < len(scenarios) else f"#{i+1}"
    print(f"{i+1:<3} {short:<15} {v7_len:>5}字 {v8_len:>5}字 {v81_len:>5}字 | ({v7_p}/{v7_s}) ({v8_p}/{v8_s}) ({v81_p}/{v81_s})")

print("-" * 75)
print(f"{'总计':<19} {'':>6} {'':>6} {'':>6} | ({v7_total_parens}/{v7_total_stars}) ({v8_total_parens}/{v8_total_stars}) ({v81_total_parens}/{v81_total_stars})")

print("\n" + "=" * 70)
print("V8.1 回复详情（检查是否还有动作描写）")
print("=" * 70)

for i, (user, ai, msg_id) in enumerate(v81_pairs):
    parens, stars = count_actions(ai)
    action_flag = "⚠️" if (parens + stars) > 0 else "✅"
    print(f"\n{action_flag} 测试{i+1}: {user[:20]}")
    print(f"   AI ({len(ai)}字): {ai[:150]}{'...' if len(ai)>150 else ''}")
    if parens or stars:
        p_list = re.findall(r'[（(][^）)]+[）)]', ai)
        s_list = re.findall(r'\*[^*（(]+\*', ai)
        if p_list:
            print(f"   括号动作: {p_list}")
        if s_list:
            print(f"   星号动作: {s_list}")

conn.close()
