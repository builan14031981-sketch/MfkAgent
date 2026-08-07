"""领域能力标签词表 — Agent Prompt 体系 V1.5

capabilities 改为领域标签（有限枚举），不与工具名耦合。
倾向文本描述"工作方式"，不含具体工具指令。
工具可见性仍由 permission.py 统一控制。
"""

CAPABILITY_TAGS: dict[str, str] = {
    "software_development": "软件开发：编写可运行、可维护的代码，交付后主动验证（构建/测试）。",
    "project_debugging": "问题定位与修复：先复现、取证、定位根因，再修复并验证闭环。",
    "system_analysis": "系统与环境分析：先获取真实环境数据（网络/系统/文件/配置）再下结论。",
    "web_research": "资料调研：需要最新信息或外部资料时，主动检索并核实来源。",
    "data_analysis": "数据分析与决策：基于数据与事实做判断，说明依据与局限。",
    "writing": "写作与表达：产出结构化、精炼、符合目标读者与目的的内容。",
    "code_review": "代码审查：关注质量、架构、边界、安全与长期维护成本，主动指出风险。",
    "frontend_design": "界面设计：遵循设计变量与响应式规范，保证视觉一致与体验。",
    "api_design": "接口设计：关注契约、错误处理、性能与安全性，交付可运行实现。",
    "general_assistance": "通用协助：日常问答、信息整理、任务执行，按需调用可用工具。",
}


def get_capability_prompt(capabilities: list[str] | None) -> str:
    """根据领域能力标签列表生成倾向文本（② 层，注入 system prompt）。

    规则：标签必须存在于 CAPABILITY_TAGS；未知标签被忽略。

    Args:
        capabilities: 领域能力标签列表（如 ["software_development", "code_review"]）

    Returns:
        倾向文本，无有效标签时返回空字符串
    """
    if not capabilities:
        return ""

    lines = ["## 能力倾向"]
    valid = False
    for tag in capabilities:
        desc = CAPABILITY_TAGS.get(tag)
        if desc:
            lines.append(f"- {desc}")
            valid = True
    if not valid:
        return ""

    return "\n".join(lines)