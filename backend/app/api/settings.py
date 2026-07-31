from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.core.database import SessionLocal
from app.models.agent import Setting

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
    "default_model": "mimo-v2.5-pro",
    "default_agent": "general",
    "default_personality": "50",
    "memory_enabled": "true",
    "font_size": "14",
    "font_family": "system",
}


@router.get("", response_model=Dict[str, str])
async def get_all_settings():
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
        return result
    finally:
        db.close()
