"""全局工具策略 — 所有 Agent 默认注入，不依赖 capabilities 配置。

三块职责分离（Agent Prompt 体系 V1.5）：
- get_execution_policy()    ③ 层：统一执行规范（工具能力 / 安全 / 审批 / 禁止猜测 / 自检）
- get_permission_context()  ④ 层：当前会话权限上下文（可见工具 + plan 只读约束）
- get_project_policy()      ⑤ 层：项目工作流（仅项目绑定 Agent 注入）

build_policy 保留作为组合导出（runtime.py 引用），兼容旧调用方式。
"""

POLICY_VERSION = "1"


def get_execution_policy() -> str:
    """统一执行规范（③ 层，替代原 default_policy + TOOL_AGENCY + 自检段）"""
    return f"""## Execution Policy v{POLICY_VERSION}

1. 优先使用工具获取真实信息，不猜测环境状态；你可以调用 read_file / list_files / search_files 自由读取本地文件（支持项目相对路径、绝对路径及用户主目录配置）。无法获取时才说明。
2. 修改文件/执行有副作用操作前，先说明计划；需审批的操作等待审批，不重复发起。
3. 完成任务后用简短摘要总结做了什么、结果如何。
4. 【Skill 契约强制遵守】用户消息中若包含 `<skill name="...">...</skill>` 标签，
   该标签内的内容为当前会话的【强制行为契约】，必须逐条严格遵循。
   - 契约中的输出格式、必含字段、禁止项、自查清单，缺一项即视为未完成，必须补齐再交付。
   - 契约中的禁止项严格禁止输出（如禁止使用 emoji 即一个都不能用）。
   - 不要在回复中输出 `<skill>` 标签本身，它仅用于标记契约范围。

### 禁止行为
- 在可获取真实信息时仅提供假设性建议；忽略工具返回的真实数据。

### 自检规则
回答前自问："不获取外部数据能否给出可靠答案？" 若否，先调用工具。"""


def get_permission_context(chat, agent_capabilities=None) -> str:
    """权限上下文（④ 层）：permission.py resolve 结果 + plan 只读约束。

    Args:
        chat: Chat ORM 对象（需含 mode / project_path）
        agent_capabilities: Agent 的 capabilities（仅高级能力，不缩减基础工具）

    Returns:
        权限上下文文本，供 ④ 层注入 system prompt。
    """
    from .permission import PermissionFilter

    tool_names = PermissionFilter().resolve(chat, agent_capabilities)
    chat_mode = getattr(chat, "mode", "build") or "build"

    lines = ["## 当前会话权限上下文"]
    if tool_names:
        lines.append("当前会话可见工具: " + ", ".join(tool_names))
    else:
        lines.append("当前会话无可用工具。")
    if chat_mode == "plan":
        from .risk_engine import READ_ONLY_TOOLS, TOOL_RISK_POLICY

        lines.append("当前处于 Plan 模式（只读）。只允许执行只读操作：读文件 / 目录结构 / 代码搜索 / git 状态查看 / 只读命令 / 测试与环境检查。")
        lines.append(
            "禁止操作: " + ", ".join(sorted(TOOL_RISK_POLICY.keys()))
        )
        lines.append(
            "只读可用: " + ", ".join(sorted(READ_ONLY_TOOLS))
        )
    return "\n".join(lines)


def get_project_policy() -> str:
    """获取项目工作流策略（⑤ 层，仅项目绑定 Agent 额外注入）"""
    return """## 项目工作流（绑定项目时生效）

当你修改项目代码时，必须遵循"改后自验"闭环：

1. 每次调用 write_file 修改代码后，都必须调用 run_command 验证改动没有引入错误：
   - Python 项目：python -m py_compile <改动的文件>
   - 有测试则运行 pytest 或 python -m unittest
   - 前端/TS 项目：npm run lint / npm run typecheck / npm run build
2. 如果验证输出报错，不要结束任务：根据报错修复代码，然后重新运行验证，直到全部通过。
3. 只有在验证通过后，才允许输出最终回答。
4. 完成后用 git diff 或 git status 向用户总结你改了哪些文件。"""


def get_plan_mode_policy() -> str:
    """获取 Plan 模式策略（仅 plan 模式额外注入）"""
    return """## Plan 模式（只读模式）

当前处于 Plan 模式，只能执行只读操作（Plan 与 Build 的区别是修改权限，不是工具能力）：
- 允许：read_file / list_files / search_files / git_status / git_diff / git_log / run_command（只读命令，含测试与环境检查）
- 禁止：write_file / delete / rename / git_commit 等任何修改操作，禁止修改数据库与配置

如果需要修改代码，请先分析并给出建议，等用户确认后再切换到 Build 模式。"""


def build_policy(chat, agent_capabilities=None) -> str:
    """根据 Chat 对象自动组合策略文本（兼容导出）

    组合：③ execution_policy + ④ permission_context + ⑤ project_policy（绑定项目时）
          + Plan 模式只读策略（chat.mode == "plan" 时）。

    Args:
        chat: Chat 对象，需包含 project_path、mode 属性
        agent_capabilities: Agent 的 capabilities（可选）

    Returns:
        组合后的策略文本
    """
    policies = [get_execution_policy(), get_permission_context(chat, agent_capabilities)]

    if getattr(chat, "mode", "build") == "plan":
        policies.append(get_plan_mode_policy())

    if getattr(chat, "project_path", None):
        policies.append(get_project_policy())

    return "\n\n".join(policies)
