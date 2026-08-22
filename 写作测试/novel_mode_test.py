# -*- coding: utf-8 -*-
"""小说模式自由发挥测试：听澜 writer_jiangnan"""
import json
import urllib.request
import time

BASE = "http://127.0.0.1:8000"

def api_post(path, data, timeout=300):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def create_chat(title):
    chat = api_post("/api/chat", {"agent_id": "writer_jiangnan", "title": title})
    return chat.get("id") or chat.get("chat_id")

def send_msg(chat_id, content):
    result = api_post(f"/api/chat/{chat_id}/send", {"content": content})
    ai_msg = result.get("ai_message", {})
    if isinstance(ai_msg, dict):
        return ai_msg.get("content", str(ai_msg))
    return str(ai_msg)

tasks = [
    (
        "小说_小人物自嘲",
        "写一段小说片段。主角是个刚被开除的程序员，深夜一个人在公司天台上吹风，手机响了，是前女友打来的。自由发挥，不限字数，不要写标题，直接写正文。"
    ),
    (
        "小说_对话声线",
        "写一段对话场景。一个衰仔和一个脾气暴躁的女生在便利店门口躲雨，两人之前认识但关系很僵。自由发挥，不限字数，直接写正文。"
    ),
    (
        "小说_逆鳞爆发",
        "写一段动作场景。一个看起来很废柴的年轻人在巷子里被三个人围堵要钱，他本来一直在求饶，然后其中一个人踩碎了他手里攥着的一个旧打火机。自由发挥，不限字数，直接写正文。"
    ),
    (
        "小说_时差刀点",
        "写一段叙事散文。多年以后，一个三十多岁的男人在旧物市场的地摊上，看到了一个很眼熟的打火机——那是他当年送给第一个女朋友的定情物。自由发挥，不限字数，直接写正文。"
    ),
]

results = []
for label, prompt in tasks:
    print(f"\n{'='*70}")
    print(f"【{label}】")
    print(f"题干: {prompt}")
    print(f"{'='*70}")
    try:
        chat_id = create_chat(f"小说模式_{label}")
        print(f"chat_id: {chat_id}")
        output = send_msg(chat_id, prompt)
        char_count = len(output.replace("\n", "").replace(" ", "").replace("\r", ""))
        print(f"\n--- 输出（约{char_count}字）---")
        print(output)
        print()
        results.append({"label": label, "chat_id": chat_id, "prompt": prompt, "output": output, "char_count": char_count})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"label": label, "error": str(e)})
    time.sleep(1)

outfile = r"E:\智慧项目\Mfkagent\写作测试\小说模式自由发挥测试_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n结果已保存: {outfile}")
