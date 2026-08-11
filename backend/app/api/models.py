from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Any
from app.services.model import model_service, Message
from app.core.model_providers import PROVIDERS, PROVIDER_MAP
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

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


class FetchRemoteRequest(BaseModel):
    """上游模型拉取请求。

    - api_key: 可选，为空时按 provider_id 从 settings 读取已存 key（支持"一键拉取"）
    - api_base: 可选，为空时按 provider_id 取默认端点；若 provider_id 也缺省则视为非法
    - provider_id: 可选，用于在 api_key/api_base 为空时回退到 PROVIDERS 默认配置
    - filter_vision: 可选，为 True 时只返回多模态模型（名称含 vl/vision/ocr）
    """
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    provider_id: Optional[str] = None
    filter_vision: bool = False


class TestConnectionRequest(BaseModel):
    """连通性测试请求。

    - provider_id: provider 唯一 ID（用于回退读取存量 Key 和默认端点）
    - api_key: 可选，为空时走 _get_api_key 三层回退读取系统存量 Key
    - api_base: 可选，为空时按 provider_id 取默认端点
    - model_id: 可选，指定测试用的具体模型（用于 max_tokens=1 对话测试）
    """
    provider_id: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model_id: Optional[str] = None

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
    supports_vision: bool = False

class CustomModelUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    enabled: Optional[bool] = None
    supports_vision: Optional[bool] = None


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
            "api_key_masked": api_key,
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
    加固规则：当 api_key 被显式置空（清除 Key）时，连带清理 api_base 覆盖、
    以及该 provider 下所有自定义模型（enabled_models），避免脏数据残留。
    """
    p = PROVIDER_MAP.get(body.provider_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"未知 provider: {body.provider_id}")

    # 判定是否为"清除 Key"动作：api_key 显式传入且为空字符串
    is_clearing_key = body.api_key is not None and not body.api_key.strip()

    if body.api_key is not None:
        _set_setting(f"api_key_{p.id}", body.api_key.strip())
    if body.api_base is not None:
        _set_setting(f"api_base_{p.id}", body.api_base.strip())

    # 清除 Key 时同步抹除关联数据
    if is_clearing_key:
        _purge_provider_associated(p.id)

    model_service.reload_models()
    return {"status": "updated", "provider": p.id, "purged": is_clearing_key}


def _purge_provider_associated(provider_id: str) -> int:
    """彻底清除 provider 关联数据：api_base 覆盖 + 候选池同步的自定义模型。

    2026-08-11 收窄：仅删 source='sync' 行（其 Key 从 provider 复制，删除无损）；
    source='manual' 行持有用户自配 Key，不连坐（旧版无差别删除会误伤手动接入）。

    Args:
        provider_id: provider 唯一 ID

    Returns:
        被清理的同步自定义模型条数
    """
    # 1. 清除 api_base_<provider> 覆盖（恢复默认端点）
    _set_setting(f"api_base_{provider_id}", "")

    # 2. 清除该 provider 下所有 source='sync' 的自定义模型（enabled_models 的实际载体）
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel
    db = SessionLocal()
    try:
        rows = db.query(CustomModel).filter(CustomModel.provider == provider_id).all()
        count = 0
        for r in rows:
            if getattr(r, "source", "manual") == "sync":
                db.delete(r)
                count += 1
        db.commit()
        if count:
            logger.info("Purged %d sync custom models for provider=%s during key clear", count, provider_id)
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ──── 上下文窗口名称推测（G6-B）────

# 上下文窗口推测关键词 → 默认值映射
_CONTEXT_WINDOW_HEURISTICS: list[tuple[list[str], int]] = [
    # 显式数字标记优先（如 "128k", "1m", "32k"）
    # 由 _extract_numeric_context_window 处理，此处仅做关键词兜底
    (["deepseek", "v4"], 1_048_576),
    (["deepseek", "v3"], 1_048_576),
    (["deepseek", "r1"], 131_072),
    (["gemini", "3."], 1_048_576),
    (["gemini", "2."], 1_048_576),
    (["gemini"], 1_048_576),
    (["qwen", "vl"], 131_072),
    (["qwen", "max"], 32_768),
    (["qwen", "flash"], 131_072),
    (["qwen", "plus"], 131_072),
    (["qwen", "coder"], 131_072),
    (["qwen", "turbo"], 131_072),
    (["qwen", "3"], 131_072),
    (["qwen"], 131_072),
    (["glm", "z1"], 1_048_576),
    (["glm", "4"], 128_000),
    (["glm"], 128_000),
    (["gpt-4"], 128_000),
    (["gpt-3.5"], 16_385),
    (["claude", "3.5"], 200_000),
    (["claude", "3"], 200_000),
    (["claude"], 200_000),
    (["llama", "70b"], 131_072),
    (["llama", "405b"], 131_072),
    (["llama", "8b"], 131_072),
    (["llama"], 131_072),
    (["mixtral"], 32_768),
    (["mistral"], 32_768),
    (["moonshot"], 8_192),
    (["ernie"], 8_192),
    (["minimax"], 256_000),
    (["spark"], 8_192),
]


def _extract_numeric_context_window(model_id: str) -> int | None:
    """从模型名中提取显式数字标记（如 128k、1m、32k）。"""
    import re
    m = re.search(r'(\d+)\s*([km])', model_id.lower())
    if m:
        num = int(m.group(1))
        unit = m.group(2).lower()
        if unit == 'm':
            return num * 1_000_000
        else:
            return num * 1_024
    return None


def _guess_context_window(model_id: str) -> int | None:
    """根据模型名推测上下文窗口大小（token 数）。

    优先级：
      1. 显式数字标记（如 "128k"、"1m"）→ 直接解析
      2. 关键词匹配（如 deepseek-v4 → 1M）→ 查表
      3. 无匹配 → 返回 None（调用方降级到默认值）

    返回 None 表示无法推测，应由调用方使用默认值。
    """
    # 1. 显式数字标记
    numeric = _extract_numeric_context_window(model_id)
    if numeric is not None:
        return numeric

    # 2. 关键词匹配（取首个命中，按注册顺序优先级递减）
    mid_lower = model_id.lower()
    for keywords, size in _CONTEXT_WINDOW_HEURISTICS:
        if all(kw in mid_lower for kw in keywords):
            return size

    return None


def _extract_context_window_from_api(item: dict) -> int | None:
    """尝试从 API 返回的模型对象中提取上下文窗口信息。

    检测字段（按优先级）：
      - max_context_length
      - context_window
      - max_tokens（注意：许多 API 此字段指 max_output_tokens，不可靠）
      - max_input_tokens
      - max_model_len
    """
    for field in ("max_context_length", "context_window", "max_input_tokens", "max_model_len"):
        val = item.get(field)
        if isinstance(val, (int, float)) and val > 0:
            return int(val)
    return None


@router.post("/fetch_remote")
async def fetch_remote_models(body: FetchRemoteRequest):
    """拉取上游服务商的官方模型列表（OpenAI 兼容 /models 端点）。

    严格防阻塞熔断：
      - 固定 5 秒超时，超时立即返回 400
      - Key 无效（401/403）→ 400 友好提示
      - 解析失败 / 网络异常 → 400 友好提示
      - 绝不卡死后端线程

    Returns:
        {"models": [{"id": "model-id-1", "context_window": 131072}, ...]}

    context_window 获取优先级：
      1. API 响应中的元数据字段（max_context_length / context_window / max_input_tokens）
      2. 模型名推测（数字标记 + 关键词匹配）
      3. null（前端/调用方降级到默认值 256K）
    """
    import httpx

    # ── 解析 api_key：优先请求体，回退 settings 已存 key（支持"一键拉取"无需重复输入）──
    api_key = (body.api_key or "").strip()
    if not api_key and body.provider_id:
        api_key = _get_setting(f"api_key_{body.provider_id}")
    if not api_key:
        raise HTTPException(status_code=400, detail="缺少 API Key，请先配置该服务商的 Key")

    # 解析目标端点：优先用 body.api_base，为空则按 provider_id 取默认值
    api_base = (body.api_base or "").strip()
    if not api_base:
        if not body.provider_id:
            raise HTTPException(status_code=400, detail="api_base 和 provider_id 不能同时为空")
        p = PROVIDER_MAP.get(body.provider_id)
        if not p:
            raise HTTPException(status_code=400, detail=f"未知 provider: {body.provider_id}")
        api_base = _get_setting(f"api_base_{body.provider_id}") or p.default_api_base

    # 规范化：去除尾部斜杠，拼接 /models
    api_base = api_base.rstrip("/")
    target_url = f"{api_base}/models"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(
                target_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )

        # 鉴权失败 / 上游错误 → 友好 400
        if resp.status_code in (401, 403):
            raise HTTPException(
                status_code=400,
                detail=f"API Key 无效或鉴权失败（上游返回 {resp.status_code}），请检查 Key 是否正确",
            )
        if resp.status_code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"上游端点不存在（404）：{target_url}，请检查 API Base 是否正确",
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=400,
                detail=f"上游服务异常（HTTP {resp.status_code}），请稍后重试或检查 API Base",
            )

        # 解析 JSON
        try:
            payload = resp.json()
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="上游返回非 JSON 数据，无法解析模型列表，请确认 API Base 为 OpenAI 兼容端点",
            )

        # 提取 data 数组（兼容多种返回结构）
        data_list = []
        if isinstance(payload, dict):
            data_list = payload.get("data") or []
        elif isinstance(payload, list):
            data_list = payload
        else:
            raise HTTPException(status_code=400, detail="上游返回数据结构异常，未找到 data 数组")

        # 解析为模型元数据列表
        raw_models: list[dict] = []
        for item in data_list:
            if isinstance(item, dict):
                mid = item.get("id")
                if isinstance(mid, str) and mid.strip():
                    raw_models.append({"id": mid.strip(), "_raw": item})
            elif isinstance(item, str) and item.strip():
                raw_models.append({"id": item.strip(), "_raw": {}})

        if not raw_models:
            raise HTTPException(
                status_code=400,
                detail="上游返回的模型列表为空，请确认该账号下已开通模型权限",
            )

        # 去重保序（按 id）
        seen = set()
        deduped_raw = []
        for m in raw_models:
            mid = m["id"]
            if mid not in seen:
                seen.add(mid)
                deduped_raw.append(m)

        # filter_vision：只保留多模态模型（名称含 vl / vision / ocr）
        if body.filter_vision:
            deduped_raw = [
                m for m in deduped_raw
                if any(kw in m["id"].lower() for kw in ("vl", "vision", "ocr"))
            ]
            if not deduped_raw:
                raise HTTPException(
                    status_code=400,
                    detail="未找到任何多模态模型（vl/vision/ocr），请确认该服务商是否支持识图模型",
                )

        # 构建响应：为每个模型附加 context_window
        result_models = []
        for m in deduped_raw:
            mid = m["id"]
            raw = m["_raw"]

            # 1. 尝试从 API 响应提取
            cw = _extract_context_window_from_api(raw)

            # 2. 名称推测
            if cw is None:
                cw = _guess_context_window(mid)

            result_models.append({
                "id": mid,
                "context_window": cw,  # None 表示无法推测，前端降级到默认值
            })

        return {"models": result_models}

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=400,
            detail="拉取模型列表超时（5秒），请检查 API Base 是否正确或网络环境是否通畅",
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=400,
            detail=f"无法连接到上游服务：{target_url}，请检查 API Base 或网络代理设置",
        )
    except httpx.HTTPError as e:
        logger.warning("fetch_remote httpx error: %s", e)
        raise HTTPException(
            status_code=400,
            detail=f"请求上游服务失败：{type(e).__name__}",
        )
    except Exception as e:
        logger.exception("fetch_remote unexpected error")
        raise HTTPException(
            status_code=400,
            detail=f"拉取模型列表失败：{type(e).__name__}: {str(e)[:100]}",
        )


@router.post("/test-connection")
async def test_connection(body: TestConnectionRequest):
    """测试 provider 的网络连通性与 Key 有效性。

    策略（轻量级探测）：
      1. 优先 GET {api_base}/models —— 最轻量，不消耗 token
      2. 若 /models 返回 404（部分服务商不支持该端点），回退 POST /chat/completions max_tokens=1

    防阻塞熔断：
      - 严格 5 秒超时
      - 超时 / 连接失败 / Key 无效 → 返回 200 + {ok:false, detail}（不抛 400，便于前端统一展示）
      - 成功 → 返回 200 + {ok:true, latency_ms, detail}

    Key 解析：api_key 为空时走 Adapter 三层回退（settings 表 > .env）
    """
    import httpx
    import time as _time

    p = PROVIDER_MAP.get(body.provider_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"未知 provider: {body.provider_id}")

    # 解析 Key：前端传值优先，否则走 Adapter 三层回退
    from app.core.model_adapter import adapter
    api_key = (body.api_key or "").strip()
    if not api_key:
        api_key = adapter.resolve_api_key(p)
    if not api_key:
        return {
            "ok": False,
            "latency_ms": 0,
            "detail": f"provider {body.provider_id} 未配置 API Key，无法测试连通性",
        }

    # 解析 Base：前端传值优先，否则走 Adapter
    api_base = (body.api_base or "").strip()
    if not api_base:
        api_base = adapter.resolve_api_base(p)
    api_base = api_base.rstrip("/")

    # 解析测试用 model_id：前端传值优先，否则取 provider 首个模型
    test_model = body.model_id
    if not test_model:
        if p.models:
            test_model = p.models[0].upstream
        else:
            return {
                "ok": False,
                "latency_ms": 0,
                "detail": f"provider {body.provider_id} 无可用模型用于测试",
            }

    t0 = _time.perf_counter()

    # ── 策略 1：GET /models（最轻量）──
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(
                f"{api_base}/models",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
        latency_ms = int((_time.perf_counter() - t0) * 1000)

        if resp.status_code == 200:
            return {
                "ok": True,
                "latency_ms": latency_ms,
                "detail": f"连通性正常（GET /models 200，{latency_ms}ms）",
                "method": "models",
            }
        # 404 → 该服务商不支持 /models 端点，回退策略 2
        if resp.status_code != 404:
            # 401/403 → Key 无效
            if resp.status_code in (401, 403):
                return {
                    "ok": False,
                    "latency_ms": latency_ms,
                    "detail": f"API Key 无效或鉴权失败（HTTP {resp.status_code}）",
                }
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "detail": f"上游返回异常状态码 HTTP {resp.status_code}",
            }
    except httpx.TimeoutException:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"连通性测试超时（5秒），请检查 API Base 或网络环境",
        }
    except httpx.ConnectError:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"无法连接到 {api_base}，请检查 API Base 或网络代理",
        }
    except httpx.HTTPError as e:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"请求失败：{type(e).__name__}",
        }

    # ── 策略 2：POST /chat/completions max_tokens=1（/models 不可用时回退）──
    t0 = _time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": test_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "stream": False,
                },
            )
        latency_ms = int((_time.perf_counter() - t0) * 1000)

        if resp.status_code == 200:
            return {
                "ok": True,
                "latency_ms": latency_ms,
                "detail": f"连通性正常（chat/completions 200，{latency_ms}ms，model={test_model}）",
                "method": "chat",
            }
        if resp.status_code in (401, 403):
            return {
                "ok": False,
                "latency_ms": latency_ms,
                "detail": f"API Key 无效或鉴权失败（HTTP {resp.status_code}）",
            }
        # 提取上游错误信息
        err_msg = ""
        try:
            err_data = resp.json()
            err_msg = err_data.get("error", {}).get("message", "")[:200]
        except Exception:
            pass
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"上游返回 HTTP {resp.status_code}{'：' + err_msg if err_msg else ''}",
        }
    except httpx.TimeoutException:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"连通性测试超时（5秒），请检查 API Base 或网络环境",
        }
    except httpx.ConnectError:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"无法连接到 {api_base}，请检查 API Base 或网络代理",
        }
    except httpx.HTTPError as e:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"请求失败：{type(e).__name__}",
        }
    except Exception as e:
        latency_ms = int((_time.perf_counter() - t0) * 1000)
        logger.warning("test-connection unexpected error: %s", e)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "detail": f"测试失败：{type(e).__name__}: {str(e)[:100]}",
        }


@router.get("/custom")
async def list_custom_models():
    """获取所有自定义模型（含 source 字段：sync=候选池自动同步 / manual=手动创建）"""
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
            "api_key_masked": r.api_key,
            "has_key": bool(r.api_key),
            "max_tokens": r.max_tokens,
            "temperature": r.temperature,
            "enabled": r.enabled,
            "supports_vision": bool(r.supports_vision),
            "source": getattr(r, "source", None) or "manual",
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
            supports_vision=body.supports_vision,
            source="manual",  # 2026-08-11：用户手动创建的第三方接入，sync 逻辑绝不触碰
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
