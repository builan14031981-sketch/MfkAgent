# -*- coding: utf-8 -*-
"""重 seed：更新听澜(writer_jiangnan)的配置到数据库"""
import sys
sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
import os
os.chdir(r'E:\智慧项目\Mfkagent\backend')
from app.core.database import SessionLocal
from app.models.agent import Agent
from seed_agents import PRESET_AGENTS

db = SessionLocal()

# 找到听澜的配置
tinglan_config = None
for a in PRESET_AGENTS:
    if a.get("agent_id") == "writer_jiangnan":
        tinglan_config = a
        break

if not tinglan_config:
    print("ERROR: 未找到 writer_jiangnan 配置")
    db.close()
    sys.exit(1)

print(f"找到听澜配置: {tinglan_config['name']}")
print(f"identity 长度: {len(tinglan_config['identity'])} 字符")

# 更新数据库
agent = db.query(Agent).filter(Agent.agent_id == "writer_jiangnan").first()
if not agent:
    print("ERROR: 数据库中未找到 writer_jiangnan")
    db.close()
    sys.exit(1)

print(f"\n更新前 identity 长度: {len(agent.identity or '')} 字符")

# 更新字段
agent.identity = tinglan_config["identity"]
agent.name = tinglan_config["name"]
agent.description = tinglan_config.get("description", agent.description)
agent.capabilities = tinglan_config.get("capabilities", agent.capabilities)
agent.default_personality_level = tinglan_config.get("default_personality_level", agent.default_personality_level)
agent.expression_profile = tinglan_config.get("expression_profile", agent.expression_profile)
agent.status = tinglan_config.get("status", agent.status)

db.commit()
db.refresh(agent)

print(f"更新后 identity 长度: {len(agent.identity or '')} 字符")
print(f"name: {agent.name}")
print(f"status: {agent.status}")
print(f"expression_profile: {agent.expression_profile}")
print(f"capabilities: {agent.capabilities}")
print(f"\n✅ 听澜配置已更新到数据库")

db.close()
