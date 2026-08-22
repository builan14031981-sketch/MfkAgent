"""MfkAgent Context Builder Phase E3 自动化验证脚本。

Phase E3：Context Builder 正式化。
  - AgentContext / AgentResult 独立为 app.core.agent_runtime.context
  - chat.py 上下文构建逻辑迁移到 ChatContextBuilder（context_builder.py）
  - ChatContextBuilder.build(input) → BuiltContext(AgentContext + system prompt + messages + 参数)

覆盖（7 项）：
  1. AgentContext 结构字段（identity/capabilities/personality/project_context/
     vision_context=None/history/tools/metadata）
  2. system prompt ①-⑦ 层组装（身份准则/capability/execution policy/permission/
     project policy/personality/intent hint）
  3. memory_text 全量拼接（global + project 记忆）
  4. 无项目 + 文件操作 → Default Workspace 兜底（tools 启用）
  5. 无项目 + 非文件操作 → 仅无路径白名单工具（project_path=None）
  6. plan 模式 → read_only=True（build 模式 → False）
  7. use_tools=False → 强制禁用工具 + 无 intent hint

运行：
  python backend/tests/test_context_builder_phase_e3.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import tempfile
import asyncio
import time
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseE3_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_e3_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402 — Persona V2：确保 persona_templates 表创建
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.models.agent import Chat, Agent, Message, MemoryItem, Project  # noqa: E402
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.context_builder import DEFAULT_IDENTITY  # noqa: E402
from app.core.identity_principle import get_identity_principle  # noqa: E402
from app.core.tool_runtime.policy import get_execution_policy, get_project_policy  # noqa: E402
from app.services.personality import get_personality_prompt  # noqa: E402
from app.core.workspace import get_default_workspace_context  # noqa: E402
from app.core.tool_runtime.permission import NO_PATH_TOOLS, PermissionFilter  # noqa: E402


AGENT_ID = "e3_coder"
CAPABILITIES = ["software_development", "code_review"]
AGENT_IDENTITY = "你是一名精通 Python 的研发助手。"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_agent(db) -> None:
    if db.query(Agent).filter(Agent.agent_id == AGENT_ID).first():
        return
    db.add(Agent(
        agent_id=AGENT_ID,
        name="E3 Coder",
        identity=AGENT_IDENTITY,
        capabilities=CAPABILITIES,
    ))
    db.commit()


def _make_project(db, path: Path) -> int:
    path.mkdir(parents=True, exist_ok=True)
    p = Project(name="E3-Project", path=str(path))
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.id


def _make_chat(db, project_id=None, mode="build", personality_level=70) -> int:
    c = Chat(
        project_id=project_id,
        project_path=(db.query(Project).filter(Project.id == project_id).first().path) if project_id else None,
        agent_id=AGENT_ID,
        title="E3-Chat",
        personality_level=personality_level,
        mode=mode,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def _add_user_message(db, chat_id: int, content: str) -> None:
    db.add(Message(chat_id=chat_id, role="user", content=content))
    db.commit()


def _add_memory(db, scope: str, content: str, project_id=None) -> None:
    db.add(MemoryItem(scope=scope, content=content, project_id=project_id))
    db.commit()


def _build(chat_id: int, content: str, **kw):
    """同步包装 ChatContextBuilder.build（真实 DB）。"""
    return asyncio.run(get_chat_context_builder().build(
        ContextBuildInput(chat_id=chat_id, content=content, **kw)
    ))


# ---------------------------------------------------------------------------
# 用例
# ---------------------------------------------------------------------------


def test_agent_context_structure(project_dir: Path) -> dict:
    """1. AgentContext 结构字段（identity/capabilities/personality/project_context/...）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db, project_dir)
        cid = _make_chat(db, pid, mode="build", personality_level=70)
        _add_user_message(db, cid, "请读取项目里所有文件并总结")
    finally:
        db.close()

    built = _build(cid, "请读取项目里所有文件并总结", personality_level=70)
    ctx = built.context

    # identity 别名
    assert ctx.identity == ctx.agent_identity, "identity 应为 agent_identity 别名"
    assert ctx.agent_identity == AGENT_IDENTITY, f"agent_identity 异常: {ctx.agent_identity!r}"

    # capabilities / personality
    assert ctx.capabilities == CAPABILITIES, f"capabilities 异常: {ctx.capabilities}"
    assert ctx.personality and ctx.personality == get_personality_prompt(70), "personality 应为 70 级人格文本"

    # project_context
    assert ctx.project_context["project_id"] == pid, ctx.project_context
    assert ctx.project_context["project_path"] == str(project_dir), ctx.project_context
    assert ctx.project_context["project_name"] == "E3-Project", ctx.project_context
    assert ctx.project_context["mode"] == "build", ctx.project_context
    assert ctx.project_context["workspace_context"] is None, ctx.project_context

    # vision_context 预留
    assert ctx.vision_context is None, "本阶段 vision_context 应预留为 None"

    # history 全量（含刚写入的 user 消息）
    assert ctx.history and ctx.history[-1] == {"role": "user", "content": "请读取项目里所有文件并总结"}, ctx.history
    assert all(isinstance(m, dict) and "role" in m and "content" in m for m in ctx.history), ctx.history

    # tools 启用（项目绑定）
    assert ctx.tools, "项目绑定会话应启用工具"
    assert built.tool_context and built.tool_context["need_tools"], "tool_context.need_tools 应为 True"

    # metadata
    assert ctx.metadata["mode"] == "build", ctx.metadata
    assert ctx.metadata["use_tools"] is True, ctx.metadata
    assert ctx.metadata["intent"], f"metadata.intent 不应为空: {ctx.metadata}"

    # BuiltContext 一致性
    assert built.system_prompt == built.messages[0].content, "system_prompt 应等于 messages[0]"
    assert built.messages[0].role == "system", "首条消息应为 system"
    assert built.effective_model, "effective_model 不应为空"
    assert built.read_only is False, "build 模式 read_only 应为 False"
    assert built.memory_text == ctx.memory_text, "memory_text 应双通道一致"

    return {"case": "agent_context_structure", "chat_id": cid}


def test_system_prompt_layers(project_dir: Path) -> dict:
    """2. system prompt ①-⑦ 层组装（intent hint 触发）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db, project_dir)
        cid = _make_chat(db, pid, mode="build", personality_level=70)
    finally:
        db.close()

    built = _build(cid, "请读取项目里所有文件并总结", personality_level=70)
    sp = built.system_prompt

    # ⓪ 最高身份准则置顶
    assert sp.startswith(get_identity_principle()), "⓪ 身份准则应置顶"

    # ① identity
    assert AGENT_IDENTITY in sp, "① identity 缺失"

    # ② capability
    assert "## 能力倾向" in sp, "② capability 缺失"

    # ③ execution policy
    assert get_execution_policy().strip() in sp, "③ execution policy 缺失"

    # ④ permission context
    assert "## 当前会话权限上下文" in sp, "④ permission context 缺失"

    # ⑤ project policy（项目绑定）
    assert "## 项目工作流" in sp, "⑤ project policy 缺失"

    # ⑥ personality
    pers = get_personality_prompt(70)
    assert pers in sp, "⑥ personality 缺失"

    # ⑦ intent hint
    assert "## 任务建议" in sp, "⑦ intent hint 缺失"

    return {"case": "system_prompt_layers", "chat_id": cid}


def test_memory_text_assembly(project_dir: Path) -> dict:
    """3. memory_text 全量拼接（global + project 记忆）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db, project_dir)
        cid = _make_chat(db, pid, mode="build", personality_level=None)
        _add_memory(db, scope="global", content="用户偏好使用中文回答")
        _add_memory(db, scope="project", content="本项目的代码规范参考 PEP8", project_id=pid)
    finally:
        db.close()

    built = _build(cid, "你好", personality_level=None)
    mt = built.memory_text

    assert mt.startswith("<user_defined_memories>"), mt
    assert "### 全局记忆 (Global Rules):" in mt, "全局记忆缺失"
    assert "用户偏好使用中文回答" in mt, "全局记忆内容缺失"
    assert "### 当前项目特定记忆 (Project Rules):" in mt, "项目记忆缺失"
    assert "本项目的代码规范参考 PEP8" in mt, "项目记忆内容缺失"
    assert mt.endswith("</user_defined_memories>"), mt
    assert "<priority>user_memory</priority>" in mt, "优先级声明缺失"

    return {"case": "memory_text_assembly", "chat_id": cid}


def test_default_workspace_fallback(project_dir: Path) -> dict:
    """4. 无项目 + 文件操作 → Default Workspace 兜底（工具启用）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        cid = _make_chat(db, project_id=None, mode="build", personality_level=None)
    finally:
        db.close()

    built = _build(cid, "新建文件 hello.txt 保存到当前目录", personality_level=None)
    ctx = built.context

    assert ctx.project_path, "文件操作请求应触发默认工作目录兜底"
    assert built.tool_context and built.tool_context["need_tools"], "兜底工作目录应启用工具"
    assert ctx.tools, "tools 不应为空"

    sp = built.system_prompt
    ws_text = get_default_workspace_context(ctx.project_path)
    assert "## 当前工作目录（Default Workspace 兜底）" in sp, "default workspace 上下文应注入"
    assert ws_text in sp, "default workspace 上下文文本应完整注入"

    return {"case": "default_workspace_fallback", "chat_id": cid}


def test_no_project_no_tools(project_dir: Path) -> dict:
    """5. 无项目 + 非文件操作 → 工具禁用（tools=None, project_path=None）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        cid = _make_chat(db, project_id=None, mode="build", personality_level=None)
    finally:
        db.close()

    built = _build(cid, "今天天气怎么样", personality_level=None)
    ctx = built.context

    assert ctx.project_path is None, "非文件操作不应启用默认工作目录"
    # 2026-08-11 策略更新：未绑定项目不再全禁工具，按 NO_PATH_TOOLS 白名单保留无路径工具；
    # 文件/Git 类项目专有工具必须被移除
    project_only = set(PermissionFilter.BASE_TOOLS) - set(NO_PATH_TOOLS)
    if ctx.tools:
        tool_names = {t["function"]["name"] for t in ctx.tools}
        assert not (tool_names & project_only), "未绑定项目不应包含项目专有工具"
        assert tool_names <= NO_PATH_TOOLS, "未绑定项目只允许无路径白名单工具"
    assert "## 项目工作流" not in built.system_prompt, "无项目不应注入项目工作流"
    assert "## 当前工作目录（Default Workspace 兜底）" not in built.system_prompt, "无项目不应注入 workspace 上下文"

    return {"case": "no_project_no_tools", "chat_id": cid}


def test_plan_mode_read_only(project_dir: Path) -> dict:
    """6. plan 模式 → read_only=True（build 模式 → False）。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db, project_dir)
        cid_plan = _make_chat(db, pid, mode="plan", personality_level=None)
        cid_build = _make_chat(db, pid, mode="build", personality_level=None)
    finally:
        db.close()

    built_plan = _build(cid_plan, "分析项目结构", personality_level=None)
    assert built_plan.read_only is True, "plan 模式 read_only 应为 True"
    assert built_plan.context.metadata["mode"] == "plan", built_plan.context.metadata
    assert built_plan.context.project_path == str(project_dir)

    built_build = _build(cid_build, "分析项目结构", personality_level=None)
    assert built_build.read_only is False, "build 模式 read_only 应为 False"

    return {"case": "plan_mode_read_only"}


def test_use_tools_false(project_dir: Path) -> dict:
    """7. use_tools=False → 强制禁用工具 + 无 intent hint。"""
    db = SessionLocal()
    try:
        _make_agent(db)
        pid = _make_project(db, project_dir)
        cid = _make_chat(db, pid, mode="build", personality_level=70)
    finally:
        db.close()

    built = _build(cid, "请读取项目里所有文件并总结", use_tools=False, personality_level=70)
    ctx = built.context

    assert ctx.tools is None, "use_tools=False 应禁用工具"
    assert built.tool_context is None, "use_tools=False 不应产生 tool_context"
    assert ctx.metadata["use_tools"] is False, ctx.metadata
    assert "## 任务建议" not in built.system_prompt, "use_tools=False 不应注入 intent hint"

    return {"case": "use_tools_false", "chat_id": cid}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 70)
    print("MfkAgent Context Builder Phase E3 自动化验证")
    print("临时工作目录:", _TEMP_DIR)
    print("=" * 70)

    project_dir = _TEMP_DIR / "project"
    project_dir.mkdir(exist_ok=True)

    results = []
    failures = []

    cases = [
        ("AgentContext 结构字段", lambda: test_agent_context_structure(project_dir / "c1")),
        ("system prompt ①-⑦ 层组装", lambda: test_system_prompt_layers(project_dir / "c2")),
        ("memory_text 全量拼接", lambda: test_memory_text_assembly(project_dir / "c3")),
        ("无项目+文件操作→Default Workspace", lambda: test_default_workspace_fallback(project_dir / "c4")),
        ("无项目+非文件操作→工具禁用", lambda: test_no_project_no_tools(project_dir / "c5")),
        ("plan 模式→read_only", lambda: test_plan_mode_read_only(project_dir / "c6")),
        ("use_tools=False→禁用工具", lambda: test_use_tools_false(project_dir / "c7")),
    ]

    for name, fn in cases:
        t0 = time.monotonic()
        try:
            detail = fn()
            ok = detail.pop("all_ok", True)
            elapsed = (time.monotonic() - t0) * 1000
            results.append({"name": name, "ok": ok, "detail": detail, "elapsed_ms": round(elapsed)})
            print(f"  PASS  {name}  ({elapsed:.0f}ms)")
        except AssertionError as e:
            results.append({"name": name, "ok": False, "detail": str(e), "elapsed_ms": 0})
            failures.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
        except Exception as e:  # noqa: BLE001
            results.append({"name": name, "ok": False, "detail": f"异常: {e!r}", "elapsed_ms": 0})
            failures.append(f"{name}: 异常 {e!r}")
            print(f"  ERROR {name}\n        {e!r}")

    total_ok = len(results) - len(failures)
    print("\n" + "=" * 70)
    print(f"结果: {total_ok}/{len(results)} 通过")
    if failures:
        print("失败明细:")
        for f in failures:
            print(f"  - {f}")
    print("=" * 70)

    if sys.argv[1:]:
        report = Path(sys.argv[1]).resolve()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "\n".join([
                "# Phase E3 — Context Builder 正式化 测试报告",
                "",
                f"- 通过: {total_ok}/{len(results)}",
                f"- 用时: {sum(r['elapsed_ms'] for r in results)}ms",
                "",
                "| 用例 | 结果 | 用时 |",
                "| --- | --- | --- |",
            ] + [
                f"| {r['name']} | {'PASS' if r['ok'] else 'FAIL'} | {r['elapsed_ms']}ms |"
                for r in results
            ]),
            encoding="utf-8",
        )
        print(f"报告已写入: {report}")

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
