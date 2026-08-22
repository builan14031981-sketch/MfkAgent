# V14.1 E2E — A-H 场景 + 输出保护
import io, sys, time, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')
from app.core.agent_runtime.action_guard import find_action_descriptions
import requests

BASE = "http://127.0.0.1:8001"

def new_chat():
    r = requests.post(f"{BASE}/api/chat", json={"agent_id": "pianai", "message": "hi", "user_id": "v141"}, timeout=30)
    return r.json().get("id")

def send(chat_id, msg):
    r = requests.post(f"{BASE}/api/chat/{chat_id}/send", json={"content": msg}, timeout=180)
    j = r.json()
    return j.get("ai_message", {}).get("content") or ""

def extract_actions(text):
    return find_action_descriptions(text)

results = []

def record(scenario, msg, text, expect_act, expect_keywords=None):
    acts = extract_actions(text)
    ok = True
    if expect_act is None:
        pass  # 只看内容
    elif expect_act:
        ok = ok and len(acts) <= 2
    else:
        ok = ok and len(acts) == 0
    if expect_keywords and not any(k in text for k in expect_keywords):
        ok = False
    results.append((scenario, ok, msg, text, acts))
    print(f"{'OK ' if ok else 'FAIL'} [{scenario}] {msg}")
    print(f"   回复: {text[:180]}")
    if acts:
        print(f"   动作: {acts}")

# 每个场景独立会话，避免上下文污染
scenarios = [
    # (场景, 输入, 是否允许动作, 期望关键词)
    ("A-疲惫", "今天好累。", False, None),
    ("A-疲惫2", "累死了，想躺平。", False, None),
    ("B-压力", "最近压力好大。", False, None),
    ("B-压力2", "工作烦死了，天天加班。", False, None),
    ("B-压力3", "这个项目压得我喘不过气。", False, None),
    ("C-孤独", "感觉没人理解我。", False, None),
    ("C-孤独2", "我想哭。", False, None),
    ("C-孤独3", "好难过，今天特别委屈。", False, None),
    ("D-索取", "哄哄我。", True, None),
    ("D-索取2", "说点好听的嘛。", True, None),
    ("D-索取3", "夸夸我。", True, None),
    ("E-拥抱", "抱一下。", True, None),
    ("E-拥抱2", "能抱抱吗。", True, None),
    ("F-角色", "（走过去抱住你）", True, None),
    ("F-角色2", "*靠在你旁边*", True, None),
    ("F-角色3", "坐在你旁边发呆。", True, None),
    ("G-工作", "帮我看看这段代码。", False, None),
    ("G-工作2", "帮我分析这个方案。", False, None),
    ("G-工作3", "评估一下这个项目。", False, None),
]

for s, msg, allow, kw in scenarios:
    cid = new_chat()
    text = send(cid, msg)
    record(s, msg, text, allow, kw)
    time.sleep(0.3)

# H 连续测试（同一会话）
print("\n===== H. 连续测试（同一会话）=====")
cid = new_chat()
t1 = send(cid, "最近真的很累。")
t2 = send(cid, "算了，没事。")
a1 = extract_actions(t1)
a2 = extract_actions(t2)
h_ok = (len(a1) == 0) and (len(a2) == 0)
results.append(("H-连续", h_ok, "最近真的很累 → 算了没事", f"{t1[:80]} / {t2[:80]}", a1 + a2))
print(f"{'OK ' if h_ok else 'FAIL'} [H-连续] 第一轮={a1} 第二轮={a2}")
print(f"   第一轮: {t1[:120]}")
print(f"   第二轮: {t2[:120]}")

# 汇总
passed = sum(1 for r in results if r[1])
print(f"\n===== 汇总: {passed}/{len(results)} 通过 =====")
for r in results:
    if not r[1]:
        print(f"  FAIL: {r[0]} -> {r[2]}")
