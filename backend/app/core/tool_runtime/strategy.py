"""Tool Execution Strategy Layer V1

在工具执行前后进行策略检查，确保工具调用符合最佳实践。

设计原则：
- 不修改 Planner / ToolSelector / ToolExecutor 核心逻辑
- 不重构 AgentRuntime
- 保持现有 Function Calling 流程兼容
- 策略检查在工具执行前进行，执行后进行后处理

V1 规则：
1. read-before-write: write_file 前必须有 read_file
2. write-after-verify: write_file 后必须有验证工具
3. 危险命令检测: run_command 中的危险模式
4. 失败循环检测: 同一工具连续失败超过 3 次
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re


class StrategyStatus(str, Enum):
    """策略检查结果状态"""
    ALLOW = "allow"              # 允许执行
    BLOCK = "block"              # 阻止执行
    REQUIRE_CONFIRM = "require_confirm"  # 需要用户确认
    NEED_FEEDBACK = "need_feedback"      # 需要反馈给 LLM


@dataclass
class StrategyResult:
    """策略检查结果"""
    status: StrategyStatus
    reason: str
    rule_name: str
    suggestion: str = ""


class ToolExecutionStrategy:
    """工具执行策略引擎"""
    
    # 写入类工具
    WRITE_TOOLS = {"write_file", "replace_in_file", "apply_patch", "delete_file"}
    
    # 验证类工具
    VERIFY_TOOLS = {"run_command"}
    
    # 危险命令模式
    DANGEROUS_COMMAND_PATTERNS = [
        # 删除大量文件
        re.compile(r"rm\s+-rf\s+/\s*$"),
        re.compile(r"rm\s+-rf\s+\*"),
        re.compile(r"del\s+/[sS]\s+/\[qQ\]"),
        # 格式化磁盘
        re.compile(r"format\s+[a-zA-Z]:", re.IGNORECASE),
        re.compile(r"mkfs\."),
        # 系统关键目录
        re.compile(r"rm\s+-rf\s+(/usr|/etc|/var|/bin|/sbin)"),
        re.compile(r"del\s+/[sS]\s+C:\\Windows"),
        # 危险系统命令
        re.compile(r"shutdown\s+-[sSrR]"),
        re.compile(r"reboot"),
        re.compile(r"taskkill\s+/F\s+/FI"),
    ]
    
    # 验证循环深度限制
    MAX_VERIFICATION_RETRIES = 3
    
    def __init__(self):
        """初始化策略引擎"""
        # 工具执行历史（用于 read-before-write 检查）
        self.tool_history: List[Dict[str, Any]] = []
        
        # 失败计数器（用于失败循环检测）
        self.failure_counter: Dict[str, int] = {}
        
        # 最近一次写入后的验证状态
        self.pending_verification: bool = False
        
        # 验证循环深度跟踪器（防止无限重试）
        self.verification_retry_count: int = 0
    
    def check_before_execution(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> StrategyResult:
        """执行前策略检查
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            
        Returns:
            StrategyResult: 策略检查结果
        """
        # Rule 1: read-before-write
        if tool_name in self.WRITE_TOOLS:
            result = self._check_read_before_write(tool_name, tool_args)
            if result.status != StrategyStatus.ALLOW:
                return result
        
        # Rule 3: 危险命令检测
        if tool_name == "run_command":
            result = self._check_dangerous_command(tool_args)
            if result.status != StrategyStatus.ALLOW:
                return result
        
        # Rule 4: 失败循环检测
        result = self._check_failure_loop(tool_name)
        if result.status != StrategyStatus.ALLOW:
            return result
        
        return StrategyResult(
            status=StrategyStatus.ALLOW,
            reason="策略检查通过",
            rule_name="none"
        )
    
    def check_after_execution(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        success: bool,
        result_text: str,
    ) -> Optional[StrategyResult]:
        """执行后策略检查
        
        Args:
            tool_name: 工具名称
            tool_args: 工具参数
            success: 是否执行成功
            result_text: 执行结果文本
            
        Returns:
            Optional[StrategyResult]: 策略检查结果（如果需要反馈）
        """
        # 记录工具执行历史
        self.tool_history.append({
            "tool_name": tool_name,
            "tool_args": tool_args,
            "success": success,
        })
        
        # 更新失败计数器
        if not success:
            key = self._get_failure_key(tool_name, tool_args)
            self.failure_counter[key] = self.failure_counter.get(key, 0) + 1
        else:
            # 成功后重置计数器
            key = self._get_failure_key(tool_name, tool_args)
            self.failure_counter[key] = 0
        
        # Rule 2: write-after-verify
        if tool_name in self.WRITE_TOOLS and success:
            self.pending_verification = True
            return StrategyResult(
                status=StrategyStatus.NEED_FEEDBACK,
                reason="文件修改已完成，但尚未验证",
                rule_name="write-after-verify",
                suggestion="请执行验证步骤（如 run_command 运行测试或编译检查）"
            )
        
        # 验证工具执行后重置 pending_verification
        if tool_name in self.VERIFY_TOOLS and success:
            self.pending_verification = False
        
        return None
    
    def _check_read_before_write(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> StrategyResult:
        """Rule 1: read-before-write 检查
        
        检查写入文件前是否已经读取过该文件
        """
        # 获取目标文件路径
        target_path = tool_args.get("path") or tool_args.get("file_path") or ""
        
        if not target_path:
            # 无法确定目标文件，放行
            return StrategyResult(
                status=StrategyStatus.ALLOW,
                reason="无法确定目标文件路径",
                rule_name="read-before-write"
            )
        
        # 检查历史中是否有对该文件的 read_file 操作
        has_read = False
        for history in self.tool_history:
            if history["tool_name"] == "read_file":
                history_path = history["tool_args"].get("path") or history["tool_args"].get("file_path") or ""
                if history_path == target_path:
                    has_read = True
                    break
        
        if not has_read:
            return StrategyResult(
                status=StrategyStatus.BLOCK,
                reason=f"修改文件 {target_path} 前必须先读取当前文件内容",
                rule_name="read-before-write",
                suggestion="请先调用 read_file 读取文件内容"
            )
        
        return StrategyResult(
            status=StrategyStatus.ALLOW,
            reason="已通过 read-before-write 检查",
            rule_name="read-before-write"
        )
    
    def _check_dangerous_command(
        self,
        tool_args: Dict[str, Any],
    ) -> StrategyResult:
        """Rule 3: 危险命令检测
        
        检查 run_command 中是否包含危险命令模式
        """
        command = tool_args.get("command", "")
        
        if not command:
            return StrategyResult(
                status=StrategyStatus.ALLOW,
                reason="命令为空",
                rule_name="dangerous-command"
            )
        
        # 检查是否匹配危险模式
        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if pattern.search(command):
                return StrategyResult(
                    status=StrategyStatus.REQUIRE_CONFIRM,
                    reason=f"检测到危险命令模式: {pattern.pattern}",
                    rule_name="dangerous-command",
                    suggestion="该命令可能具有破坏性，请确认是否继续执行"
                )
        
        return StrategyResult(
            status=StrategyStatus.ALLOW,
            reason="未检测到危险命令模式",
            rule_name="dangerous-command"
        )
    
    def _check_failure_loop(
        self,
        tool_name: str,
    ) -> StrategyResult:
        """Rule 4: 失败循环检测
        
        检查同一工具是否连续失败超过 3 次
        """
        # 统计该工具的失败次数
        failure_count = 0
        for history in reversed(self.tool_history):
            if history["tool_name"] == tool_name:
                if not history["success"]:
                    failure_count += 1
                else:
                    # 遇到成功，停止计数
                    break
        
        if failure_count >= 3:
            return StrategyResult(
                status=StrategyStatus.BLOCK,
                reason=f"工具 {tool_name} 已连续失败 {failure_count} 次",
                rule_name="failure-loop",
                suggestion="请重新评估任务方案，避免重复失败"
            )
        
        return StrategyResult(
            status=StrategyStatus.ALLOW,
            reason="未触发失败循环检测",
            rule_name="failure-loop"
        )
    
    def _get_failure_key(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> str:
        """生成失败计数器的 key
        
        使用工具名称 + 关键参数的哈希值作为 key
        """
        # 简化实现：仅使用工具名称
        # 后续可以扩展为包含关键参数
        return tool_name
    
    def reset(self):
        """重置策略引擎状态"""
        self.tool_history.clear()
        self.failure_counter.clear()
        self.pending_verification = False
        self.verification_retry_count = 0
    
    def record_verification_failure(self):
        """记录验证失败，增加重试计数"""
        self.verification_retry_count += 1
    
    def record_verification_success(self):
        """记录验证成功，重置重试计数"""
        self.verification_retry_count = 0
    
    def should_stop_verification_retry(self) -> bool:
        """检查是否应该停止验证重试"""
        return self.verification_retry_count >= self.MAX_VERIFICATION_RETRIES
    
    def get_verification_retry_count(self) -> int:
        """获取当前验证重试次数"""
        return self.verification_retry_count


# 全局策略引擎实例（每个会话一个）
_strategy_engines: Dict[str, ToolExecutionStrategy] = {}


def get_strategy_engine(session_id: str) -> ToolExecutionStrategy:
    """获取指定会话的策略引擎实例
    
    Args:
        session_id: 会话 ID
        
    Returns:
        ToolExecutionStrategy: 策略引擎实例
    """
    if session_id not in _strategy_engines:
        _strategy_engines[session_id] = ToolExecutionStrategy()
    return _strategy_engines[session_id]


def remove_strategy_engine(session_id: str):
    """移除指定会话的策略引擎实例
    
    Args:
        session_id: 会话 ID
    """
    if session_id in _strategy_engines:
        del _strategy_engines[session_id]
