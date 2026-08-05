from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from app.services.model import model_service, Message
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
        response = await model_service.chat(
            model_id=request.model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=request.stream,
        )
        return response
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
            async for chunk in model_service.chat_stream(
                model_id=request.model,
                messages=request.messages,
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
    """
    获取所有模型提供商列表
    """
    return {
        "providers": [
            {
                "id": "mimo",
                "name": "小米MiMo",
                "description": "小米大模型，性能优异",
                "website": "https://mimo.xiaomi.com",
            },
            {
                "id": "deepseek",
                "name": "DeepSeek（深度求索）",
                "description": "专注代码和对话的高性能模型",
                "website": "https://platform.deepseek.com",
            },
            {
                "id": "qwen",
                "name": "通义千问（阿里）",
                "description": "阿里云大模型，支持多种场景",
                "website": "https://dashscope.console.aliyun.com",
            },
            {
                "id": "glm",
                "name": "智谱AI（GLM）",
                "description": "清华系大模型，性能优异",
                "website": "https://open.bigmodel.cn",
            },
            {
                "id": "moonshot",
                "name": "Moonshot（月之暗面）",
                "description": "支持超长上下文的模型",
                "website": "https://platform.moonshot.cn",
            },
        ]
    }


@router.post("/reload")
async def reload_models():
    """重新加载模型配置（当API Key更新后调用）"""
    model_service.reload_models()
    return {"status": "reloaded", "models": len(model_service.get_available_models())}
