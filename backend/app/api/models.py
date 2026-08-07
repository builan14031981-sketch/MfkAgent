from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from app.services.model import model_service, Message
from app.core.model_providers import PROVIDERS, PROVIDER_MAP
import json

router = APIRouter()

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    max_tokens: int
    priority: int = 0

class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False

class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    finish_reason: str
    usage: Any

class ProviderKeyUpdate(BaseModel):
    provider_id: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None

class CustomModelCreate(BaseModel):
    model_id: str
    name: str
    provider: str = "openai"
    model_name: str
    api_base: str
    api_key: Optional[str] = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True

class CustomModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    enabled: Optional[bool] = None


def _mask_key(key: str) -> str:
    """API Key 脱敏：sk-****1234。空返回空串。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}****{key[-4:]}"


def _get_setting(key: str) -> str:
    from app.core.database import SessionLocal
    from app.models.agent import Setting
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting and setting.value else ""
    finally:
        db.close()


def _set_setting(key: str, value: str) -> None:
    """upsert settings 表；value 为空时删除该键（恢复默认）。"""
    from app.core.database import SessionLocal
    from app.models.agent import Setting
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == key).first()
        if value:
            if setting:
                setting.value = value
            else:
                db.add(Setting(key=key, value=value))
        else:
            if setting:
                db.delete(setting)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/models", response_model=List[ModelInfo])
async def list_models():
    """
    获取所有可用模型列表
    """
    models = model_service.get_available_models()
    return models

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    发送聊天请求到指定模型
    """
    try:
        result = await model_service.call_once(
            model_id=request.model,
            messages=[m.dict() for m in request.messages],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return ChatResponse(
            id="chatcmpl-1",
            model=request.model,
            content=result.content,
            finish_reason=result.finish_reason,
            usage=result.usage,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模型调用失败: {str(e)}")

@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    流式聊天接口
    """
    async def generate():
        try:
            async for chunk in model_service.stream_once(
                model_id=request.model,
                messages=[m.dict() for m in request.messages],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )

@router.get("/providers")
async def list_providers():
    """获取所有模型提供商列表（数据驱动，含免费标识与 Key 配置状态）"""
    providers = []
    for p in PROVIDERS:
        from app.core.config import settings as _settings
        has_key = bool(model_service._get_api_key(
            getattr(_settings, p.env_key, ""), f"api_key_{p.id}"
        ))
        providers.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "free": p.free,
            "website": p.website,
            "has_key": has_key,
            "api_base_override": bool(_get_setting(f"api_base_{p.id}")),
            "models": [{"id": m.id, "name": m.display_name or m.id} for m in p.models],
        })
    return {"providers": providers}


@router.get("/config")
async def get_config():
    """获取各 provider 的配置状态（Key 脱敏返回）"""
    from app.core.config import settings as _settings
    configs = []
    for p in PROVIDERS:
        api_key = model_service._get_api_key(
            getattr(_settings, p.env_key, ""), f"api_key_{p.id}"
        )
        api_base = model_service._get_api_base(p.default_api_base, p.id)
        configs.append({
            "id": p.id,
            "name": p.name,
            "free": p.free,
            "website": p.website,
            "api_key_masked": _mask_key(api_key),
            "has_key": bool(api_key),
            "api_base": api_base,
            "api_base_override": bool(_get_setting(f"api_base_{p.id}")),
            "models": [{"id": m.id, "name": m.display_name or m.id} for m in p.models],
        })
    return {"configs": configs}


@router.post("/provider-key")
async def update_provider_key(body: ProviderKeyUpdate):
    """配置 provider 的 API Key / API Base，并热重载模型。

    api_key / api_base 为空字符串时删除对应配置（恢复默认端点）。
    """
    p = PROVIDER_MAP.get(body.provider_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"未知 provider: {body.provider_id}")
    if body.api_key is not None:
        _set_setting(f"api_key_{p.id}", body.api_key.strip())
    if body.api_base is not None:
        _set_setting(f"api_base_{p.id}", body.api_base.strip())
    model_service.reload_models()
    return {"status": "updated", "provider": p.id}


@router.get("/custom")
async def list_custom_models():
    """获取所有自定义模型"""
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel
    db = SessionLocal()
    try:
        rows = db.query(CustomModel).order_by(CustomModel.id.desc()).all()
        return [{
            "id": r.id,
            "model_id": r.model_id,
            "name": r.name,
            "provider": r.provider,
            "model_name": r.model_name,
            "api_base": r.api_base,
            "api_key_masked": _mask_key(r.api_key),
            "has_key": bool(r.api_key),
            "max_tokens": r.max_tokens,
            "temperature": r.temperature,
            "enabled": r.enabled,
        } for r in rows]
    finally:
        db.close()


@router.post("/custom")
async def create_custom_model(body: CustomModelCreate):
    """创建自定义模型"""
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel
    if not body.model_id.strip() or not body.model_name.strip() or not body.api_base.strip():
        raise HTTPException(status_code=400, detail="model_id / model_name / api_base 不能为空")
    if body.provider not in PROVIDER_MAP and body.provider != "openai":
        raise HTTPException(status_code=400, detail=f"未知 provider: {body.provider}")
    db = SessionLocal()
    try:
        exists = db.query(CustomModel).filter(CustomModel.model_id == body.model_id.strip()).first()
        if exists:
            raise HTTPException(status_code=400, detail=f"model_id '{body.model_id}' 已存在")
        row = CustomModel(
            model_id=body.model_id.strip(),
            name=body.name.strip() or body.model_id.strip(),
            provider=body.provider,
            model_name=body.model_name.strip(),
            api_base=body.api_base.strip(),
            api_key=body.api_key or "",
            max_tokens=body.max_tokens,
            temperature=body.temperature,
            enabled=body.enabled,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        model_service.reload_models()
        return {"status": "created", "id": row.id}
    finally:
        db.close()


@router.put("/custom/{custom_id}")
async def update_custom_model(custom_id: int, body: CustomModelUpdate):
    """更新自定义模型"""
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel
    db = SessionLocal()
    try:
        row = db.query(CustomModel).filter(CustomModel.id == custom_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="自定义模型不存在")
        data = body.model_dump(exclude_unset=True)
        if "api_key" in data and data["api_key"] is None:
            data["api_key"] = ""
        for field, value in data.items():
            setattr(row, field, value)
        db.commit()
        model_service.reload_models()
        return {"status": "updated", "id": row.id}
    finally:
        db.close()


@router.delete("/custom/{custom_id}")
async def delete_custom_model(custom_id: int):
    """删除自定义模型"""
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel
    db = SessionLocal()
    try:
        row = db.query(CustomModel).filter(CustomModel.id == custom_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="自定义模型不存在")
        db.delete(row)
        db.commit()
        model_service.reload_models()
        return {"status": "deleted", "id": custom_id}
    finally:
        db.close()


@router.post("/reload")
async def reload_models():
    """重新加载模型配置（当API Key更新后调用）"""
    model_service.reload_models()
    return {"status": "reloaded", "models": len(model_service.get_available_models())}
