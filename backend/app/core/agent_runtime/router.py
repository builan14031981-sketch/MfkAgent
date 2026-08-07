"""Agent Runtime Phase 2 — TaskRouter

职责：
  根据用户消息 + tool_runtime decision 判断任务类型，
  不重新调用 IntentAnalyzer，不复制 tool_runtime 逻辑。
"""

from typing import Optional

from .types import TaskType, TaskDecision


# ──── 关键词规则 ────

_CHAT_KEYWORDS = [
    "你好", "谢谢", "哈哈", "嘿嘿", "再见", "拜拜", "晚安", "早安",
    "hi", "hello", "thanks", "ok", "好的", "嗯", "哦",
]


_CODE_KEYWORDS = [
    "代码", "python", "bug", "函数", "接口", "类", "class", "def",
    "变量", "循环", "递归", "算法", "数据结构", "import", "模块",
    "编译", "运行", "报错", "异常", "exception", "error",
    "重构", "优化", "性能", "类型", "type", "注释",
    "前端", "后端", "api", "数据库", "sql", "json",
    "react", "vue", "node", "typescript", "javascript", "java", "go", "rust",
    "测试", "test", "单元测试", "集成测试",
    "设计模式", "架构", "依赖", "库", "框架",
]


_ACTION_KEYWORDS = [
    "帮我创建", "帮我修改", "帮我写", "帮我做", "帮我改", "帮我删",
    "执行", "运行", "删除", "安装", "卸载", "配置", "设置",
    "创建", "新建", "生成", "修改", "更新", "删除", "移除",
    "提交", "推送", "pull", "push", "commit",
    "部署", "发布", "启动", "停止", "重启",
    "下载", "上传", "导入", "导出",
    "添加", "追加", "插入",
]


_ANALYZE_KEYWORDS = [
    "分析", "检查", "评估", "为什么", "原因", "怎么回事",
    "诊断", "排查", "定位", "对比", "比较",
    "有什么问题", "出了什么问题", "哪里不对", "哪里错了",
    "建议", "推荐", "最佳实践", "最佳方案",
    "review", "审查", "审计",
]


_RETRIEVE_KEYWORDS = [
    "查找", "搜索", "读取文件", "查看文件", "查看资料", "查看文档",
    "列出", "显示", "找到", "定位", "在哪",
    "有什么文件", "有哪些文件", "目录结构",
    "git log", "git status", "git diff", "git 记录",
    "历史", "记录", "日志", "最近", "之前",
    "是什么", "什么是", "定义", "概念", "解释",
]


class TaskRouter:
    """任务路由器 — Agent 自主决策入口。

    根据用户消息和 tool_runtime decision 判断任务类型。
    规则简单，不需要完美，目标是建立统一入口。
    """

    def route(
        self,
        message: str,
        tool_decision: Optional[dict] = None,
        has_tools: bool = False,
    ) -> TaskDecision:
        """分析消息并返回任务路由决策。

        Args:
            message: 用户消息文本
            tool_decision: tool_runtime 的 decision 结果
                          {"layer": str, "intent": str, "reason": str, "confidence": float}
            has_tools: 当前会话是否有可用工具

        Returns:
            TaskDecision: 路由决策
        """
        if not message or not message.strip():
            return TaskDecision(
                task_type=TaskType.CHAT,
                intent="empty",
                confidence=1.0,
                reason="空消息",
            )

        msg = message.strip()

        # ──── 1. CHAT: 闲聊/问候 ────
        if self._match_any(msg, _CHAT_KEYWORDS):
            return TaskDecision(
                task_type=TaskType.CHAT,
                intent="chat",
                confidence=0.9,
                reason="识别为闲聊/问候",
            )

        # ──── 2. 利用 tool_decision 辅助判断 ────
        tool_intent = ""
        tool_confidence = 0.0
        if tool_decision:
            tool_intent = tool_decision.get("intent", "")
            tool_confidence = tool_decision.get("confidence", 0.0)

        # ──── 3. CODE: 代码相关 ────
        if self._match_any(msg, _CODE_KEYWORDS):
            return TaskDecision(
                task_type=TaskType.CODE,
                intent=tool_intent or "code",
                confidence=max(0.85, tool_confidence),
                reason="识别为代码相关任务",
            )

        # ──── 4. ACTION: 执行操作 ────
        if self._match_any(msg, _ACTION_KEYWORDS):
            return TaskDecision(
                task_type=TaskType.ACTION,
                intent=tool_intent or "action",
                confidence=max(0.85, tool_confidence),
                reason="识别为执行操作任务",
            )

        # ──── 5. RETRIEVE: 查找/搜索/读取 ────
        if self._match_any(msg, _RETRIEVE_KEYWORDS):
            return TaskDecision(
                task_type=TaskType.RETRIEVE,
                intent=tool_intent or "retrieve",
                confidence=max(0.8, tool_confidence),
                reason="识别为查找/检索任务",
            )

        # ──── 6. ANALYZE: 分析/检查/评估 ────
        if self._match_any(msg, _ANALYZE_KEYWORDS):
            return TaskDecision(
                task_type=TaskType.ANALYZE,
                intent=tool_intent or "analyze",
                confidence=max(0.8, tool_confidence),
                reason="识别为分析/评估任务",
            )

        # ──── 7. ANSWER: 默认 ────
        return TaskDecision(
            task_type=TaskType.ANSWER,
            intent=tool_intent or "general",
            confidence=0.5,
            reason="默认问答类型",
        )

    @staticmethod
    def _match_any(message: str, keywords: list) -> bool:
        """检查消息是否包含任意关键词"""
        msg_lower = message.lower()
        for kw in keywords:
            if kw.lower() in msg_lower:
                return True
        return False