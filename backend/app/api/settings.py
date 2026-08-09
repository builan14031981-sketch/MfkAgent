import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from app.core.database import SessionLocal
from app.models.agent import Setting
from app.services.model import model_service

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingResponse(BaseModel):
    key: str
    value: str


class SettingUpdate(BaseModel):
    value: str


class SettingsBulkUpdate(BaseModel):
    settings: Dict[str, str]


DEFAULT_SETTINGS = {
    "theme": "system",
    "language": "zh-CN",
    "default_model": "qwen-flash",
    "default_agent": "general",
    "default_personality": "50",
    "default_reasoning_effort": "none",
    "memory_enabled": "true",
    "font_size": "14",
    "font_family": "system",
    "hero_entry": "1",
    "hero_random": "1",
    "hero_random_scope": "all",
    "hero_favorites": "[]",
    "greeting_mode": "builtin",
    "custom_greetings": "[]",
    # Phase 3: 多模态 BYOK 备用识图配置
    "vision_provider": "",
    "vision_api_key": "",
    "vision_model": "",
    "vision_base_url": "",
    # 语音转写 BYOK 配置（OpenAI 兼容 /audio/transcriptions 端点）
    "stt_provider": "",
    "stt_api_key": "",
    "stt_model": "whisper-1",
    "stt_base_url": "",
    # Provider 整体禁用开关：JSON {providerId: true}，被禁用的 Provider
    # 不出现在 /api/models，call_once/stream_once 调用会抛 ModelConfigError
    "provider_disabled": "{}",
}


def _sync_custom_models(db, enabled_models_json: str) -> None:
    """当 enabled_models 更新时，同步创建/禁用 CustomModel 记录。

    enabled_models 格式: {"qwen": ["deepseek-v4-flash-0731", ...], ...}

    规则：
      - 只在 enabled_models 中出现的远程模型（非内置 Provider 模型）→ 创建/更新 CustomModel，enabled=True
      - 之前由 sync 创建、但已从 enabled_models 移除的远程模型 → enabled=False
      - 手动创建的 CustomModel（model_id 不在任何 enabled_models 中且非内置）→ 不触碰
      - 内置 Provider 模型（model_id 在 PROVIDERS 中）→ 不创建 CustomModel
    """
    from app.models.agent import CustomModel
    from app.core.model_providers import PROVIDERS, PROVIDER_MAP
    from app.core.model_adapter import adapter

    try:
        enabled_map = json.loads(enabled_models_json)
    except (json.JSONDecodeError, TypeError):
        return

    if not isinstance(enabled_map, dict):
        return

    # 收集所有内置模型 ID（用于判断是否为远程模型）
    builtin_ids: set = set()
    for p in PROVIDERS:
        for m in p.models:
            builtin_ids.add(m.id)

    # 收集 enabled_models 中所有远程模型：(provider, model_id)
    enabled_remote: set = set()
    for provider_id, model_ids in enabled_map.items():
        if not isinstance(model_ids, list):
            continue
        provider_def = PROVIDER_MAP.get(provider_id)
        if not provider_def:
            continue
        for model_id in model_ids:
            if not isinstance(model_id, str) or not model_id.strip():
                continue
            mid = model_id.strip()
            # 只处理远程模型（非内置）
            if mid not in builtin_ids:
                enabled_remote.add((provider_id, mid))

    # 获取所有现有 CustomModel
    existing = {cm.model_id: cm for cm in db.query(CustomModel).all()}

    # Upsert：为 enabled_remote 中的模型创建/更新 CustomModel
    for provider_id, model_id in enabled_remote:
        provider_def = PROVIDER_MAP.get(provider_id)
        if not provider_def:
            continue
        api_key = adapter.resolve_api_key(provider_def)
        api_base = adapter.resolve_api_base(provider_def)

        if model_id in existing:
            cm = existing[model_id]
            cm.provider = provider_id
            cm.model_name = model_id
            cm.name = model_id
            cm.api_key = api_key
            cm.api_base = api_base
            cm.enabled = True
        else:
            db.add(CustomModel(
                model_id=model_id,
                name=model_id,
                provider=provider_id,
                model_name=model_id,
                api_base=api_base,
                api_key=api_key,
                enabled=True,
            ))

    # 禁用：之前由 sync 管理、但已不在 enabled_remote 中的远程模型
    for model_id, cm in existing.items():
        if model_id in builtin_ids:
            continue  # 内置模型不触碰
        if (cm.provider, model_id) not in enabled_remote:
            cm.enabled = False

    logger.info(
        "_sync_custom_models: enabled_remote=%d, total_custom=%d",
        len(enabled_remote), len(existing),
    )


def _sync_custom_model_api_keys(db, provider_id: str) -> None:
    """当 provider 的 API Key 更新时，同步更新该 provider 下所有 CustomModel 的 api_key。

    确保 CustomModel 记录的 api_key 与 provider 当前 Key 保持一致。
    """
    from app.models.agent import CustomModel
    from app.core.model_providers import PROVIDER_MAP
    from app.core.model_adapter import adapter

    provider_def = PROVIDER_MAP.get(provider_id)
    if not provider_def:
        return
    new_key = adapter.resolve_api_key(provider_def)
    rows = db.query(CustomModel).filter(CustomModel.provider == provider_id).all()
    for cm in rows:
        cm.api_key = new_key
    if rows:
        logger.info(
            "_sync_custom_model_api_keys: provider=%s updated %d custom models",
            provider_id, len(rows),
        )


@router.get("", response_model=Dict[str, str])
async def get_all_settings():
    """返回全部设置（本地化工具，明文下发，知情权归用户）"""
    db = SessionLocal()
    try:
        settings = db.query(Setting).all()
        result = dict(DEFAULT_SETTINGS)
        for s in settings:
            result[s.key] = s.value
        return result
    finally:
        db.close()


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(key: str):
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            return SettingResponse(key=setting.key, value=setting.value)
        if key in DEFAULT_SETTINGS:
            return SettingResponse(key=key, value=DEFAULT_SETTINGS[key])
        raise HTTPException(status_code=404, detail="Setting not found")
    finally:
        db.close()


@router.put("/{key}", response_model=SettingResponse)
async def update_setting(key: str, request: SettingUpdate):
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = request.value
        else:
            setting = Setting(key=key, value=request.value)
            db.add(setting)
        db.commit()
        db.refresh(setting)

        # enabled_models 更新 → 同步 CustomModel 表 + 热重载
        if key == "enabled_models":
            _sync_custom_models(db, request.value)
            db.commit()
            model_service.reload_models()

        # api_key 更新 → 同步 CustomModel api_key + 热重载
        if key.startswith("api_key_"):
            provider_id = key.replace("api_key_", "")
            _sync_custom_model_api_keys(db, provider_id)
            db.commit()
            model_service.reload_models()

        # provider_disabled 更新 → 热重载（get_available_models 重新过滤禁用 Provider）
        if key == "provider_disabled":
            model_service.reload_models()

        return SettingResponse(key=setting.key, value=setting.value)
    finally:
        db.close()


@router.put("", response_model=Dict[str, str])
async def update_settings(request: SettingsBulkUpdate):
    db = SessionLocal()
    try:
        result = {}
        for key, value in request.settings.items():
            setting = db.query(Setting).filter(Setting.key == key).first()
            if setting:
                setting.value = value
            else:
                setting = Setting(key=key, value=value)
                db.add(setting)
            result[key] = value
        db.commit()

        # enabled_models 更新 → 同步 CustomModel 表 + 热重载
        if "enabled_models" in request.settings:
            _sync_custom_models(db, request.settings["enabled_models"])
            db.commit()
            model_service.reload_models()

        # api_key 更新 → 同步 CustomModel api_key
        api_key_updated = False
        for k in request.settings:
            if k.startswith("api_key_"):
                provider_id = k.replace("api_key_", "")
                _sync_custom_model_api_keys(db, provider_id)
                api_key_updated = True
        if api_key_updated:
            db.commit()

        if any(k.startswith("api_key_") or k.startswith("api_base_") or k == "provider_disabled" for k in request.settings):
            model_service.reload_models()
        return result
    finally:
        db.close()
