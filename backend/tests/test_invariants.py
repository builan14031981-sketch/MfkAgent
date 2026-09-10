"""测试项目不变量通道 (Architectural Invariants) 与 Prompt 装配。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.invariants import get_invariants_prompt, BASE_INVARIANTS
from app.core.agent_base_instruction import get_agent_base_instruction
from app.core.agent_runtime.context_builder import ChatContextBuilder


class InvariantsTestCase(unittest.TestCase):
    def test_base_invariants_content(self):
        prompt = get_invariants_prompt()
        self.assertIn("项目不变量通道", prompt)
        self.assertIn("剪枝优先于修饰", prompt)
        self.assertIn("子代理绝对绝缘长期记忆", prompt)
        self.assertIn("沉浸式内聚交互", prompt)

    def test_invariants_with_project_agents_md(self):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        prompt = get_invariants_prompt(repo_root)
        self.assertIn("项目不变量通道", prompt)
        # 确认 AGENTS.md 约束被提取追加
        if os.path.isfile(os.path.join(repo_root, "AGENTS.md")):
            self.assertIn("当前项目 AGENTS.md 约束", prompt)

    def test_agent_base_instruction_code_skepticism(self):
        base_inst = get_agent_base_instruction()
        self.assertIn("代码怀疑论与剪枝优先", base_inst)
        self.assertIn("死活审查", base_inst)


if __name__ == "__main__":
    unittest.main()
