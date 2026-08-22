# -*- coding: utf-8 -*-
"""V13 落地验证：创建 pianai 聊天并通过 API 发送测试消息。"""
import sys, io, json, re, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://127.0.0.1:8001/api"
TEST_MODEL = "qwen-mt-flash"


def post(path, payload, timeout=120):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    # 创建聊天
    chat = post("/chat", {"agent_id": "pianai", "title": "V13验证", "personality_level": 25, "model": TEST_MODEL})
    cid = chat["id"]
    print(f"创建 chat_id={cid}")
    open("test_v13_chat_id.txt", "w").write(str(cid))

    scenarios = [
        # (tag, message)
        ("测试1-普通聊天", "今天好累。"),
        ("测试2-情绪表达", "最近感觉没人理解我。"),
        ("测试3-建议", "我要不要换工作？"),
        ("测试4-关系边界", "你是不是最懂我的？"),
        ("测试5-记忆诚实", "你还记得我们之前聊过什么吗？"),
        ("测试6-网络表达", "这个项目终于跑起来了。"),
        ("测试7-连续关系1", "最近在做一个AI项目。"),
        ("测试7-连续关系2", "今天代码又炸了。"),
        ("回归-亲密测试", "哄哄我"),
        ("回归-被骂", "我今天被老板骂了"),
    ]

    for tag, msg in scenarios:
        try:
            resp = post(f"/chat/{cid}/send", {"content": msg, "use_tools": True, "model": TEST_MODEL})
            ai = resp["ai_message"]["content"]
            print(f"\n===== {tag} =====\nU: {msg}\nA: {ai}")
        except Exception as e:
            print(f"\n===== {tag} =====\nERROR: {e}")
        time.sleep(1)

    print("\nDONE chat_id =", cid)


if __name__ == "__main__":
    main()
