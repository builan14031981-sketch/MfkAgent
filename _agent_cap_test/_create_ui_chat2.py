# -*- coding: utf-8 -*-
"""创建 frontend_ui 会话 chat 311 + 确认后端健康。"""
import requests

BASE = "http://127.0.0.1:8001"
try:
    h = requests.get(f"{BASE}/health", timeout=5).json()
    print("health:", h)
except Exception as e:
    print("health error:", e)

payload = {
    "agent_id": "frontend_ui",
    "project_id": 43,
    "model": "glm-4.7",
    "title": "UI验证-安全中心-2",
    "mode": "build",
}
r = requests.post(f"{BASE}/api/chat", json=payload, timeout=15)
print("status:", r.status_code)
if r.status_code in (200, 201):
    c = r.json()
    print("chat_id:", c.get("id"))
    print("agent:", c.get("agent_id"), "model:", c.get("model"), "project:", c.get("project_id"))
else:
    print(r.text[:500])
