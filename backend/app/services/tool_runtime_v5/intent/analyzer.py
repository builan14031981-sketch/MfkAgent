"""意图分析器 - 判断用户是否需要工具"""

from enum import Enum
from typing import Dict, List, Tuple
import re


class Intent(str, Enum):
    """用户意图类型"""
    SYSTEM_DIAGNOSIS = "system_diagnosis"
    FILE_OPERATION = "file_operation"
    PROJECT_DEBUG = "project_debug"
    WEB_SEARCH = "web_search"
    MEMORY_OPERATION = "memory_operation"
    KNOWLEDGE_QUESTION = "knowledge_question"
    GENERAL_CHAT = "general_chat"


class IntentAnalyzer:
    """意图分析器"""

    def __init__(self):
        # 需要工具的意图模式
        self._tool_required_patterns: Dict[Intent, List[str]] = {
            Intent.SYSTEM_DIAGNOSIS: [
                r"检查.*电脑",
                r"检查.*系统",
                r"检查.*网络",
                r"网络.*不可用",
                r"网络.*问题",
                r"为什么.*打不开",
                r"为什么.*连不上",
                r"代理.*设置",
                r"DNS.*问题",
                r"CPU.*使用率",
                r"内存.*使用",
                r"磁盘.*空间",
                r"显卡.*驱动",
                r"日志.*查看",
                r"进程.*列表",
                r"端口.*占用",
                r"服务.*状态",
                r"本机.*状态",
                r"本机.*网络",
                r"电脑.*网络",
                r"电脑.*问题",
            ],
            Intent.FILE_OPERATION: [
                r"读取.*文件",
                r"看看.*文件",
                r"分析.*代码",
                r"分析.*文件",
                r"修改.*文件",
                r"创建.*文件",
                r"删除.*文件",
                r"打开.*文件",
                r"文件.*内容",
                r"代码.*逻辑",
                r"这个文件",
                r"那个文件",
            ],
            Intent.PROJECT_DEBUG: [
                r"为什么.*报错",
                r"为什么.*失败",
                r"bug.*修复",
                r"修复.*bug",
                r"编译.*失败",
                r"测试.*失败",
                r"运行.*失败",
                r"启动.*失败",
                r"错误.*信息",
                r"异常.*处理",
                r"调试.*代码",
            ],
            Intent.WEB_SEARCH: [
                r"搜索.*",
                r"查找.*信息",
                r"查询.*资料",
                r"网上.*找",
                r"帮我.*搜",
            ],
            Intent.MEMORY_OPERATION: [
                r"记住.*",
                r"保存.*记忆",
                r"记住.*这个",
                r"以后.*记得",
            ],
        }

        # 不需要工具的意图模式（知识问答）
        self._knowledge_patterns = [
            r"什么是.*",
            r".*是什么",
            r"如何.*配置",
            r"怎么.*使用",
            r".*原理",
            r".*概念",
            r"解释.*",
            r"说明.*",
        ]

    def analyze(self, message: str) -> Dict:
        """分析用户意图

        Args:
            message: 用户消息

        Returns:
            {
                "intent": Intent,
                "confidence": float,
                "need_tool": bool
            }
        """
        message_lower = message.lower()

        # 先检查是否是知识问答（不需要工具）
        for pattern in self._knowledge_patterns:
            if re.search(pattern, message_lower):
                return {
                    "intent": Intent.KNOWLEDGE_QUESTION,
                    "confidence": 0.95,
                    "need_tool": False,
                }

        # 检查需要工具的意图
        for intent, patterns in self._tool_required_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    match_length = len(re.search(pattern, message_lower).group())
                    confidence = min(0.95, 0.7 + match_length * 0.01)
                    return {
                        "intent": intent,
                        "confidence": confidence,
                        "need_tool": True,
                    }

        # 默认普通聊天
        return {
            "intent": Intent.GENERAL_CHAT,
            "confidence": 0.5,
            "need_tool": False,
        }
