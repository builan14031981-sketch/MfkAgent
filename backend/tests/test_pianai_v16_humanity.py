# -*- coding: utf-8 -*-
"""Pianai V16 Human Imperfection Layer（人味层）验证测试。

覆盖任务测试要求（确定性验证，不调用 LLM）：
  测试1 普通聊天：「今天吃什么？」→ 不心理分析、不长篇建议
  测试2 失败：「我又失败了」→ 不鸡汤、不「你其实很优秀」，允许具体回应 + 温和挑战
  测试3 连续玩笑：5 轮轻松聊天 → humor 提升，但不变成搞笑机器人（±20 钳制）
  测试4 工作模式：「帮我设计数据库」→ 自动专业，不注入卖萌节奏提示
  测试5 稳定性：连续 20 轮 → Signature 不变化、无固定模板、无重复安慰、无主动心理分析
  附加 A：注入链顺序（Identity < Signature < Human Imperfection < Performance < Expression）
  附加 B：人味层措辞为倾向描述（非命令式），无重复人格规则

运行：python backend/tests/test_pianai_v16_humanity.py
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
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_v16_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./v16_test.db"
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
from app.core.persona_signature import get_agent_signature, render_signature_text  # noqa: E402
from app.core.persona_quirks import (  # noqa: E402
    get_agent_quirk, render_quirk_text, build_conversation_state, classify_turn_tone,
)
from app.models.agent import Agent, Chat, Message  # noqa: E402

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
            identity="# 偏爱 Pianai — Identity V16\n像朋友交流，而不是服务机器人。",
            capabilities=["general_assistance"], default_personality_level=25,
            expression_profile="natural_companion", status="active",
        )
        db.add(agent)
    chat = Chat(title="v16", agent_id="pianai", personality_level=25)
    db.add(chat)
    db.commit()
    return chat.id


def add_user_messages(chat_id, texts):
    db = SessionLocal()
    try:
        for t in texts:
            db.add(Message(chat_id=chat_id, role="user", content=t))
        db.commit()
    finally:
        db.close()


def build_prompt(chat_id, content):
    import asyncio
    builder = ChatContextBuilder()
    built = asyncio.run(builder.build(ContextBuildInput(chat_id=chat_id, content=content)))
    return built.system_prompt, built.persona_context


# ──── 测试1：普通聊天（不心理分析、不长篇建议）────

def test_casual(chat_id):
    sp, ctx = build_prompt(chat_id, "今天吃什么？")
    assert ctx.response_modes and ctx.response_modes[0] == "casual", f"modes={ctx.response_modes}"
    assert "不做分析" in ctx.strategy_text, ctx.strategy_text
    assert "不长篇大论" in ctx.strategy_text or "短回复优先" in ctx.strategy_text, "缺少短回复约束（防长篇建议）"
    q = ctx.quirk_text
    assert "心理医生口吻" in q and "过度总结" in q, "人味层缺少回避模式"
    return "casual + 回避心理医生口吻/过度总结"


# ──── 测试2：失败（不鸡汤，允许温和挑战）────

def test_failure(chat_id):
    sp, ctx = build_prompt(chat_id, "我又失败了")
    modes = ctx.response_modes
    assert "support" in modes and "challenge" in modes, f"应 support+challenge：{modes}"
    # 防鸡汤：人味层明确不喜欢空泛鸡汤；禁止表达层禁止连续安慰
    assert "不喜欢空泛鸡汤" in ctx.quirk_text
    assert "不要连续多段安慰" in ctx.restrictions_text
    # 禁止「你其实…」式定义（V2 全局禁止）
    assert "你其实" in ctx.restrictions_text
    # 温和挑战存在
    assert "温和挑战" in ctx.quirk_text and "不无条件认同" in ctx.quirk_text
    return f"modes={modes}"


# ──── 测试3：连续玩笑（humor 提升但受限）────

def test_consecutive_jokes(chat_id):
    sig = get_agent_signature("pianai")
    base = sig.humor
    jokes = ["哈哈哈这也太逗了", "笑死我了", "你今天好搞笑", "哈哈真的假的", "太逗了吧"]
    assert all(classify_turn_tone(t) == "joke" for t in jokes), "玩笑语料分类失败"
    state = build_conversation_state(sig, jokes)
    assert state.humor_level > base, f"连续玩笑后 humor 应提升：{state.humor_level} <= {base}"
    assert state.humor_level <= base + 20, f"humor 漂移超出 ±20：{state.humor_level}"
    # 再加 10 轮玩笑也不能突破上限（防漂移）
    state2 = build_conversation_state(sig, jokes * 3)
    assert state2.humor_level <= base + 20, "多轮玩笑后突破 ±20 上限"
    # 不变成搞笑机器人：节奏提示自带约束语
    from app.core.persona_quirks import render_state_hint
    hint = render_state_hint(state)
    assert "不变成搞笑角色" in hint, hint
    return f"humor {base} -> {state.humor_level}（上限 {base + 20}）"


# ──── 测试4：工作模式（自动专业，不卖萌）────

def test_work(chat_id):
    add_user_messages(chat_id, ["哈哈哈太逗了", "笑死", "哈哈"])  # 历史带玩笑也不影响
    sp, ctx = build_prompt(chat_id, "帮我设计数据库")
    assert ctx.is_work_mode, "应进入工作模式"
    assert "工作模式" in ctx.work_mode_text
    assert ctx.state_hint_text == "", "工作模式不应注入轻松节奏提示"
    assert ctx.response_modes == ["explain"], f"modes={ctx.response_modes}"
    # 表达预算：natural_companion 在 work 意图下零动作
    assert "动作描写：默认不使用" in ctx.budget_text
    return "work_mode + explain + 零节奏提示"


# ──── 测试5：稳定性（20 轮）────

def test_stability(chat_id):
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.agent_id == "pianai").first()
    finally:
        db.close()
    sig_base = render_signature_text(get_agent_signature("pianai"))
    quirk_base = render_quirk_text(get_agent_quirk("pianai"))
    questions = ["我失败了怎么办？", "今天吃什么？", "你觉得我这样对吗", "我又失败了"] * 5  # 20 轮
    sig_texts, quirk_texts = set(), set()
    mode_counter = {}
    for q in questions:
        ctx = build_persona_context(agent, None, None, user_message=q)
        assert ctx.signature_text == sig_base, "Signature 发生变化（人格漂移）"
        assert ctx.quirk_text == quirk_base, "人味层文本发生变化"
        sig_texts.add(ctx.signature_text)
        quirk_texts.add(ctx.quirk_text)
        key = tuple(ctx.response_modes)
        mode_counter[key] = mode_counter.get(key, 0) + 1
        # 无主动心理分析：全局禁止层恒定存在
        assert "禁止用这句话给用户下定义" in ctx.restrictions_text
    assert len(sig_texts) == 1 and len(quirk_texts) == 1
    # 不固定模板：不同问题产出不同 response_mode 组合
    assert len(mode_counter) >= 3, f"回应模式过于单一：{mode_counter}"
    return f"20/20 一致，modes 组合 {len(mode_counter)} 种"


# ──── 附加 A：注入链顺序 ────

def test_injection_order(chat_id):
    sp, ctx = build_prompt(chat_id, "聊聊最近的事")
    i_identity = sp.find("Identity V16")
    i_signature = sp.find("你的交流倾向")
    i_quirk = sp.find("交流习惯与人味")
    i_personality = sp.find("适度提供建议和分析")
    i_budget = sp.find("表达预算")
    assert i_identity >= 0, "identity V16 未注入"
    assert i_identity < i_signature < i_quirk, "顺序错误：Identity < Signature < Human Imperfection"
    assert i_quirk < i_personality, "人味层应在 Personality Level 之前"
    assert i_personality < i_budget, "Personality 应在 Performance/Budget 之前"
    return "Identity < Signature < 人味层 < Personality < Performance"


# ──── 附加 B：倾向式措辞 + 无重复人格规则 ────

def test_wording(chat_id):
    sp, ctx = build_prompt(chat_id, "聊聊最近的事")
    q = ctx.quirk_text
    assert "不是必须执行的规则" in q, "缺少『非强制规则』声明"
    assert "不要为了表现人味而刻意表演" in q
    assert "你必须吐槽" not in q, "出现命令式措辞"
    # 禁止虚构条款存在
    assert "虚构个人经历" in q and "虚构记忆" in q and "虚构现实生活状态" in q
    # 无重复人格规则：签名段与人味段各只出现一次
    assert sp.count("## 你的交流倾向") == 1, "签名层重复注入"
    assert sp.count("## 交流习惯与人味") == 1, "人味层重复注入"
    # 不允许的假人格表述不在 prompt 中
    assert "我今天心情不好" not in sp
    return "倾向式措辞 + 禁虚构 + 无重复段"


def main():
    print("=" * 70)
    print("Pianai V16 Human Imperfection Layer 验证")
    print("=" * 70)
    db = SessionLocal()
    chat_id = seed_pianai(db)
    db.close()

    run("测试1 普通聊天（不分析不长篇）", lambda: test_casual(chat_id))
    run("测试2 失败（不鸡汤 + 温和挑战）", lambda: test_failure(chat_id))
    run("测试3 连续玩笑（humor↑ 且 ±20 钳制）", lambda: test_consecutive_jokes(chat_id))
    run("测试4 工作模式（自动专业）", lambda: test_work(chat_id))
    run("测试5 稳定性（20 轮）", lambda: test_stability(chat_id))
    run("附加A 注入链顺序", lambda: test_injection_order(chat_id))
    run("附加B 倾向式措辞 + 无重复", lambda: test_wording(chat_id))

    print("=" * 70)
    if failures:
        print(f"结果：{len(failures)} 项失败 -> {failures}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
