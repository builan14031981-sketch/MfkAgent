# -*- coding: utf-8 -*-
"""给听澜设置默认模型为 deepseek-v4-flash（原生SQL）"""
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# 查当前值
result = db.execute(text("SELECT agent_id, name, model FROM agents WHERE agent_id = 'writer_jiangnan'")).fetchone()
print(f"修改前: agent_id={result[0]}, name={result[1]}, model={result[2]}")

# 更新
db.execute(text("UPDATE agents SET model = :model WHERE agent_id = 'writer_jiangnan'"), {"model": "deepseek-v4-flash"})
db.commit()

# 验证
result = db.execute(text("SELECT agent_id, name, model FROM agents WHERE agent_id = 'writer_jiangnan'")).fetchone()
print(f"修改后: agent_id={result[0]}, name={result[1]}, model={result[2]}")
print(f"✅ 听澜默认模型已设置为 deepseek-v4-flash")

# 验证其他Agent不受影响
print("\n所有Agent的模型配置:")
results = db.execute(text("SELECT agent_id, name, model FROM agents ORDER BY id")).fetchall()
for r in results:
    print(f"  {r[0]} ({r[1]}): model={r[2]}")

db.close()
