"""DelegateSubAgentTool — 子代理委派工具

主 Agent 在执行循环中通过本工具将子任务委派给指定子代理：
  - 子代理在独立上下文执行（上下文隔离）
  - 只返回结果摘要给主 Agent
  - 继承主会话的 project_path（经 ctx 传入）

工具名：delegate_sub_agent
参数：
  - sub_agent_id: 子代理的 agent_id（如 sub_code_reviewer / sub_researcher / sub_file_analyst）
  - task: 子任务描述文本（尽量自包含，子代理无法看到主会话历史）
"""

from app.services.tools import Tool, ToolResult


class DelegateSubAgentTool(Tool):
    def __init__(self):
        super().__init__(
            name="delegate_sub_agent",
            description=(
                "将子任务委派给一个专门化子代理执行，返回其结论摘要。"
                "适用于：代码审查、网络调研、文件/项目结构分析等有边界的子任务。"
                "注意：子代理看不到当前对话的完整历史，任务描述必须自包含、明确。"
                "子代理只返回摘要，你需根据摘要继续推进主任务。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "sub_agent_id": {
                        "type": "string",
                        "description": "子代理 ID（如 sub_code_reviewer / sub_researcher / sub_file_analyst）",
                    },
                    "task": {
                        "type": "string",
                        "description": "自包含的子任务描述：背景 + 目标 + 期望输出格式",
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
            summary = await run_sub_agent(
                sub_agent_id=sub_agent_id,
                task=task,
                chat_id=chat_id if isinstance(chat_id, int) else None,
                project_path=project_path or None,
            )
            return ToolResult(success=True, output=summary)
        except SubAgentError as e:
            return ToolResult(success=False, output="", error=str(e))