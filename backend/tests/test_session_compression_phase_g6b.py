"""MfkAgent Session Compression — Phase G6-B 单元测试。

覆盖：
  T1.  三段式拆分：System 头 / 中间 / 最近 keep_recent 条，摘要节点位置正确
  T2.  中间内容不足（< min_middle）→ 返回原列表，不调用 call_once
  T3.  摘要模型成功 → 摘要文本注入 memory 节点（dict 输入）
  T4.  摘要模型抛异常 → fail-safe 返回原列表
  T5.  摘要模型返回空 → fail-safe 返回原列表
  T6.  ModelMessage 对象输入 → 输出同为 ModelMessage，memory 节点 role=user
  T7.  keep_recent 覆盖近全部消息 → 返回原列表
  T8.  摘要 Prompt 正确（system 含核心摘要约束，user 含中间内容）
  T9.  模型解析：显式 model_id 优先 → settings.COMPRESSION_MODEL → 默认 qwen-flash
  T10. 自定义 keep_recent / min_middle 参数生效
  T11. compress_history 为独立接口，不破坏 run / run_stream 核心流转

运行：
  python backend/tests/test_session_compression_phase_g6b.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.services.model import Message as ModelMessage, SingleCallResult  # noqa: E402
from app.core.agent_runtime.agent import AgentRuntime  # noqa: E402

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


# ──── 辅助函数 ────

def _make_dict_history(system_count: int = 2, middle_count: int = 4, recent_count: int = 4) -> list:
    """构造 dict 历史：System 头 + 中间 + 近期。"""
    messages = [{"role": "system", "content": f"系统设定-{i}"} for i in range(system_count)]
    messages += [
        {"role": "user" if j % 2 == 0 else "assistant", "content": f"中间消息-{j}"}
        for j in range(middle_count)
    ]
    messages += [
        {"role": "user" if j % 2 == 0 else "assistant", "content": f"近期消息-{j}"}
        for j in range(recent_count)
    ]
    return messages


def _make_model_history(system_count: int = 2, middle_count: int = 4, recent_count: int = 4) -> list:
    """构造 ModelMessage 历史。"""
    return [ModelMessage(role=m["role"], content=m["content"])
            for m in _make_dict_history(system_count, middle_count, recent_count)]


def _make_summary_result(text: str) -> SingleCallResult:
    return SingleCallResult(content=text, tool_calls=None, finish_reason="stop", usage={"total_tokens": 60})


def _roles(messages) -> list:
    if messages and hasattr(messages[0], "role"):
        return [m.role for m in messages]
    return [m["role"] for m in messages]


def _contents(messages) -> list:
    if messages and hasattr(messages[0], "role"):
        return [m.content for m in messages]
    return [m["content"] for m in messages]


# ═════════════════════════════════════════════════════════════════════════
# T1. 三段式拆分 + 摘要节点位置
# ═════════════════════════════════════════════════════════════════════════

def _test_t1_three_part_split():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=2, middle_count=4, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("已获取变量 X=42，结论：通过。")
            compressed = await rt.compress_history(history, keep_recent=4)

        # 结构与顺序: [System] + [Memory] + [Recent]
        assert len(compressed) == 2 + 1 + 4, f"期望 7 条，实际 {len(compressed)}"
        assert _roles(compressed)[0] == "system"
        assert _roles(compressed)[1] == "system"
        assert _roles(compressed)[2] == "user", "摘要节点应为 user role"
        assert compressed[2]["content"].startswith("【历史记忆摘要】"), \
            "摘要节点 content 应以【历史记忆摘要】开头"
        assert "X=42" in compressed[2]["content"], "摘要应保留关键变量"
        assert _roles(compressed)[3:] == ["user", "assistant", "user", "assistant"], \
            "尾部应为 keep_recent 条近期消息"

        return {
            "total": len(compressed),
            "roles": _roles(compressed),
            "memory_prefix_ok": compressed[2]["content"].startswith("【历史记忆摘要】"),
            "recent_preserved": _roles(compressed)[3:] == ["user", "assistant", "user", "assistant"],
            "call_once_called": mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T2. 中间内容不足 → 返回原列表，不调用 call_once
# ═════════════════════════════════════════════════════════════════════════

def _test_t2_middle_too_short():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=3, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("不应被使用")
            result = await rt.compress_history(history, keep_recent=4)

        assert not mock_call.called, "中间内容不足时不应调用摘要模型"
        assert result is history, "应返回原列表对象（不压缩）"
        assert len(result) == len(history), "消息数应保持不变"

        return {
            "unchanged": result is history,
            "len": len(result),
            "call_once_not_called": not mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T3. 摘要模型成功 → 摘要注入 memory 节点（dict 输入）
# ═════════════════════════════════════════════════════════════════════════

def _test_t3_summary_success_dict():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=4, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("文件路径 /src/main.py，最终结论：优化完成。")
            compressed = await rt.compress_history(history, keep_recent=4)

        assert mock_call.called
        assert len(compressed) == 1 + 1 + 4
        memory = compressed[1]
        assert isinstance(memory, dict)
        assert memory["role"] == "user"
        assert "最终结论" in memory["content"]
        assert "/src/main.py" in memory["content"]

        return {
            "memory_role": memory["role"],
            "memory_has_path": "/src/main.py" in memory["content"],
            "total": len(compressed),
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T4. 摘要模型抛异常 → fail-safe 返回原列表
# ═════════════════════════════════════════════════════════════════════════

def _test_t4_summary_exception_failsafe():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=5, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("摘要模型不可用 (503)")
            result = await rt.compress_history(history, keep_recent=4)

        assert mock_call.called, "应尝试调用摘要模型"
        assert result is history, "失败时应返回原列表，不抛异常"
        assert len(result) == len(history)

        return {
            "failsafe_ok": result is history,
            "len": len(result),
            "no_exception": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T5. 摘要模型返回空 → fail-safe 返回原列表
# ═════════════════════════════════════════════════════════════════════════

def _test_t5_summary_empty_failsafe():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=5, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("   ")
            result = await rt.compress_history(history, keep_recent=4)

        assert mock_call.called
        assert result is history, "摘要为空时应返回原列表"

        return {
            "failsafe_ok": result is history,
            "empty_summary_handled": True,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T6. ModelMessage 对象输入 → 输出同为 ModelMessage
# ═════════════════════════════════════════════════════════════════════════

def _test_t6_model_message_preserved():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_model_history(system_count=2, middle_count=4, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("摘要摘要")
            compressed = await rt.compress_history(history, keep_recent=4)

        assert all(isinstance(m, ModelMessage) for m in compressed), \
            "输出应保持 ModelMessage 类型"
        assert compressed[0].role == "system"
        assert compressed[2].role == "user", "memory 节点应为 user role"
        assert compressed[2].content.startswith("【历史记忆摘要】")
        # 头部/尾部对象保持原引用
        assert compressed[0] is history[0]
        assert compressed[-1] is history[-1]

        return {
            "all_model_message": all(isinstance(m, ModelMessage) for m in compressed),
            "memory_role": compressed[2].role,
            "head_identity_preserved": compressed[0] is history[0],
            "recent_identity_preserved": compressed[-1] is history[-1],
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T7. keep_recent 覆盖近全部消息 → 返回原列表
# ═════════════════════════════════════════════════════════════════════════

def _test_t7_keep_recent_covers_all():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=3, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("x")
            result = await rt.compress_history(history, keep_recent=10)

        assert not mock_call.called, "keep_recent 覆盖全部时不应压缩"
        assert result is history

        return {
            "unchanged": result is history,
            "call_once_not_called": not mock_call.called,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T8. 摘要 Prompt 正确性
# ═════════════════════════════════════════════════════════════════════════

def _test_t8_summary_prompt_content():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=4, recent_count=4)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("ok")
            await rt.compress_history(history, keep_recent=4)

        sent_messages = mock_call.call_args.args[1]
        sys_prompt = sent_messages[0]["content"]
        user_prompt = sent_messages[1]["content"]

        assert "核心摘要" in sys_prompt, "system prompt 应包含核心摘要约束"
        assert "500" in sys_prompt, "system prompt 应包含字数上限"
        assert "关键变量" in sys_prompt
        assert "忽略中间的报错和重试" in sys_prompt
        # user prompt 应包含中间消息（不含系统头与近期消息）
        assert "中间消息-0" in user_prompt
        assert "近期消息-3" not in user_prompt, "近期消息不应被送入摘要"
        assert "系统设定" not in user_prompt, "系统头不应被送入摘要"
        # 摘要调用参数
        assert mock_call.call_args.kwargs["temperature"] == 0.2

        return {
            "sys_has_constraint": "核心摘要" in sys_prompt,
            "sys_has_max_chars": "500" in sys_prompt,
            "user_has_middle": "中间消息-0" in user_prompt,
            "user_excludes_recent": "近期消息-3" not in user_prompt,
            "user_excludes_system": "系统设定" not in user_prompt,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T9. 模型解析优先级
# ═════════════════════════════════════════════════════════════════════════

def _test_t9_model_id_resolution():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=4, recent_count=4)

        # 场景 A: 显式 model_id 优先
        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("ok")
            await rt.compress_history(history, keep_recent=4, model_id="glm-flash-9b")
            assert mock_call.call_args.args[0] == "glm-flash-9b", \
                "显式 model_id 应优先"

        # 场景 B: settings.COMPRESSION_MODEL 配置生效
        from app.core.config import settings as cfg
        with patch.object(cfg, "COMPRESSION_MODEL", "cheap-summary-model"), \
             patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("ok")
            await rt.compress_history(history, keep_recent=4)
            assert mock_call.call_args.args[0] == "cheap-summary-model", \
                "settings.COMPRESSION_MODEL 应生效"

        # 场景 C: 未配置 → 默认便宜模型
        with patch.object(cfg, "COMPRESSION_MODEL", ""), \
             patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("ok")
            await rt.compress_history(history, keep_recent=4)
            assert mock_call.call_args.args[0] == rt.DEFAULT_COMPRESSION_MODEL, \
                f"默认应使用 {rt.DEFAULT_COMPRESSION_MODEL}"

        return {
            "explicit_priority": True,
            "config_priority": True,
            "default_fallback": rt.DEFAULT_COMPRESSION_MODEL,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T10. 自定义 keep_recent / min_middle
# ═════════════════════════════════════════════════════════════════════════

def _test_t10_custom_params():
    import asyncio

    async def _run():
        rt = AgentRuntime()
        history = _make_dict_history(system_count=1, middle_count=6, recent_count=6)

        with patch("app.services.model.model_service.call_once",
                   new_callable=AsyncMock) as mock_call:
            mock_call.return_value = _make_summary_result("ok")
            compressed = await rt.compress_history(
                history, keep_recent=2, min_middle=5, max_summary_chars=300,
            )

        assert mock_call.called
        # [1 System] + [1 Memory] + [2 Recent]
        assert len(compressed) == 1 + 1 + 2, f"期望 4 条，实际 {len(compressed)}"
        assert _roles(compressed)[2:] == _roles(history)[-2:], "应保留最后 2 条近期消息"

        sent_messages = mock_call.call_args.args[1]
        assert "300" in sent_messages[0]["content"], "自定义 max_summary_chars 应生效"

        return {
            "total": len(compressed),
            "recent_len": 2,
            "max_chars_in_prompt": "300" in sent_messages[0]["content"],
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# T11. 独立接口，不破坏 run / run_stream
# ═════════════════════════════════════════════════════════════════════════

def _test_t11_independent_interface():
    import asyncio

    async def _run():
        rt = AgentRuntime()

        # compress_history 是独立方法（未被 run/run_stream 强制调用）
        assert hasattr(rt, "compress_history"), "应存在 compress_history 方法"
        assert hasattr(rt, "run"), "run 应保持不变"
        assert hasattr(rt, "run_stream"), "run_stream 应保持不变"

        # 空输入边界
        empty = await rt.compress_history([], keep_recent=4)
        assert empty == [], "空列表应返回空列表"

        # 单消息边界（无 system 头，无中间内容）
        single = await rt.compress_history([{"role": "user", "content": "hi"}], keep_recent=4)
        assert len(single) == 1 and single[0]["content"] == "hi", "单条消息应原样返回"

        return {
            "has_compress_history": hasattr(rt, "compress_history"),
            "has_run": hasattr(rt, "run"),
            "has_run_stream": hasattr(rt, "run_stream"),
            "empty_ok": empty == [],
            "single_ok": len(single) == 1,
        }

    return asyncio.run(_run())


# ═════════════════════════════════════════════════════════════════════════
# 执行
# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    print("=" * 70)
    print("MfkAgent 会话压缩引擎 单元测试（Phase G6-B）")
    print("=" * 70)

    run("T1  三段式拆分 + 摘要节点位置", _test_t1_three_part_split)
    run("T2  中间内容不足 → 返回原列表", _test_t2_middle_too_short)
    run("T3  摘要成功 → memory 节点注入（dict）", _test_t3_summary_success_dict)
    run("T4  摘要异常 → fail-safe 返回原列表", _test_t4_summary_exception_failsafe)
    run("T5  摘要为空 → fail-safe 返回原列表", _test_t5_summary_empty_failsafe)
    run("T6  ModelMessage 类型保持", _test_t6_model_message_preserved)
    run("T7  keep_recent 覆盖全部 → 不压缩", _test_t7_keep_recent_covers_all)
    run("T8  摘要 Prompt 内容正确", _test_t8_summary_prompt_content)
    run("T9  模型解析优先级", _test_t9_model_id_resolution)
    run("T10 自定义 keep_recent / min_middle", _test_t10_custom_params)
    run("T11 独立接口不破坏 run/run_stream", _test_t11_independent_interface)

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        BACKEND_DIR / "tests" / "phase_g6b_session_compression_report.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# MfkAgent 会话压缩引擎 测试报告（Phase G6-B）\n",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
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
