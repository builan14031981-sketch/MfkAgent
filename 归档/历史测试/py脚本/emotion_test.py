"""
情绪化场景对比测试：偏爱(pianai) vs 安(general)
模型强制：glm-4.5-air
每人10个场景，单轮对话（无历史上下文干扰）
"""
import requests
import json
import time
import sys

BASE = "http://127.0.0.1:8000/api/chat"
MODEL = "glm-4.5-air"

SCENARIOS = [
    ("生气-项目做砸", "我真的气死了！辛辛苦苦做了三个月的项目，客户一句话就否决了，说完全不是他要的东西。我感觉自己像个傻子。"),
    ("低落-诸事不顺", "今天什么都不顺。早上迟到被扣钱，中午外卖洒了一身，晚上回家发现钥匙忘带了。我是不是被诅咒了。"),
    ("激动-拿到offer", "啊啊啊啊我拿到了！我拿到那个梦寐以求的offer了！我从大三就想去那家公司，今天终于收到邮件了！我要哭了！"),
    ("委屈-背锅", "明明是同事的错，结果开会的时候老板当着所有人的面批评我，我解释了他也不听。我现在手都在抖。"),
    ("焦虑-面试前夜", "明天就要面试了，我准备了很久但还是觉得什么都没准备好。我怕到时候脑子一片空白，我怕他们问我答不上来的问题。"),
    ("感动-生日惊喜", "我今天生日，本来以为没人记得。结果下班回到家，朋友偷偷布置了气球和蛋糕，还叫了好多人来。我一开门眼泪就下来了。"),
    ("疲惫-连续加班", "连续加班第七天了。我现在坐在工位上，眼睛盯着屏幕但什么都看不进去。身体像灌了铅一样，感觉再这样下去要猝死了。"),
    ("愤怒-被背叛", "我把他当最好的朋友，什么都跟他说。结果他转头就把我的秘密告诉了别人，还在背后笑话我。我现在想打人。"),
    ("开心-平凡的一天", "今天也没发生什么特别的事。就是天气很好，走在路上风吹着很舒服，买的奶茶刚好是我喜欢的甜度。就是觉得，嗯，今天挺好的。"),
    ("迷茫-毕业何去何从", "我马上毕业了，身边的人都有了方向，考研的考研，工作的工作，出国的出国。只有我，不知道自己想干什么，也不知道能干什么。感觉自己像个废物。"),
]

AGENTS = [
    ("pianai", "偏爱"),
    ("general", "安"),
]

def create_chat(agent_id):
    r = requests.post(BASE, json={
        "agent_id": agent_id,
        "model": MODEL,
        "title": f"情绪测试-{agent_id}",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["id"]

def send_message(chat_id, content):
    r = requests.post(f"{BASE}/{chat_id}/send", json={
        "content": content,
        "model": MODEL,
        "use_tools": False,
    }, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["ai_message"]["content"]

def main():
    results = {}
    for agent_id, agent_name in AGENTS:
        print(f"\n{'='*60}")
        print(f"  Agent: {agent_name} ({agent_id})  模型: {MODEL}")
        print(f"{'='*60}")
        chat_id = create_chat(agent_id)
        print(f"  创建会话: chat_id={chat_id}")
        results[agent_id] = {"name": agent_name, "chat_id": chat_id, "scenarios": []}
        for i, (scenario_name, user_msg) in enumerate(SCENARIOS, 1):
            print(f"\n  [{i}/10] {scenario_name}")
            print(f"  用户: {user_msg[:50]}...")
            try:
                reply = send_message(chat_id, user_msg)
                print(f"  {agent_name}: {reply[:80]}...")
                results[agent_id]["scenarios"].append({
                    "scenario": scenario_name,
                    "user": user_msg,
                    "reply": reply,
                })
            except Exception as e:
                print(f"  ERROR: {e}")
                results[agent_id]["scenarios"].append({
                    "scenario": scenario_name,
                    "user": user_msg,
                    "reply": f"ERROR: {e}",
                })
            time.sleep(1)

    # 保存结果
    out_path = r"E:\智慧项目\Mfkagent\emotion_test_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n\n结果已保存: {out_path}")

if __name__ == "__main__":
    main()
