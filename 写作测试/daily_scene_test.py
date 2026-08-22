# -*- coding: utf-8 -*-
"""非江南日常场景测试：听澜 writer_jiangnan"""
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
        "日常_找工作面试",
        "写一段叙事。一个普通的应届毕业生，早上六点半起床，转两趟地铁去一家公司面试，到了之后发现面试官是自己大学时挂过他科的老师。自由发挥，不限字数，直接写正文。"
    ),
    (
        "日常_租房被坑",
        "写一段叙事。一个年轻人在大城市找租房，中介带他看了五套房，每一套都有各种问题，最后他在第六套房子的卫生间里发现了一只巨大的蟑螂。自由发挥，不限字数，直接写正文。"
    ),
    (
        "日常_一个人看病",
        "写一段叙事。一个人发烧到39度，自己一个人去医院挂号、排队、抽血、等报告，在候诊区睡着了，醒来的时候发现输液的手回血了。自由发挥，不限字数，直接写正文。"
    ),
    (
        "日常_超市结账",
        "写一段叙事。晚上十点半，一个人在超市自助结账，扫了半天扫不上一瓶酱油，后面排队的人开始不耐烦，这时候他发现自己忘带手机了，兜里只有一张皱巴巴的二十块钱。自由发挥，不限字数，直接写正文。"
    ),
]

results = []
for label, prompt in tasks:
    print(f"\n{'='*70}")
    print(f"【{label}】")
    print(f"题干: {prompt}")
    print(f"{'='*70}")
    try:
        chat_id = create_chat(f"日常场景_{label}")
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

outfile = r"E:\智慧项目\Mfkagent\写作测试\非江南日常场景测试_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n结果已保存: {outfile}")
