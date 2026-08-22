"""模型上下文窗口配置（G6-A）。

记录各模型的最大 Context Window（token 数），用于计算上下文水位。
查询优先级：
  1. _mp.PROVIDERS 注册表（ProviderModel.context_window）—— 内置模型主数据源
  2. 数据库 models 表 —— 自定义模型（custom provider）的 context_window
  3. MODEL_CONTEXT_WINDOWS 硬编码字典 —— 兼容旧数据
  4. DEFAULT_CONTEXT_WINDOW —— 最终兜底
"""

from typing import Dict, Optional

import app.core.model_providers as _mp

# 数据库查询缓存（避免每次 token 计算都查 DB）
_db_cache: Dict[str, Optional[int]] = {}
_db_cache_dirty = True


def _invalidate_db_cache() -> None:
    """使数据库缓存失效（添加/修改模型后调用）。"""
    global _db_cache, _db_cache_dirty
    _db_cache.clear()
    _db_cache_dirty = True


def _query_context_from_db(model_id: str) -> Optional[int]:
    """从数据库 models 表查询自定义模型的 context_window。

    带内存缓存，避免高频调用时重复查库。
    返回 None 表示数据库中无此模型或查询失败。
    """
    global _db_cache_dirty
    if model_id in _db_cache:
        return _db_cache[model_id]

    try:
        from app.core.database import SessionLocal
        from app.models.agent import CustomModel as DBModel
        db = SessionLocal()
        try:
            row = db.query(DBModel).filter(DBModel.model_id == model_id).first()
            result = row.context_window if row and row.context_window else None
        finally:
            db.close()
    except Exception:
        result = None

    _db_cache[model_id] = result
    return result


# ──── 模型最大上下文窗口配置（兼容旧数据，优先使用 _mp.PROVIDERS 中的值）────

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
    # Gemini（前缀匹配，覆盖 gemini-1.5/2.0/2.5/3.x 系列）
    "gemini-1.5-pro": 2000000,
    "gemini-1.5-flash": 1000000,
    "gemini-2.0-flash": 1000000,
    "gemini-2.5-pro": 1000000,
    "gemini-2.5-flash": 1000000,
    "gemini-3": 1000000,  # Gemini 3.x 系列默认 1M
    # 默认
    "default": 256000,
}

# 默认上下文窗口（G6-B：从 128K 提升到 256K，覆盖主流免费模型）
DEFAULT_CONTEXT_WINDOW = 256000


def get_model_max_tokens(model_id: str) -> int:
    """获取指定模型的最大上下文窗口（token 数）。

    查询优先级：
      1. _mp.PROVIDERS 注册表（ProviderModel.context_window）—— 内置模型主数据源
      2. 数据库 models 表 —— 自定义模型（custom provider）的 context_window
      3. MODEL_CONTEXT_WINDOWS 硬编码字典 —— 兼容旧数据 / 前缀匹配
      4. DEFAULT_CONTEXT_WINDOW —— 最终兜底

    未知模型返回 DEFAULT_CONTEXT_WINDOW。
    """
    if not model_id:
        return DEFAULT_CONTEXT_WINDOW

    # 1. 优先从 _mp.PROVIDERS 注册表查询（精确匹配 model_id）
    for p in _mp.PROVIDERS:
        for m in p.models:
            if m.id == model_id:
                return m.context_window

    # 2. 从数据库 models 表查询自定义模型的 context_window
    db_context = _query_context_from_db(model_id)
    if db_context and db_context > 0:
        return db_context

    # 3. 回退硬编码字典：精确匹配 > 前缀匹配
    if model_id in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model_id]

    for key, size in MODEL_CONTEXT_WINDOWS.items():
        if key == "default":
            continue
        if model_id.startswith(key):
            return size

    # 4. 最终兜底
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
