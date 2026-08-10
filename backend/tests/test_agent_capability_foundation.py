"""Agent Capability Foundation Integration V1 — 完整测试套件

Phase 3.5 Finalization 测试覆盖：
  Test A: 普通聊天 → 不加载工具、不创建任务、不搜索
  Test B: General Agent 执行 → 工具正常出现、Strategy Layer 生效、Verification Loop 生效
  Test C: Coding Agent → Prompt 人格正确、工具能力正常
  Test D: 新增 Agent → 自动拥有基础能力、工具能力、验证能力

测试方式：纯单元测试（mock 外部依赖），无需真实 API 调用。
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ──────────────────────────────────────────────────────────────────────
# Test A: 普通聊天检测
# ──────────────────────────────────────────────────────────────────────


class TestCasualChatDetection:
    """验证 _is_casual_chat 正确区分聊天与任务请求。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from app.core.agent_runtime.context_builder import _is_casual_chat
        self._is_casual_chat = _is_casual_chat

    def test_chat_greeting_hello(self):
        """"你好" → 普通聊天"""
        assert self._is_casual_chat("你好") is True

    def test_chat_greeting_hi(self):
        """"hi" → 普通聊天"""
        assert self._is_casual_chat("hi") is True

    def test_chat_greeting_bye(self):
        """"再见" → 普通聊天"""
        assert self._is_casual_chat("再见") is True

    def test_chat_greeting_thanks(self):
        """"谢谢" → 普通聊天"""
        assert self._is_casual_chat("谢谢") is True

    def test_chat_small_talk_how_are_you(self):
        """"今天怎么样" → 普通聊天"""
        assert self._is_casual_chat("今天怎么样") is True

    def test_chat_small_talk_who_are_you(self):
        """"你是谁" → 普通聊天"""
        assert self._is_casual_chat("你是谁") is True

    def test_chat_knowledge_what_is(self):
        """"什么是微服务" → 普通聊天（知识性问题）"""
        assert self._is_casual_chat("什么是微服务") is True

    def test_chat_knowledge_explain(self):
        """"解释一下闭包的原理" → 普通聊天"""
        assert self._is_casual_chat("解释一下闭包的原理") is True

    def test_chat_knowledge_why(self):
        """"为什么需要异步编程" → 普通聊天"""
        assert self._is_casual_chat("为什么需要异步编程") is True

    def test_task_action_help_me(self):
        """"帮我修改文件" → 任务执行"""
        assert self._is_casual_chat("帮我修改文件") is False

    def test_task_action_analyze(self):
        """"分析一下这个问题" → 任务执行"""
        assert self._is_casual_chat("分析一下这个问题") is False

    def test_task_action_create(self):
        """"创建一个新文件" → 任务执行"""
        assert self._is_casual_chat("创建一个新文件") is False

    def test_task_action_fix(self):
        """"修复这个 Bug" → 任务执行"""
        assert self._is_casual_chat("修复这个 Bug") is False

    def test_task_action_check(self):
        """"检查项目状态" → 任务执行"""
        assert self._is_casual_chat("检查项目状态") is False

    def test_task_action_git(self):
        """"git status" → 任务执行"""
        assert self._is_casual_chat("git status") is False

    def test_default_unknown(self):
        """普通未知消息 → 默认走工具加载路径（保守策略）"""
        assert self._is_casual_chat("今天天气不错") is False

    def test_edge_case_empty(self):
        """空字符串 → 默认走工具路径"""
        assert self._is_casual_chat("") is False


# ──────────────────────────────────────────────────────────────────────
# Test B: Agent Base Instruction 注入
# ──────────────────────────────────────────────────────────────────────


class TestAgentBaseInstruction:
    """验证 Agent Base Instruction 正确注入到 System Prompt。"""

    def test_base_instruction_not_empty(self):
        """Base Instruction 不为空"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert len(text) > 100
        assert "Agent 基础行为准则" in text

    def test_base_instruction_contains_chat_mode(self):
        """Base Instruction 包含聊天模式规则"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert "聊天模式" in text
        assert "不调用任何工具" in text

    def test_base_instruction_contains_task_mode(self):
        """Base Instruction 包含任务模式规则"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert "任务模式" in text
        assert "Strategy Layer" in text
        assert "Verification Loop" in text

    def test_base_instruction_contains_honesty(self):
        """Base Instruction 包含诚实原则"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert "诚实原则" in text
        assert "不虚构执行结果" in text

    def test_base_instruction_has_no_programming_knowledge(self):
        """Base Instruction 不包含编程知识"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert "Python" not in text
        assert "React" not in text
        assert "API" not in text

    def test_base_instruction_has_no_writing_style(self):
        """Base Instruction 不包含写作风格"""
        from app.core.agent_base_instruction import get_agent_base_instruction
        text = get_agent_base_instruction()
        assert "表达风格" not in text
        assert "对话方式" not in text


# ──────────────────────────────────────────────────────────────────────
# Test C: Prompt 合并结构
# ──────────────────────────────────────────────────────────────────────


class TestPromptMergeStructure:
    """验证 Prompt 合并结构：Base Instruction + Identity + Capability + ..."""

    def test_assemble_prompt_contains_base_instruction(self):
        """组装后的 prompt 包含 Base Instruction"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from app.core.agent_base_instruction import get_agent_base_instruction
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        base_instruction = get_agent_base_instruction()
        assert base_instruction in full_prompt

    def test_assemble_prompt_contains_identity(self):
        """组装后的 prompt 包含 Agent 身份"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        assert "你是测试助手" in full_prompt

    def test_assemble_prompt_contains_identity_principle(self):
        """组装后的 prompt 包含最高身份准则"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from app.core.identity_principle import get_identity_principle
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        identity_principle = get_identity_principle()
        assert identity_principle in full_prompt

    def test_assemble_prompt_structure_order(self):
        """验证 Prompt 层级顺序：Identity Principle → Base Instruction → Identity → ..."""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from app.core.identity_principle import get_identity_principle
        from app.core.agent_base_instruction import get_agent_base_instruction
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        identity_principle = get_identity_principle()
        base_instruction = get_agent_base_instruction()

        idx_principle = full_prompt.index(identity_principle)
        idx_base = full_prompt.index(base_instruction)
        idx_identity = full_prompt.index("你是测试助手")

        # 层级顺序：Identity Principle → Base Instruction → Identity
        assert idx_principle < idx_base < idx_identity

    def test_assemble_prompt_execution_policy_present(self):
        """组装后的 prompt 包含执行策略（Execution Policy）"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        assert "Execution Policy" in full_prompt

    def test_capability_prompt_injected(self):
        """验证 capability_prompt 正确注入"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["software_development", "code_review"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
        )

        assert "能力倾向" in full_prompt
        assert "软件开发" in full_prompt
        assert "代码审查" in full_prompt

    def test_tool_guidance_injected(self):
        """验证 Tool Guidance 正确注入"""
        from app.core.agent_runtime.context_builder import ChatContextBuilder
        from types import SimpleNamespace

        builder = ChatContextBuilder()
        full_prompt = builder._assemble_prompt(
            system_prompt="你是测试助手。",
            capabilities=["general_assistance"],
            personality_prompt="",
            effective_chat=SimpleNamespace(
                mode="build",
                project_path=None,
                agent_id="test",
                project_id=None,
            ),
            workspace_context="",
            tool_context=None,
            tool_guidance="## 工具使用指导\n- 请使用正确工具",
        )

        assert "工具使用指导" in full_prompt


# ──────────────────────────────────────────────────────────────────────
# Test D: 种子 Agent 验证
# ──────────────────────────────────────────────────────────────────────


class TestSeedAgents:
    """验证所有预设 Agent 的 identity 和 capabilities 正确。"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from seed_agents import PRESET_AGENTS
        self.agents = {a["agent_id"]: a for a in PRESET_AGENTS}

    def test_all_active_agents_have_identity(self):
        """所有 active 状态的 Agent 必须有 identity"""
        for agent_id, agent in self.agents.items():
            if agent.get("status") == "active":
                assert agent.get("identity"), f"Agent {agent_id} 缺少 identity"

    def test_all_active_agents_have_capabilities(self):
        """所有 active 状态的 Agent 必须有 capabilities"""
        for agent_id, agent in self.agents.items():
            if agent.get("status") == "active":
                caps = agent.get("capabilities", [])
                assert len(caps) > 0, f"Agent {agent_id} 缺少 capabilities"

    def test_general_agent_exists(self):
        """General Agent 存在"""
        assert "general" in self.agents
        agent = self.agents["general"]
        assert agent["status"] == "active"
        assert "MfkAgent" in agent["identity"]

    def test_coder_agent_exists(self):
        """Coder Agent 存在"""
        assert "coder" in self.agents
        agent = self.agents["coder"]
        assert agent["status"] == "active"
        assert "software_development" in agent["capabilities"]

    def test_research_agent_exists(self):
        """Research Agent 存在"""
        assert "research" in self.agents
        agent = self.agents["research"]
        assert agent["status"] == "active"
        assert "web_research" in agent["capabilities"]
        assert "调研" in agent["identity"]

    def test_g_agent_exists(self):
        """G 审查官 Agent 存在"""
        assert "g" in self.agents
        agent = self.agents["g"]
        assert agent["status"] == "active"
        assert "system_analysis" in agent["capabilities"]
        assert "code_review" in agent["capabilities"]

    def test_product_agent_exists(self):
        """Product Agent 存在"""
        assert "product" in self.agents
        agent = self.agents["product"]
        assert agent["status"] == "active"

    def test_frontend_agent_exists(self):
        """Frontend Agent 存在"""
        assert "frontend_ui" in self.agents
        agent = self.agents["frontend_ui"]
        assert agent["status"] == "active"
        assert "frontend_design" in agent["capabilities"]

    def test_mentor_agent_exists(self):
        """Mentor Agent 存在"""
        assert "mentor" in self.agents
        agent = self.agents["mentor"]
        assert agent["status"] == "active"

    def test_spark_agent_exists(self):
        """Spark Agent 存在"""
        assert "spark" in self.agents
        agent = self.agents["spark"]
        assert agent["status"] == "active"

    def test_personal_agent_exists(self):
        """Personal Agent 存在"""
        assert "personal" in self.agents
        agent = self.agents["personal"]
        assert agent["status"] == "active"

    def test_writer_agent_exists(self):
        """Writer Agent 存在"""
        assert "writer" in self.agents
        agent = self.agents["writer"]
        assert agent["status"] == "active"

    def test_legacy_agents_preserved(self):
        """Legacy Agent 数据保留"""
        assert "warm" in self.agents
        assert "rational" in self.agents
        assert self.agents["warm"]["status"] == "legacy"
        assert self.agents["rational"]["status"] == "legacy"

    def test_new_agent_auto_has_capabilities(self):
        """新增 Agent 只需提供 identity 即自动拥有基础能力。
        
        验证：Research Agent 是新增的，只提供 identity + capabilities，
        在运行时会被注入 Base Instruction（由 context_builder 负责）。
        """
        research = self.agents["research"]
        # Research Agent 有 identity
        assert len(research["identity"]) > 50
        # 有 capabilities
        assert len(research["capabilities"]) > 0
        # 有状态
        assert research["status"] == "active"


# ──────────────────────────────────────────────────────────────────────
# Test E: Prompt 文件映射验证
# ──────────────────────────────────────────────────────────────────────


class TestPromptFileMapping:
    """验证所有原始 Prompt 文件已正确映射到 Agent。"""

    PROMPT_FILE_MAP = {
        "GPT2.txt": "general",
        "开发.txt": "coder",
        "前端.txt": "frontend_ui",
        "审查.txt": "g",
        "导师.txt": "mentor",
        "产品.txt": "product",
        "中二.txt": "spark",
        "专属.txt": "personal",
        "文案.txt": "writer",
    }

    @pytest.fixture(autouse=True)
    def _setup(self):
        from seed_agents import PRESET_AGENTS
        self.agents = {a["agent_id"]: a for a in PRESET_AGENTS}

    def test_all_prompt_files_mapped(self):
        """所有原始 Prompt 文件都已映射到 Agent"""
        for prompt_file, agent_id in self.PROMPT_FILE_MAP.items():
            assert agent_id in self.agents, (
                f"Prompt 文件 {prompt_file} 映射的 Agent '{agent_id}' 不存在"
            )

    def test_all_mapped_agents_are_active(self):
        """所有映射的 Agent 均为 active 状态"""
        for agent_id in set(self.PROMPT_FILE_MAP.values()):
            agent = self.agents.get(agent_id)
            assert agent is not None
            assert agent["status"] == "active", (
                f"Agent '{agent_id}' 状态应为 active，当前为 {agent['status']}"
            )

    def test_no_giant_merged_prompt(self):
        """验证 Agent identity 没有融合成巨大 Prompt（每个 Agent 保持独立 identity）"""
        identities = []
        for agent_id, agent in self.agents.items():
            if agent.get("status") == "active":
                identity = agent.get("identity", "")
                identities.append(identity)
                # 每个 Agent 的 identity 应在合理长度内（< 2000 字符）
                assert len(identity) < 2000, (
                    f"Agent '{agent_id}' identity 过大 ({len(identity)} 字符)，"
                    f"可能被融合成巨大 Prompt"
                )

        # 所有 active Agent 的 identity 应各不相同
        unique_identities = set(identities)
        assert len(unique_identities) == len(identities), (
            "存在 Agent identity 重复，可能被错误融合"
        )


# ──────────────────────────────────────────────────────────────────────
# Test F: Tool Intelligence 层验证
# ──────────────────────────────────────────────────────────────────────


class TestToolIntelligence:
    """验证 Tool Guidance、Strategy Layer、Verification Loop 对所有 Agent 生效。"""

    def test_guidance_templates_exist(self):
        """验证 Tool Guidance 模板存在"""
        from app.core.tool_runtime.guidance import GUIDANCE_TEMPLATES
        assert "coding" in GUIDANCE_TEMPLATES
        assert "research" in GUIDANCE_TEMPLATES
        assert "file_operation" in GUIDANCE_TEMPLATES
        assert "debugging" in GUIDANCE_TEMPLATES

    def test_guidance_coding_has_flow(self):
        """验证 Coding Guidance 包含工具流程"""
        from app.core.tool_runtime.guidance import GUIDANCE_TEMPLATES
        template = GUIDANCE_TEMPLATES["coding"]
        flow = template.get("tool_flow", [])
        assert len(flow) > 0
        assert any("read" in step.lower() for step in flow)

    def test_guidance_research_has_suggestions(self):
        """验证 Research Guidance 包含搜索建议"""
        from app.core.tool_runtime.guidance import GUIDANCE_TEMPLATES
        template = GUIDANCE_TEMPLATES["research"]
        suggestions = template.get("suggestions", [])
        assert len(suggestions) > 0

    def test_strategy_engine_exists(self):
        """验证 Strategy Engine 可导入"""
        from app.core.tool_runtime.strategy import get_strategy_engine
        engine = get_strategy_engine("test_chat_id")
        assert engine is not None

    def test_verifier_exists(self):
        """验证 Verifier 可导入"""
        from app.core.verification import verifier
        assert verifier is not None

    def test_guidance_get_tool_guidance_coding(self):
        """验证 get_tool_guidance 对 coding intent 返回指导"""
        from app.core.tool_runtime.guidance import get_tool_guidance
        guidance = get_tool_guidance("coding", project_bound=True, message="帮我修复这个 Bug")
        assert guidance is not None
        assert "工具使用指导" in guidance

    def test_guidance_get_tool_guidance_research(self):
        """验证 get_tool_guidance 对 web_search intent 返回 research 指导"""
        from app.core.tool_runtime.guidance import get_tool_guidance
        guidance = get_tool_guidance("web_search", project_bound=False, message="帮我调查这个主题")
        assert guidance is not None
        assert "工具使用指导" in guidance

    def test_guidance_get_tool_guidance_general_chat_returns_none(self):
        """验证 general_chat 不返回工具指导"""
        from app.core.tool_runtime.guidance import get_tool_guidance
        guidance = get_tool_guidance("general_chat", project_bound=False, message="你好")
        assert guidance is None


# ──────────────────────────────────────────────────────────────────────
# 运行入口
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])