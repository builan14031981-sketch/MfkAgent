# -*- coding: utf-8 -*-
"""创建 frontend_ui 会话（绑定项目 43 + glm-4.7）。"""
import json
import requests

BASE = "http://127.0.0.1:8001"

# 项目 43 = 'Test Project' path='e:\\智慧项目\\Mfkagent' —— 根项目，可访问前端目录
PROJECT_ID = 43


def main():
    payload = {
        "agent_id": "frontend_ui",
        "project_id": PROJECT_ID,
        "model": "glm-4.7",
        "title": "UI验证-安全中心",
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


if __name__ == "__main__":
    main()
