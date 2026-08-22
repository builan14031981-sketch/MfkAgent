# -*- coding: utf-8 -*-
"""查询 agents 列表，定位 frontend_ui agent 的 id 及创建 chat 所需接口信息。"""
import json
import sys
import requests

BASE = "http://127.0.0.1:8001"


def main():
    # 1. 查询 agents
    r = requests.get(f"{BASE}/api/agents", timeout=10)
    agents = r.json()
    if isinstance(agents, dict):
        agents = agents.get("items", agents.get("agents", []))
    print("=== AGENTS ===")
    for a in agents:
        print(f"id={a.get('id')!r} name={a.get('name')!r} status={a.get('status')}")
    # 2. 查询 chats（看现有 chat 结构）
    r2 = requests.get(f"{BASE}/api/chats", timeout=10)
    try:
        chats = r2.json()
        if isinstance(chats, dict):
            chats = chats.get("items", chats.get("chats", []))
        print("=== RECENT CHATS ===")
        for c in chats[:8]:
            print(f"id={c.get('id')} agent={c.get('agent_id')} model={c.get('model')} project={c.get('project_id')} title={(c.get('title') or '')[:30]}")
    except Exception as e:
        print("chats error:", e, r2.text[:300])


if __name__ == "__main__":
    main()
