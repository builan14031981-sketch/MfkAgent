"""Agent Context — 独立 Context 系统模块（Phase E3 正式化）。

目标架构：
  AgentRuntime → ContextBuilder → AgentContext → ModelService

AgentContext 是 Agent 执行所需的统一上下文载体，字段按模块职责组织：
  - identity           Agent 身份（== agent_identity，来自 Agent.identity）
  - capabilities       能力标签（来自 Agent.capabilities）
  - personality        人格 Prompt 文本（personality service）
  - project_context    项目/工作目录上下文（Project / Workspace）
  - memory_context     记忆上下文（现有逻辑）
  - vision_context     视觉上下文（预留，当前 None）
  - history            历史消息（当前全量加载；未来 token budget / compression / window）
  - tools              工具目录
  - metadata           元数据

注意：
  - Vision / Multi-Agent 字段当前预留为空，仅占位，不实现。
  - task_context 已由 Planner V1（app/core/planner，Phase G1）注入；非任务型请求保持 None。
  - 本阶段不涉及 Memory 重构 / Token 压缩 / 自动任务树。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentContext:
    """Agent 执行所需的统一上下文（Phase E3 正式化结构）。

    agent_identity 为存储字段（保持向后兼容），identity 为只读别名。
    """

    agent_id: str
    agent_identity: str
    personality_level: Optional[int]
    model_id: str
    chat_id: Optional[int] = None
    project_id: Optional[int] = None
    project_path: Optional[str] = None
    memory_context: Optional[dict] = None
    memory_text: Optional[str] = None
    knowledge_context: Optional[dict] = None
    tools: Optional[list] = None
    decision: Optional[dict] = None  # Phase 2: tool_runtime decision

    # ──── Phase E3：结构化上下文（ContextBuilder 正式化）────
    capabilities: Optional[list] = None       # 能力标签（Agent.capabilities）
    personality: Optional[str] = None         # 人格 Prompt 文本
    project_context: Optional[dict] = None    # 项目/工作目录上下文
    vision_context: Optional[dict] = None     # 预留：Vision 输入（当前 None）
    history: Optional[list] = None            # 历史消息（[{"role","content"}, ...]）
    metadata: Optional[dict] = None           # 元数据（mode/use_tools 等）

    # ──── Phase E7-2：任务上下文（Planner 预留）────
    # V1 结构（勿过度设计复杂 TaskGraph，未来由 Planner 注入）：
    #   {
    #     "goal": "优化Python项目性能",
    #     "constraints": ["不能修改数据库结构"],
    #     "current_step": "分析代码",
    #   }
    task_context: Optional[dict] = None

    # ──── Phase G2-B：Planner 层级控制 ────
    planning_level: Optional[int] = None

    # ──── G4-B: TaskGraph 原始 Plan（供 AgentRuntime init_task_graph）────
    plan: Optional[object] = None  # Plan 对象或 None

    # ──── Phase 11: 工具轮次配置 ────
    max_tool_rounds: Optional[int] = None

    # ──── Phase 12: 自治模式 ────
    auto_approve: bool = False

    @property
    def identity(self) -> str:
        """结构化别名：identity == agent_identity（来自 Agent.identity）。"""
        return self.agent_identity


@dataclass
class AgentResult:
    """Agent 执行结果。"""

    content: str
    usage: Optional[dict] = None
    rounds: int = 1
    finish_reason: str = "stop"
    tool_calls: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
