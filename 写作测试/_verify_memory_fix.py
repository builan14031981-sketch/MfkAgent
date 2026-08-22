# -*- coding: utf-8 -*-
"""验证听澜记忆修复：跑一轮对话，确认没有新的全局记忆写入"""
import json
import urllib.request
import time
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import MemoryItem

BASE = "http://127.0.0.1:8000"

def api_post(path, data, timeout=120):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

# 记录修复前的全局记忆数量
db = SessionLocal()
before_count = db.query(MemoryItem).filter(MemoryItem.scope == "global").count()
before_ids = [m.id for m in db.query(MemoryItem).filter(MemoryItem.scope == "global").all()]
print(f"修复前全局记忆数量: {before_count}, ids: {before_ids}")
db.close()

# 用听澜跑一轮对话（GLM，不指定model用默认）
print("\n创建听澜会话...")
chat = api_post("/api/chat", {"agent_id": "writer_jiangnan", "title": "记忆修复验证"})
chat_id = chat.get("id") or chat.get("chat_id")
print(f"chat_id: {chat_id}")

print("\n发送写作请求...")
result = api_post(f"/api/chat/{chat_id}/send", {
    "content": "写一段50字以内的朋友圈文案，主题是深夜加班后的心情。直接给成品。"
})
ai_msg = result.get("ai_message", {})
output = ai_msg.get("content", str(ai_msg)) if isinstance(ai_msg, dict) else str(ai_msg)
print(f"输出: {output}")

# 等待记忆提取后台任务完成（autonomous模式下是后台任务）
print("\n等待3秒，让后台记忆提取任务完成...")
time.sleep(3)

# 检查修复后的全局记忆
db = SessionLocal()
after_count = db.query(MemoryItem).filter(MemoryItem.scope == "global").count()
after_items = db.query(MemoryItem).filter(MemoryItem.scope == "global").all()
after_ids = [m.id for m in after_items]
new_ids = [i for i in after_ids if i not in before_ids]
print(f"\n修复后全局记忆数量: {after_count}, ids: {after_ids}")
print(f"新增全局记忆id: {new_ids}")

if new_ids:
    print("⚠️  修复失败！仍有新的全局记忆写入：")
    for m in after_items:
        if m.id in new_ids:
            print(f"  id={m.id}: {m.content[:100]}...")
else:
    print("✅ 修复成功！没有新的全局记忆写入。")

# 同时检查有没有听澜的agent级记忆
agent_mems = db.query(MemoryItem).filter(MemoryItem.agent_id == "writer_jiangnan").all()
print(f"\n听澜的agent级记忆数量: {len(agent_mems)}")
for m in agent_mems:
    print(f"  id={m.id}, scope={m.scope}: {m.content[:80]}...")

db.close()
