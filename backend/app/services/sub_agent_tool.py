"""DelegateSubAgentTool — 角色模板委派工具

主 Agent 在执行循环中通过本工具将子任务委派给指定角色模板（子代理）：
  - 角色模板持久化在 agents 表（is_sub_agent=True，内置 + 用户自定义，前端可管理）
  - 每次委派按模板 spawn 全新隔离实例执行（上下文隔离），执行完即弃、不保留状态
  - 只返回结果摘要给主 Agent
  - 继承主会话的 project_path（经 ctx 传入）

工具名：delegate_sub_agent
参数：
  - sub_agent_id: 角色模板 id（如 sub_code_reviewer / sub_researcher / sub_architecture / sub_backend）
  - task: 子任务描述文本（尽量自包含，子代理无法看到主会话历史）
  - max_tokens / max_tool_rounds / reasoning_effort: 可选执行参数（大文件重写等场景建议调高）
"""

from app.services.tools import Tool, ToolResult


class DelegateSubAgentTool(Tool):
    def __init__(self):
        super().__init__(
            name="delegate_sub_agent",
            description=(
                "将子任务委派给一个专门化角色模板（子代理）执行，返回其结论摘要。"
                "适用于：代码审查、网络调研、文件/项目结构分析、架构设计、安全审计等有边界的子任务。"
                "注意：子代理看不到当前对话的完整历史，任务描述必须自包含、明确。"
                "子代理只返回摘要，你需根据摘要继续推进主任务。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "sub_agent_id": {
                        "type": "string",
                        "description": "角色模板 ID（如 sub_code_reviewer / sub_researcher / sub_file_analyst / sub_architecture / sub_backend / sub_frontend / sub_testing / sub_security）",
                    },
                    "task": {
                        "type": "string",
                        "description": "自包含的子任务描述：背景 + 目标 + 期望输出格式",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "可选，子代理单次回复最大 token 数（大文件重写建议调高到 8192+，默认 4096）",
                    },
                    "max_tool_rounds": {
                        "type": "integer",
                        "description": "可选，最大工具调用轮次（默认 5）",
                    },
                    "reasoning_effort": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "可选，推理强度（大文件任务建议 low/medium 以节省耗时）",
                    },
                },
                "required": ["sub_agent_id", "task"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        from app.services.sub_agent import run_sub_agent, SubAgentError

        sub_agent_id = str(kwargs.get("sub_agent_id", "") or "").strip()
        task = str(kwargs.get("task", "") or "").strip()

        # ctx 透传：chat_id / project_path 由 AgentRuntime 的 memory_context 提供
        chat_id = kwargs.get("chat_id")
        project_path = kwargs.get("project_path")

        if not sub_agent_id:
            return ToolResult(success=False, output="", error="参数 sub_agent_id 不能为空")
        if not task:
            return ToolResult(success=False, output="", error="参数 task 不能为空")

        try:
            call_kwargs = {
                "sub_agent_id": sub_agent_id,
                "task": task,
                "chat_id": chat_id if isinstance(chat_id, int) else None,
                "project_path": project_path or None,
            }
            if kwargs.get("max_tokens"):
                call_kwargs["max_tokens"] = int(kwargs["max_tokens"])
            if kwargs.get("max_tool_rounds"):
                call_kwargs["max_tool_rounds"] = int(kwargs["max_tool_rounds"])
            if kwargs.get("reasoning_effort"):
                call_kwargs["reasoning_effort"] = kwargs["reasoning_effort"]
            summary = await run_sub_agent(**call_kwargs)
            return ToolResult(success=True, output=summary)
        except SubAgentError as e:
            return ToolResult(success=False, output="", error=str(e))