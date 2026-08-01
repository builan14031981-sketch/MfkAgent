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

# DeepSeek 官方 API 模型名映射（内部展示 ID → 官方 API 名称）
DEEPSEEK_MODEL_MAPPING = {
    "deepseek-v4-flash": "deepseek-chat",
    "deepseek-v4-pro": "deepseek-reasoner",
}


class ModelService:
    def __init__(self):
        self.models = self._init_models()

    def _get_api_key(self, env_key: str, setting_key: str) -> str:
        from app.core.database import SessionLocal
        from app.models.agent import Setting
        db = SessionLocal()
        try:
            setting = db.query(Setting).filter(Setting.key == setting_key).first()
            if setting and setting.value:
                return setting.value
        finally:
            db.close()
        return env_key

    def _init_models(self) -> Dict[str, ModelConfig]:
        """初始化所有模型配置"""
        return {
            "mimo-v2.5-pro": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5-pro",
                api_key=self._get_api_key(settings.MIMO_API_KEY, "api_key_mimo"),
                api_base=settings.MIMO_API_BASE,
            ),
            "mimo-v2.5": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5",
                api_key=self._get_api_key(settings.MIMO_API_KEY, "api_key_mimo"),
                api_base=settings.MIMO_API_BASE,
            ),
            "deepseek-v4-flash": ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-v4-flash",
                api_key=self._get_api_key(settings.DEEPSEEK_API_KEY, "api_key_deepseek"),
                api_base="https://api.deepseek.com/v1",
            ),
            "deepseek-v4-pro": ModelConfig(
                provider=ModelProvider.DEEPSEEK,
                model_name="deepseek-v4-pro",
                api_key=self._get_api_key(settings.DEEPSEEK_API_KEY, "api_key_deepseek"),
                api_base="https://api.deepseek.com/v1",
            ),
            "qwen-turbo": ModelConfig(
                provider=ModelProvider.QWEN,
                model_name="qwen-turbo",
                api_key=self._get_api_key(settings.QWEN_API_KEY, "api_key_qwen"),
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "glm-4": ModelConfig(
                provider=ModelProvider.GLM,
                model_name="glm-4",
                api_key=self._get_api_key(settings.GLM_API_KEY, "api_key_glm"),
                api_base="https://open.bigmodel.cn/api/paas/v4",
            ),
            "moonshot-v1-8k": ModelConfig(
                provider=ModelProvider.MOONSHOT,
                model_name="moonshot-v1-8k",
                api_key=self._get_api_key(settings.MOONSHOT_API_KEY, "api_key_moonshot"),
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

    def _resolve_api_model_name(self, config: ModelConfig) -> str:
        """将内部模型 ID 转换为官方 API 使用的模型名"""
        if config.provider == ModelProvider.DEEPSEEK:
            return DEEPSEEK_MODEL_MAPPING.get(config.model_name, config.model_name)
        return config.model_name

    def reload_models(self):
        """重新加载模型配置（当设置更新时调用）"""
        self.models = self._init_models()

    async def chat(
        self,
        model_id: str,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: List[Dict] = None,
        reasoning_effort: str = None,
    ) -> ChatResponse:
        """发送聊天请求"""
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

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
                config, messages, temperature, max_tokens, stream, tools, reasoning_effort
            )
        else:
            raise ValueError(f"不支持的模型提供商: {config.provider}")

    async def chat_stream(
        self,
        model_id: str,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        reasoning_effort: str = None,
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
            "model": self._resolve_api_model_name(config),
            "messages": [msg.dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning_effort"] = reasoning_effort

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
        tools: List[Dict] = None,
        reasoning_effort: str = None,
    ) -> ChatResponse:
        """调用OpenAI兼容接口"""
        from app.services.tools import tool_registry

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._resolve_api_model_name(config),
            "messages": [msg.dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if reasoning_effort and reasoning_effort != "none":
            payload["reasoning_effort"] = reasoning_effort

        if tools:
            payload["tools"] = tools

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
            choice = data["choices"][0]
            message = choice["message"]

            if choice.get("finish_reason") == "tool_calls" and message.get("tool_calls"):
                tool_results = []
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    import json
                    try:
                        func_args = json.loads(tool_call["function"]["arguments"])
                    except:
                        func_args = {}
                    result = await tool_registry.execute(func_name, **func_args)
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": result.output if result.success else f"Error: {result.error}",
                    })

                new_messages = [msg.dict() for msg in messages]
                new_messages.append(message)
                new_messages.extend(tool_results)

                payload["messages"] = new_messages
                payload.pop("tools", None)

                response2 = await client.post(
                    f"{config.api_base}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )

                if response2.status_code != 200:
                    raise Exception(f"API调用失败: {response2.text}")

                data2 = response2.json()
                return ChatResponse(
                    id=data2.get("id", ""),
                    model=data2.get("model", config.model_name),
                    content=data2["choices"][0]["message"]["content"],
                    finish_reason=data2["choices"][0].get("finish_reason", "stop"),
                    usage=data2.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                )

            return ChatResponse(
                id=data.get("id", ""),
                model=data.get("model", config.model_name),
                content=message.get("content", ""),
                finish_reason=choice.get("finish_reason", "stop"),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            )

# 创建全局模型服务实例
model_service = ModelService()
