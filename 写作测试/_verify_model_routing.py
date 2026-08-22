# -*- coding: utf-8 -*-
"""验证模型路由：听澜新会话是否自动继承 deepseek-v4-flash"""
import json
import urllib.request
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from sqlalchemy import text

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

# 创建听澜新会话，不指定model
print("创建听澜新会话（不指定model）...")
chat = api_post("/api/chat", {"agent_id": "writer_jiangnan", "title": "模型路由验证"})
chat_id = chat.get("id") or chat.get("chat_id")
print(f"chat_id: {chat_id}")

# 查数据库确认chat.model
db = SessionLocal()
result = db.execute(text("SELECT id, agent_id, model FROM chats WHERE id = :cid"), {"cid": chat_id}).fetchone()
print(f"\n数据库中 chat.model: {result[2]}")
if result[2] == "deepseek-v4-flash":
    print("✅ 模型路由生效！听澜新会话自动继承 deepseek-v4-flash")
else:
    print("❌ 模型路由未生效")

# 对比：创建general Agent新会话，看model
print("\n创建 general 新会话（对比）...")
chat2 = api_post("/api/chat", {"agent_id": "general", "title": "模型路由对比"})
chat_id2 = chat2.get("id") or chat2.get("chat_id")
result2 = db.execute(text("SELECT id, agent_id, model FROM chats WHERE id = :cid"), {"cid": chat_id2}).fetchone()
print(f"general chat.model: {result2[2]}")
if result2[2] is None:
    print("✅ general 不受影响，使用全局默认模型")
else:
    print(f"⚠️  general 继承了 model: {result2[2]}")

db.close()
