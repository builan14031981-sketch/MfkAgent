# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import Agent

db = SessionLocal()
try:
    for aid in ['writer', 'writer_jiangnan', 'writer_narrative']:
        agent = db.query(Agent).filter(Agent.agent_id == aid).first()
        if agent:
            print(f"=== {aid} ===")
            print(f"  name: {agent.name}")
            print(f"  status: {agent.status}")
            print(f"  description: {agent.description}")
            identity = agent.identity or ''
            # Check for key markers
            has_tinlan = '听澜' in identity
            has_no_meta = '严禁输出元信息' in identity
            has_no_params = '严禁篡改题干' in identity
            has_tielv = '铁律一' in identity
            has_old_name = '江欣' in identity or '笔神·江南' in identity
            print(f"  identity markers: 听澜={has_tinlan}, 禁元信息={has_no_meta}, 禁篡改={has_no_params}, 铁律={has_tielv}, 旧名残留={has_old_name}")
            print()
        else:
            print(f"=== {aid} === NOT FOUND")
finally:
    db.close()
