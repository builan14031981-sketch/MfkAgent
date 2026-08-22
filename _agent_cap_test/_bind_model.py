# -*- coding: utf-8 -*-
"""PATCH chat 307 绑定模型为 glm-4.7，然后 GET 验证。"""
import httpx

BASE = "http://127.0.0.1:8001"
r = httpx.patch(f"{BASE}/api/chat/307", json={"model": "glm-4.7"})
print("PATCH status:", r.status_code)
print("PATCH body:", r.text[:500])

g = httpx.get(f"{BASE}/api/chat/307")
print("GET status:", g.status_code)
print("GET body:", g.text[:800])
