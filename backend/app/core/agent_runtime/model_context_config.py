"""模型上下文窗口配置（G6-A）。

记录各模型的最大 Context Window（token 数），用于计算上下文水位。
未知模型使用默认值 128000。
"""

from typing import Dict

# ──── 模型最大上下文窗口配置 ────

MODEL_CONTEXT_WINDOWS: Dict[str, int] = {
    # OpenAI
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    # Claude
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "claude-3-opus": 200000,
    # DeepSeek
    "deepseek-chat": 64000,
    "deepseek-coder": 64000,
    "deepseek-reasoner": 64000,
    # Qwen
    "qwen-max": 32768,
    "qwen-plus": 131072,
    # 默认
    "default": 128000,
}

# 默认上下文窗口
DEFAULT_CONTEXT_WINDOW = 128000


def get_model_max_tokens(model_id: str) -> int:
    """获取指定模型的最大上下文窗口（token 数）。

    匹配规则：精确匹配 > 前缀匹配 > 默认值。
    未知模型返回 DEFAULT_CONTEXT_WINDOW。
    """
    if not model_id:
        return DEFAULT_CONTEXT_WINDOW

    # 精确匹配
    if model_id in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_id]

    # 前缀模糊匹配（如 "gpt-4o-2024-08-06" → "gpt-4o"）
    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key == "default":
            continue
        if model_id.startswith(key):
            return size

    return DEFAULT_CONTEXT_WINDOW


def compute_watermark(total_tokens: int, model_id: str) -> float:
    """计算上下文水位百分比。

    Args:
        total_tokens: 当前消耗的总 token 数
        model_id: 模型 ID

    Returns:
        水位百分比，保留两位小数（如 15.23）
    """
    max_tokens = get_model_max_tokens(model_id)
    if max_tokens <= 0:
        return 0.0
    return round(total_tokens / max_tokens * 100, 2)
