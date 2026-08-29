# -*- coding: utf-8 -*-
"""Persona System V2 集成验证（E2E：ChatContextBuilder 真实链路）。

覆盖任务验收标准（运行时验证，非单测）：
  测试1 「我今天好累」→ 像朋友回应（Relationship 低落模式 + Human Conversation 禁心理分析）
  测试2 「我是不是很失败？」→ 自然交流（禁止连续安慰/心理报告）
  测试3 「帮我写一个方案」→ 关闭陪伴模式，进入工作模式（serious）
  测试4 交流次数递增 → 关系距离变化（陌生→熟悉→亲近→长期陪伴）

另验证：
  - 所有 Agent 默认注入 Human Conversation Rules + Expression Budget + 禁止表达
  - 仅 Pianai 注入 Relationship Layer 与专属禁止表达
  - coder（无 PersonaTemplate）也获得基础行为层，且 emoji 预算为 0
  - expression_profile 结构化配置差异（companion vs professional）

运行：
  python backend/tests/test_persona_v2_integration.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import tempfile
import time
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# 临时环境隔离：必须在 import main 之前完成（config 在导入时读取路径/DB）
# ---------------------------------------------------------------------------
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_personaE2E_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./persona_v2_e2e_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402 (persona_templates 表)
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.core.agent_runtime.context_builder import ChatContextBuilder, ContextBuildInput  # noqa: E402
from app.models.agent import Agent, Chat, Message  # noqa: E402

results = []
failures = []


def run(name, fn):
    t0 = time.monotonic()
    try:
        detail = fn()
        results.append({"name": name, "ok": True, "elapsed_ms": int((time.monotonic() - t0) * 1000), "detail": detail})
        print(f"  PASS  {name}  ({int((time.monotonic() - t0) * 1000)}ms)")
    except AssertionError as e:
        results.append({"name": name, "ok": False, "elapsed_ms": int((time.monotonic() - t0) * 1000), "detail": str(e)})
        failures.append(name)
        print(f"  FAIL  {name}\n        {e}")


# ---------------------------------------------------------------------------
# 数据准备
# ---------------------------------------------------------------------------

def seed_agent(db, agent_id, expression_profile):
    existing = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if existing:
        return existing
    agent = Agent(
        agent_id=agent_id,
        name=agent_id,
        identity=f"你是{agent_id}。",
        system_prompt=f"你是{agent_id}。",
        capabilities=[],
        expression_profile=expression_profile,
    )
    db.add(agent)
    db.commit()
    return agent


def seed_chat(db, agent_id, mode="build"):
    chat = Chat(agent_id=agent_id, title="persona-e2e", mode=mode)
    db.add(chat)
    db.commit()
    return chat


def seed_user_messages(db, agent_id, count):
    """造历史 user 消息（关系层交流次数统计用）。"""
    chat = seed_chat(db, agent_id)
    for _ in range(count):
        msg = Message(chat_id=chat.id, role="user", content="hello")
        db.add(msg)
    db.commit()


async def build_prompt(chat_id, content):
    builder = ChatContextBuilder()
    built = await builder.build(ContextBuildInput(chat_id=chat_id, content=content))
    return built


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------

def _test_pianai_low_mood_friend_reply() -> dict:
    """测试1：『我今天好累』→ 朋友式回应指令（非心理分析报告）。"""
    db = SessionLocal()
    try:
        agent = seed_agent(db, "pianai", "companion")
        chat = seed_chat(db, "pianai")
        built = asyncio_run(build_prompt(chat.id, "我今天好累"))
        sp = built.system_prompt
        checks = {
            "Human Conversation Rules 注入": "人类对话规则" in sp,
            "先回应再分析": "先回应，再分析" in sp,
            "禁止心理报告句式": "心理报告式" in sp or "心理评估" in sp,
            "Expression Budget 注入": "表达预算" in sp,
            "禁止连续表演": "不要连续表演" in sp,
            "Relationship Layer 注入": "长期朋友关系" in sp,
            "低落情绪→安静陪伴": "安静陪伴" in sp and "少开玩笑" in sp,
            "朋友式接话示例": "破事" in sp or "怎么了" in sp,
            "禁止心理分析套话": "你其实" in sp,
            "Pianai 专属禁止": "我永远陪着你" in sp,
            "不用『根据我的记忆』": "根据我的记忆" in sp,
        }
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"缺失: {failed}"
        return {"checks": len(checks), "mood": built.persona_context.mood, "distance": built.persona_context.relationship_distance}
    finally:
        db.close()


def _test_pianai_failure_question_natural() -> dict:
    """测试2：『我是不是很失败？』→ 自然交流（不连续安慰）。"""
    db = SessionLocal()
    try:
        agent = seed_agent(db, "pianai", "companion")
        chat = seed_chat(db, "pianai")
        built = asyncio_run(build_prompt(chat.id, "我是不是很失败？"))
        sp = built.system_prompt
        checks = {
            "情绪识别为低落": built.persona_context.mood == "low",
            "禁止连续多段安慰": "连续多段安慰" in sp,
            "禁止心理报告式解读": "心理报告式解读" in sp,
            "不输出心理分析报告": "心理评估" in sp,
        }
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"缺失: {failed}"
        return {"checks": len(checks)}
    finally:
        db.close()


def _test_serious_task_closes_companion_mode() -> dict:
    """测试3：『帮我写一个方案』→ 关闭陪伴模式，进入工作模式。"""
    db = SessionLocal()
    try:
        agent = seed_agent(db, "pianai", "companion")
        chat = seed_chat(db, "pianai")
        built = asyncio_run(build_prompt(chat.id, "帮我写一个方案"))
        sp = built.system_prompt
        checks = {
            "情绪识别为认真讨论": built.persona_context.mood == "serious",
            "关闭陪伴话术": "关闭陪伴话术" in sp,
            "进入工作模式": "工作模式" in sp,
            "减少玩笑": "减少玩笑" in sp,
        }
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"缺失: {failed}"
        return {"checks": len(checks)}
    finally:
        db.close()


def _test_relationship_distance_progression() -> dict:
    """测试4：交流次数递增 → 关系距离变化（陌生→熟悉→亲近→长期陪伴）。"""
    from app.core.persona_engine import compute_relationship_distance
    stages = [compute_relationship_distance(n) for n in (0, 5, 20, 50)]
    assert stages == ["陌生", "熟悉", "亲近", "长期陪伴"], stages

    db = SessionLocal()
    try:
        agent = seed_agent(db, "pianai", "companion")
        # 10 轮后：熟悉（5 ≤ n < 20）
        seed_user_messages(db, "pianai", 10)
        chat = seed_chat(db, "pianai")
        built = asyncio_run(build_prompt(chat.id, "你好"))
        assert built.persona_context.relationship_distance == "熟悉", built.persona_context.relationship_distance
        assert "累计交流" in built.system_prompt
        return {"stages": stages, "after_10_turns": built.persona_context.relationship_distance}
    finally:
        db.close()


def _test_coder_no_template_still_gets_layers() -> dict:
    """coder（无 PersonaTemplate）→ 基础行为层全注入 + emoji 预算 0 + 无关系层。"""
    db = SessionLocal()
    try:
        agent = seed_agent(db, "coder", "coder")
        chat = seed_chat(db, "coder")
        built = asyncio_run(build_prompt(chat.id, "帮我写一个 Python 脚本"))
        sp = built.system_prompt
        pc = built.persona_context
        checks = {
            "Human Conversation Rules": "人类对话规则" in sp,
            "Expression Budget": "表达预算" in sp,
            "禁止表达": "禁止表达" in sp,
            "emoji 预算为 0": "不使用" in sp and pc.budget.emoji_max == 0,
            "无 Relationship Layer": "长期朋友关系" not in sp,
            "无 Pianai 专属禁止": "我永远陪着你" not in sp,
            "非 pianai 不触发情绪检测": pc.mood == "neutral",
        }
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"缺失: {failed}"
        return {"checks": len(checks)}
    finally:
        db.close()


def _test_profile_config_structure() -> dict:
    """任务七：expression_profile 结构化配置差异。"""
    from app.core.persona_engine import get_profile_config
    companion = get_profile_config("companion")
    professional = get_profile_config("professional")
    creative = get_profile_config("creative")
    checks = {
        "companion emoji 提高": companion["budget"].emoji_max == 3 and companion["emoji_level"] == "high",
        "companion warmth 高": companion["warmth"] == "high",
        "professional 无 emoji": professional["budget"].emoji_max == 0 and professional["emoji_level"] == "none",
        "professional 无富文本": professional["budget"].rich_text_policy == "none",
        "creative 允许文学表达": creative["budget"].rich_text_policy == "allowed",
        "全部禁止连续表演": all(not c["budget"].continuous_acting for c in (companion, professional, creative)),
    }
    failed = [k for k, v in checks.items() if not v]
    assert not failed, f"配置不符: {failed}"
    return {"checks": len(checks)}


def _test_all_agents_default_behavior() -> dict:
    """所有 Agent 默认加载 Human Conversation Rules（含无 expression_profile 的）。"""
    db = SessionLocal()
    try:
        agent = seed_agent(db, "plain", None)
        chat = seed_chat(db, "plain")
        built = asyncio_run(build_prompt(chat.id, "你好"))
        sp = built.system_prompt
        pc = built.persona_context
        checks = {
            "无 profile 也注入行为层": "人类对话规则" in sp,
            "无 profile 也注入预算": "表达预算" in sp,
            "无 profile 也注入禁止表达": "禁止表达" in sp,
            "fallback 默认预算": pc.budget.emoji_max == 2,
            "无关系层": "长期朋友关系" not in sp,
        }
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"缺失: {failed}"
        return {"checks": len(checks)}
    finally:
        db.close()


_LOOP = None


def asyncio_run(coro):
    global _LOOP
    import asyncio
    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP.run_until_complete(coro)


def main():
    print("=" * 70)
    print("MfkAgent Persona System V2 集成验证")
    print(f"临时工作目录: {_TEMP_DIR}")
    print("=" * 70)
    run("测试1 「我今天好累」→ 朋友式回应（非心理分析）", _test_pianai_low_mood_friend_reply)
    run("测试2 「我是不是很失败？」→ 自然交流", _test_pianai_failure_question_natural)
    run("测试3 「帮我写一个方案」→ 工作模式", _test_serious_task_closes_companion_mode)
    run("测试4 交流次数递增 → 关系距离四阶段", _test_relationship_distance_progression)
    run("coder 无模板 → 基础层注入 + emoji 0 + 无关系层", _test_coder_no_template_still_gets_layers)
    run("任务七 expression_profile 结构化配置差异", _test_profile_config_structure)
    run("无 profile Agent → 默认基础行为层", _test_all_agents_default_behavior)

    print("=" * 70)
    passed = sum(1 for r in results if r["ok"])
    print(f"结果: {passed}/{len(results)} 通过")
    print("=" * 70)

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (BACKEND_DIR / "tests" / "phase_persona_v2_integration_report.md")
    lines = [
        "# MfkAgent Persona System V2 集成验证报告\n",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 链路: ChatContextBuilder.build() 真实组装 → BuiltContext.system_prompt 断言",
        "",
        "## 结果总览\n",
        "| # | 用例 | 结果 | 耗时 |",
        "|---|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |")
    lines.append(f"\n**通过率: {passed}/{len(results)}**\n")
    lines.append("## 验证明细\n")
    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r['name']}\n")
        d = r["detail"]
        if isinstance(d, dict):
            for k, v in d.items():
                lines.append(f"- {k}: {v}")
        else:
            lines.append(f"- 说明: {d}")
        lines.append("")
    if failures:
        lines.append(f"❌ 失败项: {failures}\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
