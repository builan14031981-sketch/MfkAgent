# V14 isolation test — 每个场景用新会话，验证不演场景在无上下文污染时保持零表演
import io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests

BASE = "http://127.0.0.1:8001"

def new_chat():
    r = requests.post(f"{BASE}/api/chat", json={"agent_id": "pianai", "message": "hi", "user_id": "v14iso"}, timeout=30)
    return r.json().get("id")

def send(chat_id, msg):
    r = requests.post(f"{BASE}/api/chat/{chat_id}/send", json={"content": msg}, timeout=180)
    j = r.json()
    return j.get("ai_message", {}).get("content") or json.dumps(j, ensure_ascii=False)[:200]

import json
scenarios = [
    ("今天好累啊", False),
    ("帮我看看这个方案", False),
    ("这个代码有bug", False),
    ("哦", False),
    ("今天写代码写累了", False),
]
for msg, expect in scenarios:
    cid = new_chat()
    text = send(cid, msg)
    # 判断是否出现动作描写（括号动作 / 星号动作）
    import re
    acts = re.findall(r'（[^）]{1,25}）|\*[^*]{1,25}\*|\([^)]{1,25}\)', text)
    print("=" * 55)
    print(f"[{'不演' if not expect else '演'}] {msg}")
    print("回复:", text[:250].replace("\n", " "))
    if acts:
        print("  ⚠️ 动作描写出现:", acts[:3])
    else:
        print("  ✅ 无动作描写")
    time.sleep(0.5)