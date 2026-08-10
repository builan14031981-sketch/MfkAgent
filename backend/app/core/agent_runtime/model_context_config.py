"""模型上下文窗口配置（G6-A）。

记录各模型的最大 Context Window（token 数），用于计算上下文水位。
查询优先级：PROVIDERS 注册表（ProviderModel.context_window）> 硬编码字典 > 默认值 128K。
"""

from typing import Dict

from app.core.model_providers import PROVIDERS

# ──── 模型最大上下文窗口配置（兼容旧数据，优先使用 PROVIDERS 中的值）────

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
    # 默认
    "default": 256000,
}

# 默认上下文窗口（G6-B：从 128K 提升到 256K，覆盖主流免费模型）
DEFAULT_CONTEXT_WINDOW = 256000


def get_model_max_tokens(model_id: str) -> int:
    """获取指定模型的最大上下文窗口（token 数）。

    查询优先级：
      1. PROVIDERS 注册表（ProviderModel.context_window）—— 主数据源
      2. MODEL_CONTEXT_WINDOWS 硬编码字典 —— 兼容旧数据 / 自定义模型
      3. DEFAULT_CONTEXT_WINDOW —— 最终兜底

    未知模型返回 DEFAULT_CONTEXT_WINDOW。
    """
    if not model_id:
        return DEFAULT_CONTEXT_WINDOW

    # 1. 优先从 PROVIDERS 注册表查询（精确匹配 model_id）
    for p in PROVIDERS:
        for m in p.models:
            if m.id == model_id:
                return m.context_window

    # 2. 回退硬编码字典：精确匹配 > 前缀匹配
    if model_id in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_id]

    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key == "default":
            continue
        if model_id.startswith(key):
            return size

    # 3. 最终兜底
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
