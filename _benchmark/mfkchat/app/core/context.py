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

    # 先找到最后一条 user 消息的位置
    last_user_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break
    
    result = list(messages)
    
    # 需求③修复：只有当 estimate > max_tokens 时才裁剪
    while tokens.estimate_messages_tokens(result) > max_tokens and len(result) > 1:
        # 如果最旧的消息不是最后一条 user 消息，可以安全删除
        if len(result) > 1 and (last_user_idx == -1 or 0 != last_user_idx):
            result.pop(0)
            # 更新 last_user_idx（因为前面删了一个元素）
            if last_user_idx != -1:
                last_user_idx -= 1
        else:
            # 如果只剩最后一条 user 消息，或者最旧的就是最后一条 user 消息
            # 但仍然超限，那么只能保留最后一条 user 消息并截断其内容
            if last_user_idx != -1 and len(result) == 1:
                # 只有一条消息且是 user 消息，需要截断内容
                content = result[0]["content"]
                # 估算当前内容的 token 数
                content_tokens = tokens.count_tokens(content)
                role_overhead = 4 + 2  # role 开销 + 末尾开销
                available_tokens = max_tokens - role_overhead
                if available_tokens > 0:
                    # 简单截断：按字符数粗略截断（实际应该按 token 截断，但这里简化）
                    # 由于 count_tokens 实现已修复，我们可以更准确地截断
                    target_chars = available_tokens * 4  # 保守估计，按英文字符计算
                    if len(content) > target_chars:
                        result[0]["content"] = content[:target_chars]
                else:
                    # 完全无法容纳，返回空列表
                    return []
            break
    
    # 最后的保障：确保最后一条 user 消息存在（如果原始消息中有）
    if last_user_idx != -1 and messages[last_user_idx].get("role") == "user":
        has_last_user = any(m.get("role") == "user" and m.get("content") == messages[last_user_idx].get("content") 
                           for m in result)
        if not has_last_user:
            # 如果最后一条 user 消息被意外删除了，重新添加（截断版本）
            last_user_msg = messages[last_user_idx].copy()
            # 确保添加后不超过限制
            temp_result = result + [last_user_msg]
            if tokens.estimate_messages_tokens(temp_result) <= max_tokens:
                result.append(last_user_msg)
    
    return result


def estimate(messages) -> int:
    return tokens.estimate_messages_tokens(messages)