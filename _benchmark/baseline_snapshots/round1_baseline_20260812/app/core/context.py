"""系统提示词组装：身份 + 人格 + 记忆 + 工具建议 + 上下文裁剪。

贴近 MfkAgent ContextBuilder 的 ①-⑦ 分层组装逻辑。

预埋 Bug ②（边界条件 Bug）：上下文裁剪。
需求：当历史消息 token 总量超过 max_tokens 时，从最旧消息开始丢弃，
但【必须保留最近一条 user 消息】（否则 Agent 不知道当前要干嘛）。
现状实现：按 token 上限截断时，可能把最后一条 user 消息一起丢/丢不干净，
且 max_tokens 恰好等于某条消息累计值时边界处理错误。
"""
import config
from app.core import tokens


def build_system_prompt(
    identity: str,
    personality_text: str = "",
    memory_text: str = "",
    tool_hint: str = "",
    capabilities: list = None,
) -> str:
    """组装系统提示词（分层拼接）。"""
    sections = []
    if identity:
        sections.append(f"## 身份\n{identity}")
    if capabilities:
        sections.append(f"## 能力\n- " + "\n- ".join(capabilities))
    if personality_text:
        sections.append(f"## 人格\n{personality_text}")
    if memory_text:
        sections.append(f"## 记忆\n{memory_text}")
    if tool_hint:
        sections.append(f"## 工具建议\n{tool_hint}")
    return "\n\n".join(sections)


def assemble_personality_text(personality_level: int, base: str = "") -> str:
    """人格程度 → 文本。level 0 表示无人格。"""
    if personality_level <= 0:
        return ""
    if not base:
        return f"人格程度: {personality_level}"
    return base


def build_memory_text(items) -> str:
    """记忆项 → 文本块。items: [{"scope","content"}, ...]"""
    lines = [f"- [{it['scope']}] {it['content']}" for it in items]
    return "\n".join(lines) if lines else ""


def truncate_history(messages, max_tokens: int) -> list:
    """裁剪历史消息以适应上下文窗口。

    预埋 Bug ② 所在：
    - 需求①：被裁剪后总 token 不得超过 max_tokens；
    - 需求②：必须保留最后一条 user 消息（当前指令，Agent 靠它知道干嘛）；
    - 需求③：max_tokens 恰好等于累计值时【不应】裁剪（应为 > 才裁）。
    当前实现：
    - 用 >= 判断，导致恰好等于上限时也误裁（违反需求③）；
    - 全部丢完仍超限时，直接 pop() 掉【最新】消息（违反需求②，
      可能把最后一条 user 指令丢掉）。此路径在历史很短但单条超长时触发。
    """
    if max_tokens <= 0:
        return []
    if not messages:
        return []

    result = list(messages)
    # 需求③被违反：应为 estimate > max_tokens 才裁，当前用 >=
    while estimate(result) >= max_tokens and len(result) > 1:
        result.pop(0)  # 丢最旧

    # 需求②被违反：全部丢完仍超限时丢【最新】，可能丢弃最后一条 user 指令
    while estimate(result) >= max_tokens and result:
        result.pop()  # 反向丢掉最新消息（错误）
    return result


def estimate(messages) -> int:
    return tokens.estimate_messages_tokens(messages)
