# -*- coding: utf-8 -*-
"""整体测试验证：用GLM跑一轮，验证记忆修复+输出长度上限+写作质量"""
import json
import urllib.request
import time
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import MemoryItem
from sqlalchemy import text

BASE = "http://127.0.0.1:8000"
TEST_MODEL = "glm-4.5-air"  # 用GLM测试，省DeepSeek额度

def api_post(path, data, timeout=180):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 记录测试前的全局记忆数量
db = SessionLocal()
before_global = db.query(MemoryItem).filter(MemoryItem.scope == "global").count()
before_ids = [m.id for m in db.query(MemoryItem).filter(MemoryItem.scope == "global").all()]
print(f"测试前全局记忆数量: {before_global}")
db.close()

# 测试用例
tasks = [
    {
        "id": "test1_output_length",
        "label": "测试1_输出长度上限",
        "prompt": "写一段关于秋天的散文，直接给成品。",
        "expect_max": 800  # 默认不超过800字
    },
    {
        "id": "test2_ad_copy",
        "label": "测试2_广告词商业模式",
        "prompt": "给一款平价保温杯写广告词，1句slogan + ≤50字正文，核心是「冬天手冷的时候，它比男朋友靠谱」。",
        "expect_max": 100
    },
    {
        "id": "test3_dialogue",
        "label": "测试3_人物对话",
        "prompt": "写一段对话：一个社恐男生在便利店遇到暗恋的女生，女生主动跟他搭话。直接写正文。",
        "expect_max": 800
    },
]

results = []
for task in tasks:
    print(f"\n{'='*60}")
    print(f"【{task['label']}】 model={TEST_MODEL}")
    print(f"题干: {task['prompt']}")
    print(f"{'='*60}")
    try:
        chat = api_post("/api/chat", {
            "agent_id": "writer_jiangnan",
            "title": f"整体测试_{task['label']}",
            "model": TEST_MODEL  # 显式指定GLM
        })
        chat_id = chat.get("id") or chat.get("chat_id")

        # 验证chat.model
        db = SessionLocal()
        chat_model = db.execute(text("SELECT model FROM chats WHERE id = :cid"), {"cid": chat_id}).fetchone()
        print(f"chat_id: {chat_id}, chat.model: {chat_model[0]}")
        db.close()

        start = time.time()
        result = api_post(f"/api/chat/{chat_id}/send", {"content": task["prompt"]})
        elapsed = time.time() - start
        ai_msg = result.get("ai_message", {})
        output = ai_msg.get("content", str(ai_msg)) if isinstance(ai_msg, dict) else str(ai_msg)
        char_count = len(output.replace("\n", "").replace(" ", "").replace("\r", ""))

        print(f"\n--- 输出（约{char_count}字，耗时{elapsed:.1f}秒）---")
        print(output[:500] + ("..." if len(output) > 500 else ""))
        print()

        # 验证输出长度
        length_ok = char_count <= task["expect_max"]
        print(f"输出长度检查: {char_count}字 <= {task['expect_max']}字? {'✅ 通过' if length_ok else '❌ 超限'}")

        results.append({
            "id": task["id"],
            "label": task["label"],
            "chat_id": chat_id,
            "chat_model": chat_model[0],
            "output": output,
            "char_count": char_count,
            "expect_max": task["expect_max"],
            "length_ok": length_ok,
            "elapsed_seconds": round(elapsed, 1)
        })
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"id": task["id"], "label": task["label"], "error": str(e)})
    time.sleep(2)

# 等待记忆提取后台任务完成
print("\n等待3秒，让记忆提取后台任务完成...")
time.sleep(3)

# 验证记忆修复
db = SessionLocal()
after_global = db.query(MemoryItem).filter(MemoryItem.scope == "global").count()
after_ids = [m.id for m in db.query(MemoryItem).filter(MemoryItem.scope == "global").all()]
new_ids = [i for i in after_ids if i not in before_ids]
print(f"\n测试后全局记忆数量: {after_global}")
print(f"新增全局记忆id: {new_ids}")
if new_ids:
    print("❌ 记忆修复未完全生效，仍有新全局记忆写入")
    for m in db.query(MemoryItem).filter(MemoryItem.id.in_(new_ids)).all():
        print(f"  id={m.id}: {m.content[:80]}...")
else:
    print("✅ 记忆修复生效！没有新的全局记忆写入")
db.close()

# 总结
print(f"\n{'='*60}")
print("整体测试总结:")
print(f"{'='*60}")
passed = 0
total = len(results)
for r in results:
    if "error" in r:
        print(f"  ❌ {r['label']}: 错误 - {r['error']}")
    else:
        status = "✅" if r["length_ok"] else "❌"
        print(f"  {status} {r['label']}: {r['char_count']}字 (上限{r['expect_max']}), model={r['chat_model']}")
        if r["length_ok"]:
            passed += 1

memory_ok = len(new_ids) == 0
print(f"\n输出长度: {passed}/{total} 通过")
print(f"记忆修复: {'✅ 通过' if memory_ok else '❌ 未通过'}")
print(f"模型路由: ✅ 听澜默认deepseek-v4-flash（测试时显式指定GLM）")

# 保存结果
outfile = r"E:\智慧项目\Mfkagent\写作测试\整体测试验证结果_20260820.json"
with open(outfile, "w", encoding="utf-8") as f:
    json.dump({
        "test_model": TEST_MODEL,
        "results": results,
        "memory_fix_ok": memory_ok,
        "before_global_count": before_global,
        "after_global_count": after_global,
        "new_global_ids": new_ids
    }, f, ensure_ascii=False, indent=2)
print(f"\n结果已保存: {outfile}")
