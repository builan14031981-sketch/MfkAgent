# -*- coding: utf-8 -*-
"""Test 听澜 (writer_jiangnan) 广告词 capability via backend API"""
import json
import urllib.request
import time

BASE = "http://127.0.0.1:8000"

def api_post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))

def api_get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

# Step 1: Create a chat for writer_jiangnan
print("=== Creating chat for writer_jiangnan ===")
chat = api_post("/api/chat", {"agent_id": "writer_jiangnan", "title": "广告词测试_听澜"})
chat_id = chat.get("id") or chat.get("chat_id")
print(f"Chat created: {chat_id}")
print(f"Agent name in chat: {chat.get('agent_name', 'N/A')}")

# Step 2: Send the 广告词 test message (same as original test)
test_msg = "连锁面馆「深夜面馆」，1 句 slogan + ≤50 字主广告词，核心「深夜一碗热面就是最好的陪伴」"
print(f"\n=== Sending test message ===")
print(f"Input: {test_msg}")

result = api_post(f"/api/chat/{chat_id}/send", {"content": test_msg})
print(f"\n=== Response (raw keys) ===")
print(list(result.keys()) if isinstance(result, dict) else type(result))

# Try to extract the response text
if isinstance(result, dict):
    response_text = result.get("response") or result.get("content") or result.get("message") or result.get("text") or ""
    if not response_text and "messages" in result:
        msgs = result["messages"]
        if msgs:
            response_text = msgs[-1].get("content", "")
    print(f"\n=== 听澜 Output ===")
    print(response_text)
else:
    print(f"\n=== Result ===")
    print(str(result)[:2000])

# Step 3: Also check messages
print(f"\n=== Chat messages ===")
try:
    msgs = api_get(f"/api/chat/{chat_id}/messages")
    if isinstance(msgs, list):
        for m in msgs:
            role = m.get("role", "?")
            content = m.get("content", "")[:500]
            print(f"[{role}]: {content}")
            print("---")
except Exception as e:
    print(f"Could not fetch messages: {e}")
