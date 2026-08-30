"""工单J：autonomous 审批死锁修复 — 预授权清单专项测试。

覆盖（对应工单验收）：
  1. preapproval 匹配器单元测试：清单命中 / 硬边界拒绝 / && 链整链放行
  2. ApprovalPolicy.decide_with_preapproval 决策：
       autonomous 命中清单 → EXECUTE + auto_approved_by_policy
       rm / format 等硬边界 → 仍 REQUIRE_APPROVAL
       开关 autonomous_preapproval_enabled 默认开，关 = 回旧行为
       非 autonomous 模式 / plan 模式不生效
  3. executor 端到端集成：autonomous 会话
       「cd → 写文件 → pytest → git add → git commit → git push」全程不卡审批
  4. settings 表读写路径验证（一键关闭 = 写 false）
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.agent import Setting  # noqa: E402
from app.core.tool_runtime.risk_engine import (  # noqa: E402
    Verdict, RiskLevel, ExecutionAction,
    command_risk_engine, RiskDecision,
)
from app.core.tool_runtime.approval_policy import (  # noqa: E402
    ApprovalPolicy, ApprovalMode,
)
from app.core.tool_runtime.preapproval import (  # noqa: E402
    command_matches_preapproval, split_chain, autonomous_preapproval_enabled,
    AUTONOMOUS_PREAPPROVAL_SETTING_KEY,
)
from app.core.tool_runtime.executor import execute_tool  # noqa: E402


# ── settings 开关助手 ─────────────────────────────────────────────────────────

def _set_switch(value):
    """写 / 清 autonomous_preapproval_enabled 设置（None = 删除行，恢复默认开）。"""
    db = SessionLocal()
    try:
        row = db.query(Setting).filter(Setting.key == AUTONOMOUS_PREAPPROVAL_SETTING_KEY).first()
        if value is None:
            if row is not None:
                db.delete(row)
                db.commit()
        else:
            if row is not None:
                row.value = value
            else:
                db.add(Setting(key=AUTONOMOUS_PREAPPROVAL_SETTING_KEY, value=value))
            db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _reset_preapproval_switch():
    """每个测试后恢复开关默认（无行 = 默认开），避免跨用例污染。"""
    yield
    _set_switch(None)


# ── 1. 匹配器单元测试 ─────────────────────────────────────────────────────────

def _hits(cmd, project_path="C:/proj"):
    """返回 command_matches_preapproval 是否命中。"""
    return command_matches_preapproval(cmd, project_path=project_path) is not None


class TestMatcherWhitelist:
    def test_git_subcommands(self):
        for cmd in [
            "git add .", "git add -A", "git commit -m 'init'", "git push origin main",
            "git pull", "git status --porcelain", "git log --oneline -5",
        ]:
            assert _hits(cmd), f"应命中清单: {cmd}"

    def test_git_dangerous_rejected(self):
        for cmd in [
            "git push --force", "git push -f", "git push --force-with-lease",
            "git push --delete origin main", "git push origin :main", "git push --mirror origin",
            "git reset --hard HEAD", "git clean -f", "git filter-branch",
        ]:
            assert not _hits(cmd), f"破坏性 git 不应预授权: {cmd}"

    def test_python_modules(self):
        for cmd in ["python -m pytest", "python -m mypy .", "python -m ruff check ."]:
            assert _hits(cmd), f"应命中清单: {cmd}"
        assert not _hits("python -m unittest"), "unittest 不在清单（保守不预授权）"
        assert not _hits("python app.py"), "普通 python 脚本不在清单"

    def test_pip_install_within_project(self):
        assert _hits("pip install requests", project_path="C:/proj")
        assert _hits("pip3 install -r requirements.txt", project_path="C:/proj")
        assert _hits("python -m pip install requests", project_path="C:/proj")
        assert _hits("python -m pip install -e .", project_path="C:/proj")
        assert _hits("pip install --target C:/proj/libs x", project_path="C:/proj")

    def test_pip_global_scope_rejected(self):
        for cmd in [
            "pip install --user requests", "pip install --system requests",
            "pip install --global requests", "pip install --prefix /usr/local x",
            "pip install --break-system-packages x",
        ]:
            assert not _hits(cmd, project_path="C:/proj"), f"全局作用域不应预授权: {cmd}"
        assert not _hits("pip install --target C:/outside/x x", project_path="C:/proj")
        # 未绑定项目（限项目内）→ 不预授权
        assert not _hits("pip install requests", project_path=None)
        assert not _hits("pip uninstall requests", project_path="C:/proj")

    def test_cd_within_project(self):
        assert _hits("cd backend")
        assert _hits("cd .")
        for cmd in ["cd ..", "cd ../x", "cd C:\\Windows", "cd E:\\", "cd /", "cd \\"]:
            assert not _hits(cmd), f"cd 越界不应预授权: {cmd}"

    def test_destructive_hard_boundary(self):
        for cmd in [
            "rm -rf /tmp/x", "rm -f x", "rmdir /s /q x", "del /f x", "erase x",
            "format C:", "format D: /q", "mkfs.ext4 /dev/sda", "diskpart",
            "shutdown /s", "reboot", "taskkill /f /im x.exe",
            "reg add HKCU\\x /v y /d z", "reg delete HKLM\\x", "reg import x.reg",
        ]:
            assert not _hits(cmd), f"破坏性动词不应预授权: {cmd}"

    def test_chain_whole_chain_must_match(self):
        assert _hits("cd backend && python -m pytest")
        assert _hits("git add . && git commit -m x && git push")
        assert _hits("python -m pytest && python -m mypy .")
        # 链中任一段破坏性/不在清单 → 整链不预授权
        assert not _hits("ls && rm -rf /")
        assert not _hits("cd backend && shutdown /s")
        assert not _hits("git add . ; git commit")  # 分号链（注入类）不预授权
        assert not _hits("echo `whoami`")  # 反引号不预授权

    def test_split_chain_quote_aware(self):
        # 引号内的 && 不拆分（引号原样保留，后续 _parse_argv 再剥引号）
        assert split_chain("a && b && \"c && d\"") == ["a", "b", "\"c && d\""]
        assert split_chain("git commit -m \"fix bug\"") == ["git commit -m \"fix bug\""]
        assert split_chain("a&&b") == ["a", "b"]
        # 引号内 && 不参与拆分 → 该段整体作为一条命令段（由 _segment_match_reason 判定）
        reason = command_matches_preapproval("git commit -m \"fix bug\" && git push")
        assert reason is not None
        assert "git commit" in reason and "git push" in reason


# ── 2. 决策层测试 ─────────────────────────────────────────────────────────────

def _high_risk(cmd):
    return command_risk_engine.evaluate(cmd, "build")


class TestDecideWithPreapproval:
    def test_autonomous_whitelist_released(self):
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("cd backend"), command="cd backend", project_path="C:/proj",
        )
        assert ed.action == ExecutionAction.EXECUTE
        assert "auto_approved_by_policy" in ed.reason

    def test_autonomous_high_risk_still_approval(self):
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("rm -rf /tmp/x"), command="rm -rf /tmp/x", project_path="C:/proj",
        )
        assert ed.action == ExecutionAction.REQUIRE_APPROVAL
        assert "auto_approved_by_policy" not in ed.reason

    def test_format_still_approval(self):
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("format C:"), command="format C:", project_path="C:/proj",
        )
        assert ed.action == ExecutionAction.REQUIRE_APPROVAL

    def test_non_autonomous_not_affected(self):
        for mode in (ApprovalMode.STANDARD, ApprovalMode.SAFE):
            policy = ApprovalPolicy(mode)
            ed = policy.decide_with_preapproval(
                _high_risk("cd backend"), command="cd backend", project_path="C:/proj",
            )
            assert ed.action == ExecutionAction.REQUIRE_APPROVAL, mode

    def test_plan_mode_not_released(self):
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("cd backend"), command="cd backend", project_path="C:/proj",
            allow_preapproval=False,
        )
        assert ed.action == ExecutionAction.REQUIRE_APPROVAL

    def test_run_outside_command_never_released(self):
        # run_outside_command 由 executor 不传 command；即使误传也不放行
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            command_risk_engine.evaluate_outside("dir", "build"),
            command=None, project_path="C:/proj",
        )
        assert ed.action == ExecutionAction.REQUIRE_APPROVAL

    def test_switch_off_old_behavior(self):
        _set_switch("false")
        assert autonomous_preapproval_enabled() is False
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("cd backend"), command="cd backend", project_path="C:/proj",
        )
        # 关 = 回旧行为：HIGH_RISK 仍强制人工审批
        assert ed.action == ExecutionAction.REQUIRE_APPROVAL

    def test_switch_default_on(self):
        _set_switch(None)
        assert autonomous_preapproval_enabled() is True
        policy = ApprovalPolicy(ApprovalMode.AUTONOMOUS)
        ed = policy.decide_with_preapproval(
            _high_risk("cd backend"), command="cd backend", project_path="C:/proj",
        )
        assert ed.action == ExecutionAction.EXECUTE

    def test_switch_true_via_db(self):
        _set_switch("true")
        assert autonomous_preapproval_enabled() is True


# ── 3. executor 端到端集成测试 ────────────────────────────────────────────────

AUTONOMOUS_CTX = {"permission_mode": "autonomous"}


def _git(cwd, *args):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=60,
    )


@pytest.fixture()
def git_project(tmp_path_factory):
    """真实 git 工作仓库 + 本地 bare 远端，用于端到端 push。"""
    base = tmp_path_factory.mktemp("mfk_j_proj")
    proj = base / "proj"
    proj.mkdir()
    _git(proj, "init", "-b", "master")
    _git(proj, "config", "user.email", "test@test")
    _git(proj, "config", "user.name", "test")
    remote = base / "remote.git"
    subprocess.run(
        ["git", "init", "--bare"], cwd=str(base),
        capture_output=True, text=True, timeout=60,
    )
    _git(proj, "remote", "add", "origin", str(remote))
    return proj


async def _exec(func_name, args_json, project_path, tool_call_id):
    return await execute_tool(
        tool_call={
            "function": {"name": func_name, "arguments": args_json},
            "id": tool_call_id,
        },
        project_path=project_path,
        read_only=False,
        ctx=AUTONOMOUS_CTX,
        emit=None,
    )


def test_autonomous_end_to_end_no_approval(git_project):
    """autonomous 会话端到端「cd → 写文件 → pytest → git add → commit → push」不卡审批。"""
    proj = git_project
    records = {}

    async def _run():
        # 1) cd（HIGH_RISK 未知命令 → 预授权放行，死锁修复核心）
        records["cd"] = await _exec(
            "run_command", '{"command": "cd ."}', str(proj), "j_cd"
        )
        # 2) 写文件（REQUIRE_APPROVAL/WRITE → autonomous 自动放行）
        records["write"] = await _exec(
            "write_file", '{"relative_path": "hello.txt", "content": "hi"}', str(proj), "j_write"
        )
        # 3) pytest（用当前解释器确保真实运行）
        (proj / "test_sample.py").write_text(
            "def test_ok():\n    assert 1 == 1\n", encoding="utf-8"
        )
        py = str(sys.executable).replace("\\", "/")
        records["pytest"] = await _exec(
            "execute_command",
            '{"command": "%s -m pytest test_sample.py -q"}' % py,
            str(proj), "j_pytest",
        )
        # 4) git add
        records["add"] = await _exec(
            "run_command", '{"command": "git add ."}', str(proj), "j_add"
        )
        # 5) git commit
        records["commit"] = await _exec(
            "run_command", '{"command": "git commit -m init"}', str(proj), "j_commit"
        )
        # 6) git push（真实推送本地 bare 远端）
        records["push"] = await _exec(
            "run_command", '{"command": "git push origin master"}', str(proj), "j_push"
        )

    asyncio.run(_run())

    # 验收①：全程无一步卡在审批
    stuck = {k: r["status"] for k, r in records.items() if r["status"] == "awaiting_approval"}
    assert not stuck, f"不应有任何步骤卡审批: {stuck}"

    # 验收②：HIGH_RISK 的 cd 被预授权放行并标注
    assert records["cd"]["auto_approved_by_policy"] is True
    # 验收③：git add / commit / push 真实执行成功且标注预授权
    for step in ("add", "commit", "push"):
        assert records[step]["success"] is True, f"{step} 执行失败: {records[step]['result'][:200]}"
        assert records[step]["auto_approved_by_policy"] is True, step
    # 写文件与 pytest 均不卡审批
    assert records["write"]["success"] is True
    assert records["pytest"]["status"] != "awaiting_approval"


def test_autonomous_rm_still_requires_approval():
    """autonomous 下 rm -rf 仍 REQUIRE_APPROVAL（硬边界）。"""

    async def _run():
        r = await _exec("run_command", '{"command": "rm -rf /tmp/x"}', "C:/proj", "j_rm")
        assert r["status"] == "awaiting_approval"
        assert "auto_approved_by_policy" not in r

    asyncio.run(_run())


def test_autonomous_format_still_requires_approval():
    """autonomous 下 format 类仍 REQUIRE_APPROVAL（硬边界）。"""

    async def _run():
        r = await _exec("run_command", '{"command": "format C:"}', "C:/proj", "j_fmt")
        assert r["status"] == "awaiting_approval"

    asyncio.run(_run())


def test_switch_off_returns_to_old_behavior(tmp_path_factory):
    """开关关闭 → autonomous 下 HIGH_RISK 回旧行为（仍人工审批）。"""
    _set_switch("false")

    async def _run():
        r = await _exec("run_command", '{"command": "cd backend"}', str(tmp_path_factory.mktemp("x")), "j_old")
        assert r["status"] == "awaiting_approval", "开关关闭后 HIGH_RISK 应仍人工审批"

    asyncio.run(_run())


def test_switch_on_releases_high_risk(tmp_path_factory):
    """开关默认开 → autonomous 下 HIGH_RISK 的 cd 被预授权放行（不卡审批）。"""

    async def _run():
        r = await _exec("run_command", '{"command": "cd backend"}', str(tmp_path_factory.mktemp("y")), "j_on")
        assert r["status"] != "awaiting_approval"
        assert r.get("auto_approved_by_policy") is True

    asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
