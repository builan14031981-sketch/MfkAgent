"""模型配置适配器（防腐层）— 封装三层优先级合并逻辑。

为下一阶段数据迁移做隔离准备：当前 ModelService 直接读取 .env / settings表 / models表，
未来迁移到统一 schema 时，只需替换本 Adapter 实现，ModelService 无需改动。

优先级语义（必须保留）：
  1. CustomModel 表（enabled=True）覆盖内置 provider 模型（同名 model_id）
  2. settings 表 api_key_{id} 覆盖 .env 的 {PROVIDER}_API_KEY
  3. settings 表 api_base_{id} 覆盖 provider 默认端点

约束：不修改 settings 表 / models 表 schema。
"""
from typing import Dict, List, Optional
import logging

import app.core.model_providers as _mp
from app.core.model_providers import ProviderDef
from app.core.config import settings

import re

logger = logging.getLogger(__name__)

def _infer_context_window(model_name: str, fallback: int = 256000) -> int:
    """基于模型名称智能推断上下文窗口大小 (2026年大模型生态)"""
    name_lower = model_name.lower()
    
    # 1. Google Gemini 阵营
    if "gemini" in name_lower:
        if "pro" in name_lower:
            return 2_000_000  # gemini pro 普遍 2M
        if "flash" in name_lower:
            return 1_048_576  # gemini flash 普遍 1M
        return 1_048_576
        
    # 2. DeepSeek 阵营
    if "deepseek" in name_lower:
        if "v4" in name_lower or "r1" in name_lower or "v3" in name_lower:
            return 1_048_576
        return 128_000
        
    # 3. 阿里 Qwen 阵营
    if "qwen" in name_lower:
        if "3.8" in name_lower or "3.7" in name_lower or "1m" in name_lower:
            return 1_048_576
        return 131_072  # 大部分 qwen-plus/max/flash 在 128k
        
    # 4. Anthropic Claude 阵营
    if "claude" in name_lower:
        return 200_000  # claude 普遍 200k
        
    # 5. OpenAI 阵营
    if "o3" in name_lower or "gpt-4o" in name_lower:
        return 200_000  # openai 主力一般 128k ~ 200k
        
    # 6. GLM / 其他
    if "glm" in name_lower:
        if "long" in name_lower:
            return 1_048_576
        return 200_000
        
    return fallback


class ModelConfigAdapter:
    """模型配置优先级合并适配器。

    封装当前分散在 ModelService._init_models / _get_api_key / _get_api_base 中的优先级逻辑，
    为下一阶段数据迁移做隔离准备。所有存储读取均通过本类，ModelService 委托调用。
    """

    def resolve_all(self) -> Dict[str, "ModelConfig"]:
        """解析全部可用模型配置（内置 provider + 自定义覆盖）。

        合并规则：
          1. 先填入内置 _mp.PROVIDERS 的全部模型
          1b. 对 p.models 为空的 provider（自定义端点），从 enabled_models 动态生成模型
          2. 再用 CustomModel 表（enabled=True）覆盖同名 model_id

        Returns:
            Dict[model_id, ModelConfig]
        """
        # 延迟导入避免循环依赖（model.py 在模块级实例化 ModelService）
        from app.services.model import ModelConfig, ModelProvider
        import json as _json

        models: Dict[str, ModelConfig] = {}

        # 读取 enabled_models（用于自定义端点动态生成模型）
        enabled_map = {}
        try:
            raw = self._read_setting("enabled_models")
            if raw:
                enabled_map = _json.loads(raw)
        except Exception:
            pass

        # 1. 内置 _mp.PROVIDERS
        for p in _mp.PROVIDERS:
            api_base = self.resolve_api_base(p)
            api_key = self.resolve_api_key(p)
            for m in p.models:
                models[m.id] = ModelConfig(
                    provider=self._provider_enum(p.id),
                    model_name=m.upstream,
                    api_key=api_key,
                    api_base=api_base,
                    context_window=m.context_window,
                    supports_vision=_detect_supports_vision(m.upstream, p.supports_vision, m.supports_vision),
                    supports_tools=True,
                )
            # 1b. 自定义端点：p.models 为空，从 enabled_models 动态生成
            if not p.models and p.id in enabled_map:
                for model_id in enabled_map[p.id]:
                    if model_id not in models:
                        models[model_id] = ModelConfig(
                            provider=ModelProvider.CUSTOM,
                            provider_id=p.id,  # 存储原始 custom_<id>
                            model_name=model_id,  # 自定义端点的 model_id 即上游模型名
                            api_key=api_key,
                            api_base=api_base,
                            supports_vision=_detect_supports_vision(model_id, p.supports_vision, None),
                            supports_tools=True,
                        )

        # 2. CustomModel 表覆盖（同名 model_id 覆盖内置）
        for cm in self._custom_models():
            provider_def = _mp.PROVIDER_MAP.get(cm.provider)
            provider_vision = provider_def.supports_vision if provider_def else False
            # 数据库级显式标记优先（用户可在模型设置面板手动切换）
            # 仅 True 视为显式启用；False（默认值）回退到名称/Provider 检测
            model_vision = True if (hasattr(cm, 'supports_vision') and cm.supports_vision) else None
            # 自定义端点（custom_<id>）用 CUSTOM 枚举 + provider_id 区分
            is_custom = cm.provider.startswith("custom_")
            models[cm.model_id] = ModelConfig(
                provider=ModelProvider.CUSTOM if is_custom else self._provider_enum(cm.provider),
                provider_id=cm.provider if is_custom else None,
                model_name=cm.model_name,
                api_key=cm.api_key or (provider_def and self.resolve_api_key(provider_def) or ""),
                api_base=cm.api_base,
                max_tokens=cm.max_tokens,
                temperature=cm.temperature,
                context_window=getattr(cm, 'context_window', None) or _infer_context_window(cm.model_name),
                supports_vision=_detect_supports_vision(cm.model_name, provider_vision, model_vision),
                supports_tools=True,
            )
        return models

    def resolve_api_key(self, provider_def: ProviderDef) -> str:
        """解析 provider 的有效 API Key。

        优先级：settings 表 api_key_{id} > .env 的 {PROVIDER}_API_KEY

        Args:
            provider_def: provider 定义

        Returns:
            API Key 字符串（可能为空）
        """
        setting_value = self._read_setting(f"api_key_{provider_def.id}")
        if setting_value:
            return setting_value
        # 回退 .env
        return getattr(settings, provider_def.env_key, "") or ""

    def resolve_api_base(self, provider_def: ProviderDef) -> str:
        """解析 provider 的有效 API Base。

        优先级：settings 表 api_base_{id} > provider 默认端点

        Args:
            provider_def: provider 定义

        Returns:
            API Base 字符串
        """
        setting_value = self._read_setting(f"api_base_{provider_def.id}")
        if setting_value:
            return setting_value
        return provider_def.default_api_base

    def resolve_single(self, model_id: str) -> Optional["ModelConfig"]:
        """解析单个 model_id 的配置（含惰性 reload 兜底语义）。

        Args:
            model_id: 模型 ID

        Returns:
            ModelConfig 或 None（未找到）
        """
        all_models = self.resolve_all()
        return all_models.get(model_id)

    # ──── 存储读取原语（隔离 DB 访问，便于后续迁移）────

    def _read_setting(self, key: str) -> str:
        """从 settings 表读取单个 key 的 value。

        Args:
            key: setting key

        Returns:
            value 字符串（不存在返回空串）
        """
        from app.core.database import SessionLocal
        from app.models.agent import Setting
        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == key).first()
            return (row.value or "") if row else ""
        finally:
            db.close()

    def _custom_models(self) -> List:
        """读取 CustomModel 表中 enabled=True 的全部记录。

        Returns:
            CustomModel ORM 列表
        """
        from app.core.database import SessionLocal
        from app.models.agent import CustomModel
        db = SessionLocal()
        try:
            return db.query(CustomModel).filter(CustomModel.enabled.is_(True)).all()
        finally:
            db.close()

    @staticmethod
    def _provider_enum(provider_id: str) -> "ModelProvider":
        """将 provider_id 字符串转为 ModelProvider 枚举，未知值回落 OPENAI。

        Args:
            provider_id: provider 唯一 ID

        Returns:
            ModelProvider 枚举值
        """
        # 延迟导入避免循环依赖
        from app.services.model import ModelProvider
        try:
            return ModelProvider(provider_id)
        except ValueError:
            return ModelProvider.OPENAI


def _detect_supports_vision(model_name: str, provider_vision: bool, model_vision: Optional[bool] = None) -> bool:
    """动态检测模型是否支持多模态视觉（Model 级粒度判定）。

    三级优先级：
      1. 模型级显式指定（非 None）→ 直接使用（最高优先级）
      2. 命名推测（含 vl / vision / gemini / 4o / claude-3 / omni / multimodal / image / llava）→ True
      3. 回退 Provider 级 supports_vision 配置

    Args:
        model_name: 模型上游名称
        provider_vision: provider 级 supports_vision 配置
        model_vision: ProviderModel.supports_vision 显式值（None 表示未指定）

    Returns:
        是否支持视觉
    """
    if model_vision is not None:
        return model_vision
    name_lower = (model_name or "").lower()
    vision_keywords = ("vl", "vision", "gemini", "4o", "claude-3", "omni", "multimodal", "image", "llava")
    if any(kw in name_lower for kw in vision_keywords):
        return True
    return provider_vision


# 模块级单例，供 ModelService 与 test-connection 端点共享
adapter = ModelConfigAdapter()
