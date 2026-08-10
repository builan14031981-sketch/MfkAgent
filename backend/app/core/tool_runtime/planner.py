"""工具规划器 — 意图 → 软提示（Phase B-2）

不再决定工具可见性（那是 PermissionFilter 的职责），只根据意图结果生成
"任务建议"文本注入 system prompt，供模型参考，不构成任何限制。
"""

from typing import Dict, List


class ToolPlanner:
    """工具规划器（软提示）"""

    def __init__(self):
        # 意图到建议工具的映射（仅供参考，不 gate）
        self._intent_hint_map: Dict[str, List[str]] = {
            "system_diagnosis": ["run_command"],
            "file_operation": ["read_file", "write_file", "list_files"],
            "project_debug": ["run_command", "read_file", "git_status", "git_diff"],
            "git_operation": ["git_status", "git_diff", "git_log", "git_commit", "git_restore"],
            "web_search": ["web_search", "fetch_url"],
            "memory_operation": ["add_memory"],
            "todo_operation": ["manage_todos"],
        }

    def soft_hint(self, intent_result: Dict, available_tools: List[str]) -> str:
        """根据意图生成工具建议文本（空字符串表示无建议）。

        Args:
            intent_result: 意图分析结果（来自 intent.py）
            available_tools: 当前会话可见工具名列表（来自 PermissionFilter.resolve）

        Returns:
            注入 system prompt 的建议文本；无建议时返回空字符串
        """
        if not intent_result.get("suggest_tools"):
            return ""

        intent = intent_result.get("intent", "")
        suggested = self._intent_hint_map.get(intent, [])

        avail = set(available_tools)
        suggested = [t for t in suggested if t in avail]
        if not suggested:
            return ""

        return (
            "## 任务建议（仅供参考，非限制）\n"
            "当前任务建议优先考虑使用工具: " + ", ".join(suggested)
            + "。你可以根据实际情况自主决定是否使用或改用其它可用工具。"
        )
