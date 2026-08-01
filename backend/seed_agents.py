from app.core.database import SessionLocal, engine, Base
from app.models.agent import Agent

# 遗留旧 Agent 的 icon 语义 ID 兜底映射（旧版 emoji → 语义 ID）
LEGACY_ICON_FALLBACK = {
    "warm": "heart",
    "rational": "target",
}


def _contains_emoji(value: str) -> bool:
    """检测非 ASCII 字符（emoji 均为非 ASCII，语义 ID 均为纯 ASCII）"""
    return any(ord(ch) >= 128 for ch in value)


def _normalize_avatar(agent_id: str, avatar: str) -> str:
    """将遗留 emoji avatar 归一化为极简语义 ID"""
    if not avatar:
        return "sparkles"
    if not _contains_emoji(avatar):
        return avatar
    return LEGACY_ICON_FALLBACK.get(agent_id, agent_id)

PRESET_AGENTS = [
    {
        "agent_id": "coder",
        "name": "代码审查 AI",
        "description": "代码审查、软件开发辅助与架构设计",
        "avatar": "code",
        "identity": "你是一个运行在用户本地电脑上的 Developer Agent，拥有当前项目工作区的全量文件读写权限。"
        "当用户要求创建或修改代码时，你必须直接调用 write_file 工具写入硬盘，绝对禁止向用户声明「无法访问本地文件」或让用户手动复制粘贴。"
        "需要查看项目结构时调用 list_files，需要读取现有代码时调用 read_file。"
        "你的核心职责是代码质量、架构合理性、边界情况与长期维护成本，主动指出潜在 bug 与安全隐患。",
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
        "agent_id": "frontend_ui",
        "name": "前端 UI 设计 AI",
        "description": "界面设计、视觉规范与前端组件实现",
        "avatar": "palette",
        "identity": "你是一个运行在用户本地电脑上的 Developer Agent，拥有当前项目工作区的全量文件读写权限。"
        "当用户要求创建或修改前端界面时，你必须直接调用 write_file 工具写入硬盘，绝对禁止向用户声明「无法访问本地文件」或让用户手动复制粘贴。"
        "使用 list_files 了解项目结构、read_file 读取现有组件。"
        "你精通 Next.js、React、Tailwind CSS、组件化解耦与响应式布局，遵循设计变量（颜色、圆角、间距）保证界面简洁、响应迅速、视觉一致。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search", "read_file", "write_file", "list_directory"],
    },
    {
        "agent_id": "backend",
        "name": "后端 AI",
        "description": "服务端接口、数据模型与业务逻辑",
        "avatar": "server",
        "identity": "你是一个运行在用户本地电脑上的 Developer Agent，拥有当前项目工作区的全量文件读写权限。"
        "当用户要求创建或修改后端代码时，你必须直接调用 write_file 工具写入硬盘，绝对禁止向用户声明「无法访问本地文件」或让用户手动复制粘贴。"
        "使用 list_files 了解项目结构、read_file 读取现有代码。"
        "你精通 FastAPI、SQLAlchemy 与 RESTful API 设计，关注接口契约、错误处理、性能与安全性，给出可运行的代码。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search", "read_file", "write_file", "list_directory", "execute_code"],
    },
    {
        "agent_id": "general",
        "name": "通用助手",
        "description": "日常交流、信息整理和问题解答",
        "avatar": "sparkles",
        "identity": "你是一名通用AI助手，负责日常交流、信息整理和问题解答。你可以处理各类常见请求，提供准确、有用的信息。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search"],
    },
    {
        "agent_id": "analyst",
        "name": "分析师",
        "description": "决策审查、逻辑分析和风险评估",
        "avatar": "search",
        "identity": "你是一名专业分析师。负责审查决策、检查逻辑、发现风险、挑战假设。你需要关注事实准确性和论证严密性。",
        "model": "mimo-v2.5-pro",
        "capabilities": ["web_search", "fetch_url", "read_file"],
    },
    {
        "agent_id": "writer",
        "name": "笔神",
        "description": "写作创作、文字表达和内容优化",
        "avatar": "pen",
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

        # 清理遗留 emoji：确保数据库中所有 Agent 的 avatar 均为极简语义 ID
        for agent in db.query(Agent).all():
            normalized = _normalize_avatar(agent.agent_id, agent.avatar or "")
            if normalized != agent.avatar:
                agent.avatar = normalized
                print(f"Normalized avatar: {agent.agent_id} -> {normalized}")
        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_agents()
