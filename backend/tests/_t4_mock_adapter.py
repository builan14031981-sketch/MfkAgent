# -*- coding: utf-8 -*-
"""T4 双循环合一的模型 mock 适配器。

T4 合一后 run() 内部消费 run_stream()（模型调用面从 model_service.call_once
统一为 model_service.stream_once）。本适配器把旧「单次返回结果对象」型的
side_effect（返回 .content/.tool_calls/.finish_reason/.usage 形状的对象）
包装成 stream_once 的事件流形状，测试断言语义保持不变。
"""
import inspect


async def _result_to_events(result):
    """把单次调用结果对象转成 stream_once 事件流。"""
    if getattr(result, "tool_calls", None):
        yield {"type": "tool_calls", "calls": result.tool_calls}
        yield {"type": "finish", "finish_reason": "tool_calls",
               "usage": getattr(result, "usage", None)}
        return
    content = getattr(result, "content", None)
    if content:
        yield {"type": "text", "content": content}
    yield {"type": "finish", "finish_reason": getattr(result, "finish_reason", "stop"),
           "usage": getattr(result, "usage", None)}


def stream_from_single_call(side_effect):
    """把旧 call_once 型 side_effect 包装为 stream_once 型调用（返回事件流）。

    side_effect 兼容三种形态：async def、sync def、AsyncMock；
    位置/关键字参数原样透传。
    """
    async def stream_once(*args, **kwargs):
        res = side_effect(*args, **kwargs)
        if inspect.isawaitable(res):
            res = await res
        async for event in _result_to_events(res):
            yield event
    return stream_once
