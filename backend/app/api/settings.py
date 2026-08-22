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
    "show_reasoning": "true",
    # 记忆三开关（2026-08-13 记忆可见化治理）：
    # - memory_read_enabled：读闸，false 时 AI 完全不读已存记忆（记忆保留在库，前端仍可管理）
    # - memory_write_enabled：写闸，false 时完全不自动提取/沉淀新记忆
    # - memory_alert：保存后提示，true 时在对话流推送"已保存记忆"通知
    "memory_enabled": "true",
    "memory_read_enabled": "true",
    "memory_write_enabled": "true",
    "memory_alert": "true",
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
    # 纹身图模型 BYOK 配置（生图专用，独立于通用文生图 image_gen_model）
    "tattoo_provider": "",
    "tattoo_api_key": "",
    "tattoo_model": "",
    "tattoo_base_url": "",
    # TTS 语音朗读配置（支持双引擎：edge 微软 / volcengine 火山引擎）
    "tts_enabled": "false",
    "tts_engine": "volcengine",
    "tts_voice": "zh-CN-YunxiNeural",
    "tts_rate": "+0%",
    "tts_auto_play": "false",
    # 火山引擎 TTS 配置（字节跳动，国内直连，低时延）
    "volcengine_appid": "",
    "volcengine_access_token": "",
    "volcengine_voice": "zh_female_cancan_mars_bigtts",
    # 语音转写 BYOK 配置（OpenAI 兼容 /audio/transcriptions 端点）
    "stt_provider": "",
    "stt_api_key": "",
    "stt_model": "whisper-1",
    "stt_base_url": "",
    # Provider 整体禁用开关：JSON {providerId: true}，被禁用的 Provider
    # 不出现在 /api/models，call_once/stream_once 调用会抛 ModelConfigError
    "provider_disabled": "{}",
    # Phase 3 T3/T8: Agent 权限模式 — safe / standard / autonomous
    "agent_permission_mode": "standard",
    # 归档：磁盘导出文件夹（空 = 默认 backend/Archive/）
    "archive_dir": "",
    # 网络代理（2026-08-14 代理可配置化）：
    # - proxy_mode: auto（环境变量>Windows系统代理>直连）/ manual（用 proxy_url）/ off（强制直连）
    # - proxy_url: 手动代理地址（如 http://127.0.0.1:7890）
    "proxy_mode": "auto",
    "proxy_url": "",
}


def _sync_custom_models(db, enabled_models_json: str) -> None:
    """当 enabled_models 更新时，同步创建/删除 CustomModel 记录。

    enabled_models 格式: {"qwen": ["deepseek-v4-flash-0731", ...], ...}

    规则（2026-08-11 治理后，source 字段区分来源）：
      - 只在 enabled_models 中出现的远程模型（非内置 Provider 模型）→ 创建/更新 CustomModel，enabled=True，source='sync'
      - source='manual' 的行：绝不触碰（不覆盖、不禁用、不删除）——用户手动创建的第三方接入
      - source='sync' 且已从 enabled_models 移除 → 直接删除（避免幽灵残留；
        字段均可从 provider 重新派生，删除零数据损失；再次入池会自动重建）
      - 内置 Provider 模型（model_id 在 _mp.PROVIDERS 中）→ 不创建 CustomModel
    """
    from app.models.agent import CustomModel
    import app.core.model_providers as _mp
    from app.core.model_adapter import adapter

    try:
        enabled_map = json.loads(enabled_models_json)
    except (json.JSONDecodeError, TypeError):
        return

    if not isinstance(enabled_map, dict):
        return

    # 收集所有内置模型 ID（用于判断是否为远程模型）
    builtin_ids: set = set()
    for p in _mp.PROVIDERS:
        for m in p.models:
            builtin_ids.add(m.id)

    # 收集 enabled_models 中所有远程模型：(provider, model_id)
    enabled_remote: set = set()
    for provider_id, model_ids in enabled_map.items():
        if not isinstance(model_ids, list):
            continue
        provider_def = _mp.PROVIDER_MAP.get(provider_id)
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
        provider_def = _mp.PROVIDER_MAP.get(provider_id)
        if not provider_def:
            continue
        api_key = adapter.resolve_api_key(provider_def)
        api_base = adapter.resolve_api_base(provider_def)

        if model_id in existing:
            cm = existing[model_id]
            # 存量 Bug 修复：手动创建的行（source='manual'）即使 model_id 撞车也不覆盖，
            # 避免 sync 把用户自配的 api_key/api_base 等字段洗掉。
            if getattr(cm, "source", "manual") == "manual":
                continue
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
                source="sync",
            ))

    # 清理：source='sync' 且已移出候选池的行直接删除（替代旧版 enabled=False 幽灵残留）。
    # source='manual' 的行任何情况下不触碰（修复旧版无差别禁用的存量 Bug）。
    for model_id, cm in existing.items():
        if model_id in builtin_ids:
            continue  # 内置模型不触碰
        if getattr(cm, "source", "manual") == "manual":
            continue  # 手动创建的第三方接入绝不触碰
        if (cm.provider, model_id) not in enabled_remote:
            db.delete(cm)

    logger.info(
        "_sync_custom_models: enabled_remote=%d, total_custom=%d",
        len(enabled_remote), len(existing),
    )


def _sync_custom_model_api_keys(db, provider_id: str) -> None:
    """当 provider 的 API Key 更新时，同步更新该 provider 下所有 CustomModel 的 api_key。

    确保 CustomModel 记录的 api_key 与 provider 当前 Key 保持一致。
    """
    from app.models.agent import CustomModel
    import app.core.model_providers as _mp
    from app.core.model_adapter import adapter

    provider_def = _mp.PROVIDER_MAP.get(provider_id)
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


def _mask_key(key: str) -> str:
    """API Key 脱敏：短 Key 全掩码，长 Key 保留首3+尾4。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:3] + "****" + key[-4:]


def _sync_approval_mode(value: str) -> None:
    """同步 agent_permission_mode 到 ApprovalPolicy 内存单例。

    get_approval_policy() 仅在首次调用时从数据库读取一次，之后永久缓存；
    若写入设置后不刷新，内存单例会锁死旧权限模式（切换 safe/standard/autonomous 失效）。
    非法值回退到默认模式并告警，绝不抛 500。
    """
    from app.core.tool_runtime.approval_policy import ApprovalMode, set_approval_mode
    try:
        set_approval_mode(ApprovalMode(value))
        logger.info("agent_permission_mode hot-reloaded: %s", value)
    except (ValueError, KeyError):
        from app.core.tool_runtime.approval_policy import DEFAULT_APPROVAL_MODE
        set_approval_mode(DEFAULT_APPROVAL_MODE)
        logger.warning("invalid agent_permission_mode=%r, fallback to default", value)



def _is_secret_key(key: str) -> bool:
    """判断是否为需脱敏的密钥类设置（provider api_key_* / stt_api_key / vision_api_key / volcengine_access_token 等）。"""
    return key.startswith("api_key_") or key.endswith("_api_key") or key == "volcengine_access_token"


@router.get("", response_model=Dict[str, str])
async def get_all_settings():
    """返回全部设置（密钥类字段脱敏，前端仅感知已配置状态）"""
    db = SessionLocal()
    try:
        settings = db.query(Setting).all()
        result = dict(DEFAULT_SETTINGS)
        for s in settings:
            if _is_secret_key(s.key):
                result[s.key] = _mask_key(s.value)
            else:
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
            value = _mask_key(setting.value) if _is_secret_key(setting.key) else setting.value
            return SettingResponse(key=setting.key, value=value)
        if key in DEFAULT_SETTINGS:
            value = DEFAULT_SETTINGS[key]
            if _is_secret_key(key):
                value = _mask_key(value)
            return SettingResponse(key=key, value=value)
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

        # agent_permission_mode 更新 → 同步内存单例（get_approval_policy 只读一次，不刷新会锁死旧值）
        if key == "agent_permission_mode":
            _sync_approval_mode(request.value)

        # proxy_* 更新 → 清代理配置缓存（proxy.py 下次读取即新值）
        if key.startswith("proxy_"):
            from app.core.proxy import invalidate as proxy_invalidate
            proxy_invalidate()

        return SettingResponse(key=setting.key, value=setting.value)
    finally:
        db.close()


@router.get("/{key}/reveal", response_model=SettingResponse)
async def reveal_setting(key: str):
    """获取明文设置值（仅用于密钥类字段，如 API Key）。

    普通 GET /{key} 会对密钥脱敏，此接口返回明文，
    供前端"显示明文"按钮调用，使用户可查看/复制已保存的真实 Key。
    """
    if not _is_secret_key(key):
        raise HTTPException(status_code=400, detail="Only secret keys can be revealed")
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

        # agent_permission_mode 更新 → 同步内存单例（与单条接口同套路）
        if "agent_permission_mode" in request.settings:
            _sync_approval_mode(request.settings["agent_permission_mode"])

        # proxy_* 更新 → 清代理配置缓存（与单条接口同套路）
        if any(k.startswith("proxy_") for k in request.settings):
            from app.core.proxy import invalidate as proxy_invalidate
            proxy_invalidate()

        return result
    finally:
        db.close()
