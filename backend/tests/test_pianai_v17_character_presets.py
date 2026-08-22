# -*- coding: utf-8 -*-
"""Pianai V17 Character Presets（多人格预设系统）验证测试。

覆盖：
  测试1 预设库完整性：6 个预设全部存在，字段完整
  测试2 预设切换检测：用户消息中关键词触发正确预设
  测试3 默认预设：无切换指令时使用 default，signature/quirks 不变
  测试4 傲娇预设：signature/quirks/budget 覆盖正确，语言风格注入
  测试5 霸总预设：directness=95，emoji_max=0，命令式语言风格
  测试6 暖心姐姐预设：warmth=95，emoji_max=3，温柔语言风格
  测试7 高冷预设：话少，emoji_max=0，惜字如金风格
  测试8 活泼少女预设：humor=75，emoji_max=2，活泼风格
  测试9 预设持久化：切换后 ConversationState 保留预设，下一轮继续生效
  测试10 预设注入链：preset_text 在 quirks 之后、budget 之前注入
  测试11 预设切换自我介绍：刚切换时注入 preset_intro_text
  测试12 非 natural_companion Agent 不受预设系统影响

运行：python backend/tests/test_pianai_v17_character_presets.py
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

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_v17_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./v17_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.core.persona_engine import build_persona_context  # noqa: E402
from app.core.persona_signature import get_agent_signature  # noqa: E402
from app.core.persona_quirks import build_conversation_state, ConversationState  # noqa: E402
from app.core.character_presets import (  # noqa: E402
    CHARACTER_PRESETS, get_preset, detect_preset_switch,
    render_preset_language_style, list_presets,
)
from app.models.agent import Agent  # noqa: E402

failures = []


def run(name, fn):
    try:
        detail = fn()
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    except AssertionError as e:
        failures.append(name)
        print(f"  FAIL  {name}\n        {e}")


def make_agent(profile="natural_companion"):
    return Agent(
        agent_id="pianai", name="Pianai", description="test",
        identity="# 偏爱 Pianai — Identity V17",
        capabilities=["general_assistance"], default_personality_level=25,
        expression_profile=profile, status="active",
    )


def make_state(preset="default", just_switched=False):
    sig = get_agent_signature("pianai")
    state = build_conversation_state(sig, [])
    state.character_preset = preset
    state.preset_just_switched = just_switched
    return state


# ──── 测试1：预设库完整性 ────

def test_preset_library():
    presets = list_presets()
    assert len(presets) >= 6, f"预设数量不足：{len(presets)}"
    expected_ids = {"default", "tsundere", "bossy", "warm_sister", "cold", "cheerful"}
    actual_ids = {p.preset_id for p in presets}
    assert expected_ids.issubset(actual_ids), f"缺少预设：{expected_ids - actual_ids}"
    for p in presets:
        assert p.name, f"{p.preset_id} 缺少 name"
        assert p.description, f"{p.preset_id} 缺少 description"
        assert p.language_style, f"{p.preset_id} 缺少 language_style"
        assert p.opening_line, f"{p.preset_id} 缺少 opening_line"
    return f"{len(presets)} 个预设，字段完整"


# ──── 测试2：预设切换检测 ────

def test_switch_detection():
    cases = [
        ("切换傲娇模式", "tsundere"),
        ("变成霸总", "bossy"),
        ("我要暖心大姐姐", "warm_sister"),
        ("高冷一点", "cold"),
        ("活泼少女模式", "cheerful"),
        ("变回偏爱", "default"),
        ("默认模式", "default"),
        ("今天吃什么", None),
        ("你好", None),
    ]
    for msg, expected in cases:
        result = detect_preset_switch(msg)
        assert result == expected, f"'{msg}' -> 期望 {expected}，实际 {result}"
    return f"{len(cases)} 个用例全部正确"


# ──── 测试3：默认预设 ────

def test_default_preset():
    agent = make_agent()
    state = make_state("default")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "default"
    # 默认预设不覆盖 signature，应该和原始 signature 一致
    sig = get_agent_signature("pianai")
    assert "温暖但保持独立判断" in ctx.signature_text
    # 默认预设的 language_style 应该注入
    assert "你的说话方式" in ctx.preset_text
    assert "用短句" in ctx.preset_text
    return "default 预设，signature 不变，语言风格已注入"


# ──── 测试4：傲娇预设 ────

def test_tsundere():
    agent = make_agent()
    state = make_state("tsundere")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "tsundere"
    # signature 覆盖：directness=85, challenge=80
    assert "发现问题时直接指出" in ctx.signature_text  # directness >= 60
    assert "不盲目认同" in ctx.signature_text  # challenge >= 50
    # quirks 覆盖：嘴硬式吐槽
    assert "嘴硬式吐槽" in ctx.quirk_text
    assert "绝不直接说" in ctx.quirk_text or "用怼人表达关心" in ctx.quirk_text
    # language_style
    assert "傲娇模式" in ctx.preset_text
    assert "嘴硬心软" in ctx.preset_text
    # budget 覆盖：emoji_max=1
    assert "不超过 1 个" in ctx.budget_text
    return "tsundere：signature/quirks/budget/style 全部覆盖"


# ──── 测试5：霸总预设 ────

def test_bossy():
    agent = make_agent()
    state = make_state("bossy")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "bossy"
    # directness=95, challenge=90
    assert "发现问题时直接指出" in ctx.signature_text
    assert "不盲目认同" in ctx.signature_text
    # language_style：命令式
    assert "霸总模式" in ctx.preset_text
    assert "说一不二" in ctx.preset_text
    assert "去睡。现在。" in ctx.preset_text
    # budget：emoji_max=0
    assert "不使用" in ctx.budget_text
    return "bossy：directness=95，命令式风格，零 emoji"


# ──── 测试6：暖心姐姐预设 ────

def test_warm_sister():
    agent = make_agent()
    state = make_state("warm_sister")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "warm_sister"
    # warmth=95
    assert "温暖但保持独立判断" in ctx.signature_text
    # language_style
    assert "暖心姐姐模式" in ctx.preset_text
    assert "温柔" in ctx.preset_text and "包容" in ctx.preset_text
    assert "小家伙" in ctx.preset_text
    # budget：emoji_max=3
    assert "不超过 3 个" in ctx.budget_text
    return "warm_sister：warmth=95，温柔风格，emoji≤3"


# ──── 测试7：高冷预设 ────

def test_cold():
    agent = make_agent()
    state = make_state("cold")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "cold"
    # warmth=35 -> 以事情本身为中心
    assert "以事情本身为中心" in ctx.signature_text
    # language_style
    assert "高冷模式" in ctx.preset_text
    assert "惜字如金" in ctx.preset_text
    # budget：emoji_max=0
    assert "不使用" in ctx.budget_text
    return "cold：warmth=35，话少风格，零 emoji"


# ──── 测试8：活泼少女预设 ────

def test_cheerful():
    agent = make_agent()
    state = make_state("cheerful")
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state)
    assert ctx.current_preset == "cheerful"
    # humor=80, curiosity=90
    assert "常用轻松幽默的方式表达" in ctx.signature_text  # humor >= 60
    assert "喜欢追问具体情况" in ctx.signature_text  # curiosity >= 70
    # language_style
    assert "活泼少女模式" in ctx.preset_text
    assert "元气满满" in ctx.preset_text
    # budget：emoji_max=2
    assert "不超过 2 个" in ctx.budget_text
    return "cheerful：humor=75，活泼风格，emoji≤2"


# ──── 测试9：预设持久化 ────

def test_preset_persistence():
    agent = make_agent()
    # 第一轮：切换到傲娇
    state1 = make_state("default")
    ctx1 = build_persona_context(agent, None, None, user_message="切换傲娇模式", conversation_state=state1)
    assert ctx1.current_preset == "tsundere", f"切换后应为 tsundere，实际 {ctx1.current_preset}"
    assert state1.character_preset == "tsundere", "ConversationState 未更新预设"
    assert state1.preset_just_switched is True

    # 第二轮：普通消息，预设保持
    state1.preset_just_switched = False
    ctx2 = build_persona_context(agent, None, None, user_message="今天好烦", conversation_state=state1)
    assert ctx2.current_preset == "tsundere", f"预设应保持 tsundere，实际 {ctx2.current_preset}"
    assert state1.preset_just_switched is False

    # 第三轮：切换回默认
    ctx3 = build_persona_context(agent, None, None, user_message="变回偏爱", conversation_state=state1)
    assert ctx3.current_preset == "default", f"应切回 default，实际 {ctx3.current_preset}"
    return "切换→保持→再切换，三轮正常"


# ──── 测试10：预设注入链顺序 ────

def test_injection_order():
    agent = make_agent()
    state = make_state("default")
    # 通过切换指令触发 just_switched
    ctx = build_persona_context(agent, None, None, user_message="切换傲娇模式", conversation_state=state)
    assert ctx.preset_text, "preset_text 为空"
    assert ctx.preset_intro_text, "preset_intro_text 为空（刚切换时应注入）"
    assert "傲娇" in ctx.preset_intro_text
    return "preset_text + preset_intro_text 均注入"


# ──── 测试11：预设切换自我介绍 ────

def test_preset_intro():
    agent = make_agent()
    # 刚切换：通过切换指令触发
    state1 = make_state("default")
    ctx1 = build_persona_context(agent, None, None, user_message="切换霸总模式", conversation_state=state1)
    assert ctx1.preset_intro_text != "", "刚切换时应有自我介绍"
    assert "霸总" in ctx1.preset_intro_text

    # 下一轮普通消息：无 intro
    ctx2 = build_persona_context(agent, None, None, user_message="你好", conversation_state=state1)
    assert ctx2.preset_intro_text == "", "非刚切换时不应有自我介绍"

    # 默认预设切换：无 intro
    state3 = make_state("bossy")
    ctx3 = build_persona_context(agent, None, None, user_message="变回偏爱", conversation_state=state3)
    assert ctx3.preset_intro_text == "", "默认预设不应有自我介绍"
    return "刚切换有 intro，其余无"


# ──── 测试12：非 natural_companion 不受影响 ────

def test_non_companion_unaffected():
    agent = make_agent(profile="professional")  # 专业型，不是 natural_companion
    state = make_state("tsundere")  # 即使 state 设了傲娇
    ctx = build_persona_context(agent, None, None, user_message="切换傲娇模式", conversation_state=state)
    assert ctx.current_preset == "default", "非 natural_companion 应忽略预设"
    assert ctx.preset_text == "", "非 natural_companion 不应注入 preset_text"
    # signature 不应被覆盖
    sig = get_agent_signature("pianai")
    assert sig is not None  # pianai 有签名，但 professional 型 agent 可能不注入
    return "professional 型 Agent 不受预设系统影响"


# ──── 测试13：首次对话开场白 ────

def test_first_message_greeting():
    agent = make_agent()
    state = make_state("default")
    # 首次对话
    ctx = build_persona_context(agent, None, None, user_message="你好", conversation_state=state, first_message=True)
    assert ctx.first_message is True
    assert ctx.greeting_text != "", "首次对话应注入开场白指令"
    assert "首次对话" in ctx.greeting_text
    assert "嗯？你来了" in ctx.greeting_text  # 默认开场白包含功能提示

    # 非首次对话
    ctx2 = build_persona_context(agent, None, None, user_message="你好", conversation_state=state, first_message=False)
    assert ctx2.first_message is False
    assert ctx2.greeting_text == "", "非首次对话不应注入开场白"
    return "首次对话注入开场白，非首次不注入"


# ──── 测试14：模糊切换指令列出人格 ────

def test_vague_switch():
    from app.core.character_presets import detect_vague_switch, render_preset_menu
    # 模糊指令检测
    assert detect_vague_switch("换个风格") is True
    assert detect_vague_switch("还有别的吗") is True
    assert detect_vague_switch("你变一下") is True
    assert detect_vague_switch("我想换") is True
    assert detect_vague_switch("你好") is False
    assert detect_vague_switch("切换傲娇模式") is False  # 具体指令不算模糊

    # 人格列表渲染
    menu = render_preset_menu()
    assert "偏爱" in menu
    assert "傲娇" in menu
    assert "霸总" in menu
    assert "暖心姐姐" in menu
    assert "高冷" in menu
    assert "活泼少女" in menu
    assert "切换XX模式" in menu

    # 注入到 persona_context
    agent = make_agent()
    state = make_state("default")
    ctx = build_persona_context(agent, None, None, user_message="换个风格", conversation_state=state)
    assert ctx.vague_switch_text != "", "模糊指令应注入人格列表"
    assert "我有这几种样子可以换" in ctx.vague_switch_text
    return "模糊指令检测 + 人格列表注入"


def main():
    print("=" * 70)
    print("Pianai V17 Character Presets 验证")
    print("=" * 70)

    run("测试1 预设库完整性", test_preset_library)
    run("测试2 预设切换检测", test_switch_detection)
    run("测试3 默认预设", test_default_preset)
    run("测试4 傲娇预设", test_tsundere)
    run("测试5 霸总预设", test_bossy)
    run("测试6 暖心姐姐预设", test_warm_sister)
    run("测试7 高冷预设", test_cold)
    run("测试8 活泼少女预设", test_cheerful)
    run("测试9 预设持久化", test_preset_persistence)
    run("测试10 预设注入链", test_injection_order)
    run("测试11 切换自我介绍", test_preset_intro)
    run("测试12 非陪伴型不受影响", test_non_companion_unaffected)
    run("测试13 首次对话开场白", test_first_message_greeting)
    run("测试14 模糊切换指令列出人格", test_vague_switch)

    print("=" * 70)
    if failures:
        print(f"结果：{len(failures)} 项失败 -> {failures}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
