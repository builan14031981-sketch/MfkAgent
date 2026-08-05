"""意图检测器 - 基于规则的用户意图识别

职责：
1. 分析用户消息，识别意图类型
2. 返回意图和置信度
3. 不生成答案，只做意图分类

支持的意图类型：
- SYSTEM_DIAGNOSIS: 系统诊断（网络、硬件、软件状态）
- FILE_OPERATION: 文件操作（读取、写入、分析）
- PROJECT_DEBUG: 项目调试（bug、报错、编译失败）
- WEB_SEARCH: 网络搜索
- MEMORY_OPERATION: 记忆操作
- GENERAL_CHAT: 普通聊天
"""

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
    GENERAL_CHAT = "general_chat"


class IntentDetector:
    """意图检测器 - 基于关键词规则匹配"""

    def __init__(self):
        # 意图关键词映射（优先级从高到低）
        self._intent_patterns: Dict[Intent, List[str]] = {
            Intent.SYSTEM_DIAGNOSIS: [
                # 系统状态检查
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
                # 英文关键词
                r"check.*network",
                r"check.*system",
                r"network.*issue",
                r"why.*can.*not.*open",
            ],
            Intent.FILE_OPERATION: [
                # 文件操作
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
                # 英文关键词
                r"read.*file",
                r"analyze.*code",
                r"analyze.*file",
                r"modify.*file",
                r"create.*file",
            ],
            Intent.PROJECT_DEBUG: [
                # 项目调试
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
                r"debug.*code",
                r"fix.*bug",
                r"why.*error",
                r"why.*failed",
            ],
            Intent.WEB_SEARCH: [
                # 网络搜索
                r"搜索.*",
                r"查找.*信息",
                r"查询.*资料",
                r"网上.*找",
                r"帮我.*搜",
                r"search.*",
                r"find.*information",
            ],
            Intent.MEMORY_OPERATION: [
                # 记忆操作
                r"记住.*",
                r"保存.*记忆",
                r"记住.*这个",
                r"以后.*记得",
                r"remember.*",
                r"save.*memory",
            ],
        }

        # 排除模式：匹配这些模式的不是对应意图
        self._exclude_patterns: Dict[Intent, List[str]] = {
            Intent.SYSTEM_DIAGNOSIS: [
                r"什么是.*网络",  # 知识解释
                r"如何.*配置.*网络",  # 教程类
                r"网络.*协议",  # 概念类
            ],
            Intent.FILE_OPERATION: [
                r"什么是.*文件",  # 知识解释
                r"如何.*使用.*文件",  # 教程类
            ],
        }

    def detect(self, message: str) -> Tuple[Intent, float]:
        """检测用户意图

        Args:
            message: 用户消息

        Returns:
            (意图类型, 置信度)
        """
        message_lower = message.lower()

        # 按优先级检查每个意图
        for intent, patterns in self._intent_patterns.items():
            # 先检查排除模式
            exclude_patterns = self._exclude_patterns.get(intent, [])
            for exclude in exclude_patterns:
                if re.search(exclude, message_lower):
                    continue

            # 检查匹配模式
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    # 根据匹配长度计算置信度
                    match_length = len(re.search(pattern, message_lower).group())
                    confidence = min(0.95, 0.7 + match_length * 0.01)
                    return intent, confidence

        # 默认返回普通聊天
        return Intent.GENERAL_CHAT, 0.5

    def get_intent_description(self, intent: Intent) -> str:
        """获取意图描述"""
        descriptions = {
            Intent.SYSTEM_DIAGNOSIS: "系统诊断 - 检查系统状态、网络、硬件等",
            Intent.FILE_OPERATION: "文件操作 - 读取、写入、分析文件",
            Intent.PROJECT_DEBUG: "项目调试 - 修复 bug、解决报错",
            Intent.WEB_SEARCH: "网络搜索 - 搜索互联网信息",
            Intent.MEMORY_OPERATION: "记忆操作 - 保存或查询记忆",
            Intent.GENERAL_CHAT: "普通聊天 - 日常对话",
        }
        return descriptions.get(intent, "未知意图")
