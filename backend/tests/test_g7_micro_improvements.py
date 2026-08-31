"""派工单 G7 微改进三件 — 专项测试。

覆盖：
1. run_command 新增 cwd 参数：调用方可指定命令工作目录（默认保持旧行为）
2. write_file 对 _init_.py 类笔误（__init__.py 写错）给纠错提示，不静默失败
3. 只读误触发豁免词扩充：原本只读却被误判需审批的命令自动放行

运行：python -m pytest backend/tests/test_g7_micro_improvements.py -v
"""
import asyncio
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.command_tools import (  # noqa: E402
    run_command,
    execute_command_tool,
    COMMAND_TOOLS_DEFINITIONS,
)
from app.core.tool_runtime.risk_engine import CommandRiskEngine, Verdict  # noqa: E402
from app.core.tool_runtime.executor import _init_file_typo_hint, _run_tool  # noqa: E402


def _cwd_cmd() -> str:
    """返回打印当前工作目录的命令（Windows: cmd /c cd；其他: pwd）。"""
    return "cmd /c cd" if sys.platform == "win32" else "pwd"


# ──── 任务1：run_command 新增 cwd 参数 ────


class TestRunCommandCwd(unittest.TestCase):
    """run_command 支持调用方指定命令工作目录（默认保持旧行为）。"""

    @classmethod
    def setUpClass(cls):
        cls.project = tempfile.mkdtemp(prefix="mfk_g7_proj_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.project, ignore_errors=True)

    def test_cwd_relative_to_project(self):
        sub = os.path.join(self.project, "subdir")
        os.makedirs(sub, exist_ok=True)
        out = run_command(self.project, _cwd_cmd(), cwd="subdir")
        self.assertIn(os.path.normpath(sub), out)

    def test_cwd_default_keeps_old_behavior(self):
        # 不传 cwd → 保持旧行为：绑定项目时工作目录为项目根
        out = run_command(self.project, _cwd_cmd())
        self.assertIn(os.path.normpath(self.project), out)

    def test_cwd_nonexistent_returns_error(self):
        out = run_command(self.project, _cwd_cmd(), cwd="no_such_dir")
        self.assertIn("工作目录不存在", out)

    def test_cwd_escape_project_rejected(self):
        # cwd 越出项目沙箱（..）→ 沙箱校验拒绝，不执行
        out = run_command(self.project, _cwd_cmd(), cwd="..")
        self.assertTrue(out.startswith("错误"), msg=out)

    def test_dispatch_cwd_passthrough(self):
        # executor 分发路径（execute_command_tool）透传 cwd 生效
        sub = os.path.join(self.project, "subdir")
        os.makedirs(sub, exist_ok=True)
        out = execute_command_tool("run_command", self.project, command=_cwd_cmd(), cwd="subdir")
        self.assertIn(os.path.normpath(sub), out)

    def test_schema_declares_cwd(self):
        # 工具 Schema 声明 cwd 参数，模型才可知会调用方
        schema = next(d for d in COMMAND_TOOLS_DEFINITIONS if d["function"]["name"] == "run_command")
        props = schema["function"]["parameters"]["properties"]
        self.assertIn("cwd", props)


# ──── 任务2：write_file 对 _init_.py 类笔误给纠错提示 ────


class TestWriteFileInitTypoHint(unittest.TestCase):
    """_init_file_typo_hint 助手：识别 __init__.py 的常见笔误。"""

    def test_common_typos_detected(self):
        for name in ("_init_.py", "_init__.py", "__init_.py", "___init___.py"):
            hint = _init_file_typo_hint(name)
            self.assertTrue(hint, msg=name)
            self.assertTrue(hint.startswith("错误"), msg=name)
            self.assertIn("__init__.py", hint, msg=name)

    def test_correct_name_not_detected(self):
        self.assertEqual(_init_file_typo_hint("__init__.py"), "")

    def test_normal_files_not_detected(self):
        for name in ("main.py", "init.py", "setup.py", "a/b/c.py", ""):
            self.assertEqual(_init_file_typo_hint(name), "", msg=name)

    def test_nested_typo_detected(self):
        # 嵌套路径仅校验文件名组件
        hint = _init_file_typo_hint("mypkg/_init_.py")
        self.assertIn("__init__.py", hint)


class TestWriteFileExecutorHint(unittest.TestCase):
    """executor 层：write_file 笔误路径返回纠错提示且不写入错误文件。"""

    @classmethod
    def setUpClass(cls):
        cls.project = tempfile.mkdtemp(prefix="mfk_g7_wf_")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.project, ignore_errors=True)

    def test_typo_not_written_and_hinted(self):
        result = asyncio.run(_run_tool(
            "write_file", {"relative_path": "_init_.py", "content": "x"}, self.project, {}
        ))
        self.assertIn("__init__.py", result)
        self.assertFalse(os.path.exists(os.path.join(self.project, "_init_.py")))

    def test_correct_write_unchanged(self):
        # 正确文件名写文件行为不变
        result = asyncio.run(_run_tool(
            "write_file", {"relative_path": "a.py", "content": "print(1)"}, self.project, {}
        ))
        self.assertIn("文件已写入", result)
        self.assertTrue(os.path.exists(os.path.join(self.project, "a.py")))


# ──── 任务3：只读误触发豁免词扩充 ────


class TestReadonlyExemptionExpansion(unittest.TestCase):
    """新增只读豁免词：原本只读却被误判需审批的命令自动放行。"""

    def setUp(self):
        self.engine = CommandRiskEngine()

    def test_new_readonly_commands_allow(self):
        for cmd in (
            "pip list",
            "pip freeze",
            "pip show requests",
            "npm ls",
            "npm view react",
            "git ls-files",
            "git rev-parse HEAD",
            "driverquery",
            "pathping 8.8.8.8",
            "nbtstat -a 127.0.0.1",
            "fc a b",
            "comp a b",
            "vol",
            "schtasks /query",
            "query user",
            "query session",
            "powercfg /a",
            "powercfg /getactivescheme",
        ):
            d = self.engine.evaluate(cmd)
            self.assertEqual(d.verdict, Verdict.ALLOW, msg=cmd)

    def test_new_readonly_commands_allow_in_plan(self):
        for cmd in ("pip list", "git ls-files", "driverquery", "schtasks /query", "npm ls"):
            d = self.engine.evaluate(cmd, mode="plan")
            self.assertEqual(d.verdict, Verdict.ALLOW, msg=cmd)

    def test_new_powershell_readonly_cmdlets_allow(self):
        for cmd in (
            'powershell -Command "Get-Service"',
            'powershell -Command "Get-Date"',
            'powershell -Command "Get-CimInstance Win32_ComputerSystem"',
            'powershell -Command "Get-WmiObject Win32_BIOS"',
            'powershell -Command "Get-Process; Select-Object -First 1"',
        ):
            d = self.engine.evaluate(cmd)
            self.assertEqual(d.verdict, Verdict.ALLOW, msg=cmd)

    def test_write_commands_still_not_allowlisted(self):
        # 豁免词扩充不得放行写入/危险命令（守住权限边界）
        for cmd in (
            "pip install requests",
            "npm install x",
            "npm uninstall lodash",
            "git remote add origin https://x",
            "git tag v1.0",
            "git push origin main",
            "schtasks /create /tn x /tr calc",
            "powercfg /change standby-timeout-ac 0",
            "query /unknown",
        ):
            d = self.engine.evaluate(cmd)
            self.assertNotEqual(d.verdict, Verdict.ALLOW, msg=cmd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
