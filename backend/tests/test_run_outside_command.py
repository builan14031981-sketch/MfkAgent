"""run_outside_command（沙箱外命令 · 强制人工审批）专项测试。

覆盖：
- evaluate_outside：空命令/元字符/plan → DENY；build 恒定 HIGH_RISK（不查白名单）
- 三权限模式（SAFE/STANDARD/AUTONOMOUS）下 HIGH_RISK 全部 REQUIRE_APPROVAL（人类把关）
- run_command_outside 拦截：空命令/缺 project_path/cwd 空/相对路径/不存在/黑名单/元字符
- run_command_outside 成功执行：cwd 真实生效 + exit_code 0
- _describe_tool_command：审批卡片展示 cwd
- ToolVerification：run_outside_command 归入命令族，被拦截结果正确豁免

运行：python -m pytest backend/tests/test_run_outside_command.py -v
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.tool_runtime.risk_engine import (  # noqa: E402
    CommandRiskEngine,
    Verdict,
    RiskLevel,
    ExecutionAction,
)
from app.core.tool_runtime.approval_policy import ApprovalPolicy, ApprovalMode  # noqa: E402
from app.core.tool_runtime.executor import _describe_tool_command  # noqa: E402
from app.core.agent_runtime.completion.tool_check import ToolVerification  # noqa: E402
from app.core.command_tools import run_command_outside  # noqa: E402
from app.core.sandbox import is_forbidden_cwd  # noqa: E402


class TestEvaluateOutside(unittest.TestCase):
    """evaluate_outside 风险判定：恒定 HIGH_RISK。"""

    def setUp(self):
        self.engine = CommandRiskEngine()

    def test_empty_command_deny(self):
        d = self.engine.evaluate_outside("")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_forbidden_meta_deny(self):
        d = self.engine.evaluate_outside("cmd && echo hi")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_plan_mode_deny(self):
        d = self.engine.evaluate_outside("dir", mode="plan")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_build_always_high_risk(self):
        # 即使"安全只读"命令也不查白名单，恒定 HIGH_RISK
        for cmd in ("ver", "dir", "ipconfig", "python -m py_compile app.py", "git status"):
            d = self.engine.evaluate_outside(cmd, mode="build")
            self.assertEqual(d.verdict, Verdict.HIGH_RISK, msg=cmd)
            self.assertEqual(d.risk_level, RiskLevel.DESTRUCTIVE)


class TestMandatoryHumanApproval(unittest.TestCase):
    """沙箱外命令 → HIGH_RISK → 三权限模式全部 REQUIRE_APPROVAL。"""

    def test_all_modes_require_approval(self):
        engine = CommandRiskEngine()
        d = engine.evaluate_outside("dir", mode="build")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)
        for mode in (ApprovalMode.SAFE, ApprovalMode.STANDARD, ApprovalMode.AUTONOMOUS):
            ed = ApprovalPolicy(mode).decide(d)
            self.assertEqual(ed.action, ExecutionAction.REQUIRE_APPROVAL, msg=mode)
            # 任何模式都不允许自动执行或阻断（必须人类审批）
            self.assertNotEqual(ed.action, ExecutionAction.EXECUTE, msg=mode)


class TestRunCommandOutside(unittest.TestCase):
    """run_command_outside 执行函数：拦截与成功路径。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="mfk_outside_")
        cls.project = tempfile.mkdtemp(prefix="mfk_proj_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        shutil.rmtree(cls.project, ignore_errors=True)

    def _call(self, **kw):
        return json.loads(run_command_outside(project_path=self.project, **kw))

    def test_empty_command(self):
        r = self._call(command="", cwd=self.tmp)
        self.assertEqual(r["exit_code"], -1)

    def test_missing_project(self):
        r = json.loads(run_command_outside(project_path="", command="ver", cwd=self.tmp))
        self.assertEqual(r["exit_code"], -1)

    def test_empty_cwd(self):
        r = self._call(command="ver", cwd="")
        self.assertEqual(r["exit_code"], -1)

    def test_relative_cwd_rejected(self):
        r = self._call(command="ver", cwd="subdir")
        self.assertEqual(r["exit_code"], -1)
        self.assertIn("绝对路径", r["stderr"])

    def test_nonexistent_cwd_rejected(self):
        r = self._call(command="ver", cwd=os.path.join(self.tmp, "no_such_dir"))
        self.assertEqual(r["exit_code"], -1)
        self.assertIn("工作目录不存在", r["stderr"])

    def test_forbidden_cwd_rejected(self):
        sysroot = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if not sysroot:
            self.skipTest("非 Windows 环境，无系统目录")
        forbidden, _ = is_forbidden_cwd(sysroot)
        if not forbidden:
            self.skipTest("当前系统目录不在黑名单内")
        r = self._call(command="ver", cwd=sysroot)
        self.assertEqual(r["exit_code"], -1)
        self.assertIn("安全拦截", r["stderr"])

    def test_meta_rejected(self):
        r = self._call(command="ver && dir", cwd=self.tmp)
        self.assertEqual(r["exit_code"], -1)

    def test_success_executes(self):
        r = self._call(command="python -V", cwd=self.tmp)
        self.assertEqual(r["exit_code"], 0, msg=r["stderr"])
        self.assertIn("Python", r["stdout"])

    @unittest.skipUnless(sys.platform == "win32", "cmd /c cd 仅 Windows")
    def test_cwd_effective(self):
        # cmd /c cd 打印当前工作目录，验证 cwd 真实生效（沙箱外目录）
        r = self._call(command="cmd /c cd", cwd=self.tmp)
        self.assertEqual(r["exit_code"], 0, msg=r["stderr"])
        self.assertIn(os.path.normpath(self.tmp), r["stdout"])


class TestDescribeToolCommand(unittest.TestCase):
    def test_shows_cwd(self):
        desc = _describe_tool_command("run_outside_command", {"command": "dir", "cwd": "E:/data"})
        self.assertIn("E:/data", desc)
        self.assertIn("dir", desc)


class TestToolCheckFamily(unittest.TestCase):
    def test_family_includes_outside_command(self):
        self.assertIn("run_outside_command", ToolVerification._COMMAND_TOOLS)

    def test_intercepted_result_exempted(self):
        # 以"错误:" 开头的被拦截结果 → 豁免（不构成未完成项，避免重试循环）
        rec = {"tool": "run_outside_command", "status": "error", "result": "错误: 工作目录不存在: X"}
        self.assertTrue(ToolVerification._is_intercepted(rec))

    def test_family_key_aggregates(self):
        self.assertEqual(ToolVerification._family_key("run_outside_command"), "command")


if __name__ == "__main__":
    unittest.main(verbosity=2)
