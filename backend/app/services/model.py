from typing import List, Optional, Dict, Any, AsyncIterator
from pydantic import BaseModel
from enum import Enum
import httpx
import json
from app.core.config import settings
from app.core.model_providers import PROVIDERS, PROVIDER_MAP
from app.core.tool_runtime.normalizer import normalize_tool_call_text

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
    SILICONFLOW = "siliconflow"
    FREELLMAPI = "freellmapi"
    GOOGLE = "google"
    OPENAI = "openai"  # 通用 OpenAI 兼容端点（自定义模型默认 provider）

class ModelConfig(BaseModel):
    provider: ModelProvider
    model_name: str
    api_key: str
    api_base: str
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 0  # 0 = 主力模型（可用），1 = 备用模型（可能不可用）

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


class SingleCallResult(BaseModel):
    """单次 LLM 调用结果（Phase 3: AgentRuntime 执行循环用）"""
    content: str
    tool_calls: Optional[list] = None
    finish_reason: str = "stop"
    usage: Optional[dict] = None


class ModelService:
    def __init__(self):
        self.models = self._init_models()

    @staticmethod
    def _upstream_error_message(status_code: int, raw: str) -> str:
        """从上游 API 错误响应中提取一句话人话，避免把整段原始字节串刷给前端。

        上游 OpenAI 兼容错误体形如：
          {"error": {"message": "...", "type": "provider_error", "code": "upstream_failed"}}
        无法解析时回退为 HTTP 状态码 + 截断原文。
        """
        try:
            import json as _json
            parsed = _json.loads(raw)
            msg = parsed.get("error", {}).get("message")
            if msg and isinstance(msg, str):
                # 免费模型常见的 503 队列满，附加中文提示
                if "503" in msg or "queue is full" in msg.lower() or "upstream" in msg.lower():
                    return f"模型服务暂时不可用（{status_code}），上游队列繁忙，请稍后重试：{msg[:200]}"
                return f"模型服务返回错误（{status_code}）：{msg[:300]}"
        except Exception:
            pass
        return f"模型服务返回错误（{status_code}）：{raw[:300]}"

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

    def _get_api_base(self, env_base: str, provider_id: str) -> str:
        """读取 api_base_<provider> 覆盖；未配置时用 provider 默认端点。"""
        from app.core.database import SessionLocal
        from app.models.agent import Setting
        db = SessionLocal()
        try:
            setting = db.query(Setting).filter(Setting.key == f"api_base_{provider_id}").first()
            if setting and setting.value:
                return setting.value
        finally:
            db.close()
        return env_base

    @staticmethod
    def _provider_enum(provider_id: str) -> ModelProvider:
        """将 provider id 字符串映射为 ModelProvider 枚举；未知值回落为通用 OpenAI 兼容。"""
        try:
            return ModelProvider(provider_id)
        except ValueError:
            return ModelProvider.OPENAI

    def _custom_models(self):
        """读取 models 表中已启用的自定义模型。"""
        from app.core.database import SessionLocal
        from app.models.agent import CustomModel
        db = SessionLocal()
        try:
            return db.query(CustomModel).filter(CustomModel.enabled.is_(True)).all()
        finally:
            db.close()

    def _init_models(self) -> Dict[str, ModelConfig]:
        """初始化所有模型配置：内置 Provider 注册表 + models 表自定义模型合并。

        同名 model_id 时自定义模型覆盖内置（便于用户替换默认端点/模型名）。
        """
        models: Dict[str, ModelConfig] = {}
        for p in PROVIDERS:
            env_key = getattr(settings, p.env_key, "")
            api_base = self._get_api_base(p.default_api_base, p.id)
            for m in p.models:
                models[m.id] = ModelConfig(
                    provider=self._provider_enum(p.id),
                    model_name=m.upstream,
                    api_key=self._get_api_key(env_key, f"api_key_{p.id}"),
                    api_base=api_base,
                )
        for cm in self._custom_models():
            models[cm.model_id] = ModelConfig(
                provider=self._provider_enum(cm.provider),
                model_name=cm.model_name,
                api_key=cm.api_key or "",
                api_base=cm.api_base,
                max_tokens=cm.max_tokens,
                temperature=cm.temperature,
            )
        return models
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型列表（按优先级排序：主力模型在前，备用模型在后）"""
        models = []
        for model_id, config in self.models.items():
            if config.api_key:
                # 查找 display_name（优先用 ProviderModel 中定义的展示名）
                display_name = model_id
                provider_def = PROVIDER_MAP.get(config.provider.value)
                if provider_def:
                    for m in provider_def.models:
                        if m.id == model_id and m.display_name:
                            display_name = m.display_name
                            break
                models.append({
                    "id": model_id,
                    "name": display_name,
                    "provider": config.provider.value,
                    "max_tokens": config.max_tokens,
                    "priority": config.priority,
                })
        models.sort(key=lambda m: m["priority"])
        return models
    
    def get_model_config(self, model_id: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self.models.get(model_id)

    def _resolve_api_model_name(self, config: ModelConfig) -> str:
        """将内部模型 ID 转换为官方 API 使用的模型名。

        DeepSeek V4-Flash / V4-Pro 即为官方 API 模型名（deepseek-chat / deepseek-reasoner 旧名已于 2026-07 停用），
        直接透传 config.model_name，不做任何映射。
        """
        return config.model_name

    def _apply_reasoning_payload(self, payload: dict, config: ModelConfig, reasoning_effort: str) -> None:
        """按 provider 官方规范设置思考/推理参数。

        档位语义（前端三档：none / high / max）：
          - none：显式关闭思考（各 provider 发送官方关闭字段，不依赖模型默认）
          - high：开启思考，官方标准档
          - max：开启思考，官方最高档（DeepSeek V4 / GLM-5.2）

        provider 差异：
          - DEEPSEEK（V4-Flash / V4-Pro）：thinking: {type: enabled|disabled} + reasoning_effort(high/max)
          - GLM：thinking: {type: enabled|disabled} + reasoning_effort(high/max)
          - QWEN：enable_thinking 布尔开关（无强度档位）
        """
        if not reasoning_effort:
            return
        effort = reasoning_effort if reasoning_effort in ("high", "max") else "high"
        if config.provider == ModelProvider.DEEPSEEK or config.provider == ModelProvider.SILICONFLOW:
            if reasoning_effort == "none":
                payload["thinking"] = {"type": "disabled"}
            else:
                payload["thinking"] = {"type": "enabled", "reasoning_effort": effort}
        elif config.provider == ModelProvider.GLM:
            if reasoning_effort == "none":
                payload["thinking"] = {"type": "disabled"}
            else:
                payload["thinking"] = {"type": "enabled"}
                payload["reasoning_effort"] = effort
        elif config.provider == ModelProvider.QWEN:
            payload["enable_thinking"] = reasoning_effort != "none"

    def reload_models(self):
        """重新加载模型配置（当设置更新时调用）"""
        self.models = self._init_models()

    async def call_once(
        self,
        model_id: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list = None,
        reasoning_effort: str = None,
        memory_text: str = None,
    ) -> SingleCallResult:
        """单次 LLM 调用 — Phase 3 Execution Loop 用。

        只做一次 API 请求，不负责工具循环/重试/决策。
        与 chat() 不同：chat() 内部有 8 轮 Tool Calling 循环，
        call_once() 只做一次原始调用，工具循环由 AgentRuntime 控制。

        Args:
            model_id: 模型 ID
            messages: 消息列表（List[dict]）
            temperature: 模型温度
            max_tokens: 最大 token 数
            tools: 工具定义列表
            reasoning_effort: 推理强度
            memory_text: 记忆文本（仅首轮注入）

        Returns:
            SingleCallResult: content / tool_calls / finish_reason / usage
        """
        config = self.get_model_config(model_id)
        if not config or not config.api_key:
            raise ValueError(f"模型 {model_id} 不可用")

        # Memory 注入（仅首轮，处理 dict 格式 messages）
        work_messages = list(messages)
        if memory_text:
            for m in work_messages:
                if isinstance(m, dict) and m.get("role") == "system":
                    m["content"] = m["content"] + "\n\n" + memory_text
                    break

        payload = {
            "model": self._resolve_api_model_name(config),
            "messages": work_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if reasoning_effort:
            self._apply_reasoning_payload(payload, config, reasoning_effort)
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{config.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code != 200:
                raise Exception(self._upstream_error_message(response.status_code, response.text))

        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls")

        # Phase C-1: 归一化非标准工具调用
        if tools and not tool_calls and content:
            available_names = {t["function"]["name"] for t in tools}
            norm = normalize_tool_call_text(content, available_names)
            if norm["calls"] and not norm["issues"]:
                tool_calls = norm["calls"]

        return SingleCallResult(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=data.get("usage"),
        )

    async def stream_once(
        self,
        model_id: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list = None,
        reasoning_effort: str = None,
        memory_text: str = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """单次流式 LLM 调用 — Phase E1 Execution Loop 用。

        只做一次流式 API 请求，不负责工具执行 / 轮次判断 / 决策。
        工具循环由 AgentRuntime 控制。

        yield 协议（与 chat_stream 旧协议保持兼容，供 chat.py 透传 SSE）：
          {"type": "text", "content": str}                    文本增量
          {"type": "thinking", "content": str}                思考段增量
          {"type": "tool_calls", "calls": [...]}              本轮结构化 tool_calls（已排序，含结果前原始参数）
          {"type": "finish", "finish_reason": str}

        Args:
            model_id: 模型 ID
            messages: 消息列表（List[dict]）
            temperature: 模型温度
            max_tokens: 最大 token 数
            tools: 工具定义列表
            reasoning_effort: 推理强度
            memory_text: 记忆文本（仅首轮注入）
        """
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

        # Memory 注入（仅首轮，处理 dict 格式 messages）
        work_messages = list(messages)
        if memory_text:
            for m in work_messages:
                if isinstance(m, dict) and m.get("role") == "system":
                    m["content"] = m["content"] + "\n\n" + memory_text
                    break

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._resolve_api_model_name(config),
            "messages": work_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},  # G6-A: 请求 token 用量
        }
        if reasoning_effort:
            self._apply_reasoning_payload(payload, config, reasoning_effort)
        if tools:
            payload["tools"] = tools

        collected_tool_calls: dict = {}
        final_finish = "stop"
        final_usage = None  # G6-A: 捕获 token 用量

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{config.api_base}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0,
            ) as response:
                if response.status_code != 200:
                    raise Exception(self._upstream_error_message(response.status_code, await response.aread()))

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
                                # G6-A: 捕获 token 用量（usage chunk 无 choices）
                                if "usage" in data and data["usage"]:
                                    final_usage = data["usage"]
                                choices = data.get("choices", [])
                                if not choices:
                                    continue
                                choice = choices[0]
                                delta = choice.get("delta", {})
                                content = delta.get("content", "")
                                reasoning_content = delta.get("reasoning_content", "")
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
                                    yield {"type": "text", "content": content}
                                # 思考段增量独立透传
                                if reasoning_content and not collected_tool_calls:
                                    yield {"type": "thinking", "content": reasoning_content}
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue

        # 本轮结束：结构化 tool_calls 汇总（有序）＋ finish（含 usage）
        if collected_tool_calls:
            ordered = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
            yield {"type": "tool_calls", "calls": ordered}
        yield {"type": "finish", "finish_reason": final_finish, "usage": final_usage}

# 创建全局模型服务实例
model_service = ModelService()
