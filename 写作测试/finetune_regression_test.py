# -*- coding: utf-8 -*-
"""微调回归测试：听澜 writer_jiangnan"""
import json
import urllib.request
import time

BASE = "http://127.0.0.1:8000"

def api_post(path, data, timeout=180):
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
    ("微调_面馆_R1", "连锁面馆「深夜面馆」，1 句 slogan + ≤50 字主广告词，核心「深夜一碗热面就是最好的陪伴」"),
    ("微调_面馆_R2", "连锁面馆「深夜面馆」，1 句 slogan + ≤50 字主广告词，核心「深夜一碗热面就是最好的陪伴」"),
    ("微调_面馆_R3", "连锁面馆「深夜面馆」，1 句 slogan + ≤50 字主广告词，核心「深夜一碗热面就是最好的陪伴」"),
    ("微调_耳机_品牌名", "某品牌降噪耳机，1句slogan + ≤50字主广告词，面向加班白领，核心「戴上它，世界就安静了」"),
    ("微调_朋友圈_字数", "深夜加班走出写字楼，又累又倔强，≤200字，不鸡汤。"),
]

results = []
for label, prompt in tasks:
    print(f"\n{'='*60}")
    print(f"【{label}】")
    print(f"题干: {prompt}")
    print(f"{'='*60}")
    try:
        chat_id = create_chat(f"微调回归_{label}")
        print(f"chat_id: {chat_id}")
        output = send_msg(chat_id, prompt)
        # 统计字数（去掉空白和换行）
        char_count = len(output.replace("\n", "").replace(" ", "").replace("\r", ""))
        print(f"\n--- 输出（约{char_count}字）---\n{output}\n")
        results.append({"label": label, "chat_id": chat_id, "prompt": prompt, "output": output, "char_count": char_count})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"label": label, "error": str(e)})
    time.sleep(1)

outfile = r"E:\智慧项目\Mfkagent\写作测试\微调回归测试结果_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n结果已保存: {outfile}")
