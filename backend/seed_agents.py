from app.core.database import SessionLocal, engine, Base
from app.models.agent import Agent

PRESET_AGENTS = [
    {
        "agent_id": "warm",
        "name": "小暖",
        "description": "情感理解型助手",
        "avatar": "🌸",
        "system_prompt": "你是一名温暖的AI伙伴。你的目标不是立即解决问题，而是在理解用户情绪和需求后，提供陪伴和帮助。",
        "model": "mimo-v2.5-pro",
        "temperature": 70,
    },
    {
        "agent_id": "rational",
        "name": "锐",
        "description": "理性决策型助手",
        "avatar": "⚔️",
        "system_prompt": "你是一名严格的决策分析者。你的职责是发现问题、分析风险、指出逻辑漏洞。",
        "model": "mimo-v2.5-pro",
        "temperature": 50,
    },
    {
        "agent_id": "coder",
        "name": "码农",
        "description": "编程开发助手",
        "avatar": "💻",
        "system_prompt": "你是一名专业软件工程师。你需要关注：代码质量、架构合理性、长期维护成本。回答时优先给出代码，再解释。",
        "model": "mimo-v2.5-pro",
        "temperature": 30,
    },
    {
        "agent_id": "writer",
        "name": "笔神",
        "description": "写作创作助手",
        "avatar": "✍️",
        "system_prompt": "你是一名专业写作助手。你的目标是帮助用户提升文字表达力和创作质量。",
        "model": "mimo-v2.5-pro",
        "temperature": 80,
    },
]


def seed_agents():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for agent_data in PRESET_AGENTS:
            existing = db.query(Agent).filter(Agent.agent_id == agent_data["agent_id"]).first()
            if not existing:
                db.add(Agent(**agent_data))
                print(f"Created agent: {agent_data['name']}")
            else:
                existing.name = agent_data["name"]
                existing.description = agent_data["description"]
                existing.avatar = agent_data["avatar"]
                existing.system_prompt = agent_data["system_prompt"]
                existing.model = agent_data["model"]
                existing.temperature = agent_data["temperature"]
                print(f"Updated agent: {agent_data['name']}")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
