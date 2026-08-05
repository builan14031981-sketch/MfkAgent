"""决策引擎 - 决定是否应该使用工具

职责：
1. 基于意图和上下文，决定是否应该使用工具
2. 选择合适的工具组合
3. 返回决策结果（需要工具、工具列表、原因）

决策策略：
- Rule First：优先使用规则匹配
- LLM Second：规则无法判断时，交给模型判断
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from .intent_detector import IntentDetector, Intent


@dataclass
class ToolDecision:
    """工具决策结果"""
    need_tool: bool  # 是否需要工具
    tools: List[str]  # 推荐工具列表
    reason: str  # 决策原因
    confidence: float  # 置信度


class DecisionEngine:
    """决策引擎"""

    def __init__(self):
        self._intent_detector = IntentDetector()

        # 意图到工具的映射
        self._intent_tool_mapping: Dict[Intent, List[str]] = {
            Intent.SYSTEM_DIAGNOSIS: [
                "run_command",  # 执行系统命令
            ],
            Intent.FILE_OPERATION: [
                "read_file",
                "write_file",
                "list_files",
            ],
            Intent.PROJECT_DEBUG: [
                "run_command",  # 运行测试、查看日志
                "read_file",  # 读取代码
                "git_status",
                "git_diff",
                "git_log",
            ],
            Intent.WEB_SEARCH: [
                "web_search",
                "fetch_url",
            ],
            Intent.MEMORY_OPERATION: [
                "add_memory",
            ],
            Intent.GENERAL_CHAT: [],  # 普通聊天不需要工具
        }

        # 系统诊断命令推荐
        self._system_diagnosis_commands = {
            "网络": ["ipconfig", "netstat", "ping -n 3 8.8.8.8", "nslookup"],
            "代理": ["ipconfig", "netstat"],
            "CPU": ["systeminfo"],
            "内存": ["systeminfo"],
            "磁盘": ["systeminfo"],
            "端口": ["netstat"],
            "进程": ["tasklist"],
            "服务": ["sc query"],
        }

    def decide(
        self,
        message: str,
        available_tools: List[str],
        project_path: Optional[str] = None,
    ) -> ToolDecision:
        """做出工具决策

        Args:
            message: 用户消息
            available_tools: 可用工具列表
            project_path: 项目路径（如果有）

        Returns:
            ToolDecision: 决策结果
        """
        # 1. 检测意图
        intent, confidence = self._intent_detector.detect(message)

        # 2. 基于意图获取推荐工具
        recommended_tools = self._intent_tool_mapping.get(intent, [])

        # 3. 过滤可用工具
        filtered_tools = [t for t in recommended_tools if t in available_tools]

        # 4. 判断是否需要工具
        need_tool = len(filtered_tools) > 0

        # 5. 生成决策原因
        reason = self._generate_reason(intent, filtered_tools, project_path)

        return ToolDecision(
            need_tool=need_tool,
            tools=filtered_tools,
            reason=reason,
            confidence=confidence,
        )

    def _generate_reason(
        self,
        intent: Intent,
        tools: List[str],
        project_path: Optional[str],
    ) -> str:
        """生成决策原因"""
        intent_descriptions = {
            Intent.SYSTEM_DIAGNOSIS: "用户要求检查系统状态",
            Intent.FILE_OPERATION: "用户要求操作文件",
            Intent.PROJECT_DEBUG: "用户要求调试项目",
            Intent.WEB_SEARCH: "用户要求搜索信息",
            Intent.MEMORY_OPERATION: "用户要求保存记忆",
            Intent.GENERAL_CHAT: "普通聊天，不需要工具",
        }

        base_reason = intent_descriptions.get(intent, "未知意图")

        if tools:
            tool_names = ", ".join(tools)
            return f"{base_reason}，推荐使用工具：{tool_names}"
        else:
            return base_reason

    def get_intent(self, message: str) -> Intent:
        """获取用户意图（便捷方法）"""
        intent, _ = self._intent_detector.detect(message)
        return intent
