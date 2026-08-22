# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import Setting, Agent, Chat

db = SessionLocal()
s = db.query(Setting).filter(Setting.key == 'default_model').first()
print(f'默认模型(default_model): {s.value if s else "未设置"}')

a = db.query(Agent).filter(Agent.agent_id == 'writer_jiangnan').first()
print(f'听澜模型: {a.model if a else "未找到"}')

chats = db.query(Chat).filter(Chat.agent_id == 'writer_jiangnan').order_by(Chat.id.desc()).limit(8).all()
print('最近chat使用的模型:')
for c in chats:
    print(f'  chat {c.id}: model={c.model}, title={c.title}')

db.close()
