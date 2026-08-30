"""SubAgentService — 子代理（角色模板）调度服务

职责：
  1. 查角色模板定义（Agent 表，is_sub_agent=True）
  2. 构建隔离 AgentContext（新身份 + 窄工具集 + 仅任务描述，不放主会话历史）
  3. 调用 AgentRuntime.run() 执行子任务
  4. 只返回结果摘要，中间过程不注入主窗口

上下文隔离（核心价值）：
  - 子代理的 history 只包含 [system_prompt, task_description]
  - 子代理内部多轮工具调用只存在于自己的 AgentRun 中
  - 结束后只产出 content 摘要返回给主 Agent
  - 主窗口 token 不被撑爆

角色模板语义（Phase Orchestration 统一后）：
  - 模板定义持久化于 agents 表（is_sub_agent=True），前端可管理（编辑/新建）
  - 每次委派/编排按模板 spawn 全新隔离实例，执行完即弃、不保留状态
  - identity_override / allowed_tools_override 保留为兜底参数（内存角色回退）

安全：
  - 子代理继承主会话 project_path / 权限模式
  - 工具集被 allowed_tools 收窄
  - 高风险工具走同一审批链（不豁免）
  - 无项目绑定时不注入项目专有工具
"""

from typing import Optional

from app.core.database import SessionLocal
from app.models.agent import Agent, Setting
from app.core.agent_runtime import AgentRuntime, AgentContext, AgentResult
from app.core.agent_runtime.context_builder import get_default_model
from app.services.model import Message as ModelMessage


class SubAgentError(Exception):
    """子代理调度异常"""
    pass


# ──── T10: 任务图 × 子代理委托 ────
# 灰度开关：settings 表 key，缺失/值非法时默认关闭（默认串行 + 主循环节点执行，行为与现状一致）。
_TASK_GRAPH_SUBAGENT_SETTING_KEY = "task_graph_subagent_enabled"


def is_task_graph_subagent_enabled() -> bool:
    """读取 task_graph_subagent_enabled 开关（默认关，灰度开）。

    开启后：TaskGraph 就绪节点 assigned_agent 指向 is_sub_agent 子代理时委托
    run_sub_agent 执行（独立上下文、只带任务文本），无依赖的就绪可委托节点
    asyncio.gather 并行分派（并发上限复用编排 MAX_CONCURRENCY）。
    回滚路径：settings 中删除该 key 或置 false/0/off/no 即恢复现状串行路径，
    无需回滚代码。
    """
    try:
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == _TASK_GRAPH_SUBAGENT_SETTING_KEY).first()
        finally:
            db.close()
        if row is None or row.value is None:
            return False
        return str(row.value).strip().lower() in ("1", "true", "on", "yes")
    except Exception:  # noqa: BLE001 — DB 不可用时按默认关闭处理
        return False


def is_sub_agent_id(agent_key: str) -> bool:
    """判断 agent_id 是否指向 is_sub_agent 标记的子代理（T10 任务图委托判定）。

    Args:
        agent_key: TaskNode.assigned_agent 的值（如 sub_code_reviewer）

    Returns:
        bool: 该 key 对应 agents 表中 is_sub_agent=True 的记录时为 True；
              key 为空 / 记录不存在 / DB 不可用时一律 False（不可委托）。
    """
    if not agent_key:
        return False
    try:
        db = SessionLocal()
        try:
            agent = db.query(Agent).filter(Agent.agent_id == agent_key).first()
        finally:
            db.close()
        return bool(agent and agent.is_sub_agent)
    except Exception:  # noqa: BLE001 — DB 不可用时按不可委托处理
        return False



def _get_tool_definitions(allowed_tools: list) -> list:
    """从允许的工具名列表获取 OpenAI Function Calling 定义。
    
    使用 ToolSelector 的 _def_map 避免重复导入。
    """
    from app.core.search_tools import SEARCH_TOOLS_DEFINITIONS
    from app.core.tools import FILE_TOOLS_DEFINITIONS
    from app.core.git_tools import GIT_TOOLS_DEFINITIONS
    from app.core.command_tools import COMMAND_TOOLS_DEFINITIONS
    from app.core.spec_check_tools import SPEC_CHECK_TOOLS_DEFINITIONS
    from app.services.tools import tool_registry

    def_map = {}
    for t in COMMAND_TOOLS_DEFINITIONS:
        def_map[t["function"]["name"]] = t
    for t in FILE_TOOLS_DEFINITIONS:
        def_map[t["function"]["name"]] = t
    for t in GIT_TOOLS_DEFINITIONS:
        def_map[t["function"]["name"]] = t
    for t in SEARCH_TOOLS_DEFINITIONS:
        def_map[t["function"]["name"]] = t
    for t in SPEC_CHECK_TOOLS_DEFINITIONS:
        def_map[t["function"]["name"]] = t
    for t in tool_registry.get_definitions():
        def_map[t["function"]["name"]] = t

    return [def_map[name] for name in allowed_tools if name in def_map]


async def run_sub_agent(
    sub_agent_id: str,
    task: str,
    *,
    chat_id: Optional[int] = None,
    project_path: Optional[str] = None,
    model_id: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    max_tool_rounds: Optional[int] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    identity_override: Optional[str] = None,
    allowed_tools_override: Optional[list] = None,
) -> str:
    """执行子代理任务。

    Args:
        sub_agent_id: 子代理的 agent_id（如 sub_code_reviewer）
        task: 子任务描述文本（不含完整历史）
        chat_id: 主会话 chat_id（可选，用于审计）
        project_path: 工作目录（继承自主会话）
        model_id: 模型 ID（默认使用系统默认模型）
        reasoning_effort: 推理强度
        max_tool_rounds: 最大工具轮次
        temperature: 温度
        max_tokens: 最大 token 数
        identity_override: 动态角色身份模板（编排用）。非空时不再校验 agents 表
            的 is_sub_agent，直接以该身份构建隔离上下文（支持任意角色 spawn）。
        allowed_tools_override: 动态角色工具白名单（编排用）。与 identity_override
            同时使用；为空时按 agents 表 allowed_tools 解析。

    Returns:
        子代理执行结果摘要文本

    Raises:
        SubAgentError: 子代理不存在/未标记为子代理/执行失败
    """
    db = SessionLocal()
    try:
        # 1. 查子代理定义（identity_override 时跳过，支持动态角色 spawn）
        dynamic_role = bool(identity_override)
        agent = None
        if not dynamic_role:
            agent = db.query(Agent).filter(Agent.agent_id == sub_agent_id).first()
            if not agent:
                raise SubAgentError(f"子代理 {sub_agent_id} 不存在")
            if not agent.is_sub_agent:
                raise SubAgentError(f"Agent {sub_agent_id} 未标记为子代理")

        # 2. 构建工具定义（动态角色用 override 白名单）
        if dynamic_role:
            allowed = allowed_tools_override or []
        else:
            allowed = agent.allowed_tools or []
        tool_defs = _get_tool_definitions(allowed) if allowed else []

        # 2.5 动态角色时解析身份与能力
        if dynamic_role:
            effective_agent_id = sub_agent_id
            effective_identity = identity_override
            effective_capabilities: list = []
        else:
            effective_agent_id = agent.agent_id
            effective_identity = agent.identity or agent.system_prompt or ""
            effective_capabilities = agent.capabilities or []

        # 3. 构建隔离 AgentContext
        effective_model = model_id or get_default_model()
        context = AgentContext(
            agent_id=effective_agent_id,
            agent_identity=effective_identity,
            personality_level=None,  # 子代理不注入人格
            model_id=effective_model,
            chat_id=chat_id,
            project_path=project_path,
            project_id=None,
            # ctx 透传给工具执行：子代理内部工具（如 delegate 传参、文件工具）需要这些键
            memory_context={"chat_id": chat_id, "project_path": project_path},
            memory_text=None,         # 上下文隔离
            knowledge_context=None,
            tools=tool_defs if tool_defs else None,
            decision=None,
            capabilities=effective_capabilities,
            personality=None,
            project_context=None,
            vision_context=None,
            history=None,             # 不注入完整历史
            metadata={
                "mode": "build",
                "use_tools": len(tool_defs) > 0,
            },
            plan=None,
            max_tool_rounds=max_tool_rounds or 5,
            completion_verification=False,
        )

        # 4. 构造 messages（仅 system + user；AgentRuntime.run 期望 ModelMessage 对象）
        system_content = effective_identity
        messages = [
            ModelMessage(role="system", content=system_content),
            ModelMessage(role="user", content=task),
        ]

        # 5. 执行（AgentRuntime 默认 PassthroughContextBuilder，不额外组装上下文）
        runtime = AgentRuntime()

        result: AgentResult = await runtime.run(
            context=context,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            read_only=False,
        )

        # 6. 返回摘要
        content = result.content or ""
        if not content:
            content = "[子代理执行完成，无返回内容]"
        return content

    except SubAgentError:
        raise
    except Exception as e:
        raise SubAgentError(f"子代理执行异常: {e}") from e
    finally:
        db.close()