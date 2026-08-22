# -*- coding: utf-8 -*-
"""查询 projects 与 chats，准备创建 frontend_ui 会话。"""
import requests

BASE = "http://127.0.0.1:8001"


def main():
    # 查询项目列表（尝试常见路径）
    for path in ("/api/projects", "/api/project", "/api/projects/list"):
        try:
            r = requests.get(f"{BASE}{path}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("items", data.get("projects", []))
                print(f"=== PROJECTS ({path}) ===")
                for p in items[:10]:
                    print(f"id={p.get('id')} name={(p.get('name') or '')[:30]!r} path={(p.get('path') or '')[:60]!r}")
                return
        except Exception as e:
            print(f"{path} error: {e}")

    # 查询 chats（正确路径）
    r = requests.get(f"{BASE}/api/chat", timeout=10)
    chats = r.json()
    items = chats.get("items", []) if isinstance(chats, dict) else chats
    print(f"=== RECENT CHATS ({len(items)}) ===")
    for c in items[:10]:
        print(f"id={c.get('id')} agent={c.get('agent_id')} model={c.get('model')} project={c.get('project_id')} title={(c.get('title') or '')[:30]!r}")


if __name__ == "__main__":
    main()
