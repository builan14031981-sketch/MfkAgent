"""MfkAgent Role Template Phase — 角色模板统一 + 用完即弃实例 单元测试（2026-08-16）。

覆盖：
  R1. 模板映射完整性：ROLE_TO_TEMPLATE_ID 覆盖全部 7 个编排角色，agent_id 以 sub_ 开头
  R2. DB 优先加载：agents 表存在 is_sub_agent=True 模板时，get_orchestration_role 返回 DB 定义
      （identity / allowed_tools 来自 DB，而非内存）
  R3. 内存兜底：DB 无对应模板时回退 ORCHESTRATION_ROLES 内置定义
  R4. 模板一致性：DB 模板与 roles.py 内置定义字段语义对齐（role_id/name/description 非空）
  R5. 用完即弃：run_sub_agent 每次调用构建全新隔离 AgentContext（history=None，独立上下文），
      两次调用不共享状态；并校验 identity/allowed_tools 按模板注入

运行：
  python backend/tests/test_role_template_phase.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import asyncio
import io
import os
import sys
import tempfile
import time
from pathlib import Path

if "pytest" not in sys.modules and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

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
            failures.append(name)
            print(f"  FAIL  {name}  ({elapsed:.0f}ms)  {detail}")
    except Exception as e:
        failures.append(name)
        results.append({"name": name, "ok": False, "detail": {"error": str(e)}})
        print(f"  ERROR {name}  {e!r}")


# ── 临时数据库夹具：替换 app.core.database.SessionLocal ─────────────────────

class _FakeDB:
    """持有临时 SQLite engine + sessionmaker，供本测试模块替换全局 SessionLocal。"""

    def __init__(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        from app.models.agent import Base
        Base.metadata.create_all(bind=self.engine)

    def add_template(self, agent_id, name, identity, allowed_tools):
        from app.models.agent import Agent
        db = self.SessionLocal()
        try:
            db.add(Agent(
                agent_id=agent_id,
                name=name,
                description="测试模板",
                avatar="sparkles",
                identity=identity,
                capabilities=[],
                status="active",
                is_sub_agent=True,
                allowed_tools=allowed_tools,
                parent_agent_id="general",
            ))
            db.commit()
        finally:
            db.close()


def _patch_sessionlocal(fake: _FakeDB):
    import app.core.database as database_mod
    original = database_mod.SessionLocal
    database_mod.SessionLocal = fake.SessionLocal
    return original


def _restore_sessionlocal(original):
    import app.core.database as database_mod
    database_mod.SessionLocal = original


# ── R1: 模板映射完整性 ───────────────────────────────────────────────────────

def t_mapping():
    from app.core.orchestrator.roles import ORCHESTRATION_ROLES, ROLE_TO_TEMPLATE_ID

    all_ok = True
    detail = {}
    all_roles = set(ORCHESTRATION_ROLES.keys())
    mapped = set(ROLE_TO_TEMPLATE_ID.keys())
    detail["role_count"] = len(all_roles)
    detail["mapped_count"] = len(mapped)
    if all_roles != mapped:
        all_ok = False
        detail["unmapped"] = sorted(all_roles - mapped)
        detail["extra"] = sorted(mapped - all_roles)
    bad_ids = [v for v in ROLE_TO_TEMPLATE_ID.values() if not str(v).startswith("sub_")]
    detail["bad_ids"] = bad_ids
    if bad_ids:
        all_ok = False
    # 每个角色都有模板 id 且 identity 模板非空（内存兜底）
    missing_identity = [rid for rid in ORCHESTRATION_ROLES if not ORCHESTRATION_ROLES[rid].identity_template]
    detail["missing_identity"] = missing_identity
    if missing_identity:
        all_ok = False
    return {"all_ok": all_ok, **detail}


# ── R2: DB 优先加载 ──────────────────────────────────────────────────────────

def t_db_first():
    from app.core.orchestrator.roles import get_orchestration_role

    fake = _FakeDB()
    custom_identity = "【DB模板】你是自定义架构师（DB优先加载验证）。"
    fake.add_template(
        agent_id="sub_architecture",
        name="架构师-DB",
        identity=custom_identity,
        allowed_tools=["read_file", "list_files", "search_files"],
    )
    original = _patch_sessionlocal(fake)
    try:
        role = get_orchestration_role("architecture")
        all_ok = bool(role and role.identity_template == custom_identity)
        detail = {
            "got": role.identity_template if role else None,
            "expected": custom_identity,
            "db_name": role.name if role else None,
            "tools": role.suggested_tools if role else None,
        }
        if not all_ok:
            return {"all_ok": False, **detail}
        if role.suggested_tools != ["read_file", "list_files", "search_files"]:
            return {"all_ok": False, "msg": "allowed_tools 未从 DB 注入", **detail}
        return {"all_ok": True, **detail}
    finally:
        _restore_sessionlocal(original)


# ── R3: 内存兜底 ─────────────────────────────────────────────────────────────

def t_memory_fallback():
    from app.core.orchestrator.roles import get_orchestration_role

    fake = _FakeDB()  # 空库：无任何模板
    original = _patch_sessionlocal(fake)
    try:
        role = get_orchestration_role("backend")
        all_ok = bool(role and role.identity_template and "后端" in role.name)
        detail = {
            "name": role.name if role else None,
            "identity_prefix": (role.identity_template[:30] if role and role.identity_template else None),
            "has_tools": bool(role and role.suggested_tools),
        }
        return {"all_ok": all_ok, **detail}
    finally:
        _restore_sessionlocal(original)


# ── R4: 全部角色 DB 命中或兜底均可解析 ───────────────────────────────────────

def t_all_resolvable():
    from app.core.orchestrator.roles import get_orchestration_role, role_ids

    fake = _FakeDB()
    fake.add_template("sub_backend", "后端-DB", "【DB模板】后端工程师。", ["read_file", "run_command"])
    fake.add_template("sub_researcher", "调研-DB", "【DB模板】调研员。", ["web_search", "fetch_url"])
    original = _patch_sessionlocal(fake)
    try:
        all_ok = True
        detail = {"roles": {}}
        for rid in role_ids():
            r = get_orchestration_role(rid)
            if not r or not r.identity_template:
                all_ok = False
                detail["roles"][rid] = "不可解析"
            else:
                detail["roles"][rid] = ("DB" if r.identity_template.startswith("【DB模板】") else "memory")
        return {"all_ok": all_ok, **detail}
    finally:
        _restore_sessionlocal(original)


# ── R5: 用完即弃 — 每次调用全新隔离上下文 ────────────────────────────────────

def t_spawn_isolation():
    from app.services.sub_agent import run_sub_agent

    fake = _FakeDB()
    fake.add_template(
        agent_id="sub_code_reviewer",
        name="代码审查-DB",
        identity="【DB模板】你是只读代码审查员。",
        allowed_tools=["read_file", "list_files"],
    )
    original = _patch_sessionlocal(fake)

    captured = []

    class _FakeRuntime:
        async def run(self, context, messages, **kwargs):
            captured.append(context)
            from app.core.agent_runtime import AgentResult
            return AgentResult(content="审查结论：无严重问题。")

    try:
        import app.services.sub_agent as sub_agent_mod

        # sub_agent.py 在模块顶层 `from app.core.database import SessionLocal` 绑定了自己的引用，
        # 需同时替换其内部 SessionLocal，否则查询仍走真实库。
        real_sub_session = sub_agent_mod.SessionLocal
        sub_agent_mod.SessionLocal = fake.SessionLocal
        real_runtime = sub_agent_mod.AgentRuntime
        sub_agent_mod.AgentRuntime = _FakeRuntime
        try:
            async def _call_twice():
                s1 = await run_sub_agent(
                    "sub_code_reviewer", "审查 login.py",
                    chat_id=1, project_path="/tmp/proj",
                    model_id="test-model", max_tokens=1024,
                )
                s2 = await run_sub_agent(
                    "sub_code_reviewer", "审查 auth.py",
                    chat_id=1, project_path="/tmp/proj",
                    model_id="test-model", max_tokens=1024,
                )
                return s1, s2

            s1, s2 = asyncio.run(_call_twice())
            all_ok = True
            detail = {
                "spawn_count": len(captured),
                "s1": s1,
                "s2": s2,
            }
            if len(captured) != 2:
                return {"all_ok": False, "msg": "应产生 2 次独立 spawn", **detail}
            c1, c2 = captured
            # 全新上下文：对象不同
            if c1 is c2:
                return {"all_ok": False, "msg": "两次调用复用了同一上下文对象", **detail}
            # 上下文隔离：不注入完整历史
            if c1.history is not None or c2.history is not None:
                return {"all_ok": False, "msg": "子代理不应注入完整历史", **detail}
            # 身份/工具按模板注入
            if c1.agent_identity != "【DB模板】你是只读代码审查员。":
                return {"all_ok": False, "msg": "身份未按 DB 模板注入", "identity": c1.agent_identity}
            if not c1.tools or len(c1.tools) != 2:
                return {"all_ok": False, "msg": "工具白名单未按 DB 模板注入", "tools": getattr(c1, "tools", None)}
            return {"all_ok": True, **detail}
        finally:
            sub_agent_mod.AgentRuntime = real_runtime
            sub_agent_mod.SessionLocal = real_sub_session
    finally:
        _restore_sessionlocal(original)


def main():
    print("Role Template Phase 单元测试")
    print("=" * 60)
    run("R1 模板映射完整性", t_mapping)
    run("R2 DB 优先加载", t_db_first)
    run("R3 内存兜底", t_memory_fallback)
    run("R4 全部角色可解析", t_all_resolvable)
    run("R5 用完即弃隔离", t_spawn_isolation)

    print("=" * 60)
    passed = len(results) - len(failures)
    print(f"结果: {passed}/{len(results)} 通过")
    for f in failures:
        print(f"  失败: {f}")

    out_path = None
    if len(sys.argv) > 1:
        out_path = sys.argv[1]
    else:
        out_path = str(Path(__file__).with_suffix(".report.json"))
    import json

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "suite": "role_template_phase",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "passed": passed,
            "total": len(results),
            "failures": failures,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"报告已写入: {out_path}")

    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()