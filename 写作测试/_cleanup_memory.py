# -*- coding: utf-8 -*-
"""清理听澜误存的全局记忆"""
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import MemoryItem
from sqlalchemy import text

db = SessionLocal()

# 查所有全局记忆
print("清理前的全局记忆:")
items = db.query(MemoryItem).filter(MemoryItem.scope == "global").order_by(MemoryItem.id).all()
for item in items:
    print(f"  id={item.id}: {item.content[:80]}... (source_chat={item.source_chat_id})")

# 删除听澜误存的全局记忆（source_chat_id 382, 405 都是听澜的测试会话）
# 以及 agent_id=None 且 content 涉及写作/许晟/鸡汤的
deleted = 0
for item in items:
    # 听澜的测试会话范围：352-408
    if item.source_chat_id and 352 <= item.source_chat_id <= 408:
        print(f"\n删除 id={item.id}: {item.content[:60]}...")
        db.delete(item)
        deleted += 1

db.commit()
print(f"\n共删除 {deleted} 条误存记忆")

# 验证
print("\n清理后的全局记忆:")
items = db.query(MemoryItem).filter(MemoryItem.scope == "global").order_by(MemoryItem.id).all()
for item in items:
    print(f"  id={item.id}: {item.content[:80]}...")

db.close()
