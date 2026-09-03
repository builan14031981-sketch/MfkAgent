"""
2026-09-03：context_preview 上下文预览事件测试。

背景：token_usage 只在 LLM finish 时才发（usage 需流式响应结束才有），导致思考/生成阶段
前端无数据、上下文仪表盘不出现、输出完才冒出来。新增 context_preview 事件在每轮 LLM
调用前先发一版（仅透出上下文构成 + 估算水位/命中率），让仪表盘在思考阶段即可显示。

本测试覆盖 AgentRuntime._build_context_preview_event 的构建逻辑：
  1. 事件类型/字段正确（type=context_preview、cache_source=estimated、completion=0）
  2. context_breakdown 透出
  3. cached_tokens / watermark 计算正确
"""
from app.core.agent_runtime import AgentRuntime


def _runtime():
    return AgentRuntime()


def test_context_preview_event_basic_fields():
    """事件应标记为 context_preview / estimated，completion=0。"""
    runtime = _runtime()
    event = runtime._build_context_preview_event(
        prompt_tokens=5474,
        cached_tokens=5472,
        model_id="deepseek-chat",
        context_breakdown={"system_prompt": 100, "tools": 200, "memory": 50, "messages": 800},
    )
    assert event["type"] == "context_preview"
    assert event["prompt_tokens"] == 5474
    assert event["completion_tokens"] == 0
    assert event["total_tokens"] == 5474
    assert event["cached_tokens"] == 5472
    assert event["cache_source"] == "estimated"


def test_context_preview_event_breakdown_passed_through():
    """context_breakdown 应完整透出（供前端展示上下文分类占比）。"""
    runtime = _runtime()
    breakdown = {"system_prompt": 500, "tools": 200, "memory": 50, "messages": 800, "reminder": 30, "other": 0}
    event = runtime._build_context_preview_event(1000, 900, "deepseek-chat", breakdown)
    assert event["context_breakdown"] == breakdown


def test_context_preview_event_without_breakdown():
    """无 breakdown 时不崩溃，字段为 None。"""
    runtime = _runtime()
    event = runtime._build_context_preview_event(1000, 900, "deepseek-chat")
    assert event["context_breakdown"] is None
    assert event["type"] == "context_preview"


def test_context_preview_event_watermark_and_model_max():
    """watermark_percentage 应基于估算 prompt_tokens 计算，model_max_tokens 来自模型配置。"""
    runtime = _runtime()
    event = runtime._build_context_preview_event(prompt_tokens=5000, cached_tokens=4000, model_id="deepseek-chat")
    assert event["model_max_tokens"] > 0, "模型上下文窗口上限应 > 0"
    assert 0 <= event["watermark_percentage"] <= 100
