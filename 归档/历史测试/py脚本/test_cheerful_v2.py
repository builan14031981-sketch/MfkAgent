# -*- coding: utf-8 -*-
"""活泼少女优化专项测试"""
import time
import requests

BASE = "http://127.0.0.1:8000/api/chat"


def create_chat(title):
    r = requests.post(f"{BASE}/", json={"agent_id": "pianai", "title": title}, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def send(chat_id, content):
    r = requests.post(f"{BASE}/{chat_id}/send", json={"content": content}, timeout=120)
    r.raise_for_status()
    return r.json()["ai_message"]["content"]


def main():
    chat_id = create_chat("测试-活泼少女v2")
    print("切换活泼少女模式...")
    send(chat_id, "活泼少女模式")
    time.sleep(1)

    tests = [
        "我不太好，很多东西压得我喘不过气",
        "今天被老板骂了",
        "我好开心啊！",
        "你是谁",
    ]

    for i, msg in enumerate(tests, 1):
        print(f"\n{'='*50}")
        print(f"测试{i}: {msg}")
        print(f"{'='*50}")
        reply = send(chat_id, msg)
        print(f"回复: {reply}")
        # 统计段数和emoji
        paragraphs = [p for p in reply.split("\n") if p.strip()]
        print(f"  -> 段数: {len(paragraphs)}, 句数: {reply.count('。') + reply.count('！') + reply.count('？')}")
        time.sleep(1)

    print("\n" + "=" * 50)
    print("测试完成")


if __name__ == "__main__":
    main()
