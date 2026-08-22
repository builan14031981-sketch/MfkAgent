# -*- coding: utf-8 -*-
"""调查听澜保存的记忆"""
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 查所有记忆表
print("="*70)
print("数据库中的记忆相关表:")
print("="*70)
tables = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memor%'")).fetchall()
for t in tables:
    print(f"  - {t[0]}")

# 查所有记忆
print("\n" + "="*70)
print("所有记忆记录:")
print("="*70)
try:
    memories = db.execute(text("SELECT * FROM memories ORDER BY id DESC LIMIT 20")).fetchall()
    # 获取列名
    cols = db.execute(text("PRAGMA table_info(memories)")).fetchall()
    col_names = [c[1] for c in cols]
    print(f"列名: {col_names}")
    print()
    for m in memories:
        print(f"--- id={m[0]} ---")
        for i, col in enumerate(col_names):
            val = m[i]
            if val and len(str(val)) > 200:
                val = str(val)[:200] + "..."
            print(f"  {col}: {val}")
        print()
except Exception as e:
    print(f"查询memories表失败: {e}")

# 查agent_memory关联表
print("\n" + "="*70)
print("Agent-Memory 关联表:")
print("="*70)
try:
    agent_mems = db.execute(text("SELECT * FROM agent_memories ORDER BY id DESC LIMIT 20")).fetchall()
    cols = db.execute(text("PRAGMA table_info(agent_memories)")).fetchall()
    col_names = [c[1] for c in cols]
    print(f"列名: {col_names}")
    print()
    for am in agent_mems:
        print(f"--- id={am[0]} ---")
        for i, col in enumerate(col_names):
            print(f"  {col}: {am[i]}")
        print()
except Exception as e:
    print(f"查询agent_memories表失败: {e}")

db.close()
