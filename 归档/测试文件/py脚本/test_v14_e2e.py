# V14 e2e — 表演状态按需触发
import io, sys, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests

BASE = "http://127.0.0.1:8001"

def new_chat():
    r = requests.post(f"{BASE}/api/chat", json={
        "agent_id": "pianai",
        "message": "hi",
        "user_id": "v14test",
    }, timeout=30)
    print("create:", r.status_code, r.text[:200])
    return r.json()

def send(chat_id, msg):
    r = requests.post(f"{BASE}/api/chat/{chat_id}/send", json={
        "content": msg,
    }, timeout=180)
    return r.json()

cid = new_chat().get("id")
print("chat_id:", cid)

scenarios = [
    ("今天写代码写累了", False),
    ("帮我看看这个方案的可行性", False),
    ("哄哄我嘛", True),
    ("能抱一下吗", True),
    ("今晚有点睡不着", True),
    ("晚安，我睡了", True),
    ("你会不会离开我", True),
    ("（轻轻靠在你肩上）我有点累", True),
    ("今天好累啊", False),
]

for msg, expect in scenarios:
    resp = send(cid, msg)
    text = ""
    if isinstance(resp, dict) and "ai_message" in resp:
        text = resp["ai_message"].get("content") or ""
    elif isinstance(resp, dict):
        text = resp.get("reply") or resp.get("content") or str(resp)
    print("=" * 55)
    print(f"[{'演' if expect else '不演'}] {msg}")
    print("回复:", text[:400].replace("\n", " "))
    time.sleep(1)
