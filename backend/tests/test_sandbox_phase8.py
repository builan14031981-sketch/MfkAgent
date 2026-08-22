"""统一路径沙箱（Phase 8 P0）专项测试。

覆盖 app.core.sandbox 及 5 个接线入口：
- resolve_sandbox_path：.. 穿越 / 绝对路径 / 前缀仿冒(proj_evil) / 大小写容错 / 符号链接逃逸
- read_file / write_file / list_files：UTF-8 往返、越权拦截
- run_command：沙箱 cwd 锚定、cd 逃逸拦截、shell 元字符拦截、UTF-8 输出
- git_tools._resolve_rel / verification._resolve_path / api._resolve_safe_path 委托
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.sandbox import (
    SandboxViolation,
    decode_subprocess_output,
    resolve_sandbox_path,
    run_subprocess,
)
from app.core.tools import (
    ToolExecutionError,
    execute_file_tool,
    list_files,
    read_file,
    write_file,
)
from app.core.command_tools import run_command
from app.core.git_tools import GitToolError, _resolve_rel


class SandboxTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp(prefix="mfk_sandbox_"))
        self.project = self._tmp / "Project"
        self.project.mkdir()
        (self.project / "src").mkdir()
        (self.project / "src" / "app.py").write_text(
            "print('中文内容测试')\n", encoding="utf-8"
        )
        # 项目外的敏感文件（供穿越测试）
        self.outside = self._tmp / "outside_secret.txt"
        self.outside.write_text("SECRET", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    # ──── resolve_sandbox_path 基础 ────

    def test_valid_nested_relative(self):
        target = resolve_sandbox_path("src/app.py", str(self.project))
        self.assertEqual(target, self.project / "src" / "app.py")

    def test_empty_relative_returns_root(self):
        target = resolve_sandbox_path("", str(self.project))
        self.assertEqual(target, self.project)

    def test_dot_relative_returns_root(self):
        target = resolve_sandbox_path(".", str(self.project))
        self.assertEqual(target, self.project)

    def test_dotdot_traversal_blocked(self):
        with self.assertRaises(PermissionError):
            resolve_sandbox_path("../outside_secret.txt", str(self.project))

    def test_deep_traversal_blocked(self):
        with self.assertRaises(SandboxViolation):
            resolve_sandbox_path("../../../../Windows/system32", str(self.project))

    def test_absolute_escape_blocked(self):
        with self.assertRaises(SandboxViolation):
            resolve_sandbox_path(str(self.outside), str(self.project))

    def test_absolute_inside_allowed(self):
        target = resolve_sandbox_path(str(self.project / "src" / "app.py"), str(self.project))
        self.assertEqual(target, self.project / "src" / "app.py")

    def test_sibling_prefix_impersonation_blocked(self):
        # 仿冒前缀：Project_evil 不落于 Project/ 下，必须被拦截
        evil = self._tmp / "Project_evil"
        evil.mkdir()
        (evil / "x.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(SandboxViolation):
            resolve_sandbox_path("../Project_evil/x.txt", str(self.project))

    @unittest.skipUnless(os.name == "nt", "Windows-only case-insensitivity")
    def test_case_insensitive_containment(self):
        # 大小写不同的路径必须判定为在项目内（Windows 文件系统不区分大小写）
        target = resolve_sandbox_path("SRC/APP.PY", str(self.project))
        self.assertEqual(target.resolve(), (self.project / "src" / "app.py").resolve())

    def test_error_is_permission_error(self):
        with self.assertRaises(SandboxViolation) as cm:
            resolve_sandbox_path("../x", str(self.project))
        self.assertIsInstance(cm.exception, PermissionError)

    def test_symlink_escape_blocked(self):
        # 符号链接指向项目外 → 真实路径解析后必须被拦截（无权限则跳过）
        outside_dir = self._tmp / "outside_dir"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("SECRET", encoding="utf-8")
        link = self.project / "evil_link"
        try:
            os.symlink(outside_dir, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("当前环境无权限创建符号链接")
        with self.assertRaises(SandboxViolation):
            resolve_sandbox_path("evil_link/secret.txt", str(self.project))

    # ──── decode_subprocess_output 阶梯解码 ────

    def test_decode_utf8(self):
        self.assertEqual(decode_subprocess_output("中文".encode("utf-8")), "中文")

    def test_decode_gbk_fallback(self):
        self.assertEqual(decode_subprocess_output("中文".encode("gbk")), "中文")

    def test_decode_invalid_bytes_never_raises(self):
        out = decode_subprocess_output(b"\xff\xfe\x00\x80")
        self.assertIsInstance(out, str)

    def test_decode_empty(self):
        self.assertEqual(decode_subprocess_output(b""), "")

    # ──── 文件工具接线 ────

    def test_write_read_utf8_roundtrip(self):
        result = write_file(str(self.project), "src/new.py", "hello 中文\n")
        self.assertIn("文件已写入", result)
        content = read_file(str(self.project), "src/new.py")
        self.assertEqual(content, "hello 中文\n")

    def test_write_traversal_blocked(self):
        # Phase 9 sanitize：`..` 被清理为合法目录名，写入落在项目内（不越权）
        result = execute_file_tool(
            "write_file", str(self.project), relative_path="../hacked.py", content="x"
        )
        self.assertIn("文件已写入", result)
        # 项目外不产生文件
        self.assertFalse((self._tmp / "hacked.py").exists())
        # 内容落在项目内 untitled/hacked.py（`..` → untitled 目录，未越权）
        self.assertTrue((self.project / "untitled" / "hacked.py").exists())
        with (self.project / "untitled" / "hacked.py").open(encoding="utf-8") as f:
            self.assertEqual(f.read(), "x")

    def test_read_traversal_blocked(self):
        result = execute_file_tool(
            "read_file", str(self.project), relative_path="../outside_secret.txt"
        )
        self.assertIn("错误", result)
        self.assertIn("越权", result)

    def test_read_nonexistent(self):
        with self.assertRaises(ToolExecutionError):
            read_file(str(self.project), "missing.py")

    def test_list_files_in_sandbox(self):
        out = list_files(str(self.project), "src")
        self.assertIn("app.py", out)

    def test_list_traversal_blocked(self):
        result = execute_file_tool(
            "list_files", str(self.project), relative_path="../"
        )
        self.assertIn("错误", result)
        self.assertIn("越权", result)

    # ──── run_command 接线 ────

    def test_run_command_in_project_cwd(self):
        out = run_command(str(self.project), 'cmd /c "echo hello-project"')
        self.assertIn("hello-project", out)
        self.assertIn("[exit code 0]", out)

    def test_run_command_utf8_output(self):
        # PYTHONIOENCODING=utf-8 引导子进程以 UTF-8 输出，中文不应乱码
        py = sys.executable
        script = self.project / "src" / "print_utf8.py"
        script.write_text("print('hello 中文')\n", encoding="utf-8")
        out = run_command(str(self.project), f'"{py}" src/print_utf8.py')
        self.assertIn("hello 中文", out)

    def test_run_command_cd_escape_rejected(self):
        out = run_command(str(self.project), "cd C:\\Windows")
        self.assertIn("不支持 cd", out)

    def test_run_command_shell_metachar_rejected(self):
        out = run_command(str(self.project), "dir & echo hack")
        self.assertIn("不允许的字符", out)

    def test_run_command_system_allowed_without_project(self):
        out = run_command("", "cmd /c ver")
        self.assertIn("[exit code 0]", out)

    # ──── git 工具委托 ────

    def test_git_resolve_rel_valid(self):
        self.assertEqual(_resolve_rel(str(self.project), "src/app.py"), "src/app.py")

    def test_git_resolve_rel_escape(self):
        with self.assertRaises(GitToolError):
            _resolve_rel(str(self.project), "../outside_secret.txt")


if __name__ == "__main__":
    unittest.main()
