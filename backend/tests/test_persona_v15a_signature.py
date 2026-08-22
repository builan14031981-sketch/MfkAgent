# -*- coding: utf-8 -*-
"""Pianai V15-A Persona Signature 验证测试。

覆盖任务测试要求（确定性验证，不调用 LLM）：
  测试1 人格稳定：同一问题连续 10 次，signature/strategy 文本逐字一致
  测试2 独立判断：「我觉得我应该放弃。」→ support + challenge（禁止无脑支持）
  测试3 普通聊天：「今天吃什么？」→ casual（自然，不分析）
  测试4 工作测试：「帮我设计数据库。」→ 任务模式（explain / work_mode）
  附加 ：注入层级顺序验证（Identity > Capability > Signature > Personality > Performance > Expression）
  附加 ：专业型 Agent（coder）不注入签名层，人格不干扰专业性

运行：python backend/tests/test_persona_v15a_signature.py
退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import tempfile
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 临时环境隔离（必须在 import app 之前）
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_v15a_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./v15a_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.core.agent_runtime.context_builder import ChatContextBuilder, ContextBuildInput  # noqa: E402
from app.core.persona_engine import build_persona_context  # noqa: E402
from app.core.persona_signature import (  # noqa: E402
    get_agent_signature, render_signature_text, select_response_mode, PIANAI_SIGNATURE,
)
from app.models.agent import Agent, Chat  # noqa: E402

failures = []


def run(name, fn):
    try:
        detail = fn()
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    except AssertionError as e:
        failures.append(name)
        print(f"  FAIL  {name}\n        {e}")


def seed_pianai(db):
    agent = db.query(Agent).filter(Agent.agent_id == "pianai").first()
    if not agent:
        agent = Agent(
            agent_id="pianai", name="Pianai", description="test", avatar="heart",
            identity="# 偏爱 Pianai — Identity V15\n你是一个通过长期真实交流，与用户形成独特关系的存在。",
            capabilities=["general_assistance"], default_personality_level=25,
            expression_profile="natural_companion", status="active",
        )
        db.add(agent)
    chat = Chat(title="v15a", agent_id="pianai", personality_level=25)
    db.add(chat)
    db.commit()
    return chat.id


def seed_coder(db):
    agent = db.query(Agent).filter(Agent.agent_id == "coder_test").first()
    if not agent:
        agent = Agent(
            agent_id="coder_test", name="CoderTest", description="test", avatar="code",
            identity="你是一个软件开发工程师。", capabilities=["software_development"],
            default_personality_level=75, expression_profile="coder", status="active",
        )
        db.add(agent)
        db.commit()
    return agent


# ──── 测试1：人格稳定（10 次确定性一致）────

def test_stability():
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == "pianai").first()
        msg = "我失败了怎么办？"
        texts = set()
        strategies = set()
        for _ in range(10):
            ctx = build_persona_context(agent, None, None, user_message=msg)
            texts.add(ctx.signature_text)
            strategies.add(ctx.strategy_text)
        assert len(texts) == 1, f"signature_text 10 次渲染不一致：{len(texts)} 个变体"
        assert len(strategies) == 1, f"strategy_text 10 次渲染不一致：{len(strategies)} 个变体"
        assert "交流倾向" in next(iter(texts)), "签名文本缺失「交流倾向」"
        return "10/10 逐字一致"
    finally:
        db.close()


# ──── 测试2：独立判断（support + challenge，禁止无脑支持）────

def test_independent_judgment():
    sig = get_agent_signature("pianai")
    modes = select_response_mode("我觉得我应该放弃。", sig)
    assert "support" in modes, f"缺少 support：{modes}"
    assert "challenge" in modes, f"缺少 challenge（无脑支持风险）：{modes}"
    modes2 = select_response_mode("我是不是很差？", sig)
    assert "challenge" in modes2, f"「我是不是很差？」应含 challenge：{modes2}"
    # 任务测试 1 指定问题：不能固定鸡汤（需 challenge 平衡）
    modes3 = [select_response_mode("我失败了怎么办？", sig) for _ in range(10)]
    assert all(m == modes3[0] for m in modes3), "10 次策略不一致"
    assert "challenge" in modes3[0], f"「我失败了怎么办？」应含 challenge（防固定鸡汤）：{modes3[0]}"
    return f"modes={modes}"


# ──── 测试3：普通聊天（自然，不分析）────

def test_casual_chat():
    sig = get_agent_signature("pianai")
    modes = select_response_mode("今天吃什么？", sig)
    assert modes[0] == "casual", f"普通聊天应为 casual：{modes}"
    assert "challenge" not in modes and "support" not in modes, f"普通聊天不应分析/安慰：{modes}"
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == "pianai").first()
        ctx = build_persona_context(agent, None, None, user_message="今天吃什么？")
        assert "casual" in ctx.response_modes, f"response_modes={ctx.response_modes}"
    finally:
        db.close()
    return f"modes={modes}"


# ──── 测试4：工作模式（人格存在但不影响专业性）----

def test_work_mode():
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == "pianai").first()
        ctx = build_persona_context(agent, None, None, user_message="帮我设计数据库。")
        assert ctx.is_work_mode, "「帮我设计数据库。」应进入工作模式"
        assert ctx.signature_text, "工作模式下签名层仍应存在（人格存在）"
        assert ctx.strategy_text == "", "工作模式由 work_mode_text 承担，strategy 不重复注入"
        assert "工作模式" in ctx.work_mode_text
        modes = select_response_mode("帮我设计数据库。", get_agent_signature("pianai"))
        assert modes == ["explain"], f"工作意图应为 explain：{modes}"
        return "work_mode=True, signature 保留"
    finally:
        db.close()


# ──── 附加：注入层级顺序验证 ----

def test_injection_order(chat_id):
    import asyncio
    builder = ChatContextBuilder()
    built = asyncio.run(builder.build(ContextBuildInput(chat_id=chat_id, content="聊聊最近的事")))
    sp = built.system_prompt
    i_identity = sp.find("Identity V15")
    i_signature = sp.find("你的交流倾向")
    i_personality = sp.find("适度提供建议和分析")  # personality_level=25 文案
    i_budget = sp.find("表达预算")
    i_restrict = sp.find("禁止表达")
    assert i_identity >= 0, "identity 未注入"
    assert i_signature > i_identity, "Signature 应在 Identity 之后"
    assert i_signature < i_personality, "Signature 应在 Personality Level 之前"
    assert i_personality < i_budget, "Personality Level 应在 Performance/Budget 之前"
    assert i_budget < i_restrict, "Performance 应在 Expression/Restrictions 之前"
    assert "层级优先级" in sp, "优先级声明缺失"
    assert "角色扮演" not in sp[i_signature:i_signature + 200], "签名层出现角色扮演语言"
    return "① Identity < ③ Signature < ④ Personality < ⑤ Performance < 限制层"


# ──── 附加：专业型 Agent 不注入签名层 ----

def test_professional_no_signature():
    agent = get_agent_signature("coder_test")
    assert agent is None, "coder 不应有签名"
    db = SessionLocal()
    try:
        coder = seed_coder(db)
        ctx = build_persona_context(coder, None, None, user_message="帮我修一个 bug")
        assert ctx.signature_text == "", "coder 不应注入签名层"
    finally:
        db.close()
    return "coder 零人格注入，专业性不受干扰"


# ──── 附加：签名默认值符合任务规格 ----

def test_signature_values():
    sig = PIANAI_SIGNATURE
    assert (sig.warmth, sig.directness, sig.humor, sig.curiosity, sig.challenge) == (80, 65, 45, 75, 55), \
        f"Pianai 签名值偏离规格：{sig}"
    text = render_signature_text(sig)
    assert "温暖但保持独立判断" in text
    assert "不盲目认同" in text
    return "80/65/45/75/55"


def main():
    print("=" * 70)
    print("Pianai V15-A Persona Signature 验证")
    print("=" * 70)
    db = SessionLocal()
    chat_id = seed_pianai(db)
    db.close()

    run("测试1 人格稳定（10 次一致性）", test_stability)
    run("测试2 独立判断（support+challenge）", test_independent_judgment)
    run("测试3 普通聊天（casual 不分析）", test_casual_chat)
    run("测试4 工作模式（人格存在不干扰专业）", test_work_mode)
    run("附加 注入层级顺序", lambda: test_injection_order(chat_id))
    run("附加 专业型 Agent 零签名注入", test_professional_no_signature)
    run("附加 签名默认值符合规格", test_signature_values)

    print("=" * 70)
    if failures:
        print(f"结果：{len(failures)} 项失败 -> {failures}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
