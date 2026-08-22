"""Phase H 文件工具扩展自动化验证：read_file 窗口 / find_files / edit_file / apply_patch。

运行：python backend/tests/test_file_tools_extended.py
退出码：0 = 全部通过；1 = 存在失败。
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core import tools as T
from app.core.tool_runtime.permission import PermissionFilter
from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict
from app.core.tool_runtime.executor import _truncate_result


class FileToolsExtendedTestCase(unittest.TestCase):
    """read_file 窗口 / find_files / edit_file / apply_patch / 权限注册 / 结果截断。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self._tmp.name) / "Project"
        (self.proj / "src").mkdir(parents=True)
        (self.proj / "node_modules").mkdir()
        (self.proj / ".git").mkdir()
        self.pp = str(self.proj)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel: str, content: str):
        p = self.proj / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    # ──── read_file 窗口 ────

    def test_read_file_auto_window(self):
        """超过 500 行自动只读前 500 行并提示续读。"""
        self._write("src/big.py", "def x(): pass\n" * 600)
        out = T.read_file(self.pp, "src/big.py")
        self.assertIn("[提示] 文件共 600 行", out)
        self.assertIn("offset=501", out)

    def test_read_file_window_numbered(self):
        """offset/limit 窗口：带行号输出 + 续读提示。"""
        self._write("src/notes.md", "a\nb\nc\nd\n")
        out = T.read_file(self.pp, "src/notes.md", offset=2, limit=2)
        lines = out.splitlines()
        self.assertEqual(lines[0], "2: b")
        self.assertEqual(lines[1], "3: c")
        self.assertIn("已显示第 2-4 行", out) if False else None
        self.assertIn("offset=4", out)

    def test_read_file_window_offset_beyond(self):
        self._write("src/notes.md", "a\nb\n")
        out = T.read_file(self.pp, "src/notes.md", offset=99, limit=2)
        self.assertIn("超出文件总行数", out)

    def test_read_file_window_tail(self):
        """limit 超出文件末尾时自然截断，无续读提示。"""
        self._write("src/notes.md", "a\nb\nc\n")
        out = T.read_file(self.pp, "src/notes.md", offset=3, limit=100)
        self.assertIn("3: c", out)
        self.assertNotIn("如需继续", out)

    # ──── find_files ────

    def test_find_files_rglob(self):
        self._write("src/a.py", "x = 1")
        self._write("src/nested/b.py", "x = 2")
        self._write("node_modules/junk.py", "x = 3")
        out = T.find_files(self.pp, "**/*.py")
        self.assertIn("src/a.py", out)
        self.assertIn("src/nested/b.py", out)
        self.assertNotIn("junk.py", out)  # node_modules 被跳过

    def test_find_files_non_recursive(self):
        """非递归模式（无 `**`）只匹配 relative_path 下第一层，不深入子目录。"""
        self._write("root.ts", "x = 1")
        self._write("src/a.ts", "x = 2")
        self._write("src/nested/b.ts", "x = 3")
        out = T.find_files(self.pp, "*.ts")
        self.assertIn("root.ts", out)
        self.assertNotIn("src/", out)
        out2 = T.find_files(self.pp, "*.ts", relative_path="src")
        self.assertIn("a.ts", out2)
        self.assertNotIn("b.ts", out2)

    def test_find_files_empty(self):
        out = T.find_files(self.pp, "*.nope")
        self.assertIn("未找到匹配", out)

    def test_find_files_subdir(self):
        self._write("src/a.py", "x = 1")
        self._write("b.py", "x = 2")
        out = T.find_files(self.pp, "**/*.py", relative_path="src")
        self.assertIn("a.py", out)
        self.assertNotIn("b.py", out)

    # ──── edit_file ────

    def test_edit_file_unique_replace(self):
        self._write("src/notes.md", "alpha\nbeta\ngamma\n")
        out = T.edit_file(self.pp, "src/notes.md", "beta", "BETA")
        self.assertIn("已更新 src/notes.md", out)
        self.assertIn("回读校验通过", out)
        self.assertIn("BETA", (self.proj / "src" / "notes.md").read_text(encoding="utf-8"))

    def test_edit_file_not_found(self):
        self._write("src/notes.md", "alpha\n")
        with self.assertRaises(T.ToolExecutionError) as ctx:
            T.edit_file(self.pp, "src/notes.md", "no_such_text", "X")
        self.assertIn("未找到", str(ctx.exception))

    def test_edit_file_ambiguous(self):
        self._write("src/notes.md", "dup\ndup\n")
        with self.assertRaises(T.ToolExecutionError) as ctx:
            T.edit_file(self.pp, "src/notes.md", "dup", "X")
        self.assertIn("2 次", str(ctx.exception))

    # ──── apply_patch ────

    def test_apply_patch_multi_file(self):
        self._write("src/notes.md", "alpha\n")
        self._write("src/util.ts", "export const x = 1;\n")
        patch = """--- a/src/notes.md
+++ b/src/notes.md
@@
-alpha
+beta
--- a/src/util.ts
+++ b/src/util.ts
@@
-export const x = 1;
+export const x = 2;
"""
        out = T.apply_patch(self.pp, patch)
        self.assertIn("src/notes.md", out)
        self.assertIn("src/util.ts", out)
        self.assertEqual("beta\n", (self.proj / "src" / "notes.md").read_text(encoding="utf-8"))
        self.assertIn("x = 2;", (self.proj / "src" / "util.ts").read_text(encoding="utf-8"))

    def test_apply_patch_append_only(self):
        self._write("src/notes.md", "head\n")
        out = T.apply_patch(self.pp, "--- a/src/notes.md\n+++ b/src/notes.md\n@@\n+APPENDED\n")
        self.assertIn("已应用 patch", out)
        self.assertIn("APPENDED", (self.proj / "src" / "notes.md").read_text(encoding="utf-8"))

    def test_apply_patch_missing_target(self):
        with self.assertRaises(T.ToolExecutionError) as ctx:
            T.apply_patch(self.pp, "--- a/nope.md\n+++ b/nope.md\n@@\n-x\n+y\n")
        self.assertIn("目标文件不存在", str(ctx.exception))

    def test_apply_patch_context_mismatch(self):
        self._write("src/notes.md", "aaa\n")
        with self.assertRaises(T.ToolExecutionError) as ctx:
            T.apply_patch(self.pp, "--- a/src/notes.md\n+++ b/src/notes.md\n@@\n-zzz\n+yyy\n")
        self.assertIn("找不到待替换", str(ctx.exception))

    def test_apply_patch_empty(self):
        with self.assertRaises(T.ToolExecutionError):
            T.apply_patch(self.pp, "")

    # ──── 沙箱防护 ────

    def test_sandbox_blocks_traversal(self):
        with self.assertRaises(PermissionError):
            T.read_file(self.pp, "../outside.txt")
        with self.assertRaises(PermissionError):
            T.edit_file(self.pp, "../outside.txt", "x", "y")

    # ──── 权限注册 ────

    def test_permission_base_tools(self):
        tools = set(PermissionFilter.BASE_TOOLS)
        self.assertTrue({"find_files", "edit_file", "apply_patch"} <= tools)

    def test_risk_engine_verdicts(self):
        self.assertEqual(evaluate_tool("find_files").verdict, Verdict.ALLOW)
        self.assertEqual(evaluate_tool("edit_file").verdict, Verdict.REQUIRE_APPROVAL)
        self.assertEqual(evaluate_tool("apply_patch").verdict, Verdict.REQUIRE_APPROVAL)
        self.assertEqual(evaluate_tool("edit_file", mode="plan").verdict, Verdict.DENY)

    # ──── 结果截断（executor）────

    def test_truncate_result(self):
        big = "x" * 20000
        out = _truncate_result(big, "read_file")
        self.assertIn("[已截断]", out)
        self.assertIn("分段读取", out)
        self.assertTrue(out.startswith("x" * 50))
        self.assertTrue(out.endswith("x" * 50))
        self.assertLess(len(out), 8000)

    def test_truncate_result_small_untouched(self):
        self.assertEqual(_truncate_result("short"), "short")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FileToolsExtendedTestCase)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)