from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.core.database import SessionLocal
from app.models.agent import Setting
from app.services.model import model_service

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
}


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


@router.get("", response_model=Dict[str, str])
async def get_all_settings():
    """返回全部设置；api_key_* 属敏感配置，不再走通用接口（改由 /api/models/config 脱敏返回）"""
    db = SessionLocal()
    try:
        settings = db.query(Setting).all()
        result = dict(DEFAULT_SETTINGS)
        for s in settings:
            if s.key.startswith("api_key_"):
                continue
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
        if key.startswith("api_key_"):
            model_service.reload_models()
            return SettingResponse(key=setting.key, value=_mask_key(setting.value))
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
            result[key] = _mask_key(value) if key.startswith("api_key_") else value
        db.commit()
        if any(k.startswith("api_key_") or k.startswith("api_base_") for k in request.settings):
            model_service.reload_models()
        return result
    finally:
        db.close()
