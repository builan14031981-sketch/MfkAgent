# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import Agent
from sqlalchemy import text

db = SessionLocal()
cols = db.execute(text("PRAGMA table_info(agents)")).fetchall()
print("Agent表字段:")
for c in cols:
    print(f"  {c[1]} ({c[2]})")

a = db.query(Agent).filter(Agent.agent_id == "writer_jiangnan").first()
print(f"\n听澜当前model字段: {getattr(a, 'model', '无此字段')}")
print(f"听澜所有字段值:")
for c in cols:
    val = getattr(a, c[1], None)
    if val and len(str(val)) > 100:
        val = str(val)[:100] + "..."
    print(f"  {c[1]}: {val}")

db.close()
