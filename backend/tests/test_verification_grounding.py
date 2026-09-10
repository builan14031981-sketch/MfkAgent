"""测试 Verification 确定性断言器 (Grounding Verifier) 防幻觉与崩溃特征拦截。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.verification import verifier, PASSED, FAILED, NEED_RETRY


class VerificationGroundingTestCase(unittest.TestCase):
    def test_run_command_exit_0_normal_passed(self):
        """退出码为 0 且无致命错误正常通过。"""
        record = {
            "tool": "run_command",
            "status": "success",
            "result": "$ python script.py\n[exit code 0]\nSuccess! Output generated.",
            "arguments": {"command": "python script.py"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, PASSED)
        self.assertEqual(r.evidence.get("exit_code"), 0)

    def test_run_command_exit_0_with_traceback_triggers_retry(self):
        """退出码虽为 0，但输出中包含 Traceback 时拦截并要求重试，防假性成功幻觉。"""
        record = {
            "tool": "run_command",
            "status": "success",
            "result": (
                "$ python bad_script.py\n[exit code 0]\n"
                "Traceback (most recent call last):\n"
                "  File \"bad_script.py\", line 4, in <module>\n"
                "ZeroDivisionError: division by zero"
            ),
            "arguments": {"command": "python bad_script.py"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, NEED_RETRY)
        self.assertTrue(r.evidence.get("fatal_error_detected"))
        self.assertIn("致命未捕获异常", r.message)

    def test_run_command_exit_0_with_syntax_error_triggers_retry(self):
        """退出码虽为 0，但输出中包含 SyntaxError 时拦截并要求重试。"""
        record = {
            "tool": "run_command",
            "status": "success",
            "result": "$ node app.js\n[exit code 0]\nSyntaxError: Unexpected token '{'",
            "arguments": {"command": "node app.js"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, NEED_RETRY)
        self.assertTrue(r.evidence.get("fatal_error_detected"))

    def test_run_command_grep_query_is_exempt(self):
        """查询类命令（如 grep/findstr）即便输出匹配到了 Traceback 也不误判。"""
        record = {
            "tool": "run_command",
            "status": "success",
            "result": "$ grep -rn \"Traceback\" logs/\n[exit code 0]\nlogs/app.log:12: Traceback (most recent call last):",
            "arguments": {"command": "grep -rn \"Traceback\" logs/"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, PASSED)

    def test_execute_command_json_format_support(self):
        """execute_command 的 JSON 结构输出支持与退出码解析。"""
        record = {
            "tool": "execute_command",
            "status": "success",
            "result": '{"stdout": "Build succeeded", "stderr": "", "exit_code": 0, "execution_time": 0.12}',
            "arguments": {"command": "npx tsc --noEmit"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, PASSED)
        self.assertEqual(r.evidence.get("exit_code"), 0)

    def test_execute_command_json_nonzero_triggers_retry(self):
        """execute_command 非零退出码返回 NEED_RETRY。"""
        record = {
            "tool": "execute_command",
            "status": "success",
            "result": '{"stdout": "", "stderr": "error TS2304: Cannot find name", "exit_code": 2, "execution_time": 0.3}',
            "arguments": {"command": "npx tsc --noEmit"},
        }
        r = verifier.verify(record)
        self.assertEqual(r.status, NEED_RETRY)
        self.assertEqual(r.evidence.get("exit_code"), 2)


if __name__ == "__main__":
    unittest.main()
