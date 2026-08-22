# -*- coding: utf-8 -*-
"""Pianai V17.1 新功能测试：首次开场白 + 模糊指令 + 优化后预设"""
import sys
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
    print("=" * 60)
    print("测试1：首次对话开场白")
    print("=" * 60)
    chat_id = create_chat("测试-首次对话")
    print(f"  会话ID: {chat_id}")
    print(f"  发送: 你好")
    reply = send(chat_id, "你好")
    print(f"  回复: {reply}")
    print()

    print("=" * 60)
    print("测试2：模糊指令列出人格")
    print("=" * 60)
    chat_id2 = create_chat("测试-模糊指令")
    print(f"  会话ID: {chat_id2}")
    # 先发一条普通消息（不是首次对话了）
    send(chat_id2, "你好")
    time.sleep(1)
    print(f"  发送: 换个风格")
    reply2 = send(chat_id2, "换个风格")
    print(f"  回复: {reply2}")
    print()

    print("=" * 60)
    print("测试3：优化后的高冷")
    print("=" * 60)
    chat_id3 = create_chat("测试-高冷优化")
    send(chat_id3, "切换高冷模式")
    time.sleep(1)
    print(f"  发送: 我不太好，很多东西压得我喘不过气")
    reply3 = send(chat_id3, "我不太好，很多东西压得我喘不过气")
    print(f"  回复: {reply3}")
    print()

    print("=" * 60)
    print("测试4：优化后的活泼少女")
    print("=" * 60)
    chat_id4 = create_chat("测试-活泼优化")
    send(chat_id4, "活泼少女模式")
    time.sleep(1)
    print(f"  发送: 我不太好，很多东西压得我喘不过气")
    reply4 = send(chat_id4, "我不太好，很多东西压得我喘不过气")
    print(f"  回复: {reply4}")
    print()

    print("=" * 60)
    print("测试5：优化后的霸总（少问多做）")
    print("=" * 60)
    chat_id5 = create_chat("测试-霸总优化")
    send(chat_id5, "切换霸总模式")
    time.sleep(1)
    print(f"  发送: 我不太好，很多东西压得我喘不过气")
    reply5 = send(chat_id5, "我不太好，很多东西压得我喘不过气")
    print(f"  回复: {reply5}")
    print()

    print("=" * 60)
    print("全部测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
