"""Thought Pruning — G6-B Phase 2：历史思考段裁剪。

在 ContextBuilder 组装发送给 LLM 的 payload 时，对历史 assistant 消息做思考段裁剪，
减少历史 reasoning 对上下文的污染：

  1. 移除 thinking / reasoning 字段
  2. 移除 content 中的 <thinking>...</thinking> 块，保留正常回答
  3. 保留 assistant content / tool_calls / tool 结果

纯函数设计：
  - 返回新列表，绝不修改原始 message 对象（数据安全：不触碰 DB 与持久化结构）
  - 不涉及 Runtime 执行链（run / run_stream / Execution Loop / TaskGraph 均不感知）

处理位置：
  DB Message → [Thought Pruning] → ContextBuilder 新 payload → LLM
"""

import re
from typing import List

# <thinking>...</thinking> 块（含前后空白），用单个换行替换以保持段落结构
_THINK_BLOCK_RE = re.compile(r"\s*<thinking>.*?</thinking>\s*", re.DOTALL)


def _strip_think_blocks(content: str) -> str:
    """移除 content 中的 <thinking>...</thinking> 块，保留正常回答。"""
    if not isinstance(content, str) or not content:
        return content
    return _THINK_BLOCK_RE.sub("\n", content).strip()


def _role_of(m) -> str:
    if isinstance(m, dict):
        return m.get("role", "user")
    return getattr(m, "role", "user")


def _content_of(m):
    if isinstance(m, dict):
        return m.get("content")
    return getattr(m, "content", None)


def _rebuild(m, role: str, content):
    """按输入类型重建消息；同时剔除 thinking / reasoning 字段，保留其余字段。

    - dict        → 复制 dict，移除 thinking/reasoning 键
    - pydantic    → 以 role/content 重建（Message 仅这两字段）
    - ORM Message → 以 role/content 重建，并保留 tool_calls / timeline
    """
    if isinstance(m, dict):
        d = dict(m)
        d.pop("thinking", None)
        d.pop("reasoning", None)
        if content is not None:
            d["content"] = content
        return d

    cls = type(m)
    # pydantic 模型（ModelMessage）：role/content
    if hasattr(m, "dict"):
        try:
            return cls(role=role, content=content)
        except Exception:
            return {"role": role, "content": content}

    # ORM Message：role/content + tool_calls/timeline
    kwargs = {"role": role, "content": content}
    for attr in ("tool_calls", "timeline"):
        val = getattr(m, attr, None)
        if val is not None:
            kwargs[attr] = val
    try:
        return cls(**kwargs)
    except Exception:
        return {"role": role, "content": content}


def prune_thought_history(messages: List, strip_thinking_tags: bool = True) -> List:
    """裁剪历史消息中的思考段，返回新的消息列表（不修改原始对象）。

    Args:
        messages: 历史消息列表（dict / ModelMessage / ORM Message）
        strip_thinking_tags: 是否移除 assistant content 中的 <thinking>...</thinking> 块

    Returns:
        裁剪后的新列表；空输入原样返回。
    """
    if not messages:
        return messages

    out = []
    for m in messages:
        role = _role_of(m)
        content = _content_of(m)
        if strip_thinking_tags and role == "assistant" and isinstance(content, str):
            content = _strip_think_blocks(content)
        out.append(_rebuild(m, role, content))
    return out
