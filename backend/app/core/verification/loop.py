"""Verification Loop V1 — 验证循环控制器。

负责跟踪工具验证的重试次数，防止无限重试循环。

核心职责：
  - 按 tool_call_id 跟踪重试次数
  - 检测循环耗尽（达到最大重试次数）
  - 提供循环状态查询接口
  - 支持循环重置（用于新任务）

设计原则：
  - 无状态：不存储验证结果，只跟踪重试计数
  - 会话级：每个 chat_id 独立的循环控制器
  - 透明集成：与现有 Verifier 和 Strategy Layer 无缝协作
"""

from typing import Dict, Optional
from dataclasses import dataclass, field
from app.core.verification.models import DEFAULT_MAX_RETRIES


@dataclass
class LoopState:
    """单个工具调用的循环状态。"""
    retry_count: int = 0
    last_tool: Optional[str] = None
    last_message: Optional[str] = None


class VerificationLoop:
    """验证循环控制器。
    
    按 tool_call_id 跟踪重试次数，防止无限重试。
    """
    
    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES):
        """初始化循环控制器。
        
        Args:
            max_retries: 最大重试次数（默认 3 次）
        """
        self.max_retries = max_retries
        self._loops: Dict[str, LoopState] = {}
    
    def should_retry(self, tool_call_id: str) -> bool:
        """判断是否应该重试。
        
        Args:
            tool_call_id: 工具调用 ID
            
        Returns:
            True 如果未超过最大重试次数
        """
        if tool_call_id not in self._loops:
            return True
        
        state = self._loops[tool_call_id]
        return state.retry_count < self.max_retries
    
    def increment_retry(self, tool_call_id: str, tool: Optional[str] = None, message: Optional[str] = None) -> int:
        """增加重试计数。
        
        Args:
            tool_call_id: 工具调用 ID
            tool: 工具名称（可选，用于日志）
            message: 验证失败消息（可选，用于日志）
            
        Returns:
            当前重试次数
        """
        if tool_call_id not in self._loops:
            self._loops[tool_call_id] = LoopState()
        
        state = self._loops[tool_call_id]
        state.retry_count += 1
        state.last_tool = tool
        state.last_message = message
        
        return state.retry_count
    
    def get_retry_count(self, tool_call_id: str) -> int:
        """获取当前重试次数。
        
        Args:
            tool_call_id: 工具调用 ID
            
        Returns:
            当前重试次数（不存在则返回 0）
        """
        if tool_call_id not in self._loops:
            return 0
        
        return self._loops[tool_call_id].retry_count
    
    def reset(self, tool_call_id: Optional[str] = None):
        """重置循环状态。
        
        Args:
            tool_call_id: 指定重置某个工具调用，None 表示重置所有
        """
        if tool_call_id:
            if tool_call_id in self._loops:
                del self._loops[tool_call_id]
        else:
            self._loops.clear()
    
    def get_exhausted_loops(self) -> Dict[str, LoopState]:
        """获取所有已达到最大重试次数的循环。
        
        Returns:
            字典：tool_call_id -> LoopState
        """
        return {
            tid: state
            for tid, state in self._loops.items()
            if state.retry_count >= self.max_retries
        }
    
    def get_active_loops(self) -> Dict[str, LoopState]:
        """获取所有仍在重试中的循环。
        
        Returns:
            字典：tool_call_id -> LoopState
        """
        return {
            tid: state
            for tid, state in self._loops.items()
            if state.retry_count < self.max_retries
        }
    
    def get_summary(self) -> Dict:
        """获取循环状态摘要（用于日志和调试）。
        
        Returns:
            字典：包含总数、活跃数、耗尽数
        """
        total = len(self._loops)
        exhausted = len(self.get_exhausted_loops())
        active = len(self.get_active_loops())
        
        return {
            "total": total,
            "active": active,
            "exhausted": exhausted,
            "max_retries": self.max_retries,
        }


# 全局循环控制器实例（按 chat_id 管理）
_verification_loops: Dict[str, VerificationLoop] = {}


def get_verification_loop(chat_id: str, max_retries: int = DEFAULT_MAX_RETRIES) -> VerificationLoop:
    """获取指定会话的验证循环控制器。
    
    Args:
        chat_id: 会话 ID
        max_retries: 最大重试次数
        
    Returns:
        VerificationLoop 实例
    """
    if chat_id not in _verification_loops:
        _verification_loops[chat_id] = VerificationLoop(max_retries)
    return _verification_loops[chat_id]


def remove_verification_loop(chat_id: str):
    """移除指定会话的验证循环控制器。
    
    Args:
        chat_id: 会话 ID
    """
    if chat_id in _verification_loops:
        del _verification_loops[chat_id]
