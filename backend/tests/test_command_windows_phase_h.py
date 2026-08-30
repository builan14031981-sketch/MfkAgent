"""Phase H Windows 命令适配自动化验证：身份约束第 5 条 + 命令工具分次调用提示。

运行：python backend/tests/test_command_windows_phase_h.py
退出码：0 = 全部通过；1 = 存在失败。
"""
import json
import os
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import app.core.identity_principle as IP
import app.core.command_tools as CT


def _principle_text():
    return IP.IDENTITY_PRINCIPLE


class CommandWindowsPhaseHTestCase(unittest.TestCase):
    # ──── identity_principle 第 5 条（Windows 平台约束）────

    def test_windows_principle_present(self):
        self.assertIn("Windows", _principle_text())

    def test_windows_principle_path_hint(self):
        self.assertIn("盘符", _principle_text())
        self.assertIn("PowerShell", _principle_text())

    def test_windows_principle_mentions_no_semicolon_chain(self):
        self.assertIn("分多次调用", _principle_text())

    # ──── command_tools：禁止字符 + 分次调用提示 ────
    # T11 契约：run_command 对可安全拆分的链式命令放行（chain_gate_allows，逐段风险判定），
    # 仅对不可安全解析的命令替换类（$(...)/`...`/$VAR）fail-closed 拒绝；拒绝文案不含
    # "分多次调用"提示（该提示保留在 run_command_outside）。

    def test_run_command_semicolon_rejected_with_hint(self):
        # 命令替换使链式命令无法安全解析（fail-closed）→ 仍拒绝
        out = CT.run_command(".", "echo a; $(whoami)")
        self.assertIn("不允许的字符", out)

    def test_run_command_pipe_rejected_with_hint(self):
        # 管道 + 命令替换同理被拒绝
        out = CT.run_command(".", "echo a | $(whoami)")
        self.assertIn("不允许的字符", out)

    def test_execute_command_rejected_with_hint(self):
        # execute_command 无 chain_gate_allows 放行，含元字符的链式命令直接拒绝
        out = json.loads(CT.execute_command(".", "cd a && npm i"))
        self.assertIn("不允许的字符", out["stderr"])
        self.assertEqual(out["exit_code"], -1)

    def test_run_command_outside_rejected_with_hint(self):
        out = json.loads(CT.run_command_outside(".", "echo a; echo b", os.getcwd()))
        self.assertIn("不允许的字符", out["stderr"])
        self.assertIn("分多次调用", out["stderr"])

    def test_clean_windows_command_passes_gate(self):
        # 纯 Windows 合法命令（单命令、无反斜杠转义问题）不应被误杀
        self.assertIsNone(CT._FORBIDDEN_RE.search('dir C:\\Users\\Me /b'))
        self.assertIsNone(CT._FORBIDDEN_RE.search('python -m pytest tests\\test_a.py'))

    # ──── 执行层：合法 Windows 命令可执行（不依赖外部环境，用解释器自带命令）────

    def test_run_command_executes_windows_builtin(self):
        out = CT.run_command(".", "python --version")
        self.assertIn("Python", out)

    def test_execute_command_executes_windows_builtin(self):
        out = json.loads(CT.execute_command(".", "python --version"))
        self.assertTrue("Python" in out["stdout"] or "Python" in out["stderr"])
        self.assertEqual(out["exit_code"], 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CommandWindowsPhaseHTestCase)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)