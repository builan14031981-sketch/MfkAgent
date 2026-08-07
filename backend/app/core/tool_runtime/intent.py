"""意图分析器 — 两层判断模型

Layer 1 — 明确事实需求 (Factual Need)
  用户问题涉及真实环境状态，不获取数据无法准确回答。

Layer 2 — 用户动作意图 (Action Intent)
  用户明确要求执行操作（检查、查看、修改、调试），而非仅仅是提问。

Layer 3 — 模型自判断 (Model Self-Judgment)
  自检提示词已并入 execution_policy（policy.py ③ 层），意图结果仅保留 soft_hint。
"""

from typing import Dict, List, Tuple
import re


class IntentAnalyzer:
    """三层意图分析器"""

    def __init__(self):
        # Layer 1: 事实需求模式 — 问题涉及真实环境状态
        self._factual_patterns: List[Tuple[str, List[str]]] = [
            (
                "system_diagnosis",
                [
                    # 网络状态
                    r"网络.*不可用", r"网络.*问题", r"网络.*连不上", r"网络.*断开",
                    r"为什么.*打不开", r"为什么.*连不上", r"为什么.*无法访问",
                    r"代理.*设置", r"代理.*问题", r"DNS.*问题", r"DNS.*解析",
                    r"ping.*不通", r"端口.*占用", r"端口.*冲突",
                    r"IP.*地址", r"IP.*配置", r"网关.*问题",
                    # 系统状态
                    r"CPU.*使用率", r"CPU.*占用", r"内存.*使用", r"内存.*不足",
                    r"磁盘.*空间", r"磁盘.*满", r"硬盘.*空间",
                    r"显卡.*驱动", r"驱动.*问题", r"驱动.*版本",
                    r"系统.*版本", r"系统.*信息", r"系统.*状态",
                    r"进程.*列表", r"进程.*运行", r"服务.*状态",
                    r"本机.*状态", r"本机.*网络", r"本机.*信息",
                    r"电脑.*问题", r"电脑.*状态", r"电脑.*网络",
                    r"日志.*查看", r"日志.*分析", r"错误.*日志",
                    # 配置状态
                    r"环境变量", r"配置.*文件", r"设置.*检查",
                    r"版本.*检查", r"版本.*信息",
                ],
            ),
            (
                "file_operation",
                [
                    r"文件.*内容", r"文件.*存在", r"文件.*在哪",
                    r"读取.*文件", r"查看.*文件", r"看看.*文件",
                    r"分析.*代码", r"分析.*文件", r"分析.*项目",
                    r"代码.*逻辑", r"代码.*结构", r"代码.*问题",
                    r"修改.*文件", r"创建.*文件", r"删除.*文件",
                    r"这个文件", r"那个文件", r"哪个文件",
                ],
            ),
            (
                "project_debug",
                [
                    r"为什么.*报错", r"为什么.*失败", r"为什么.*错误",
                    r"bug.*修复", r"修复.*bug", r"修复.*错误",
                    r"编译.*失败", r"编译.*错误", r"测试.*失败",
                    r"运行.*失败", r"运行.*错误", r"启动.*失败",
                    r"错误.*信息", r"异常.*处理", r"调试.*代码",
                    r"怎么.*解决", r"如何.*修复",
                ],
            ),
        ]

        # Layer 2: 动作意图模式 — 动词 + 目标对象
        self._action_patterns: List[Tuple[str, List[str]]] = [
            (
                "system_diagnosis",
                [
                    r"检查.*电脑", r"检查.*系统", r"检查.*网络", r"检查.*代理",
                    r"检查.*设备", r"检查.*状态", r"检查.*配置",
                    r"查看.*网络", r"查看.*系统", r"查看.*状态", r"查看.*配置",
                    r"测试.*网络", r"测试.*连接", r"测试.*速度",
                    r"诊断.*网络", r"诊断.*系统", r"诊断.*问题",
                    r"帮我.*看看", r"帮我.*检查", r"帮我.*查",
                    r"扫描.*端口", r"扫描.*网络",
                ],
            ),
            (
                "file_operation",
                [
                    r"读取.*文件", r"读.*文件", r"打开.*文件",
                    r"查看.*代码", r"看看.*代码", r"查看.*文件",
                    r"修改.*文件", r"改.*文件", r"编辑.*文件",
                    r"创建.*文件", r"新建.*文件", r"写.*文件",
                    r"删除.*文件", r"删.*文件",
                    r"列出.*文件", r"列出.*目录", r"显示.*目录",
                ],
            ),
            (
                "project_debug",
                [
                    r"调试.*代码", r"调试.*程序", r"调试.*项目",
                    r"运行.*测试", r"执行.*测试", r"跑.*测试",
                    r"编译.*代码", r"编译.*项目", r"构建.*项目",
                    r"修复.*bug", r"修复.*错误", r"解决.*问题",
                ],
            ),
            (
                "web_search",
                [
                    r"搜索.*", r"查找.*", r"查询.*", r"网上.*找",
                    r"帮我.*搜", r"帮我.*找", r"帮我.*查",
                ],
            ),
            (
                "memory_operation",
                [
                    r"记住.*", r"保存.*记忆", r"记住.*这个",
                    r"以后.*记得", r"添加.*记忆", r"记录.*",
                ],
            ),
            (
                "git_operation",
                [
                    r"git.*状态", r"git.*修改", r"git.*提交", r"git.*日志",
                    r"git.*记录", r"git.*历史", r"git.*有没有",
                    r"查看.*git", r"检查.*git", r"看看.*git",
                    r"检查.*项目", r"查看.*项目", r"看看.*项目",
                    r"项目.*改动", r"项目.*修改", r"项目.*变更",
                    r"项目.*提交", r"项目.*状态",
                    r"改了什么", r"改了哪些", r"有哪些改动",
                    r"有没有.*修改", r"有没有.*改动",
                ],
            ),
        ]

        # Layer 3: 自检提示词已并入 execution_policy（policy.py），此处不再注入
        self._self_check_prompt = ""

    def analyze(self, message: str) -> Dict:
        """分析用户意图（三层判断）

        注意（Phase B-2）：意图结果仅作为"工具建议"软提示注入 system prompt，
        不再决定工具可见性。工具可见性由 PermissionFilter.resolve 根据模式/项目决定。

        Args:
            message: 用户消息

        Returns:
            {
                "suggest_tools": bool,    # 是否建议使用工具（软提示，非 gate）
                "layer": str,             # factual_need / action_intent / self_check
                "intent": str,            # system_diagnosis / file_operation / ...
                "confidence": float,
                "reason": str,
            }
        """
        message_lower = message.lower().strip()
        if not message_lower:
            return self._no_tools_result("empty_message")

        # Layer 1: 明确事实需求
        result = self._check_factual_need(message_lower)
        if result:
            return result

        # Layer 2: 用户动作意图
        result = self._check_action_intent(message_lower)
        if result:
            return result

        # Layer 3: 模型自判断 — 无法通过规则确定，不注入额外提示
        return {
            "suggest_tools": False,
            "layer": "self_check",
            "intent": "general_chat",
            "confidence": 0.5,
            "reason": "无法通过规则确定是否需要工具，由模型自行判断",
        }

    def _check_factual_need(self, message: str) -> Dict | None:
        """Layer 1: 检查是否有明确事实需求"""
        for intent, patterns in self._factual_patterns:
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    return {
                        "suggest_tools": True,
                        "layer": "factual_need",
                        "intent": intent,
                        "confidence": 0.9,
                        "reason": f"用户问题涉及真实环境状态，需要获取数据才能准确回答（匹配: {pattern}）",
                    }
        return None

    def _check_action_intent(self, message: str) -> Dict | None:
        """Layer 2: 检查是否有明确的动作意图"""
        for intent, patterns in self._action_patterns:
            for pattern in patterns:
                match = re.search(pattern, message)
                if match:
                    return {
                        "suggest_tools": True,
                        "layer": "action_intent",
                        "intent": intent,
                        "confidence": 0.85,
                        "reason": f"用户明确要求执行操作，需要工具配合（匹配: {pattern}）",
                    }
        return None

    def _no_tools_result(self, reason: str) -> Dict:
        return {
            "suggest_tools": False,
            "layer": "none",
            "intent": "general_chat",
            "confidence": 1.0,
            "reason": reason,
        }