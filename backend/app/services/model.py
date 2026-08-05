from typing import List, Optional, Dict, Any, AsyncIterator
from pydantic import BaseModel
from enum import Enum
import httpx
import json
from app.core.config import settings
from app.core.tool_runtime.executor import execute_tool as _execute_tool
from app.core.tool_runtime.events import ToolEventSource

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
    FREELLMAPI = "freellmapi"
    GOOGLE = "google"

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

    def _init_models(self) -> Dict[str, ModelConfig]:
        """初始化所有模型配置"""
        return {
            "mimo-v2.5-pro": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5-pro",
                api_key=self._get_api_key(settings.MIMO_API_KEY, "api_key_mimo"),
                api_base=settings.MIMO_API_BASE,
                priority=2,  # API Key 无效，隐藏
            ),
            "mimo-v2.5": ModelConfig(
                provider=ModelProvider.MIMO,
                model_name="mimo-v2.5",
                api_key=self._get_api_key(settings.MIMO_API_KEY, "api_key_mimo"),
                api_base=settings.MIMO_API_BASE,
                priority=2,  # API Key 无效，隐藏
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
            "qwen-plus": ModelConfig(
                provider=ModelProvider.QWEN,
                model_name="qwen-plus",
                api_key=self._get_api_key(settings.QWEN_API_KEY, "api_key_qwen"),
                api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "qwen-flash": ModelConfig(
                provider=ModelProvider.QWEN,
                model_name="qwen-flash",
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
            # FreeLLMAPI 本地聚合网关（http://127.0.0.1:31415/v1）
            # 内部 ID 加 freellm- 前缀避免与官方同名模型冲突；model_name 透传上游真实模型名
            "freellm-deepseek-v4-flash": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="deepseek-v4-flash",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-qwen3-coder-30b": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="qwen3-coder-30b",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-reka-edge": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="reka-edge",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-reka-flash": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="reka-flash",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-cydonia-24b-v4.3": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="cydonia-24b-v4.3",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-auto": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="auto",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            "freellm-fusion": ModelConfig(
                provider=ModelProvider.FREELLMAPI,
                model_name="fusion",
                api_key=self._get_api_key(settings.FREELLMAPI_API_KEY, "api_key_freellm"),
                api_base=settings.FREELLMAPI_API_BASE,
                priority=2,  # 本地网关未运行，隐藏
            ),
            # Google Gemini 系列（免费额度，所有模型都支持函数调用）
            "gemini-3.5-flash": ModelConfig(
                provider=ModelProvider.GOOGLE,
                model_name="gemini-3.5-flash",  # 稳定版，最智能
                api_key=self._get_api_key(settings.GOOGLE_API_KEY, "api_key_google"),
                api_base="https://generativelanguage.googleapis.com/v1beta/openai",
            ),
            "gemini-3-flash": ModelConfig(
                provider=ModelProvider.GOOGLE,
                model_name="gemini-3-flash-preview",  # 预览版需要 -preview 后缀
                api_key=self._get_api_key(settings.GOOGLE_API_KEY, "api_key_google"),
                api_base="https://generativelanguage.googleapis.com/v1beta/openai",
            ),
            "gemini-3.1-flash-lite": ModelConfig(
                provider=ModelProvider.GOOGLE,
                model_name="gemini-3.1-flash-lite",  # 稳定版，成本效益最高
                api_key=self._get_api_key(settings.GOOGLE_API_KEY, "api_key_google"),
                api_base="https://generativelanguage.googleapis.com/v1beta/openai",
            ),
        }
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型列表（按优先级排序：主力模型在前，备用模型在后）"""
        models = []
        for model_id, config in self.models.items():
            if config.api_key:
                models.append({
                    "id": model_id,
                    "name": model_id,
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
        if config.provider == ModelProvider.DEEPSEEK:
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

    def _inject_memory_text(self, messages: List[Message], memory_text: str) -> List[Message]:
        """将记忆 XML 块强制追加到 system 消息末尾（最高指令优先级）"""
        for i, m in enumerate(messages):
            if m.role == "system":
                messages[i] = Message(role="system", content=m.content + "\n\n" + memory_text)
                return messages
        return [Message(role="system", content=memory_text)] + messages

    def _log_memory_injection(self, messages: List[Message]) -> None:
        try:
            print("\n" + "=" * 70)
            print("[MEMORY-INJECTION] 最终 messages[0]（system 消息）：")
            print("-" * 70)
            print(messages[0].content)
            print("=" * 70 + "\n")
        except Exception:
            pass

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
        max_tool_rounds: int = 8,
        read_only: bool = False,
        memory_context: dict = None,
        memory_text: str = None,
    ) -> ChatResponse:
        """发送聊天请求"""
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

        if memory_text:
            messages = self._inject_memory_text(messages, memory_text)
            self._log_memory_injection(messages)

        if config.provider in [
            ModelProvider.MIMO,
            ModelProvider.DEEPSEEK,
            ModelProvider.QWEN,
            ModelProvider.GLM,
            ModelProvider.MOONSHOT,
            ModelProvider.MINIMAX,
            ModelProvider.BAICHUAN,
            ModelProvider.FREELLMAPI,
            ModelProvider.GOOGLE,
        ]:
            return await self._chat_openai_compatible(
                config, messages, temperature, max_tokens, stream, tools,
                reasoning_effort, project_path, max_tool_rounds, read_only,
                memory_context,
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
        max_tool_rounds: int = 8,
        read_only: bool = False,
        memory_context: dict = None,
        memory_text: str = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式聊天请求（支持多轮 Tool Calling 自动执行环）。

        yield 协议（统一信封，顶层 type 判别）：
          {"type": "text", "content": str}                    文本增量
          {"type": "thinking", "content": str}                思考段增量
          {"type": "tool_start", ...}                         工具开始事件
          {"type": "tool_result", ...}                        工具结束事件（含结果/耗时）
          {"type": "tool_calls", "calls": [...]}              本轮累计的工具调用汇总（含结果，供持久化）
          {"type": "finish", "finish_reason": str}
          {"type": "error", "message": str}
        """
        config = self.get_model_config(model_id)
        if not config:
            raise ValueError(f"模型 {model_id} 不存在")

        if not config.api_key:
            raise ValueError(f"模型 {model_id} 未配置API Key")

        # 工具执行上下文：注入 agent_id / project_id 供 add_memory 等工具使用
        ctx = {k: v for k, v in (memory_context or {}).items() if v is not None}

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        if memory_text:
            messages = self._inject_memory_text(messages, memory_text)
            self._log_memory_injection(messages)

        current_messages = [msg.dict() for msg in messages]
        all_tool_calls: List[dict] = []

        for round_no in range(max_tool_rounds + 1):
            # 轮次预算：前 max_tool_rounds 轮允许工具调用，最后一轮强制移除工具，
            # 保证模型必须输出文本总结，避免"工具轮耗尽后静默结束 → 空回复"。
            round_tools = tools if round_no < max_tool_rounds else None
            payload = {
                "model": self._resolve_api_model_name(config),
                "messages": current_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if reasoning_effort:
                self._apply_reasoning_payload(payload, config, reasoning_effort)
            if round_tools:
                payload["tools"] = round_tools

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
                                    # 思考段增量独立透传（thinking != content，前端据此实时渲染思考中/灰色思考块）
                                    if reasoning_content and not collected_tool_calls:
                                        yield {"type": "thinking", "content": reasoning_content}
                                except (json.JSONDecodeError, IndexError, KeyError):
                                    continue

            # 该轮结束时判断是否触发工具调用
            if final_finish == "tool_calls" and collected_tool_calls and round_tools:
                ordered = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
                assistant_msg = {"role": "assistant", "content": None, "tool_calls": ordered}
                current_messages.append(assistant_msg)

                for tc in ordered:
                    event_source = ToolEventSource()
                    record = await _execute_tool(
                        tool_call=tc,
                        project_path=project_path,
                        read_only=read_only,
                        ctx=ctx,
                        emit=event_source.emit,
                    )
                    all_tool_calls.append(record)
                    # 流式工具事件：tool_start → tool_result 按序透传（ToolCallCard v2 实时渲染）
                    for event in event_source.drain():
                        yield event

                    current_messages.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "content": record["result"],
                    })
                continue  # 继续下一轮，驱动 LLM 生成最终文本

            # 正常结束：透传 finish_reason + 工具调用汇总
            yield {"type": "finish", "finish_reason": final_finish}
            if all_tool_calls:
                yield {"type": "tool_calls", "calls": all_tool_calls}
            return

        # 兜底：工具轮把循环耗尽仍无总结（理论上一轮无工具必然产出文本，
        # 但部分厂商可能在无工具轮仍回空）→ 再补一次无工具收尾请求。
        if all_tool_calls:
            try:
                summary_messages = current_messages
                payload = {
                    "model": self._resolve_api_model_name(config),
                    "messages": summary_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if reasoning_effort:
                    self._apply_reasoning_payload(payload, config, reasoning_effort)
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
                                        choices = data.get("choices", [])
                                        if not choices:
                                            continue
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content", "")
                                        if content:
                                            yield {"type": "text", "content": content}
                                    except (json.JSONDecodeError, IndexError, KeyError):
                                        continue
                yield {"type": "finish", "finish_reason": "stop"}
                yield {"type": "tool_calls", "calls": all_tool_calls}
            except Exception as e:
                yield {"type": "error", "message": f"工具执行完成，但最终总结生成失败: {e}"}

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
        max_tool_rounds: int = 8,
        read_only: bool = False,
        memory_context: dict = None,
    ) -> ChatResponse:
        """调用OpenAI兼容接口（支持多轮 Tool Calling 自动执行环）"""
        ctx = {k: v for k, v in (memory_context or {}).items() if v is not None}

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            round_no = 0
            data = None
            # 累积消息历史（含各轮 assistant tool_calls + tool 结果），避免每轮从原始 messages 重建导致前轮上下文丢失
            tool_messages = [msg.dict() for msg in messages]
            while True:
                # 工具轮次预算：前 max_tool_rounds 轮允许工具，之后移除工具强制模型输出总结
                round_tools = tools if round_no < max_tool_rounds else None
                payload = {
                    "model": self._resolve_api_model_name(config),
                    "messages": tool_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }
                if reasoning_effort:
                    self._apply_reasoning_payload(payload, config, reasoning_effort)
                if round_tools:
                    payload["tools"] = round_tools

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

                # 无工具调用，或已达工具轮次上限：视为最终结果
                if (
                    choice.get("finish_reason") != "tool_calls"
                    or not message.get("tool_calls")
                    or not round_tools
                ):
                    break

                round_no += 1

                # 执行工具调用，将结果追加到累积消息历史
                tool_messages.append(message)
                for tool_call in message["tool_calls"]:
                    record = await _execute_tool(
                        tool_call=tool_call,
                        project_path=project_path,
                        read_only=read_only,
                        ctx=ctx,
                    )
                    tool_messages.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "content": record["result"],
                    })

            if not data:
                raise Exception("API 未返回结果")

            choice = data["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""

            # 轮次耗尽导致最后一条仍是 tool_call 消息（content 为空）→ 补一次无工具请求取总结
            if not content and message.get("tool_calls"):
                final_payload = dict(payload)
                final_payload["messages"] = tool_messages
                final_payload.pop("tools", None)
                final_resp = await client.post(
                    f"{config.api_base}/chat/completions",
                    headers=headers,
                    json=final_payload,
                    timeout=60.0,
                )
                if final_resp.status_code != 200:
                    raise Exception(self._upstream_error_message(final_resp.status_code, final_resp.text))
                data = final_resp.json()
                choice = data["choices"][0]
                message = choice["message"]
                content = message.get("content") or ""

            return ChatResponse(
                id=data.get("id", ""),
                model=data.get("model", config.model_name),
                content=content,
                finish_reason=choice.get("finish_reason", "stop"),
                usage=data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
            )

# 创建全局模型服务实例
model_service = ModelService()
