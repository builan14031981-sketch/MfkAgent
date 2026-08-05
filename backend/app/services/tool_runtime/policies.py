"""工具策略 - 统一的工具使用策略 Prompt

职责：
1. 提供统一的工具使用策略 Prompt
2. 告诉模型什么时候应该使用工具
3. 定义工具使用原则和边界

策略内容：
- 涉及真实环境状态时，优先获取真实数据
- 不要在缺少事实依据时猜测
- 知识解释类问题无需调用工具
- 执行修改行为前，必须确认工具权限
"""

from typing import Optional


class ToolPolicy:
    """工具策略"""

    @staticmethod
    def get_policy_prompt(
        project_path: Optional[str] = None,
        chat_mode: str = "build",
    ) -> str:
        """获取工具策略 Prompt

        Args:
            project_path: 项目路径（如果有）
            chat_mode: 聊天模式（build/plan）

        Returns:
            工具策略 Prompt
        """
        policy_parts = []

        # 1. 基础工具使用策略
        policy_parts.append(_BASE_TOOL_POLICY)

        # 2. 如果有项目路径，添加项目工作流策略
        if project_path:
            policy_parts.append(_PROJECT_WORKFLOW_POLICY)

            # 3. 如果是 plan 模式，添加只读约束
            if chat_mode == "plan":
                policy_parts.append(_PLAN_MODE_POLICY)

        return "\n\n".join(policy_parts)


# 基础工具使用策略
_BASE_TOOL_POLICY = """## 工具使用策略

你拥有工具调用能力。工具使用原则：

1. **涉及真实环境状态的问题，优先获取真实数据**
   包括：
   - 系统状态（CPU、内存、磁盘）
   - 网络状态（连接、代理、DNS）
   - 文件状态（存在、内容、权限）
   - 软件状态（版本、配置、日志）
   - 配置信息（环境变量、设置文件）

2. **不要在缺少事实依据时猜测**
   
   ❌ 错误：
   用户：检查网络问题
   回答：可能是 DNS、防火墙、代理问题...
   
   ✅ 正确：
   调用网络诊断工具，根据结果分析。

3. **知识解释类问题无需调用工具**
   - "什么是 DNS？" → 直接回答
   - "如何配置代理？" → 直接回答

4. **执行任何修改行为前，必须确认工具权限**
   - 写文件、执行命令等修改行为需要谨慎
   - 优先使用只读工具获取信息"""

# 项目工作流策略
_PROJECT_WORKFLOW_POLICY = """## 项目工作流（绑定项目时生效）

当你修改项目代码时，必须遵循以下"改后自验"闭环：

1. **每次调用 write_file 修改代码后，都必须调用 run_command 验证**
   - 验证命令示例：
     - pytest / python -m py_compile / python -m unittest
     - npm run lint / npm run test / npm run build
   - 验证通过后，再告知用户修改完成

2. **调试项目问题时，优先使用工具获取信息**
   - 读取相关文件：read_file
   - 查看 Git 状态：git_status / git_diff / git_log
   - 运行测试：run_command (pytest / npm test)

3. **不要假设代码状态，必须实际查看**
   - 不要猜测文件是否存在
   - 不要猜测代码逻辑
   - 使用工具获取真实信息"""

# Plan 模式只读策略
_PLAN_MODE_POLICY = """## Plan 模式（只读模式）

当前处于 Plan 模式，只能执行只读操作：
- ✅ 允许：read_file / list_files / search_files / git_status / git_diff / git_log / run_command（只读命令）
- ❌ 禁止：write_file / git_commit / git_push 等修改操作

如果需要修改代码，请先分析并给出建议，等用户确认后再切换到 Build 模式。"""
