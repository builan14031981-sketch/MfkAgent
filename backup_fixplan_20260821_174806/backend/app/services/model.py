from typing import List, Optional, Dict, Any, AsyncIterator, Union
from pydantic import BaseModel
from enum import Enum
import httpx
import json
import os
import base64
import logging
import time
import asyncio
from app.core.config import settings
import app.core.model_providers as _mp
from app.core.tool_runtime.normalizer import normalize_tool_call_text

logger = logging.getLogger(__name__)

# 证据化/健壮性：单次 LLM 调用硬超时（秒）。防止模型 API 挂死导致 run 永久卡在 running。
# 可通过环境变量 MFK_MODEL_CALL_TIMEOUT 覆盖。
_MODEL_CALL_TIMEOUT = float(os.environ.get("MFK_MODEL_CALL_TIMEOUT", "300"))

class ModelProvider(str, Enum):
    MIMO = "mimo"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    GLM = "glm"
    WENXIN = "wenxin"
    SPARK = "spark"
    MOONSHOT = "moonshot"
    MINIMAX = "minimax"
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
    context_window: int = 200000  # 上下文窗口大小（token），默认200K
    priority: int = 0  # 0 = 主力模型（可用），1 = 备用模型（可能不可用）
    supports_vision: bool = False   # 动态能力：是否支持多模态图片
    supports_tools: bool = True     # 动态能力：是否支持函数调用（Tool Calling）


class ModelNotFoundError(Exception):
    """LLM 服务商返回 404 / Model Not Found / Invalid Model 时抛出。

    携带用户友好的错误提示，避免原始异常卡死 Agent 状态。
    """
    pass


class ModelConfigError(Exception):
    """模型配置错误（无 Key / 模型未注册等）专项异常。

    与 ModelNotFoundError 平级，agent.py 应专项捕获并跳过反思自愈
    （反思用同一无 Key 模型也会失败，无意义）。
    """
    pass

class Message(BaseModel):
    role: str
    # Phase 2: content 支持纯文本(str)或多模态数组(List[dict]，OpenAI Vision 格式)
    # 兼容：现有 str 赋值不受影响；多模态时为 [{type:"text",text:...},{type:"image_url",image_url:{url:...}}]
    content: Union[str, List[dict]]

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


# ──────────────────────────────────────────────────────────────────────────
# Phase 2: 多模态视觉上下文注入
# ──────────────────────────────────────────────────────────────────────────

# 图片附件最大读取字节数（10MB，防 base64 编码后撑爆请求体）
_MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _image_to_data_uri(file_path: str, mime: str) -> Optional[str]:
    """将本地图片文件读取为 base64 data URI（OpenAI Vision image_url 格式）。

    返回形如 "data:image/png;base64,iVBOR..." 的字符串；读取失败返回 None。
    """
    try:
        size = os.path.getsize(file_path)
        if size > _MAX_IMAGE_BYTES:
            return None
        with open(file_path, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except OSError:
        return None


def _inject_vision_into_messages(
    messages: list,
    vision_context: Optional[dict],
    provider_supports_vision: bool,
) -> list:
    """将 vision_context 中的图片注入到最后一条 user 消息的 content。

    - 若 provider 不支持 vision 或 vision_context 为空：原样返回（不改动）
    - 若最后一条 user 消息 content 为 str：转为 [{type:"text",...},{type:"image_url",...}]
    - 若 content 已是 list：追加 image_url 项
    - 图片文件读取失败（不存在/过大）：跳过该图，不中断

    返回新的 messages 列表（深拷贝，不修改原列表）。
    """
    if not vision_context or not provider_supports_vision:
        return messages

    images = vision_context.get("images") or []
    if not images:
        return messages

    # 构建 image_url content 项
    image_parts = []
    for img in images:
        file_path = img.get("path")
        mime = img.get("mime", "image/png")
        if not file_path or not os.path.isfile(file_path):
            continue
        data_uri = _image_to_data_uri(file_path, mime)
        if data_uri:
            image_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

    if not image_parts:
        return messages  # 无可用图片，不改动

    # 深拷贝 messages，找到最后一条 user 消息并注入
    work = [dict(m) for m in messages]
    for i in range(len(work) - 1, -1, -1):
        if work[i].get("role") == "user":
            content = work[i].get("content")
            if isinstance(content, str):
                # str → 多模态数组：文本 + 图片
                work[i]["content"] = [{"type": "text", "text": content}] + image_parts
            elif isinstance(content, list):
                # 已是多模态：追加图片
                work[i]["content"] = list(content) + image_parts
            # content 为其他类型：不改（防御性）
            break

    return work


def _provider_supports_vision(provider_value: str) -> bool:
    """查询 provider 是否支持多模态图片（provider 级别粗判）。"""
    provider_def = _mp.PROVIDER_MAP.get(provider_value)
    return bool(provider_def and provider_def.supports_vision)


def _detect_supports_vision(model_name: str, provider_vision: bool, model_vision: Optional[bool] = None) -> bool:
    """动态能力检测：三级优先级。
    
    1. 模型级显式指定（非 None）→ 直接使用
    2. 命名推测（含 vl/vision）→ True
    3. 回退 provider 级配置
    """
    if model_vision is not None:
        return model_vision
    name_lower = (model_name or "").lower()
    if "vl" in name_lower or "vision" in name_lower:
        return True
    return provider_vision


# ──────────────────────────────────────────────────────────────────────────
# Phase 3: Vision Auto-Routing — 智能路由 + 熔断兜底
# ──────────────────────────────────────────────────────────────────────────

# Vision Fallback 默认 API Base（未配置 vision_base_url 时使用）
_VISION_FALLBACK_DEFAULT_BASE = "https://api.siliconflow.cn/v1"

# Vision Fallback 提示词：要求详细描述图片内容
_VISION_FALLBACK_PROMPT = (
    "请详细描述这张图片的内容，包括其中的文字、物体、场景、人物、颜色、布局等所有可见信息。请用中文描述。"
)

# Vision Fallback 单图最大 token 数
_VISION_FALLBACK_MAX_TOKENS = 1024

# Vision Fallback 超时（秒）
_VISION_FALLBACK_TIMEOUT = 30.0


async def _vision_fallback_extract(vision_context: dict) -> str:
    """使用备用识图模型解析图片，返回文本描述（Phase 3 熔断兜底）。

    从 settings 表读取 vision_fallback 配置，调用备用 Vision 模型解析图片，
    返回图片文本描述。全程包裹 try-except，任何异常均返回友好提示，绝不崩溃。

    Returns:
        解析后的文本描述，或错误提示信息（以 [图片解析...] 包装）。
    """
    from app.core.database import SessionLocal
    from app.models.agent import Setting

    # ── 读取 vision_fallback 配置 ──
    db = SessionLocal()
    try:
        vision_provider = (
            db.query(Setting).filter(Setting.key == "vision_provider").first()
        )
        vision_api_key = (
            db.query(Setting).filter(Setting.key == "vision_api_key").first()
        )
        vision_model = (
            db.query(Setting).filter(Setting.key == "vision_model").first()
        )
        vision_base_url = (
            db.query(Setting).filter(Setting.key == "vision_base_url").first()
        )
        vp = vision_provider.value if vision_provider else ""
        vak = vision_api_key.value if vision_api_key else ""
        vm = vision_model.value if vision_model else ""
        vbu = vision_base_url.value if vision_base_url else ""
    finally:
        db.close()

    # ── 未配置：返回友好提示 ──
    if not vak or not vm:
        return (
            "[图片解析提示] 当前主模型不支持识图，"
            "请在设置中配置备用识图模型（vision_provider + vision_api_key + vision_model）。"
        )

    # ── 检查备用识图 provider 是否被禁用 ──
    if vp in model_service._disabled_providers:
        return "[图片解析失败: 备用识图 Provider 已被禁用，请在设置中开启]"

    # ── 解析 API Base URL ──
    if not vbu:
        provider_def = _mp.PROVIDER_MAP.get(vp)
        if provider_def:
            vbu = provider_def.default_api_base
        else:
            vbu = _VISION_FALLBACK_DEFAULT_BASE

    # ── 提取图片并编码 ──
    images = vision_context.get("images") or []
    if not images:
        return ""

    image_parts = []
    for img in images:
        file_path = img.get("path")
        mime = img.get("mime", "image/png")
        if not file_path or not os.path.isfile(file_path):
            continue
        data_uri = _image_to_data_uri(file_path, mime)
        if data_uri:
            image_parts.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
            })

    if not image_parts:
        return "[图片解析失败: 无法读取图片文件]"

    # ── 调用备用 Vision 模型（熔断兜底）──
    _llm_start = time.perf_counter()
    try:
        from app.core.proxy import build_llm_client

        async with build_llm_client(vbu, timeout=_VISION_FALLBACK_TIMEOUT) as client:
            response = await client.post(
                f"{vbu}/chat/completions",
                headers={
                    "Authorization": f"Bearer {vak}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": vm,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": _VISION_FALLBACK_PROMPT},
                                *image_parts,
                            ],
                        }
                    ],
                    "max_tokens": _VISION_FALLBACK_MAX_TOKENS,
                    "temperature": 0.3,
                },
            )

            if response.status_code != 200:
                _llm_duration_ms = int((time.perf_counter() - _llm_start) * 1000)
                logger.info(
                    "LLM request finished:\nprovider=%s\nmodel=%s\nduration_ms=%d\nsuccess=%s",
                    vp or "unknown", vm or "unknown", _llm_duration_ms, False,
                )
                # 提取上游错误信息
                error_detail = ""
                try:
                    error_data = response.json()
                    error_detail = error_data.get("error", {}).get("message", "")
                except Exception:
                    pass
                if not error_detail:
                    error_detail = response.text[:200]
                logger.warning(
                    "Phase3 vision fallback: API error status=%s detail=%s",
                    response.status_code, error_detail,
                )
                # 检查是否为 Model Not Found
                if response.status_code == 404 or (
                    response.status_code in (400, 422) and any(
                        kw in (error_detail or "").lower()
                        for kw in ("model not found", "invalid model", "does not exist", "unknown model", "no such model", "model disabled")
                    )
                ):
                    return f"[图片解析失败: 备用识图模型 {vm} 不可用（{response.status_code}），请更换为可用模型：{error_detail[:150]}]"
                return f"[图片解析失败: 备用识图 API 返回错误（{response.status_code}）：{error_detail[:150]}]"

            data = response.json()
            _llm_duration_ms = int((time.perf_counter() - _llm_start) * 1000)
            logger.info(
                "LLM request finished:\nprovider=%s\nmodel=%s\nduration_ms=%d\nsuccess=%s",
                vp or "unknown", vm or "unknown", _llm_duration_ms, True,
            )
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                logger.warning("Phase3 vision fallback: empty content from vision model")
                return "[图片解析失败: 备用模型返回空内容]"

            logger.info(
                "Phase3 vision fallback: extracted %d chars from %d images",
                len(content), len(image_parts),
            )
            return content

    except httpx.TimeoutException:
        logger.warning("Phase3 vision fallback: timeout after %.1fs", _VISION_FALLBACK_TIMEOUT)
        return "[图片解析失败: 备用识图 API 超时，请检查网络或 API 配置]"
    except Exception as e:
        logger.warning("Phase3 vision fallback: exception=%s", e)
        return f"[图片解析失败: 备用识图 API 调用异常：{str(e)[:150]}]"


def _inject_fallback_text_into_messages(messages: list, fallback_text: str) -> list:
    """将 Vision Fallback 解析文本注入到最后一条 user 消息的 content。

    - 若 content 为 str：追加 "\n\n[图片解析文本说明]\n<text>"
    - 若 content 为 list：追加 type:"text" 项
    - 若找不到 user 消息：在末尾追加一条 user 消息

    返回新的 messages 列表（深拷贝，不修改原列表）。
    """
    if not fallback_text:
        return messages

    work = [dict(m) for m in messages]
    injected = f"\n\n[图片解析文本说明]\n{fallback_text}"

    for i in range(len(work) - 1, -1, -1):
        if work[i].get("role") == "user":
            content = work[i].get("content")
            if isinstance(content, str):
                work[i]["content"] = content + injected
            elif isinstance(content, list):
                work[i]["content"] = list(content) + [{"type": "text", "text": injected}]
            # content 为其他类型：不改（防御性）
            return work

    # 找不到 user 消息：追加一条
    work.append({"role": "user", "content": injected.lstrip()})
    return work


class ModelService:
    def __init__(self):
        # 防腐层：委托 Adapter 读取三层存储（.env / settings 表 / models 表），
        # 未来迁移到统一 schema 时只需替换 Adapter，ModelService 无需改动。
        from app.core.model_adapter import adapter as _adapter
        self._adapter = _adapter
        self.models = self._init_models()
        # 被禁用的 Provider 集合（来自 settings.provider_disabled，JSON {id: true}）
        # reload_models 时同步刷新，get_available_models 过滤、call_once/stream_once 校验
        self._disabled_providers: set = self._load_disabled_providers()

    def _load_disabled_providers(self) -> set:
        """从 settings 表读取 provider_disabled，返回被禁用的 provider id 集合。

        格式：settings.provider_disabled = '{"deepseek": true, "qwen": true}'
        容错：JSON 解析失败或值非 dict 时返回空集合（不影响模型加载主流程）。
        """
        import json
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == "provider_disabled").first()
            if not row or not row.value:
                return set()
            try:
                data = json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                return set()
            if not isinstance(data, dict):
                return set()
            # 只收集 value 为 truthy 的 key
            return {pid for pid, v in data.items() if v}
        finally:
            db.close()

    @staticmethod
    def _check_model_not_found(status_code: int, raw, model_name: str):
        """检测 404 / Model Not Found / Invalid Model，抛出 ModelNotFoundError。

        某些服务商返回 400+错误体而非 404，因此也检查错误文本关键词。
        raw 兼容 str 与 bytes（stream_once 的 response.aread() 返回 bytes）。
        """
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if status_code == 404:
            raise ModelNotFoundError(
                f"服务商未找到模型 [{model_name}]，请在设置中检查 Model ID 是否正确。"
            )
        text_lower = (raw or "").lower()
        if status_code in (400, 422) and any(
            kw in text_lower
            for kw in ("model not found", "invalid model", "does not exist", "unknown model", "no such model")
        ):
            raise ModelNotFoundError(
                f"服务商未找到模型 [{model_name}]，请在设置中检查 Model ID 是否正确。"
            )

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
        """读取 provider 的有效 API Key（委托 Adapter）。

        优先级：settings 表 api_key_{id} > .env 的 {PROVIDER}_API_KEY
        保留原签名以兼容内部调用。
        """
        provider_id = setting_key.replace("api_key_", "")
        provider_def = _mp.PROVIDER_MAP.get(provider_id)
        if provider_def is None:
            return env_key
        return self._adapter.resolve_api_key(provider_def)

    def _get_api_base(self, env_base: str, provider_id: str) -> str:
        """读取 api_base_<provider> 覆盖（委托 Adapter）。

        未配置时用 provider 默认端点。保留原签名以兼容内部调用。
        """
        provider_def = _mp.PROVIDER_MAP.get(provider_id)
        if provider_def is None:
            return env_base
        return self._adapter.resolve_api_base(provider_def)

    @staticmethod
    def _provider_enum(provider_id: str) -> ModelProvider:
        """将 provider id 字符串映射为 ModelProvider 枚举；未知值回落为通用 OpenAI 兼容。"""
        try:
            return ModelProvider(provider_id)
        except ValueError:
            return ModelProvider.OPENAI

    def _custom_models(self):
        """读取 models 表中已启用的自定义模型（委托 Adapter）。"""
        return self._adapter._custom_models()

    def _init_models(self) -> Dict[str, ModelConfig]:
        """初始化所有模型配置：内置 Provider 注册表 + models 表自定义模型合并。

        委托 ModelConfigAdapter.resolve_all() 完成三层优先级合并：
          1. 内置 _mp.PROVIDERS（.env Key + settings 表覆盖）
          2. CustomModel 表（enabled=True）覆盖同名 model_id

        同名 model_id 时自定义模型覆盖内置（便于用户替换默认端点/模型名）。
        动态能力检测：supports_vision 按模型名启发式 + provider 级回退；
        supports_tools 默认 True（OpenAI 兼容协议标配）。
        """
        return self._adapter.resolve_all()

    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取所有可用模型列表（按优先级排序：主力模型在前，备用模型在后）。

        被禁用的 Provider（self._disabled_providers）其模型不在此列表中，
        从而 /api/models 不返回，前端所有模型消费点自动一致。
        """
        models = []
        for model_id, config in self.models.items():
            # 跳过被禁用的 Provider（强禁用：UI 选不到 + API 直调会被 call_once 拦截）
            if config.provider.value in self._disabled_providers:
                continue
            if config.api_key:
                # 查找 display_name（优先用 ProviderModel 中定义的展示名）
                display_name = model_id
                provider_def = _mp.PROVIDER_MAP.get(config.provider.value)
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
        """获取模型配置，未找到时尝试一次 reload 兜底。

        惰性 reload 场景：用户通过 models API 添加自定义模型后，
        reload_models() 通常已被调用；但若因并发/时序问题未触发，
        此处兜底 reload 一次，确保自定义模型可被平滑发现。
        """
        config = self.models.get(model_id)
        if config is None:
            self.reload_models()
            config = self.models.get(model_id)
        return config

    def _resolve_api_model_name(self, config: ModelConfig) -> str:
        """将内部模型 ID 转换为官方 API 使用的模型名。

        DeepSeek V4-Flash / V4-Pro 即为官方 API 模型名（deepseek-chat / deepseek-reasoner 旧名已于 2026-07 停用），
        直接透传 config.model_name，不做任何映射。
        """
        return config.model_name

    def _apply_reasoning_payload(self, payload: dict, config: ModelConfig, reasoning_effort: str) -> None:
        """按 provider 官方规范设置思考/推理参数 — Phase 12 统一档位映射。

        档位语义（前端三档：none / high / max）：
          - none：显式关闭思考。优先发送官方关闭字段；若 provider 不支持关闭字段，
                  则剥离所有推理参数，依赖模型默认（通常为非推理模式）。
          - high：开启思考，官方标准档
          - max：开启思考，官方最高档

        Provider 映射表：
          ┌───────────────┬──────────────────────────────────────────────────────┐
          │ Provider      │ API 字段                                              │
          ├───────────────┼──────────────────────────────────────────────────────┤
          │ DEEPSEEK      │ thinking: {type: enabled|disabled} + reasoning_effort │
          │ SILICONFLOW   │ 同 DeepSeek（兼容 OpenAI 扩展）                        │
          │ GLM           │ thinking: {type: enabled|disabled} + reasoning_effort │
          │ QWEN          │ enable_thinking: bool（无强度档位）                     │
          │ OPENAI        │ reasoning_effort: low|medium|high（通用 OpenAI 兼容）   │
          │ 其他          │ 不发送推理参数（非推理 provider）                        │
          └───────────────┴──────────────────────────────────────────────────────┘
        """
        if not reasoning_effort:
            return

        provider = config.provider
        model_name = config.model_name
        effort = reasoning_effort if reasoning_effort in ("high", "max") else "high"

        # ── DeepSeek 官方 API ──
        if provider == ModelProvider.DEEPSEEK:
            if reasoning_effort == "none":
                payload["thinking"] = {"type": "disabled"}
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=none → thinking.type=disabled",
                    provider.value, model_name,
                )
            else:
                payload["thinking"] = {"type": "enabled", "reasoning_effort": effort}
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=%s → thinking.type=enabled reasoning_effort=%s",
                    provider.value, model_name, reasoning_effort, effort,
                )

        # ── SiliconFlow（聚合网关，兼容 OpenAI 扩展）──
        elif provider == ModelProvider.SILICONFLOW:
            if reasoning_effort == "none":
                # SiliconFlow 可能不完全支持 thinking 字段；发送 disabled 优先，
                # 若上游忽略则依赖模型默认行为（通常为非推理模式）
                payload["thinking"] = {"type": "disabled"}
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=none → thinking.type=disabled "
                    "(SiliconFlow 兼容模式，若上游忽略则依赖模型默认)",
                    provider.value, model_name,
                )
            else:
                payload["thinking"] = {"type": "enabled", "reasoning_effort": effort}
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=%s → thinking.type=enabled reasoning_effort=%s",
                    provider.value, model_name, reasoning_effort, effort,
                )

        # ── 智谱 GLM ──
        elif provider == ModelProvider.GLM:
            if reasoning_effort == "none":
                payload["thinking"] = {"type": "disabled"}
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=none → thinking.type=disabled",
                    provider.value, model_name,
                )
            else:
                payload["thinking"] = {"type": "enabled"}
                payload["reasoning_effort"] = effort
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=%s → thinking.type=enabled reasoning_effort=%s",
                    provider.value, model_name, reasoning_effort, effort,
                )

        # ── 通义千问 QWEN ──
        elif provider == ModelProvider.QWEN:
            if reasoning_effort == "none":
                payload["enable_thinking"] = False
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=none → enable_thinking=False",
                    provider.value, model_name,
                )
            else:
                payload["enable_thinking"] = True
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=%s → enable_thinking=True",
                    provider.value, model_name, reasoning_effort,
                )

        # ── 通用 OpenAI 兼容端点（自定义模型 / OPENAI provider）──
        elif provider == ModelProvider.OPENAI:
            if reasoning_effort == "none":
                # 剥离 reasoning_effort，不发送任何推理参数
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=none → 剥离推理参数，不发送 reasoning 字段",
                    provider.value, model_name,
                )
            else:
                payload["reasoning_effort"] = effort
                logger.info(
                    "Phase12 reasoning: provider=%s model=%s effort=%s → reasoning_effort=%s",
                    provider.value, model_name, reasoning_effort, effort,
                )

        # ── 其他 Provider（MIMO / MOONSHOT / WENXIN / SPARK / MINIMAX / FREELLMAPI / GOOGLE）──
        else:
            # 这些 provider 不支持推理参数，reasoning_effort 配置无效
            # 不发送任何推理字段，避免 API 400 错误
            logger.info(
                "Phase12 reasoning: provider=%s model=%s effort=%s → provider 不支持推理参数，跳过",
                provider.value, model_name, reasoning_effort,
            )

    def reload_models(self):
        """重新加载模型配置（当设置更新时调用）。

        原子替换两个缓存（models + _disabled_providers），避免并发读取半状态：
        先在局部变量构造完毕，再一次性赋值给 self，保证读端要么看到旧全集要么看到新全集。
        """
        new_models = self._init_models()
        new_disabled = self._load_disabled_providers()
        self.models = new_models
        self._disabled_providers = new_disabled

    async def call_once(
        self,
        model_id: str,
        messages: list,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list = None,
        reasoning_effort: str = None,
        memory_text: str = None,
        vision_context: dict = None,
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
            vision_context: Phase 3 视觉上下文（含图片绝对路径，仅首轮注入；支持智能路由 + 熔断兜底）

        Returns:
            SingleCallResult: content / tool_calls / finish_reason / usage
        """
        config = self.get_model_config(model_id)
        if not config:
            raise ModelConfigError(f"模型 {model_id} 未注册或不存在")
        if config.provider.value in self._disabled_providers:
            raise ModelConfigError(f"Provider {config.provider.value} 已被禁用，请在设置中开启")
        if not config.api_key:
            raise ModelConfigError(f"模型 {model_id} 未配置 API Key")

        # Memory 注入（仅首轮，处理 dict 格式 messages）
        work_messages = list(messages)
        if memory_text:
            for m in work_messages:
                if isinstance(m, dict) and m.get("role") == "system":
                    m["content"] = m["content"] + "\n\n" + memory_text
                    break

        # Phase 3: Vision Auto-Routing — 智能路由 + 熔断兜底
        if vision_context:
            provider_supports = config.supports_vision
            logger.warning(
                "Phase3 vision routing: provider=%s supports_vision=%s images=%d",
                config.provider.value, provider_supports,
                len(vision_context.get("images") or []),
            )
            if provider_supports:
                # 场景 A：主模型支持 Vision → 直接注入多模态消息
                work_messages = _inject_vision_into_messages(
                    work_messages, vision_context, True
                )
            else:
                # 场景 B：主模型不支持 Vision → 备用识图模型解析 + 熔断兜底
                fallback_text = await _vision_fallback_extract(vision_context)
                logger.warning("Phase3 vision fallback result: %d chars", len(fallback_text))
                work_messages = _inject_fallback_text_into_messages(work_messages, fallback_text)

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

        # ── 模型调用耗时统计（仅日志，不改变返回结果与异常行为）──
        _llm_start = time.perf_counter()
        _llm_success = True
        _llm_error = None
        try:
            from app.core.proxy import build_llm_client

            async with build_llm_client(config.api_base, timeout=300.0) as client:
                response = await asyncio.wait_for(
                    client.post(
                        f"{config.api_base}/chat/completions",
                        headers=headers,
                        json=payload,
                    ),
                    timeout=_MODEL_CALL_TIMEOUT,
                )
                if response.status_code != 200:
                    self._check_model_not_found(response.status_code, response.text, config.model_name)
                    raise Exception(self._upstream_error_message(response.status_code, response.text))
        except Exception as _e:
            _llm_success = False
            _llm_error = _e
        finally:
            _llm_duration_ms = int((time.perf_counter() - _llm_start) * 1000)
            logger.info(
                "LLM request finished:\nprovider=%s\nmodel=%s\nduration_ms=%d\nsuccess=%s",
                config.provider.value, config.model_name, _llm_duration_ms, _llm_success,
            )
        if _llm_error is not None:
            raise _llm_error

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
        vision_context: dict = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """单次流式 LLM 调用 — Phase E1 Execution Loop 用。

        只做一次流式 API 请求，不负责工具执行 / 轮次判断 / 决策。
        工具循环由 AgentRuntime 控制。

        yield 协议（Phase 12 双轨透传，向后兼容旧版客户端）：
          {"type": "text", "content": str}                    文本增量
          {"type": "thinking", "content": str}                思考段增量（标准字段，兼容旧客户端）
          {"type": "tool_calls", "calls": [...]}              本轮结构化 tool_calls（已排序，含结果前原始参数）
          {"type": "finish", "finish_reason": str, "usage": dict}

        Args:
            model_id: 模型 ID
            messages: 消息列表（List[dict]）
            temperature: 模型温度
            max_tokens: 最大 token 数
            tools: 工具定义列表
            reasoning_effort: 推理强度
            memory_text: 记忆文本（仅首轮注入）
            vision_context: Phase 3 视觉上下文（含图片绝对路径，仅首轮注入；支持智能路由 + 熔断兜底）
        """
        config = self.get_model_config(model_id)
        if not config:
            raise ModelConfigError(f"模型 {model_id} 未注册或不存在")
        if config.provider.value in self._disabled_providers:
            raise ModelConfigError(f"Provider {config.provider.value} 已被禁用，请在设置中开启")
        if not config.api_key:
            raise ModelConfigError(f"模型 {model_id} 未配置 API Key")

        # Memory 注入（仅首轮，处理 dict 格式 messages）
        work_messages = list(messages)
        if memory_text:
            for m in work_messages:
                if isinstance(m, dict) and m.get("role") == "system":
                    m["content"] = m["content"] + "\n\n" + memory_text
                    break

        # Phase 3: Vision Auto-Routing — 智能路由 + 熔断兜底
        if vision_context:
            provider_supports = config.supports_vision
            logger.warning(
                "Phase3 vision routing: provider=%s supports_vision=%s images=%d",
                config.provider.value, provider_supports,
                len(vision_context.get("images") or []),
            )
            if provider_supports:
                # 场景 A：主模型支持 Vision → 直接注入多模态消息
                work_messages = _inject_vision_into_messages(
                    work_messages, vision_context, True
                )
            else:
                # 场景 B：主模型不支持 Vision → 备用识图模型解析 + 熔断兜底
                fallback_text = await _vision_fallback_extract(vision_context)
                logger.warning("Phase3 vision fallback result: %d chars", len(fallback_text))
                work_messages = _inject_fallback_text_into_messages(work_messages, fallback_text)

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

        # Phase 12: 推理内容统计（用于日志和验收）
        reasoning_chunk_count = 0
        reasoning_total_chars = 0
        provider_name = config.provider.value

        # ── 模型调用耗时统计（仅日志，不改变返回结果与异常行为）──
        _llm_start = time.perf_counter()
        from app.core.proxy import build_llm_client

        async with build_llm_client(config.api_base, timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{config.api_base}/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    _llm_duration_ms = int((time.perf_counter() - _llm_start) * 1000)
                    logger.info(
                        "LLM request finished:\nprovider=%s\nmodel=%s\nduration_ms=%d\nsuccess=%s",
                        provider_name, config.model_name, _llm_duration_ms, False,
                    )
                    raw_err = await response.aread()
                    self._check_model_not_found(response.status_code, raw_err, config.model_name)
                    raise Exception(self._upstream_error_message(response.status_code, raw_err))

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
                                choices = data.get("choices") or []
                                if not choices:
                                    continue
                                choice = choices[0]
                                delta = choice.get("delta") or {}
                                content = delta.get("content", "")

                                # Phase 12: 多字段兼容提取 reasoning_content
                                #   - reasoning_content：OpenAI / DeepSeek 标准字段
                                #   - reasoning_details：部分代理网关（如某些 OneAPI 部署）
                                #   - thoughts / think：少数非标准实现
                                reasoning_content = (
                                    delta.get("reasoning_content")
                                    or delta.get("reasoning_details", {}).get("text")
                                    or delta.get("thoughts")
                                    or delta.get("think")
                                    or ""
                                )

                                finish_reason = choice.get("finish_reason")
                                if finish_reason:
                                    final_finish = finish_reason

                                # 收集流式 tool_calls delta（兼容上游返回 null 的情况）
                                for tc in (delta.get("tool_calls") or []):
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
                                    if (tc.get("function") or {}).get("name"):
                                        acc["function"]["name"] = tc["function"]["name"]
                                    if (tc.get("function") or {}).get("arguments"):
                                        acc["function"]["arguments"] += tc["function"]["arguments"]

                                # 普通文本增量才透传（工具调用段不输出文本）
                                if content and not collected_tool_calls:
                                    yield {"type": "text", "content": content}
                                # Phase 12: 思考段增量独立透传 + 统计日志
                                if reasoning_content and not collected_tool_calls:
                                    reasoning_chunk_count += 1
                                    reasoning_total_chars += len(reasoning_content)
                                    yield {"type": "thinking", "content": reasoning_content}
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue

        # ── 模型调用耗时统计日志（流式请求成功完成）──
        _llm_duration_ms = int((time.perf_counter() - _llm_start) * 1000)
        logger.info(
            "LLM request finished:\nprovider=%s\nmodel=%s\nduration_ms=%d\nsuccess=%s",
            provider_name, config.model_name, _llm_duration_ms, True,
        )

        # Phase 12: 流结束时输出推理统计日志
        if reasoning_chunk_count > 0:
            logger.info(
                "Phase12 stream reasoning: provider=%s model=%s chunks=%d total_chars=%d",
                provider_name, config.model_name, reasoning_chunk_count, reasoning_total_chars,
            )

        # 本轮结束：结构化 tool_calls 汇总（有序）＋ finish（含 usage）
        if collected_tool_calls:
            ordered = [collected_tool_calls[i] for i in sorted(collected_tool_calls)]
            yield {"type": "tool_calls", "calls": ordered}
        yield {"type": "finish", "finish_reason": final_finish, "usage": final_usage}

# 创建全局模型服务实例
model_service = ModelService()
