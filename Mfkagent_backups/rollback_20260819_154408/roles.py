"""Orchestration 角色目录 — 角色模板统一加载。

每个角色 = 身份模板 + 建议工具 + 展示名。
模板来源（统一）：
  - 持久化层：`agents` 表 is_sub_agent=True 的内置模板（seed_agents 中 sub_* 项），
    用户可通过子代理管理面板（SubAgentPanel）编辑，前端可管理；
  - 兜底层：本模块内存内置定义（ORCHESTRATION_ROLES），当 DB 无对应模板时回退，
    保证离线/未 seed 场景编排仍可用。

get_orchestration_role 规则：DB 优先（经 ROLE_TO_TEMPLATE_ID 映射到 agent_id），
未命中回退内存内置定义。

角色工具白名单（allowed_tools）：
  - 只读/搜索/网络类工具为主；写操作走统一审批链（与主 Agent 相同）。
  - 后端/前端实现类角色额外开放写文件与命令执行（构建/运行验证闭环所需）。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class OrchestrationRole:
    """编排角色定义。"""

    role_id: str
    name: str
    description: str
    identity_template: str                 # 身份模板（{task} 由 runner 填充到 user 消息）
    suggested_tools: List[str] = field(default_factory=list)
    max_tokens: int = 4096


# 只读研究/审查类工具（默认安全子集）
_READ_ONLY_TOOLS = ["read_file", "list_files", "find_files", "search_files",
                    "git_status", "git_diff", "git_log",
                    "web_search", "fetch_url", "get_datetime"]
# 实现类工具（写文件 + 命令执行，走审批链）
_IMPLEMENT_TOOLS = _READ_ONLY_TOOLS + ["write_file", "run_command", "git_commit", "git_restore", "verify_spec"]

# 每个子任务最大 token（防止并行撑爆上下文）
DEFAULT_SUB_AGENT_MAX_TOKENS = 4096

ORCHESTRATION_ROLES: Dict[str, OrchestrationRole] = {}

# 角色 → agents 表内置模板 agent_id 映射（模板持久化于 agents 表，is_sub_agent=True）。
# DB 有对应模板时优先加载；缺失时回退内存定义。
ROLE_TO_TEMPLATE_ID: Dict[str, str] = {
    "architecture": "sub_architecture",
    "backend": "sub_backend",
    "frontend": "sub_frontend",
    "testing": "sub_testing",
    "security": "sub_security",
    "researcher": "sub_researcher",
    "code_reviewer": "sub_code_reviewer",
}


def _register(role: OrchestrationRole) -> None:
    ORCHESTRATION_ROLES[role.role_id] = role


_register(OrchestrationRole(
    role_id="architecture",
    name="架构师",
    description="负责整体架构设计、技术选型、模块划分与接口契约",
    identity_template=(
        "你是资深系统架构师子代理。\n"
        "职责：分析任务需求，输出架构设计：技术选型、模块划分、数据模型、接口契约、边界与依赖。\n"
        "只读原则：不修改任何文件，不执行命令，只产出架构决策。\n"
        "输出格式：按「总体架构 → 模块划分 → 数据模型/接口契约 → 关键技术决策 → 风险与权衡」组织，结论前置。"
    ),
    suggested_tools=_READ_ONLY_TOOLS,
))


_register(OrchestrationRole(
    role_id="backend",
    name="后端工程师",
    description="负责后端接口、数据模型与业务逻辑实现",
    identity_template=(
        "你是资深后端工程师子代理。\n"
        "职责：实现或分析后端服务，关注接口契约、错误处理、性能与安全，交付可运行实现。\n"
        "工作方式：先阅读现有代码理解上下文，再最小范围实现；写文件/执行命令需走审批链。\n"
        "输出格式：按「变更清单 → 关键实现要点 → 验证结果 → 风险说明」组织。"
    ),
    suggested_tools=_IMPLEMENT_TOOLS,
))


_register(OrchestrationRole(
    role_id="frontend",
    name="前端工程师",
    description="负责前端界面实现、组件设计与交互逻辑",
    identity_template=(
        "你是资深前端工程师子代理。\n"
        "职责：实现或分析前端功能（React/TypeScript），关注组件职责、数据流、视觉一致与可维护性。\n"
        "工作方式：先阅读现有代码理解上下文，再最小范围实现；写文件需走审批链。\n"
        "输出格式：按「变更清单 → 关键实现要点 → 验证结果 → 风险说明」组织。"
    ),
    suggested_tools=_IMPLEMENT_TOOLS,
))


_register(OrchestrationRole(
    role_id="testing",
    name="测试工程师",
    description="负责测试设计、用例编写与回归验证",
    identity_template=(
        "你是资深测试工程师子代理。\n"
        "职责：分析待测模块，设计并执行测试（单元/集成/回归），报告覆盖与风险。\n"
        "工作方式：先了解被测代码与现有测试基建，再设计用例；执行命令需走审批链。\n"
        "输出格式：按「测试范围 → 用例清单 → 执行结果 → 遗留风险」组织。"
    ),
    suggested_tools=_IMPLEMENT_TOOLS,
))


_register(OrchestrationRole(
    role_id="security",
    name="安全审计师",
    description="负责安全审计、漏洞排查与风险缓解建议",
    identity_template=(
        "你是资深安全审计师子代理。\n"
        "职责：审查目标代码/配置/流程，识别安全风险（注入、越权、密钥泄露、依赖漏洞等），给出缓解建议。\n"
        "只读原则：不修改任何文件，不执行有副作用命令，只产出审计结论。\n"
        "输出格式：按「风险列表（严重程度排序）→ 位置 → 缓解建议 → 结论」组织。"
    ),
    suggested_tools=_READ_ONLY_TOOLS,
))


_register(OrchestrationRole(
    role_id="researcher",
    name="调研员",
    description="负责联网调研、资料搜集与结构化总结",
    identity_template=(
        "你是资深调研员子代理。\n"
        "职责：针对调研主题联网搜集资料，交叉验证来源，整理为结构化结论。\n"
        "只读原则：不修改文件、不执行命令。\n"
        "输出格式：按「结论摘要 → 分点要点 → 来源列表」组织，区分事实与推测。"
    ),
    suggested_tools=["web_search", "fetch_url", "get_datetime"],
))


_register(OrchestrationRole(
    role_id="code_reviewer",
    name="代码审查员",
    description="负责只读代码审查、风险发现与改进建议",
    identity_template=(
        "你是资深代码审查员子代理。\n"
        "职责：只读审查代码，找出潜在 Bug、性能问题、安全隐患与可维护性改进点。\n"
        "只读原则：绝不修改文件、不执行命令。\n"
        "输出格式：按「发现的问题 → 严重程度 → 位置 → 建议」组织，最后给结论摘要。"
    ),
    suggested_tools=_READ_ONLY_TOOLS,
))


def get_orchestration_role(role_id: str) -> Optional[OrchestrationRole]:
    """按 role_id 获取角色定义；DB 模板优先，内存定义兜底。不存在返回 None。"""
    role = ORCHESTRATION_ROLES.get(role_id)
    template_id = ROLE_TO_TEMPLATE_ID.get(role_id)
    if not template_id:
        return role

    # DB 优先：agents 表内置模板（is_sub_agent=True）
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Agent

        db = SessionLocal()
        try:
            agent = (
                db.query(Agent)
                .filter(Agent.agent_id == template_id, Agent.is_sub_agent.is_(True))
                .first()
            )
            if agent:
                name = agent.name or (role.name if role else role_id)
                desc = agent.description or (role.description if role else "")
                identity = agent.identity or (role.identity_template if role else "")
                tools = agent.allowed_tools or (role.suggested_tools if role else [])
                return OrchestrationRole(
                    role_id=role_id,
                    name=name,
                    description=desc,
                    identity_template=identity,
                    suggested_tools=tools,
                    max_tokens=role.max_tokens if role else DEFAULT_SUB_AGENT_MAX_TOKENS,
                )
        finally:
            db.close()
    except Exception:  # noqa: BLE001 — DB 异常不阻断编排（回退内存定义）
        pass

    return role


def list_orchestration_roles() -> List[OrchestrationRole]:
    """列出全部角色定义（按注册顺序）。"""
    return list(ORCHESTRATION_ROLES.values())


def role_ids() -> List[str]:
    return list(ORCHESTRATION_ROLES.keys())