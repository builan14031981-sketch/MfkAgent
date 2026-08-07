"""Agent Runtime Phase 2 — Task 类型定义"""

from enum import Enum
from dataclasses import dataclass


class TaskType(Enum):
    CHAT = "chat"          # 闲聊/问候
    ANSWER = "answer"      # 默认问答
    RETRIEVE = "retrieve"  # 查找/搜索/读取
    ACTION = "action"      # 执行操作
    ANALYZE = "analyze"    # 分析/检查/评估
    CODE = "code"          # 代码相关


@dataclass
class TaskDecision:
    """任务路由决策结果"""
    task_type: TaskType
    intent: str = ""
    confidence: float = 0.0
    reason: str = ""