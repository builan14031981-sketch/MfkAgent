"""工具结果观察器 — 判断是否需要继续调用更多工具。"""

from typing import Dict, List, Optional


class ToolResultObserver:
    """工具结果观察器"""

    def __init__(self):
        # 失败信号（触发继续调用）
        self._failure_signals = [
            "失败", "错误", "超时", "无法连接",
            "拒绝访问", "未找到", "不存在",
            "timeout", "refused", "not found",
        ]

        # 诊断链：当前工具 → 推荐的下一步工具
        self._diagnostic_chain: Dict[str, List[str]] = {
            "ping": ["ipconfig", "nslookup"],
            "ipconfig": ["netstat", "nslookup"],
            "netstat": ["nslookup", "ping"],
            "nslookup": ["ping"],
        }

    def observe(
        self,
        tool_name: str,
        tool_result: str,
        original_intent: str,
    ) -> Dict:
        """观察工具执行结果，判断是否需要继续调用

        Args:
            tool_name: 工具名称
            tool_result: 工具执行结果
            original_intent: 原始意图

        Returns:
            {
                "should_continue": bool,
                "next_tools": List[str],
                "reason": str,
            }
        """
        # 检查结果是否包含失败信号
        has_failure = any(signal in tool_result for signal in self._failure_signals)

        if not has_failure:
            return {
                "should_continue": False,
                "next_tools": [],
                "reason": "工具执行成功",
            }

        # 根据当前工具和意图推荐下一步
        next_tools = self._get_next_tools(tool_name, original_intent)

        if not next_tools:
            return {
                "should_continue": False,
                "next_tools": [],
                "reason": "工具执行失败，但没有推荐的后续工具",
            }

        return {
            "should_continue": True,
            "next_tools": next_tools,
            "reason": f"工具 {tool_name} 执行失败，建议继续调用: {', '.join(next_tools)}",
        }

    def _get_next_tools(self, current_tool: str, intent: str) -> List[str]:
        """获取下一步推荐工具"""
        if intent == "system_diagnosis":
            return self._diagnostic_chain.get(current_tool, [])
        return []