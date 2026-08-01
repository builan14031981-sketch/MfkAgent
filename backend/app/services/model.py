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
        project_path: str = None,
        max_tool_rounds: int = 4,
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
                config, messages, temperature, max_tokens, stream, tools,
                reasoning_effort, project_path, max_tool_rounds,
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
        tools: List[Dict] = None,
        project_path: str = None,
        max_tool_rounds: int = 4,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天请求（支持多轮 Tool Calling 自动执行环）。

        yield 协议：
          {"content": str}            文本增量
          {"tool_call": {...}}        工具执行事件（name/arguments/result）
          {"tool_calls": [...]}       本轮累计的工具调用汇总（含结果）
          {"finish_reason": str}
        """
        from app.core.tools import execute_file_tool

        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        current_messages = [msg.dict() for msg in messages]
        all_tool_calls: List[dict] = []

        for round_no in range(max_tool_rounds + 1):
            payload = {
                "model": self._resolve_api_model_name(config),
                "messages": current_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if reasoning_effort and reasoning_effort != "none":
                payload["reasoning_effort"] = reasoning_effort
            if tools:
                payload["tools"] = tools

            collected_tool_calls: dict = {}
            final_finish = "stop"

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
                                    choice = choices[0]
                                    delta = choice.get("delta", {})
                                    content = delta.get("content", "")
                                    finish_reason = choice.get("finish_reason")
                                    if finish_reason:
                                        final_finish = finish_reason

                                    # 收集流式 tool_calls delta
                                    for tc in delta.get("tool_calls", []):
                                        idx = tc.get("index")
                                        if idx is None:
                                            continue
                                        acc = collected_tool_calls.setdefault(idx, {
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        })
                                        if tc.get("id"):
                                            acc["id"] = tc["id"]
                                        if tc.get("function", {}).get("name"):
                                            acc["function"]["name"] = tc["function"]["name"]
                                        if tc.get("function", {}).get("arguments"):
                                            acc["function"]["arguments"] += tc["function"]["arguments"]

                                    # 普通文本增量才透传（工具调用段不输出文本）
                                    if content and not collected_tool_calls:
                                        yield {"content": content}
                                except (json.JSONDecodeError, IndexError, KeyError):
                                    continue

            # 该轮结束时判断是否触发工具调用
            if final_finish == "tool_calls" and collected_tool_calls:
                ordered = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
                assistant_msg = {"role": "assistant", "content": None, "tool_calls": ordered}
                current_messages.append(assistant_msg)

                for tc in ordered:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"] or "{}")
                    except Exception:
                        func_args = {}

                    if func_name in ("write_file", "read_file", "list_files") and project_path:
                        result = execute_file_tool(func_name, project_path=project_path, **func_args)
                        result_text = result
                    else:
                        from app.services.tools import tool_registry
                        r = await tool_registry.execute(func_name, **func_args)
                        result_text = r.output if r.success else f"Error: {r.error}"

                    # ToolCallCard 期望格式：{ name, path, success }（path 从 arguments 提取）
                    rel_path = str(func_args.get("relative_path", ""))
                    record = {
                        "name": func_name,
                        "path": rel_path,
                        "success": not result_text.startswith("错误"),
                        "arguments": func_args,
                        "result": result_text,
                        "tool_call_id": tc.get("id", ""),
                    }
                    all_tool_calls.append(record)
                    # 向前端 SSE 推送工具调用事件（ToolCallCard 实时渲染）
                    yield {"tool_call": {
                        "name": func_name,
                        "path": rel_path,
                        "success": record["success"],
                    }}

                    current_messages.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "content": result_text,
                    })
                continue  # 继续下一轮，驱动 LLM 生成最终文本

            # 正常结束：透传 finish_reason + 工具调用汇总
            yield {"finish_reason": final_finish}
            if all_tool_calls:
                yield {"tool_calls": all_tool_calls}
            return

    async def _chat_openai_compatible(
        self,
        config: ModelConfig,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
        stream: bool,
        tools: List[Dict] = None,
        reasoning_effort: str = None,
        project_path: str = None,
        max_tool_rounds: int = 4,
    ) -> ChatResponse:
        """调用OpenAI兼容接口（支持多轮 Tool Calling 自动执行环）"""
        from app.services.tools import tool_registry
        from app.core.tools import execute_file_tool

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
            round_no = 0
            data = None
            while True:
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

                # 无工具调用：返回最终结果
                if choice.get("finish_reason") != "tool_calls" or not message.get("tool_calls"):
                    break

                round_no += 1
                if round_no > max_tool_rounds:
                    break

                # 执行工具调用，将结果追加到消息历史
                tool_messages = [msg.dict() for msg in messages]
                tool_messages.append(message)
                for tool_call in message["tool_calls"]:
                    func_name = tool_call["function"]["name"]
                    try:
                        func_args = json.loads(tool_call["function"]["arguments"])
                    except Exception:
                        func_args = {}

                    if func_name in ("write_file", "read_file", "list_files") and project_path:
                        result = execute_file_tool(func_name, project_path=project_path, **func_args)
                        content = result
                    else:
                        r = await tool_registry.execute(func_name, **func_args)
                        content = r.output if r.success else f"Error: {r.error}"

                    tool_messages.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": content,
                    })

                payload["messages"] = tool_messages

            if not data:
                raise Exception("API 未返回结果")

            choice = data["choices"][0]
            message = choice["message"]
            return ChatResponse(
                id=data.get("id", ""),
                model=data.get("model", config.model_name),
                content=message.get("content", ""),
                finish_reason=choice.get("finish_reason", "stop"),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            )

# 创建全局模型服务实例
model_service = ModelService()
