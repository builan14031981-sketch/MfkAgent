"""工具事件源 — 进程内、请求级工具事件收集器。

Phase A 定位：
- 仅被 model_service.chat_stream 单向消费（执行工具时收集 → 透传给 SSE）。
- 后续可扩展订阅者（日志、审计、后台任务持久化）。

工具事件统一信封（顶层 type 字段是唯一判别依据）：

  tool_start   {"type","tool_call_id","tool","input","title?"}
  tool_output  {"type","tool_call_id","delta"}            （协议预留，Phase A 不发射）
  tool_result  {"type","tool_call_id","tool","success","result","duration_ms","error?"}
  tool_approval {"type","approval_id","tool_call_id","tool","command","risk_level","risk_reason","chat_id","created_at"}（Phase B-1 新增，additive）

事件字段约定（一经发布即稳定）：
  - 全部 snake_case
  - tool_call_id 在单次会话流内唯一，是前端去重键
  - 每个 tool_result 之前必有同 tool_call_id 的 tool_start
  - tool_start / tool_result 之间可穿插 text / thinking 事件
  - tool_approval 必在 tool_start 之后、tool_result 之前，与二者同 tool_call_id
"""

from typing import Callable, Dict, Optional


class ToolEventSource:
    """请求级工具事件收集器。

    用法：
        source = ToolEventSource()
        record = await execute_tool(..., emit=source.emit)
        for event in source.drain():
            yield event
    """

    def __init__(self):
        self._events: list[Dict] = []

    def emit(self, event: Dict) -> None:
        """收集一个事件。发射失败不影响工具执行（副作用，非主链路）。"""
        try:
            self._events.append(event)
        except Exception:
            pass

    def drain(self) -> list[Dict]:
        """取走并清空已收集的事件（保序）。"""
        events = self._events
        self._events = []
        return events


def make_tool_start(
    tool_call_id: str,
    tool: str,
    input_args: Dict,
    title: Optional[str] = None,
) -> Dict:
    """构造 tool_start 事件。"""
    event: Dict = {
        "type": "tool_start",
        "tool_call_id": tool_call_id,
        "tool": tool,
        "input": input_args,
    }
    if title:
        event["title"] = title
    return event


def make_tool_result(
    tool_call_id: str,
    tool: str,
    success: bool,
    result: str,
    duration_ms: int,
    file_path: Optional[str] = None,
) -> Dict:
    """构造 tool_result 事件。

    file_path: 可选，文件类工具操作后返回的绝对路径，供前端直接用于打开/定位文件。
    """
    event: Dict = {
        "type": "tool_result",
        "tool_call_id": tool_call_id,
        "tool": tool,
        "success": success,
        "result": result,
        "duration_ms": duration_ms,
    }
    if not success and result:
        event["error"] = result[:500]
    if file_path:
        event["file_path"] = file_path
    return event


def make_tool_approval(
    approval_id: str,
    tool_call_id: str,
    tool: str,
    command: str,
    risk_level: str,
    risk_reason: str,
    chat_id: Optional[int] = None,
) -> Dict:
    """构造 tool_approval 事件（Phase B-1 新增，additive）。"""
    from datetime import datetime, timezone

    event: Dict = {
        "type": "tool_approval",
        "approval_id": approval_id,
        "tool_call_id": tool_call_id,
        "tool": tool,
        "command": command,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if chat_id is not None:
        event["chat_id"] = chat_id
    return event


def make_choice_request(
    choice_id: str,
    tool_call_id: str,
    question: str,
    options: list,
    recommended: "int | None",
    allow_custom: bool = True,
    chat_id: "int | None" = None,
) -> Dict:
    """构造 choice_request 事件（ask_user_choice 工具，additive）。

    前端渲染抉择卡：选项列表（recommended 下标高亮）+ 自定义输入。
    """
    from datetime import datetime, timezone

    event: Dict = {
        "type": "choice_request",
        "choice_id": choice_id,
        "tool_call_id": tool_call_id,
        "question": question,
        "options": options,
        "recommended": recommended,
        "allow_custom": allow_custom,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if chat_id is not None:
        event["chat_id"] = chat_id
    return event
