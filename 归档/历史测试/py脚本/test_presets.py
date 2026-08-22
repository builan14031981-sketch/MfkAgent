# -*- coding: utf-8 -*-
"""Pianai V17 多人格预设实际对话测试 — 多会话对比"""
import sys
import time
import requests

BASE = "http://127.0.0.1:8000/api/chat"

# 测试场景：用户说压力大
TEST_MSG = "我不太好，很多东西压得我喘不过气，事太多了烦人"

PRESETS = [
    {"name": "默认偏爱", "switch": None},
    {"name": "傲娇", "switch": "切换傲娇模式"},
    {"name": "霸总", "switch": "切换霸总模式"},
    {"name": "暖心姐姐", "switch": "暖心大姐姐"},
    {"name": "高冷", "switch": "切换高冷模式"},
    {"name": "活泼少女", "switch": "活泼少女模式"},
]


def create_chat(title):
    r = requests.post(f"{BASE}/", json={"agent_id": "pianai", "title": title}, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def send(chat_id, content):
    r = requests.post(f"{BASE}/{chat_id}/send", json={"content": content}, timeout=120)
    r.raise_for_status()
    return r.json()["ai_message"]["content"]


def main():
    results = []
    for p in PRESETS:
        print(f"\n{'='*60}")
        print(f"预设：{p['name']}")
        print(f"{'='*60}")
        chat_id = create_chat(f"测试-{p['name']}")
        print(f"  会话ID: {chat_id}")

        if p["switch"]:
            print(f"  切换指令: {p['switch']}")
            switch_reply = send(chat_id, p["switch"])
            print(f"  切换回复: {switch_reply}")
            time.sleep(1)

        print(f"  测试消息: {TEST_MSG}")
        reply = send(chat_id, TEST_MSG)
        print(f"  预设回复: {reply}")
        results.append({"preset": p["name"], "reply": reply})
        time.sleep(1)

    print(f"\n\n{'='*60}")
    print("对比总结")
    print(f"{'='*60}")
    print(f"\n测试消息：「{TEST_MSG}」\n")
    for r in results:
        print(f"【{r['preset']}】")
        print(f"  {r['reply']}")
        print()


if __name__ == "__main__":
    main()
