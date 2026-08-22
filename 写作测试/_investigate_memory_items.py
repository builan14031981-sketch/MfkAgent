# -*- coding: utf-8 -*-
"""调查memory_items表"""
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

print("="*70)
print("memory_items 表结构:")
print("="*70)
cols = db.execute(text("PRAGMA table_info(memory_items)")).fetchall()
for c in cols:
    print(f"  {c[1]} ({c[2]})")

print("\n" + "="*70)
print("memory_items 所有记录:")
print("="*70)
try:
    items = db.execute(text("SELECT * FROM memory_items ORDER BY id DESC LIMIT 30")).fetchall()
    col_names = [c[1] for c in cols]
    for item in items:
        print(f"--- id={item[0]} ---")
        for i, col in enumerate(col_names):
            val = item[i]
            if val and len(str(val)) > 300:
                val = str(val)[:300] + "..."
            print(f"  {col}: {val}")
        print()
    print(f"总计: {len(items)} 条")
except Exception as e:
    print(f"查询失败: {e}")

db.close()
