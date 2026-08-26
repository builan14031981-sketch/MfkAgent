"""Tool Guidance Layer V1 — 动态工具使用指导注入。

职责：
  根据当前任务类型（intent）和会话上下文，生成结构化的工具使用指导文本，
  注入 System Prompt，帮助 LLM 正确选择和使用工具。

设计原则：
  - 纯指导（Guidance），不替代 LLM 决策（非 Gate）
  - 不修改 ToolSelector / Executor / AgentRuntime
  - 仅在上下文构建阶段注入，零运行时开销

V1 支持的任务类型：
  - coding        : 代码编写/修改任务
  - research      : 信息检索/调研任务
  - file_operation: 文件读取/操作任务
  - debugging     : 问题排查/调试任务

每类指导包含：
  - 推荐工具流程（Tool Flow）
  - 工具使用建议（Suggestions）
  - 常见错误提醒（Warnings）
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ──── 意图到指导类型的映射 ────

# tool_runtime intent → guidance type
_INTENT_TO_GUIDANCE: dict[str, str] = {
    "file_operation": "file_operation",
    "project_debug": "debugging",
    "system_diagnosis": "debugging",
    "web_search": "research",
    "git_operation": "coding",
    "memory_operation": "file_operation",
    "image_generation": "creative",
    "creative": "creative",
}


def _resolve_guidance_type(
    intent: str,
    project_bound: bool,
    message: str,
) -> Optional[str]:
    """根据意图和上下文解析应使用的指导类型。

    优先级：
      1. 意图直接映射（_INTENT_TO_GUIDANCE）
      2. 已绑定项目 + 无明确意图 → coding（代码上下文）
      3. 其余 → None（不注入指导）

    Args:
        intent: tool_runtime decision 的 intent 字段
        project_bound: 是否已绑定项目
        message: 用户消息（备用判断）

    Returns:
        指导类型标识符，或 None（不注入）
    """
    # 1. 意图直接映射
    guidance_type = _INTENT_TO_GUIDANCE.get(intent)
    if guidance_type:
        return guidance_type

    # 2. 已绑定项目 + 无明确意图 → 不强制注入 coding 指导
    #    Phase 3.5: 已绑定项目不代表用户需要 coding 帮助，
    #    避免 guidance 干扰 casual chat 的场景。
    if project_bound and intent != "general_chat":
        return "coding"

    # 3. 消息关键词兜底
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in ["代码", "code", "编程", "函数", "bug", "修复", "修改"]):
        return "coding"
    if any(kw in msg_lower for kw in ["搜索", "查找", "调研", "资料", "search", "research"]):
        return "research"
    if any(kw in msg_lower for kw in ["文件", "读取", "写入", "创建", "file", "read", "write"]):
        return "file_operation"
    if any(kw in msg_lower for kw in ["海报", "生图", "宣传", "设计", "周边", "画张", "画一个", "图片", "画图"]):
        return "creative"
    if any(kw in msg_lower for kw in ["调试", "debug", "报错", "错误", "排查", "诊断"]):
        return "debugging"

    return None


# ──── 指导模板 ────

# 通用前缀（所有指导类型共享）
_GUIDANCE_PREAMBLE = (
    "## 工具使用指导 (Tool Guidance)\n"
    "以下为当前任务类型的工具使用建议，请优先参考但不强制遵循："
)

GUIDANCE_TEMPLATES: dict[str, dict] = {
    "creative": {
        "tool_flow": [
            "1. 方案选型与交互：当用户需求较宽泛或询问建议时，优先使用 `ask_user_choice` 提供 2-4 个推荐方案/预置模板供用户在卡片中点选",
            "2. 风格匹配与 Prompt 编译：按选定技能/模板规范将需求编译为高质量英文 Prompt（遵守留白/平涂/控色等纪律）",
            "3. 图像生成与自检：调用 `generate_image` 生成图像，并在生成后对照质量检查表做自检说明",
        ],
        "suggestions": [
            "当用户询问有哪些设计方案或模板推荐时，调用 `ask_user_choice` 可以在界面上为用户弹出精致的可交互选择卡片",
            "生成图像 Prompt 统一使用英文表达，避免中文图生图出现乱码",
            "严格遵循选定技能的负空间与配色规则，不混用互斥画风",
        ],
        "warnings": [
            "禁止在用户询问方案建议时在文本中僵硬罗列选项，应优先使用 `ask_user_choice` 弹出选择卡片",
            "禁止对平涂/剪影类技能使用复杂的渐变色和高光渲染",
        ],
    },
    "coding": {
        "tool_flow": [
            "1. 探索阶段：先用 list_files 了解项目结构，再用 read_file 阅读相关代码",
            "2. 修改阶段：用 write_file 写入修改后的代码，每次只改动必要的部分",
            "3. 验证阶段：修改后立即用 execute_command 编译/运行验证，确保无语法错误",
            "4. 版本管理阶段（推荐）：用 git_status 查看改动 → git_diff 查看差异 → git_commit 提交",
            "5. 同步阶段（可选）：用 git_push 推送提交到远程（需审批）",
        ],
        "suggestions": [
            "修改代码前必须先用 read_file 读取目标文件的最新内容",
            "每次 write_file 后立即用 execute_command 验证（如 pytest 或 npm test 或 npm run build）",
            "优先使用项目已有的工具和依赖，不引入冗余第三方库",
            "如果验证失败，根据报错信息修正后重新验证，直到通过",
            "修改完成后，用 git_status 总结改动，询问用户是否需要提交",
        ],
        "warnings": [
            "禁止在未读取文件的情况下直接修改代码",
            "禁止一次修改多个不相关的文件，应逐个修改并验证",
            "禁止忽略验证失败的结果，必须先修复再继续",
            "禁止猜测文件路径，先用 list_files 确认",
        ],
        "execute_workflow": [
            "## 项目命令执行（execute_command）",
            "使用 execute_command 执行项目命令，自动放行的安全命令：",
            "- pytest / python -m pytest — 运行 Python 测试",
            "- npm test / npm run build / npm run lint — Node.js 项目命令",
            "- cargo test / cargo build — Rust 项目命令",
            "- go test / go build — Go 项目命令",
            "",
            "启动/运行项目时：",
            "1. 先检查项目类型（package.json / Cargo.toml / go.mod 等）",
            "2. 再执行对应命令：npm run dev / python app.py / cargo run",
            "3. 未知命令会触发审批，请先向用户说明",
        ],
        "git_workflow": [
            "## Git 工作流推荐",
            "代码修改任务的标准 Git 流程：",
            "1. git_status — 查看当前工作区状态",
            "2. git_branch_list — 确认当前分支",
            "3. git_log — 查看最近的提交历史，了解上下文",
            "4. read_file — 阅读目标文件",
            "5. 修改代码（write_file）",
            "6. git_diff — 查看改动内容，确认无误",
            "7. git_commit — 提交改动",
            "8. git_push — 推送到远程（需审批，询问用户是否执行）",
            "",
            "远程同步相关：",
            "- git_fetch — 获取远程更新（只读，无需审批）",
            "- git_pull — 拉取并合并远程更新（需审批）",
            "- git_remote — 查看远程仓库信息",
            "- git_clone — 克隆新仓库（需审批）",
            "- github_create_pr — 创建 Pull Request（需审批 + GitHub Token）",
        ],
    },
    "research": {
        "tool_flow": [
            "1. 搜索阶段：用 web_search 搜索相关资料，使用精准的关键词",
            "2. 深入阶段：用 fetch_url 打开高价值链接，获取详细内容",
            "3. 筛选阶段：对搜索结果进行相关性筛选，过滤广告和噪音",
            "4. 总结阶段：按主题分类，结构化输出关键发现并注明来源",
        ],
        "suggestions": [
            "搜索时使用具体的关键词组合，而非模糊的单个词",
            "至少查看 2-3 个不同来源，进行交叉验证",
            "区分事实与推测，引用信息时注明来源",
            "总结时按主题分类，突出关键发现",
        ],
        "warnings": [
            "禁止仅依赖单一来源的信息",
            "禁止将推测当作事实陈述",
            "禁止忽略搜索结果中的矛盾信息，应如实报告",
            "搜索结果为空时，尝试更换关键词重新搜索，而非凭空编造",
        ],
    },
    "file_operation": {
        "tool_flow": [
            "1. 确认阶段：用 list_files 确认目标目录和文件是否存在",
            "2. 读取阶段：用 read_file 读取文件内容进行分析",
            "3. 操作阶段（如需写入）：用 write_file 写入内容",
            "4. 确认阶段：用 read_file 或 list_files 验证操作结果",
        ],
        "suggestions": [
            "操作文件前先用 list_files 确认路径和文件存在",
            "read_file 只能读取 100KB 以内的文件，超大文件需分段处理",
            "write_file 会自动创建不存在的父目录",
            "文件路径使用相对路径（相对于项目根目录）",
        ],
        "warnings": [
            "禁止在未确认路径的情况下直接操作文件",
            "禁止写入系统目录或项目外的文件",
            "write_file 会覆盖已有文件，写入前确认用户意图",
            "文件不存在时不要猜测内容，先报告用户",
        ],
    },
    "debugging": {
        "tool_flow": [
            "1. 复现阶段：用 run_command 复现问题，获取完整错误信息",
            "2. 定位阶段：用 read_file 阅读报错涉及的代码文件",
            "3. 分析阶段：根据错误堆栈和日志定位根因",
            "4. 修复阶段：用 write_file 实施修复",
            "5. 验证阶段：用 run_command 重新运行，确认问题已解决",
        ],
        "suggestions": [
            "先复现问题获取完整错误信息，不要猜测原因",
            "使用 git diff 或 git log 查看最近的改动，定位可能引入问题的变更",
            "一次只修改一个可能的原因，修改后立即验证",
            "如果首次修复失败，重新分析错误信息，调整方案",
        ],
        "warnings": [
            "禁止在未复现和获取错误信息的情况下直接猜测修改",
            "禁止同时修改多个可能原因，导致无法判断哪个修复有效",
            "禁止忽略错误堆栈中的关键信息（文件路径、行号、错误类型）",
            "调试失败时不要反复尝试相同的修复方案",
        ],
    },
}


def get_tool_guidance(
    intent: str,
    project_bound: bool = False,
    message: str = "",
) -> Optional[str]:
    """根据任务类型生成工具使用指导文本。

    Args:
        intent: tool_runtime decision 的 intent 字段
        project_bound: 是否已绑定项目
        message: 用户消息文本（备用关键词匹配）

    Returns:
        格式化的指导文本，或 None（无需指导时）
    """
    guidance_type = _resolve_guidance_type(intent, project_bound, message)
    if not guidance_type:
        return None

    template = GUIDANCE_TEMPLATES.get(guidance_type)
    if not template:
        return None

    sections = [_GUIDANCE_PREAMBLE]

    # 推荐工具流程
    flow = template.get("tool_flow", [])
    if flow:
        sections.append("\n### 推荐工具流程")
        sections.extend(flow)

    # 工具使用建议
    suggestions = template.get("suggestions", [])
    if suggestions:
        sections.append("\n### 工具使用建议")
        sections.extend(f"- {s}" for s in suggestions)

    # Git 工作流推荐（coding 类型专属）
    git_workflow = template.get("git_workflow", [])
    if git_workflow:
        sections.append("")
        sections.extend(git_workflow)

    # 项目命令执行指导（coding 类型专属）
    execute_workflow = template.get("execute_workflow", [])
    if execute_workflow:
        sections.append("")
        sections.extend(execute_workflow)

    # 常见错误提醒
    warnings = template.get("warnings", [])
    if warnings:
        sections.append("\n### 常见错误提醒")
        sections.extend(f"- {s}" for s in warnings)

    guidance_text = "\n".join(sections)
    logger.info(
        "[guidance] 已注入工具使用指导 type=%s intent=%s project_bound=%s",
        guidance_type, intent, project_bound,
    )
    return guidance_text