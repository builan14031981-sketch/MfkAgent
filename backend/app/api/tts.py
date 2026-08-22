"""文字转语音 API — /api/tts

支持双引擎：
  - edge: 微软 Edge TTS（免费，需代理，流式）
  - volcengine: 火山引擎（字节跳动，国内直连，低时延，非流式）

端点：
  GET /api/tts?text=...&voice=...&rate=+0%  → 音频（audio/mpeg）
  GET /api/tts/voices                          → 当前引擎的音色列表
  GET /api/tts/volcengine/voices               → 火山引擎精选音色列表
"""
import logging
import os
import socket
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.core.edge_tts_ws import synthesize_stream
from app.core.volcengine_tts import synthesize as volcengine_synthesize, get_curated_voices

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_ENGINE = "volcengine"
DEFAULT_EDGE_VOICE = "zh-CN-YunxiNeural"
DEFAULT_VOLC_VOICE = "zh_female_cancan_mars_bigtts"
DEFAULT_RATE = "+0%"
MAX_CHARS = 2000

LOCAL_PROXY_CANDIDATES = [
    ("http", "127.0.0.1", 10808, "V2RayN 混合端口"),
    ("http", "127.0.0.1", 7890, "Clash HTTP"),
    ("http", "127.0.0.1", 7891, "Clash HTTP 备用"),
    ("http", "127.0.0.1", 10809, "V2RayN HTTP"),
]


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _detect_local_proxy() -> Optional[str]:
    for proto, host, port, desc in LOCAL_PROXY_CANDIDATES:
        if _port_open(host, port):
            url = f"{proto}://{host}:{port}"
            logger.info("[tts] 自动探测到本地代理: %s (%s)", url, desc)
            return url
    return None


def _get_proxy() -> Optional[str]:
    """获取代理：settings 配置 > 环境变量 > 本地自动探测。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting
        db = SessionLocal()
        try:
            def _get(key: str) -> str:
                row = db.query(Setting).filter(Setting.key == key).first()
                return row.value if row else ""
            mode = _get("proxy_mode") or "auto"
            if mode == "off":
                return None
            if mode == "manual":
                url = _get("proxy_url").strip()
                if url:
                    return url
            env_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
            if env_proxy:
                return env_proxy
        finally:
            db.close()
    except Exception as e:
        logger.warning("[tts] 读取代理配置失败: %s", e)
    return _detect_local_proxy()


def _get_tts_settings() -> dict:
    """从数据库读取 TTS 相关设置。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting
        db = SessionLocal()
        try:
            def _get(key: str, default: str = "") -> str:
                row = db.query(Setting).filter(Setting.key == key).first()
                return row.value if row and row.value else default
            return {
                "engine": _get("tts_engine", DEFAULT_ENGINE),
                "edge_voice": _get("tts_voice", DEFAULT_EDGE_VOICE),
                "volc_appid": _get("volcengine_appid", ""),
                "volc_token": _get("volcengine_access_token", ""),
                "volc_voice": _get("volcengine_voice", DEFAULT_VOLC_VOICE),
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning("[tts] 读取 TTS 设置失败: %s", e)
        return {
            "engine": DEFAULT_ENGINE,
            "edge_voice": DEFAULT_EDGE_VOICE,
            "volc_appid": "",
            "volc_token": "",
            "volc_voice": DEFAULT_VOLC_VOICE,
        }


@router.get("")
async def text_to_speech(
    text: str = Query(..., min_length=1, max_length=MAX_CHARS),
    voice: Optional[str] = Query(None),
    rate: str = Query(DEFAULT_RATE),
):
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    settings = _get_tts_settings()
    engine = settings["engine"]

    # 火山引擎
    if engine == "volcengine":
        appid = settings["volc_appid"]
        token = settings["volc_token"]
        volc_voice = voice or settings["volc_voice"]

        if not appid or not token:
            raise HTTPException(
                status_code=400,
                detail="火山引擎 TTS 未配置 AppID 或 Access Token，请在设置中配置"
            )

        try:
            # 语速映射：edge 的 "+0%" 格式 → 火山的 speed_ratio (0.1~2.0)
            speed_ratio = 1.0
            if rate and rate != "+0%":
                try:
                    pct = int(rate.replace("%", "").replace("+", ""))
                    speed_ratio = max(0.1, min(2.0, 1.0 + pct / 100.0))
                except ValueError:
                    pass

            audio_bytes = await volcengine_synthesize(
                text=text,
                appid=appid,
                access_token=token,
                voice_type=volc_voice,
                speed_ratio=speed_ratio,
            )
            return Response(
                content=audio_bytes,
                media_type="audio/mpeg",
                headers={
                    "Cache-Control": "no-cache",
                    "Content-Disposition": 'inline; filename="tts.mp3"',
                },
            )
        except ValueError as e:
            logger.error("[tts] 火山引擎合成失败: %s", e)
            raise HTTPException(status_code=502, detail=str(e))
        except Exception as e:
            logger.error("[tts] 火山引擎合成异常: %s", e, exc_info=True)
            raise HTTPException(status_code=502, detail=f"火山引擎 TTS 错误: {e}")

    # 微软 Edge TTS（默认兜底）
    edge_voice = voice or settings["edge_voice"]
    proxy = _get_proxy()
    if proxy:
        logger.info("[tts] edge 使用代理: %s", proxy)
    else:
        logger.warning("[tts] edge 未配置代理，直连微软服务器（国内可能失败）")

    audio_received = False

    async def audio_generator():
        nonlocal audio_received
        try:
            async for chunk in synthesize_stream(text, edge_voice, rate=rate, proxy=proxy):
                audio_received = True
                yield chunk
        except ValueError as e:
            logger.error("[tts] edge 合成失败: %s", e)
        except Exception as e:
            logger.error("[tts] edge 合成异常: %s", e, exc_info=True)
        if not audio_received:
            logger.error("[tts] edge 无音频产出 voice=%s text_len=%d", edge_voice, len(text))

    return StreamingResponse(
        audio_generator(),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": 'inline; filename="tts.mp3"',
        },
    )


@router.get("/voices")
async def list_voices():
    """当前引擎的音色列表。"""
    settings = _get_tts_settings()
    engine = settings["engine"]

    if engine == "volcengine":
        voices = get_curated_voices()
        return {"voices": voices, "default": DEFAULT_VOLC_VOICE, "engine": "volcengine"}

    # Edge 音色
    CURATED_VOICES = [
        {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "男", "style": "阳光少年，推荐"},
        {"id": "zh-CN-YunyangNeural", "name": "云扬", "gender": "男", "style": "专业解说，新闻播报"},
        {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "男", "style": "沉稳有力"},
        {"id": "zh-CN-YunxiaNeural", "name": "云夏", "gender": "男", "style": "少年声线"},
        {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "女", "style": "温暖亲切，推荐女声"},
        {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "女", "style": "活泼可爱"},
        {"id": "zh-CN-XiaohanNeural", "name": "晓涵", "gender": "女", "style": "多情感风格"},
        {"id": "zh-CN-XiaomengNeural", "name": "晓梦", "gender": "女", "style": "温柔甜美"},
        {"id": "zh-CN-XiaomoNeural", "name": "晓墨", "gender": "女", "style": "沉稳知性"},
        {"id": "zh-CN-XiaoruiNeural", "name": "晓睿", "gender": "女", "style": "干练专业"},
        {"id": "zh-HK-WanLungNeural", "name": "云龙", "gender": "男", "style": "粤语，香港"},
        {"id": "zh-TW-YunJheNeural", "name": "云哲", "gender": "男", "style": "国语，台湾"},
    ]
    return {"voices": CURATED_VOICES, "default": DEFAULT_EDGE_VOICE, "engine": "edge"}


@router.get("/volcengine/voices")
async def list_volcengine_voices():
    """火山引擎精选音色列表。"""
    return {"voices": get_curated_voices(), "default": DEFAULT_VOLC_VOICE}
