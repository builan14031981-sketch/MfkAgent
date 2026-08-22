# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
cols = db.execute(text("PRAGMA table_info(models)")).fetchall()
print("models表字段:", [c[1] for c in cols])

models = db.execute(text("SELECT id, name, provider FROM models ORDER BY id")).fetchall()
print("\n已配置的模型:")
for m in models:
    print(f"  {m[0]} ({m[2]}): {m[1]}")

qwen = db.execute(text("SELECT id, name FROM models WHERE id LIKE '%qwen%' OR name LIKE '%qwen%'")).fetchall()
print("\n含qwen的模型:", qwen)

# 查默认模型
from app.core.agent_runtime.context_builder import get_default_model
print(f"\nget_default_model(): {get_default_model()}")

db.close()
