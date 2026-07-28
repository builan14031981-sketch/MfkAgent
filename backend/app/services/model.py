from typing import List, Optional, Dict, Any, AsyncIterator
from pydantic import BaseModel
from enum import Enum
import httpx
import json
from app.core.config import settings

class ModelProvider(str, Enum):
    MIMO = "mimo"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    GLM = "glm"
    WENXIN = "wenxin"
    SPARK = "spark"
    MOONSHOT = "moonshot"
    MINIMAX = "minimax"
    BAICHUAN = "baichuan"

class ModelConfig(BaseModel):
    provider: ModelProvider
    model_name: str
    api_key: str
    api_base: str
    max_tokens: int = 4096
    temperature: float = 0.7

class Message(BaseModel):
    role: str
    content: str

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

class ModelService:
    def __init__(self):
        self.models = self._init_models()
    
    def _init_models(self) -> Dict[str, ModelConfig]:
        """初始化所有模型配置"""
        return {
            # 小米MiMo模型
            "mimo-v2.5-pro": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5-pro",
                api_key=settings.MIMO_API_KEY,
                api_base=settings.MIMO_API_BASE,
            ),
            "mimo-v2.5": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5",
                api_key=settings.MIMO_API_KEY,
                api_base=settings.MIMO_API_BASE,
            ),
            # DeepSeek模型
            "deepseek-chat": ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-chat",
                api_key=settings.DEEPSEEK_API_KEY,
                api_base="https://api.deepseek.com/v1",
            ),
            # 通义千问模型
            "qwen-turbo": ModelConfig(
                provider=ModelProvider.QWEN,
                model_name="qwen-turbo",
                api_key=settings.QWEN_API_KEY,
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            # 智谱AI模型
            "glm-4": ModelConfig(
                provider=ModelProvider.GLM,
                model_name="glm-4",
                api_key=settings.GLM_API_KEY,
                api_base="https://open.bigmodel.cn/api/paas/v4",
            ),
            # Moonshot模型
            "moonshot-v1-8k": ModelConfig(
                provider=ModelProvider.MOONSHOT,
                model_name="moonshot-v1-8k",
                api_key=settings.MOONSHOT_API_KEY,
                api_base="https://api.moonshot.cn/v1",
            ),
        }
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型列表"""
        models = []
        for model_id, config in self.models.items():
            if config.api_key:
                models.append({
                    "id": model_id,
                    "name": model_id,
                    "provider": config.provider.value,
                    "max_tokens": config.max_tokens,
                })
        return models
    
    def get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self.models.get(model_id)
    
    async def chat(
        self,
        model_id: str,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> ChatResponse:
        """发送聊天请求"""
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")
        
        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")
        
        # 根据不同的provider调用不同的接口
        if config.provider in [
            ModelProvider.MIMO,
            ModelProvider.DEEPSEEK,
            ModelProvider.QWEN,
            ModelProvider.GLM,
            ModelProvider.MOONSHOT,
            ModelProvider.MINIMAX,
            ModelProvider.BAICHUAN,
        ]:
            return await self._chat_openai_compatible(
                config, messages, temperature, max_tokens, stream
            )
        else:
            raise ValueError(f"不支持的模型提供商: {config.provider}")
    
    async def chat_stream(
        self,
        model_id: str,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天请求"""
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": config.model_name,
            "messages": [msg.dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{config.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0,
            ) as response:
                if response.status_code != 200:
                    raise Exception(f"API调用失败: {await response.aread()}")

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line or line == "data: [DONE]":
                            continue
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                choices = data.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                finish_reason = choices[0].get("finish_reason")
                                if content:
                                    yield {"content": content}
                                if finish_reason:
                                    yield {"finish_reason": finish_reason}
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue

    async def _chat_openai_compatible(
        self,
        config: ModelConfig,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> ChatResponse:
        """调用OpenAI兼容接口"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": config.model_name,
            "messages": [msg.dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            
            if response.status_code != 200:
                raise Exception(f"API调用失败: {response.text}")
            
            data = response.json()
            
            return ChatResponse(
                id=data.get("id", ""),
                model=data.get("model", config.model_name),
                content=data["choices"][0]["message"]["content"],
                finish_reason=data["choices"][0].get("finish_reason", "stop"),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            )

# 创建全局模型服务实例
model_service = ModelService()
