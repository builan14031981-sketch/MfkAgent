from app.core.database import SessionLocal, engine, Base
from app.models.agent import Agent

PRESET_AGENTS = [
    {
        "agent_id": "general",
        "name": "通用助手",
        "description": "日常交流、信息整理和问题解答",
        "avatar": "🤖",
        "identity": "你是一名通用AI助手，负责日常交流、信息整理和问题解答。你可以处理各类常见请求，提供准确、有用的信息。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search"],
    },
    {
        "agent_id": "analyst",
        "name": "分析师",
        "description": "决策审查、逻辑分析和风险评估",
        "avatar": "🔍",
        "identity": "你是一名专业分析师。负责审查决策、检查逻辑、发现风险、挑战假设。你需要关注事实准确性和论证严密性。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search", "fetch_url", "read_file"],
    },
    {
        "agent_id": "coder",
        "name": "码农",
        "description": "软件开发辅助、代码审查和技术架构",
        "avatar": "💻",
        "identity": "你是一名专业软件工程师。你需要关注代码质量、架构合理性和长期维护成本。回答时优先给出代码示例，再提供解释。",
        "model": "mimo-v2.5-pro",
        "capabilities": [
            "web_search",
            "read_file",
            "write_file",
            "list_directory",
            "execute_code",
            "format_json",
        ],
    },
    {
        "agent_id": "writer",
        "name": "笔神",
        "description": "写作创作、文字表达和内容优化",
        "avatar": "✍️",
        "identity": "你是一名专业写作助手。帮助用户提升文字表达力和创作质量，提供结构建议、修辞优化和内容策划。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search", "read_file"],
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
                existing.identity = agent_data["identity"]
                existing.capabilities = agent_data["capabilities"]
                existing.model = agent_data["model"]
                print(f"Updated agent: {agent_data['name']}")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
