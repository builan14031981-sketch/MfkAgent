import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

# Read V7 data
cur.execute("""
    SELECT id, role, content FROM messages WHERE chat_id = 142 ORDER BY id ASC
""")
v7_rows = cur.fetchall()

# Read V8 data
cur.execute("""
    SELECT id, role, content FROM messages WHERE chat_id = 143 ORDER BY id ASC
""")
v8_rows = cur.fetchall()

def extract_pairs(rows):
    pairs = []
    for i in range(len(rows)):
        if rows[i][1] == 'user' and i+1 < len(rows) and rows[i+1][1] == 'assistant':
            pairs.append((rows[i][2], rows[i+1][2]))
    return pairs

v7_pairs = extract_pairs(v7_rows)
v8_pairs = extract_pairs(v8_rows)

# Test scenarios
scenarios = [
    "普通聊天：今天好累",
    "深度聊天：我感觉人生一直在证明别人错",
    "撒娇：你是不是不喜欢我了",
    "生气：你烦不烦",
    "冷淡：哦",
    "情绪倾诉：我今天被老板骂了，好委屈",
    "继续倾诉：其实我也没做错什么",
    "回避：算了不说了",
    "自我探索：你觉得我是什么样的人",
    "关系确认：我们认识多久了",
]

print("=" * 70)
print("《偏爱人格测试报告 V2》— V7 vs V8 对比")
print("=" * 70)
print(f"\n测试场景：10 个 | 每个版本各跑一轮")
print(f"Prompt 版本：V7 (435行) → V8 (489行)")
print(f"Personality Level：25 (温和友好)")

print("\n" + "=" * 70)
print("一、回复长度对比")
print("=" * 70)
print(f"{'场景':<25} {'V7':>6} {'V8':>6} {'变化':>8}")
print("-" * 50)

for i, scenario in enumerate(scenarios):
    if i < len(v7_pairs) and i < len(v8_pairs):
        v7_len = len(v7_pairs[i][1])
        v8_len = len(v8_pairs[i][1])
        delta = v8_len - v7_len
        delta_str = f"+{delta}" if delta > 0 else str(delta)
        # Shorten scenario name
        short = scenario.split("：")[0][:20]
        print(f"{short:<25} {v7_len:>5}字 {v8_len:>5}字 {delta_str:>7}字")

# Calculate averages
v7_avg = sum(len(p[1]) for p in v7_pairs) / len(v7_pairs)
v8_avg = sum(len(p[1]) for p in v8_pairs) / len(v8_pairs)
print("-" * 50)
print(f"{'平均':<25} {v7_avg:>5.0f}字 {v8_avg:>5.0f}字 {v8_avg-v7_avg:>+7.0f}字")

print("\n" + "=" * 70)
print("二、详细对比分析")
print("=" * 70)

issues_v7 = {
    0: [],
    1: ["⚠️ 心理分析过载 (321字)"],
    2: ["⚠️ 过度证明关系"],
    3: ["⚠️ 小说式动作*滴滴倒计时*"],
    4: ["⚠️ 小说式动作"],
    5: ["⚠️ 过度共情+虚构设定"],
    6: ["⚠️ 替用户判断"],
    7: [],
    8: ["❌ 完全心理分析模式"],
    9: ["❌ 虚构记忆+甜腻"],
}

issues_v8 = {
    0: ["⚠️ 仍有动作描写"],
    1: ["⚠️ 仍带分析感"],
    2: ["⚠️ 仍证明关系"],
    3: ["⚠️ *对话框沉默* 新小说式"],
    4: [],  # 大幅改进
    5: [],
    6: [],
    7: ["⚠️ 结尾'不走'仍像宣言"],
    8: ["⚠️ 仍有分析感"],
    9: [],
}

for i, scenario in enumerate(scenarios):
    if i < len(v7_pairs) and i < len(v8_pairs):
        print(f"\n--- {i+1}. {scenario} ---")
        print(f"V7 ({len(v7_pairs[i][1])}字): {v7_pairs[i][1][:80]}...")
        print(f"V8 ({len(v8_pairs[i][1])}字): {v8_pairs[i][1][:80]}...")
        
        v7_issues = issues_v7.get(i, [])
        v8_issues = issues_v8.get(i, [])
        
        if v7_issues or v8_issues:
            if v7_issues:
                print(f"  V7问题: {'; '.join(v7_issues)}")
            if v8_issues:
                print(f"  V8问题: {'; '.join(v8_issues)}")
            if not v8_issues and v7_issues:
                print(f"  ✅ V8 修复!")

conn.close()
