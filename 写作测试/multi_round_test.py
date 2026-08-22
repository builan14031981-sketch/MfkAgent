# -*- coding: utf-8 -*-
"""多轮对话测试 - 在chat 405同一会话里继续写故事，3轮"""
import json
import urllib.request
import time

BASE = "http://127.0.0.1:8000"
CHAT_ID = 405  # 刚才小说叙事的会话，许晟和陈默的故事
TEST_MODEL = "deepseek-v4-flash"

def api_post(path, data, timeout=600):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def send_msg(content):
    result = api_post(f"/api/chat/{CHAT_ID}/send", {"content": content, "model": TEST_MODEL})
    ai_msg = result.get("ai_message", {})
    if isinstance(ai_msg, dict):
        return ai_msg.get("content", str(ai_msg))
    return str(ai_msg)

rounds = [
    {
        "id": "round1",
        "label": "第一轮_回到出租屋",
        "prompt": "继续写许晟的故事。写他同学聚会结束后回到出租屋的场景。许晟是一个独立开发者，正在做一个叫MfkAgent的AI Agent项目，一边做项目一边找工作。他的父亲在工厂里做高温劳作，有高血压高血脂。他住在一个月租一千二的老小区出租屋里，深夜打开电脑继续调试代码。自由发挥，不限字数，直接写正文。"
    },
    {
        "id": "round2",
        "label": "第二轮_父亲的电话",
        "prompt": "继续写。许晟正在调试代码的时候，父亲打来了电话。父亲在工厂里刚下夜班，声音很疲惫，问他工作找得怎么样了，钱够不够花，叮嘱他别熬夜。许晟一边对着代码里的bug，一边跟父亲说话。自由发挥，不限字数，直接写正文。"
    },
    {
        "id": "round3",
        "label": "第三轮_深夜决定",
        "prompt": "继续写。挂了电话之后，许晟看着屏幕上跑不通的代码，又看了看手机里招聘软件上已读不回的消息，他做了一个决定。自由发挥，不限字数，直接写正文。"
    },
]

results = []
for r in rounds:
    print(f"\n{'='*70}")
    print(f"【{r['label']}】 chat_id={CHAT_ID} model={TEST_MODEL}")
    print(f"输入: {r['prompt'][:80]}...")
    print(f"{'='*70}")
    try:
        start = time.time()
        output = send_msg(r["prompt"])
        elapsed = time.time() - start
        char_count = len(output.replace("\n", "").replace(" ", "").replace("\r", ""))
        print(f"\n--- 输出（约{char_count}字，耗时{elapsed:.1f}秒）---")
        print(output)
        print()
        results.append({
            "id": r["id"],
            "label": r["label"],
            "prompt": r["prompt"],
            "output": output,
            "char_count": char_count,
            "elapsed_seconds": round(elapsed, 1),
            "chat_id": CHAT_ID,
            "model": TEST_MODEL
        })
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"id": r["id"], "label": r["label"], "error": str(e)})
    time.sleep(2)

outfile = r"E:\智慧项目\Mfkagent\写作测试\多轮对话测试_deepseek_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n\n{'='*70}")
print(f"多轮对话测试完成，结果已保存: {outfile}")
print(f"共完成 {len([r for r in results if 'output' in r])}/{len(rounds)} 轮")
print(f"{'='*70}")
