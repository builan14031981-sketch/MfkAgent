# -*- coding: utf-8 -*-
"""第二轮AB测试 - MfkAgent端换模型后重跑4个情景"""
import json
import urllib.request
import time

BASE = "http://127.0.0.1:8000"

def api_get(path, timeout=30):
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

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

# 先查当前默认模型
print("="*70)
print("查询当前默认模型...")
try:
    # 尝试从agent配置获取模型
    agent_info = api_get("/api/agents/writer_jiangnan")
    print(f"Agent模型配置: {agent_info.get('model', '未指定(使用默认)')}")
except Exception as e:
    print(f"查询agent模型失败: {e}")

try:
    config = api_get("/api/config")
    print(f"全局默认模型: {config.get('default_model', '未知')}")
except Exception as e:
    print(f"查询全局配置失败: {e}")
print("="*70)

# 4个测试情景（与第一轮完全一致）
tasks = [
    {
        "id": "scene1_novel",
        "label": "情景1_小说叙事",
        "prompt": "写一段小说片段。一个三十岁的男人在同学聚会上遇到了当年拒绝过他的女生，她现在离婚了带着一个孩子。饭局结束后，两人在饭店门口的路灯下站了一会儿。自由发挥，不限字数，直接写正文。"
    },
    {
        "id": "scene2_daily",
        "label": "情景2_日常场景",
        "prompt": "写一段叙事。一个人早上起来发现自己发烧了，但今天有一个重要的面试。他挣扎着起床，煮了一碗粥，换衣服出门，在地铁上差点晕倒。自由发挥，不限字数，直接写正文。"
    },
    {
        "id": "scene3_ad",
        "label": "情景3_广告词",
        "prompt": "一个国产平价剃须刀品牌，面向刚毕业的大学生男生，1句slogan + ≤50字主广告词，核心「第一次刮胡子，别刮伤自己」。"
    },
    {
        "id": "scene4_dialogue",
        "label": "情景4_人物对话",
        "prompt": "写一段对话场景。一个废柴男生和一个脾气暴躁但内心柔软的女生合租，女生发现男生把她的限量版手办碰掉在地上摔碎了。自由发挥，不限字数，直接写正文。"
    },
]

results = []
for task in tasks:
    print(f"\n{'='*70}")
    print(f"【{task['label']}】")
    print(f"题干: {task['prompt']}")
    print(f"{'='*70}")
    try:
        chat_id = create_chat(f"AB测试第二轮_{task['label']}")
        print(f"chat_id: {chat_id}")
        output = send_msg(chat_id, task["prompt"])
        char_count = len(output.replace("\n", "").replace(" ", "").replace("\r", ""))
        print(f"\n--- 输出（约{char_count}字）---")
        print(output)
        print()
        results.append({
            "id": task["id"],
            "label": task["label"],
            "prompt": task["prompt"],
            "chat_id": chat_id,
            "output": output,
            "char_count": char_count,
            "round": "第二轮(换模型后)",
            "agent": "听澜 (writer_jiangnan)"
        })
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"id": task["id"], "label": task["label"], "error": str(e)})
    time.sleep(1)

outfile = r"E:\智慧项目\Mfkagent\写作测试\AB测试第二轮_MfkAgent端结果_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n结果已保存: {outfile}")
print(f"共完成 {len([r for r in results if 'output' in r])}/{len(tasks)} 个情景")
