# -*- coding: utf-8 -*-
"""Persona System V2 单元测试（2026-08-11 新增）。

覆盖任务验收标准：
  测试1 「我今天好累」→ 像朋友回应，不输出心理分析报告
  测试2 「我是不是很失败？」→ 自然交流，不连续安慰
  测试3 「帮我写一个方案」→ 关闭陪伴模式，进入工作模式
  测试4 交流次数递增 → 关系距离变化（陌生→熟悉→亲近→长期陪伴）

另覆盖：
  - Persona Knowledge 知识层（md 加载 / 按类型加载 / 全 Agent 行为规则）
  - Expression Budget（各 profile 预算差异 + 渲染文本）
  - Human Conversation Rules（所有 Agent 默认注入）
  - Pianai Relationship Layer（专属 / 非 pianai 不注入）
  - Restrictions（全局禁止 + pianai 专属禁止）
  - V1 向后兼容（旧签名调用不报错）
"""
from types import SimpleNamespace

from app.core import persona_engine as pe
from app.core.persona import loader as knowledge
from app.core.persona_engine import (
    PROFILE_CONFIGS,
    ExpressionBudget,
    build_persona_context,
    compute_relationship_distance,
    detect_user_mood,
    get_profile_config,
    render_budget_text,
    render_relationship_text,
    render_restrictions_text,
)

from app.models.persona import PersonaTemplate, ExpressionKnowledge


def make_agent(agent_id="general", expression_profile="warm"):
    return SimpleNamespace(agent_id=agent_id, expression_profile=expression_profile)


def make_template(**overrides):
    data = {
        "personality_traits": {"warmth": 0.9, "curiosity": 0.7, "playfulness": 0.6,
                               "empathy": 0.95, "authenticity": 0.9},
        "communication_style": {"directness": 0.4, "humor": 0.6, "formality": 0.1,
                                "naturalness": 0.95},
        "behavior_rules": {"proactive_level": 0.6, "intimacy_level": 0.7,
                           "emotional_expression": 0.9},
        "expression_preferences": {"emoji_usage": 0.6, "kaomoji_usage": 0.7,
                                   "markdown_usage": 0.8, "colloquial_level": 0.8,
                                   "internet_slang": 0.4, "pause_frequency": 0.6},
    }
    data.update(overrides)
    return PersonaTemplate(agent_id="test", **data)


# ──── 一、Persona Knowledge 知识层 ────

class TestKnowledgeLayer:
    def test_behavior_rules_loaded(self):
        text = knowledge.get_behavior_rules()
        assert "先回应，再分析" in text
        assert "你其实" in text          # 禁止词
        assert "Anti-AI" in text or "AI 腔" in text

    def test_profile_text_by_type(self):
        assert "真人陪伴" in knowledge.get_profile_text("companion")
        assert "专业" in knowledge.get_profile_text("professional")
        assert "代码" in knowledge.get_profile_text("coder")
        assert "文学" in knowledge.get_profile_text("creative")

    def test_unknown_profile_returns_empty(self):
        assert knowledge.get_profile_text("nonexistent") == ""
        assert knowledge.get_profile_text(None) == ""

    def test_expression_sections_loaded(self):
        for section in ("emoji", "internet_language", "typography", "emotional_expression"):
            assert knowledge.get_expression_section(section), f"section {section} 为空"
        assert "emoji" in knowledge.get_expression_section("emoji").lower()


# ──── 二、Agent 类型表达配置 + Expression Budget ────

class TestExpressionBudget:
    def test_profiles_have_structured_config(self):
        for pid in ("companion", "professional", "coder", "creative", "warm"):
            cfg = get_profile_config(pid)
            for key in ("style", "emoji_level", "humor_level", "formatting_level", "warmth", "budget"):
                assert key in cfg, f"{pid} 缺 {key}"
            assert isinstance(cfg["budget"], ExpressionBudget)

    def test_default_budget_fallback(self):
        cfg = get_profile_config("unknown_profile")
        assert cfg is PROFILE_CONFIGS["default"]
        assert cfg["budget"].emoji_max == 2

    def test_budget_difference_companion_vs_professional(self):
        # 偏爱：emoji 允许提高（3 个）；专业：不用 emoji（0 个）
        assert get_profile_config("companion")["budget"].emoji_max == 3
        assert get_profile_config("professional")["budget"].emoji_max == 0
        # 动作描写都低频
        assert get_profile_config("companion")["budget"].action_desc_max == 1
        assert get_profile_config("professional")["budget"].action_desc_max == 0
        # 都不允许连续表演
        assert get_profile_config("companion")["budget"].continuous_acting is False

    def test_budget_text_rendered(self):
        text = render_budget_text(get_profile_config("default")["budget"], get_profile_config("default"))
        assert "emoji" in text
        assert "动作描写" in text
        assert "情绪词" in text
        assert "不要连续表演" in text

    def test_creative_allows_rich_text(self):
        assert get_profile_config("creative")["budget"].rich_text_policy == "allowed"
        assert get_profile_config("coder")["budget"].rich_text_policy == "none"


# ──── 三、Human Conversation Rules（所有 Agent 默认）────

class TestHumanConversationAllAgents:
    def test_agent_without_template_still_gets_behavior(self):
        # 无 PersonaTemplate 的 Agent（如 coder）也应获得基础行为层
        ctx = build_persona_context(make_agent("coder", "coder"))
        assert ctx.behavior_text, "无模板 Agent 应注入 Human Conversation Rules"
        assert "先回应，再分析" in ctx.behavior_text
        assert ctx.budget_text, "无模板 Agent 应注入表达预算"
        assert ctx.restrictions_text, "无模板 Agent 应注入禁止表达层"

    def test_template_agent_gets_all_layers(self):
        ctx = build_persona_context(make_agent("pianai", "companion"), make_template())
        assert ctx.has_persona
        assert ctx.persona_text
        assert ctx.expression_text
        assert ctx.behavior_text
        assert ctx.budget_text
        assert ctx.restrictions_text

    def test_v1_backward_compat(self):
        # V1 旧签名（不传新参数）不报错
        ctx = build_persona_context(make_agent(), make_template())
        assert ctx.persona_text
        assert ctx.expression_text


# ──── 四、测试标准 1&2：情感场景不演 ────

class TestMoodDetection:
    def test_tired_message_is_low(self):
        assert detect_user_mood("我今天好累") == "low"
        assert detect_user_mood("我好烦，今天真倒霉") == "low"

    def test_failure_question_is_low(self):
        assert detect_user_mood("我是不是很失败？") == "low"

    def test_task_message_is_serious(self):
        assert detect_user_mood("帮我写一个方案") == "serious"
        assert detect_user_mood("分析一下这个项目") == "serious"

    def test_happy_message(self):
        assert detect_user_mood("哈哈今天太开心了") == "happy"

    def test_neutral(self):
        assert detect_user_mood("今天天气怎么样") == "neutral"
        assert detect_user_mood("") == "neutral"


class TestNoPsychoanalysis:
    def test_low_mood_renders_quiet_companion_not_report(self):
        # 测试1：低落 → 安静陪伴（Relationship 层），且 Human Conversation 层禁止心理分析
        text = render_relationship_text("熟悉", "low", 10)
        assert "安静陪伴" in text
        assert "少开玩笑" in text
        behavior = knowledge.get_behavior_rules()
        assert "你其实" in behavior          # 禁止心理分析套话
        assert "心理评估" in behavior        # 不输出心理分析报告

    def test_no_continuous_comfort(self):
        # 测试2：禁止连续多段安慰
        behavior = knowledge.get_behavior_rules()
        assert "连续多段安慰" in behavior
        budget = render_budget_text(PROFILE_CONFIGS["companion"]["budget"], PROFILE_CONFIGS["companion"])
        assert "不要连续表演" in budget


# ──── 五、测试标准 3：工作模式切换 ────

class TestWorkModeSwitch:
    def test_serious_mood_closes_companion_mode(self):
        text = render_relationship_text("亲近", "serious", 30)
        assert "关闭陪伴话术" in text or "关闭陪伴模式" in text
        assert "工作模式" in text
        assert "减少玩笑" in text


# ──── 六、测试标准 4：关系距离随交流次数变化 ────

class TestRelationshipDistance:
    def test_stages(self):
        assert compute_relationship_distance(0) == "陌生"
        assert compute_relationship_distance(4) == "陌生"
        assert compute_relationship_distance(5) == "熟悉"
        assert compute_relationship_distance(19) == "熟悉"
        assert compute_relationship_distance(20) == "亲近"
        assert compute_relationship_distance(49) == "亲近"
        assert compute_relationship_distance(50) == "长期陪伴"
        assert compute_relationship_distance(500) == "长期陪伴"

    def test_distance_in_context_after_many_turns(self):
        # 10 轮连续聊天后从陌生到熟悉
        ctx_early = build_persona_context(
            make_agent("pianai", "companion"), make_template(),
            user_message="你好", interaction_count=2,
        )
        ctx_late = build_persona_context(
            make_agent("pianai", "companion"), make_template(),
            user_message="你好", interaction_count=30,
        )
        assert ctx_early.relationship_distance == "陌生"
        assert ctx_late.relationship_distance == "亲近"
        assert ctx_late.relationship_text != ctx_early.relationship_text

    def test_relationship_text_uses_friend_memory_style(self):
        text = render_relationship_text("亲近", "neutral", 30)
        assert "你之前不是说过" in text      # 记忆引用改写
        # 指令是「不要用『根据我的记忆…』」，不是教 Agent 使用它
        assert "不要「根据我的记忆" in text


# ──── 七、Pianai 专属 + Restrictions ────

class TestPianaiRelationshipLayer:
    def test_only_pianai_gets_relationship(self):
        ctx_pianai = build_persona_context(
            make_agent("pianai", "companion"), make_template(),
            user_message="我今天好累", interaction_count=10,
        )
        assert ctx_pianai.relationship_text
        assert ctx_pianai.relationship_distance == "熟悉"
        assert ctx_pianai.mood == "low"

        ctx_general = build_persona_context(
            make_agent("general", "warm"), make_template(),
            user_message="我今天好累", interaction_count=10,
        )
        assert ctx_general.relationship_text == ""
        assert ctx_general.mood == "neutral"

    def test_pianai_restrictions(self):
        text = render_restrictions_text("pianai")
        assert "我永远陪着你" in text
        assert "你是唯一" in text
        assert "刻进代码" in text
        assert "你其实" in text              # 全局禁止也在

    def test_global_restrictions_all_agents(self):
        text = render_restrictions_text("coder")
        assert "你其实" in text
        assert "心理报告式解读" in text
        assert "我永远陪着你" not in text    # pianai 专属不泄漏给其他 Agent


# ──── 八、任务七：Agent 类型表达配置覆盖全部预设 Agent ────

class TestAgentTypeConfigs:
    def test_all_preset_profiles_have_config(self):
        # seed_agents.py 中使用的全部 expression_profile 值都应有结构化配置
        for pid in ("warm", "coder", "professional", "companion", "creative"):
            assert get_profile_config(pid) is not PROFILE_CONFIGS["default"] or pid == "warm", pid
