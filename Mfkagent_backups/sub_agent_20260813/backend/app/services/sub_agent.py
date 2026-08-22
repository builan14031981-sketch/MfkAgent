"""SubAgentService — 子代理调度服务

职责：
  1. 查子代理定义（Agent 表，is_sub_agent=True）
  2. 构建隔离 AgentContext（新身份 + 窄工具集 + 仅任务描述，不放主会话历史）
  3. 调用 AgentRuntime.run() 执行子任务
  4. 只返回结果摘要，中间过程不注入主窗口

上下文隔离（核心价值）：
  - 子代理的 history 只包含 [system_prompt, task_description]
  - 子代理内部多轮工具调用只存在于自己的 AgentRun 中
  - 结束后只产出 content 摘要返回给主 Agent
  - 主窗口 token 不被撑爆

安全：
  - 子代理继承主会话 project_path / 权限模式
  - 工具集被 allowed_tools 收窄
  - 高风险工具走同一审批链（不豁免）
  - 无项目绑定时不注入项目专有工具
"""

from typing import Optional

from app.core.database import SessionLocal
from app.models.agent import Agent
from app.core.agent_runtime import AgentRuntime, AgentContext, AgentResult
from app.core.agent_runtime.context_builder import get_default_model


class SubAgentError(Exception):
    """子代理调度异常"""
    pass


def _get_tool_definitions(allowed_tools: list) -> list:
    """从允许的工具名列表获取 OpenAI Function Calling 定义。
    
    使用 ToolSelector 的 _def_map 避免重复导入。
    """
    from app.core.search_tools import SEARCH_TOOLS_DEFINITIONS
    from app.core.tools import FILE_TOOLS_DEFINITIONS
    from app.core.git_tools import GIT_TOOLS_DEFINITIONS
    from app.core.command_tools import COMMAND_TOOLS_DEFINITIONS
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

    Returns:
        子代理执行结果摘要文本

    Raises:
        SubAgentError: 子代理不存在/未标记为子代理/执行失败
    """
    db = SessionLocal()
    try:
        # 1. 查子代理定义
        agent = db.query(Agent).filter(Agent.agent_id == sub_agent_id).first()
        if not agent:
            raise SubAgentError(f"子代理 {sub_agent_id} 不存在")
        if not agent.is_sub_agent:
            raise SubAgentError(f"Agent {sub_agent_id} 未标记为子代理")

        # 2. 构建工具定义
        allowed = agent.allowed_tools or []
        tool_defs = _get_tool_definitions(allowed) if allowed else []

        # 3. 构建隔离 AgentContext
        effective_model = model_id or get_default_model()
        context = AgentContext(
            agent_id=agent.agent_id,
            agent_identity=agent.identity or agent.system_prompt or "",
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
            capabilities=agent.capabilities or [],
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

        # 4. 构造 messages（仅 system + user）
        system_content = agent.identity or agent.system_prompt or ""
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": task},
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