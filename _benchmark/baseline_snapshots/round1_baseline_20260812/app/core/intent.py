"""用户意图识别（chat / task / file / memory / ...）。

贴近 MfkAgent IntentAnalyzer：用正则规则做确定性分类，
结果仅作为「工具建议」软提示，不做硬 gate。
"""
import re
from typing import Dict


class IntentAnalyzer:
    """两层意图分析：事实需求 → 动作意图。"""

    def __init__(self):
        self._factual_patterns = [
            (
                "file_operation",
                [
                    r"文件.*内容", r"文件.*存在", r"文件.*在哪",
                    r"读取.*文件", r"查看.*文件", r"分析.*代码",
                    r"这个文件", r"那个文件", r"哪个文件",
                ],
            ),
            (
                "project_debug",
                [
                    r"为什么.*报错", r"为什么.*失败", r"修复.*bug",
                    r"测试.*失败", r"运行.*失败", r"调试.*代码",
                ],
            ),
            (
                "memory",
                [
                    r"记住.*", r"记得.*", r"我之前.*说过", r"上次.*提到",
                ],
            ),
        ]

        self._action_patterns = [
            (
                "file_operation",
                [
                    r"创建.*文件", r"修改.*文件", r"删除.*文件",
                    r"列出.*目录", r"写.*文件",
                ],
            ),
            (
                "project_debug",
                [
                    r"调试.*代码", r"修复.*错误", r"解决.*问题", r"跑.*测试",
                ],
            ),
            (
                "memory_operation",
                [
                    r"记住.*", r"保存.*记忆", r"添加.*记忆", r"以后.*记得",
                ],
            ),
        ]

    def analyze(self, message: str) -> Dict:
        """返回 {"suggest_tools": bool, "intent": str, "layer": str, "confidence": float}"""
        msg = (message or "").lower().strip()
        if not msg:
            return {"suggest_tools": False, "intent": "general_chat", "layer": "empty", "confidence": 1.0}

        for intent, patterns in self._factual_patterns:
            for p in patterns:
                if re.search(p, msg):
                    return {"suggest_tools": True, "intent": intent, "layer": "factual_need", "confidence": 0.9}

        for intent, patterns in self._action_patterns:
            for p in patterns:
                if re.search(p, msg):
                    return {"suggest_tools": True, "intent": intent, "layer": "action_intent", "confidence": 0.85}

        return {"suggest_tools": False, "intent": "general_chat", "layer": "self_check", "confidence": 0.5}
