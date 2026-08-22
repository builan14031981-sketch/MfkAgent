"""MfkAgent 会话压缩 G6-B 端到端验证（Phase G6-B E2E）。

链路：真实 ChatContextBuilder → 历史消息 payload → 压缩引擎 → 模型 payload。

覆盖：
  E2E-1. 真实 ContextBuilder 生成 payload（1 system + 24 条历史），消息数 > 20
  E2E-2. 压缩触发正常：压缩后消息数明显减少
  E2E-3. system message 保留
  E2E-4. 存在【历史记忆摘要】节点
  E2E-5. 最近 keep_recent=4 条消息仍然存在
  E2E-6. 摘要包含关键变量（AgentRuntime / TaskGraph / FastAPI）
  E2E-7. 原始 messages 未被修改（数量与内容不变）
  E2E-8. model_service.call_once 被 mock 调用，摘要正确注入

限制（均已遵守）：
  - 不修改任何生产代码
  - 不修改 AgentRuntime 主链（run / run_stream）
  - 不调用真实 LLM（model_service.call_once 全 mock）
  - 不创建新架构模块（仅新增测试脚本）

运行：
  python backend/tests/test_g6b_compression_e2e.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import time
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# ──── 临时 DB 环境（先于 app 导入设置）────
_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_g6b_e2e_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_g6b_e2e.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.models.agent import Chat, Agent, Message, Project  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.agent import AgentRuntime  # noqa: E402

AGENT_ID = "g6b_e2e_coder"
AGENT_IDENTITY = "你是一名精通 Python 与系统架构的研发助手。"
SUMMARY_TEXT = "MfkAgent 使用 FastAPI 和 AgentRuntime 架构，已经完成 TaskGraph 和 Planner。"

results = []
failures = []


def run(name, fn):
    t0 = time.monotonic()
    try:
        detail = fn()
        ok = detail.pop("all_ok", True)
        elapsed = (time.monotonic() - t0) * 1000
        results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
        if ok:
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        else:
            failures.append(f"{name}: {detail}")
            print(f"  FAIL  {name}  ({elapsed:.0f}ms)")
    except AssertionError as e:
        results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
        failures.append(f"{name}: {e}")
        print(f"  FAIL  {name}\n        {e}")
    except Exception as e:
        results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
        failures.append(f"{name}: {e!r}")
        print(f"  ERROR {name}\n        {e!r}")


# ═════════════════════════════════════════════════════════════════════════
# Fixtures：真实 DB（Chat / Agent / Project / 24 条历史消息）
# ═════════════════════════════════════════════════════════════════════════

def _make_agent(db) -> None:
    if db.query(Agent).filter(Agent.agent_id == AGENT_ID).first():
        return
    db.add(Agent(
        agent_id=AGENT_ID,
        name="G6B E2E Coder",
        identity=AGENT_IDENTITY,
        capabilities=["software_development"],
    ))
    db.commit()


def _make_project(db) -> int:
    path = _TEMP_DIR / "e2e_project"
    path.mkdir(parents=True, exist_ok=True)
    p = Project(name="G6B-E2E-Project", path=str(path))
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


def _make_chat(db, project_id: int) -> int:
    c = Chat(
        project_id=project_id,
        project_path=(db.query(Project).filter(Project.id == project_id).first().path),
        agent_id=AGENT_ID,
        title="G6B-E2E-Chat",
        personality_level=70,
        mode="build",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def _seed_history(db, chat_id: int) -> None:
    """构造 24 条 user/assistant 交替历史（含项目信息/文件路径/技术决策/最终结论）。"""
    lines = [
        ("user", "我们要为 MfkAgent 搭建后端服务，先决定技术栈。"),
        ("assistant", "建议使用 FastAPI 作为后端框架，异步支持好、文档完备。"),
        ("user", "决定使用 FastAPI 作为后端框架，同时确认执行入口。"),
        ("assistant", "确认 Runtime 使用 AgentRuntime 作为执行入口，统一封装 LLM 与工具调用。"),
        ("user", "Runtime 的内部结构如何组织？"),
        ("assistant", "AgentRuntime 位于 backend/app/core/agent_runtime/，包含 agent.py / context.py / recorder.py。"),
        ("user", "任务规划部分我们引入了 TaskGraph。"),
        ("assistant", "TaskGraph 依赖图位于 backend/app/core/task_graph/，由 Planner 输出 Plan 转换而来。"),
        ("user", "会话压缩策略怎么接入？"),
        ("assistant", "压缩引擎 compress_history 作为独立接口，在发送前对长历史做摘要。"),
        ("user", "Planner 生成计划后，历史消息里需要保留关键决策。"),
        ("assistant", "保留 FastAPI / AgentRuntime / TaskGraph 等关键变量，压缩时写入摘要节点。"),
        ("user", "请读取 backend/app/main.py 查看路由挂载情况。"),
        ("assistant", "main.py 已挂载 chat / models / settings 等路由，使用 FastAPI 应用实例。"),
        ("user", "记忆系统的文件在哪？"),
        ("assistant", "记忆实现位于 backend/app/services/tools/ 与 memory 相关模块，通过 MemoryItem 三作用域管理。"),
        ("user", "工具执行需要审批闭环吗？"),
        ("assistant", "需要：stream 路径支持审批，非流式路径明确拒绝并提示改用流式。"),
        ("user", "验证工具动作用什么机制？"),
        ("assistant", "Verifier 基于程序化验证策略，对 write_file / run_command 等做确定性校验。"),
        ("user", "计划步骤如何与任务节点对应？"),
        ("assistant", "Plan 线性步骤经 TaskGraphBuilder 转为 task_0..task_N，构成依赖链。"),
        ("user", "那失败传播如何处理？"),
        ("assistant", "单任务失败后级联跳过依赖链上后续节点，图中断时收敛到终态。"),
        ("user", "前端如何展示任务进度？"),
        ("assistant", "前端 TaskProgressCard 消费 task_started/task_completed/task_failed/task_skipped 事件。"),
        ("user", "当前最后结论是什么？"),
        ("assistant", "MfkAgent 使用 FastAPI 和 AgentRuntime 架构，已经完成 TaskGraph 和 Planner。"),
        ("user", "下一步计划做什么？"),
        ("assistant", "推进 Scheduler/Executor 抽象，稳定任务执行链后接入自动化规划。"),
        ("user", "压缩后这些历史还需要吗？"),
        ("assistant", "最近 4 条保留为工作窗口，更早内容由摘要节点承载。"),
        ("user", "好的，我们验证一下压缩链路。"),
        ("assistant", "收到，准备验证 ContextBuilder → 压缩 → 模型 payload 全链路。"),
    ]
    base = time.time()
    for i, (role, content) in enumerate(lines):
        db.add(Message(
            chat_id=chat_id,
            role=role,
            content=content,
            created_at=__import__("datetime").datetime.fromtimestamp(base + i),
        ))
    db.commit()


def _build_payload(chat_id: int):
    """真实 ChatContextBuilder 生成 payload（同步包装；use_tools=False 零 LLM 依赖）。"""
    return asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(
            chat_id=chat_id,
            content="验证会话压缩链路",
            use_tools=False,
            personality_level=70,
        )
    ))


# ═════════════════════════════════════════════════════════════════════════
# 共享状态：一次构建 + 一次压缩，供多个断言复用
# ═════════════════════════════════════════════════════════════════════════

_PAYLOAD = None   # BuiltContext
_ORIGINAL = None  # 压缩前的 messages 快照
_COMPRESSED = None


def _setup_e2e():
    global _PAYLOAD, _ORIGINAL, _COMPRESSED
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db)
        cid = _make_chat(db, pid)
        _seed_history(db, cid)
    finally:
        db.close()

    _PAYLOAD = _build_payload(cid)
    _ORIGINAL = [{"role": m.role, "content": m.content} for m in _PAYLOAD.messages]

    async def _compress():
        rt = AgentRuntime()
        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = __import__(
                "app.services.model", fromlist=["SingleCallResult"]
            ).SingleCallResult(
                content=SUMMARY_TEXT,
                tool_calls=None,
                finish_reason="stop",
                usage={"total_tokens": 60},
            )
            compressed = await rt.compress_history(_PAYLOAD.messages, keep_recent=4)
        return compressed, mock_call

    _COMPRESSED, _mock = asyncio.run(_compress())
    return _mock


def _compressed_roles():
    if _COMPRESSED and hasattr(_COMPRESSED[0], "role"):
        return [m.role for m in _COMPRESSED]
    return [m["role"] for m in _COMPRESSED]


def _compressed_contents():
    if _COMPRESSED and hasattr(_COMPRESSED[0], "role"):
        return [m.content for m in _COMPRESSED]
    return [m["content"] for m in _COMPRESSED]


# ═════════════════════════════════════════════════════════════════════════
# E2E 用例
# ═════════════════════════════════════════════════════════════════════════

def _test_e2e_1_payload_over_20():
    total = len(_ORIGINAL)
    assert total > 20, f"payload 消息数应 > 20，实际 {total}"
    return {"before_count": total, "over_20": True}


def _test_e2e_2_compression_reduced():
    before = len(_ORIGINAL)
    after = len(_COMPRESSED)
    assert after < before, f"压缩后应明显减少，{before} -> {after}"
    return {"before": before, "after": after, "reduced": after < before}


def _test_e2e_3_system_preserved():
    assert _compressed_roles()[0] == "system", "压缩后首条应为 system"
    # system 内容与原始首条一致（对象保持原引用）
    orig_first = _ORIGINAL[0]
    comp_first = _COMPRESSED[0]
    if hasattr(comp_first, "content"):
        assert comp_first.content == orig_first["content"]
    else:
        assert comp_first["content"] == orig_first["content"]
    return {"system_role": _compressed_roles()[0], "preserved": True}


def _test_e2e_4_memory_node_exists():
    roles = _compressed_roles()
    assert "user" in roles, "应存在 memory 节点（user role）"
    memory_idx = roles.index("user")  # 首个非 system 即 memory 节点
    mem_content = _compressed_contents()[memory_idx]
    assert mem_content.startswith("【历史记忆摘要】"), "memory 节点应以【历史记忆摘要】开头"
    return {"memory_index": memory_idx, "prefix_ok": True}


def _test_e2e_5_recent_4_preserved():
    # 最近 4 条 = 原始历史（去掉首条 system）的最后 4 条
    history = _ORIGINAL[1:]
    recent_expected = [m["content"] for m in history[-4:]]
    comp_contents = _compressed_contents()
    tail = comp_contents[-4:]
    assert tail == recent_expected, f"最近 4 条应保留\n 期望: {recent_expected}\n 实际: {tail}"
    return {"recent_preserved": tail == recent_expected}


def _test_e2e_6_summary_key_vars():
    mem_content = next(
        c for c in _compressed_contents() if c.startswith("【历史记忆摘要】")
    )
    missing = [k for k in ("AgentRuntime", "TaskGraph", "FastAPI") if k not in mem_content]
    assert not missing, f"摘要缺少关键变量: {missing}"
    return {"key_vars": ["AgentRuntime", "TaskGraph", "FastAPI"], "all_present": True}


def _test_e2e_7_original_unchanged():
    after = [{"role": m.role, "content": m.content} for m in _PAYLOAD.messages]
    assert after == _ORIGINAL, "原始 messages 不应被修改"
    assert len(after) == len(_ORIGINAL), "原始 messages 数量不应变化"
    return {"unchanged": after == _ORIGINAL, "len": len(after)}


def _test_e2e_8_mock_called_and_injected(mock_call):
    assert mock_call.called, "应调用 model_service.call_once 生成摘要"
    mem_content = next(
        c for c in _compressed_contents() if c.startswith("【历史记忆摘要】")
    )
    assert SUMMARY_TEXT in mem_content, "摘要文本应正确注入 memory 节点"
    return {"call_once_called": True, "injected": SUMMARY_TEXT in mem_content}


# ═════════════════════════════════════════════════════════════════════════
# 执行
# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("MfkAgent 会话压缩 端到端验证（Phase G6-B E2E）")
    print("链路: ChatContextBuilder → 历史 payload → 压缩引擎 → 模型 payload")
    print("=" * 70)

    mock_call = _setup_e2e()

    run("E2E-1 真实 ContextBuilder payload > 20 条", _test_e2e_1_payload_over_20)
    run("E2E-2 压缩触发，消息数明显减少", _test_e2e_2_compression_reduced)
    run("E2E-3 system message 保留", _test_e2e_3_system_preserved)
    run("E2E-4 存在【历史记忆摘要】节点", _test_e2e_4_memory_node_exists)
    run("E2E-5 最近 4 条消息保留", _test_e2e_5_recent_4_preserved)
    run("E2E-6 摘要含关键变量", _test_e2e_6_summary_key_vars)
    run("E2E-7 原始 messages 未被修改", _test_e2e_7_original_unchanged)
    run("E2E-8 call_once mock + 摘要注入", lambda: _test_e2e_8_mock_called_and_injected(mock_call))

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        BACKEND_DIR / "tests" / "phase_g6b_compression_e2e_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MfkAgent 会话压缩 端到端验证报告（Phase G6-B E2E）\n",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        "- 链路: ChatContextBuilder → 历史 payload → 压缩引擎 → 模型 payload\n",
        "- 方式: 真实 DB + 真实 ContextBuilder + mock model_service.call_once（零真实 LLM）\n",
        "## 结果总览\n",
        "| # | 用例 | 结果 | 耗时 |",
        "|---|------|------|------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"| {i} | {r['name']} | {'✅ PASS' if r['ok'] else '❌ FAIL'} | {r['elapsed_ms']}ms |"
        )
    passed = sum(1 for r in results if r["ok"])
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
        if not r["ok"]:
            lines.append(f"> 失败: {d}\n")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n报告已生成:", report_path)

    print(f"结果: {passed}/{len(results)} 通过")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
