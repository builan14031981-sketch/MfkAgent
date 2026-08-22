"""文字转语音 API — /api/tts

基于微软 Edge TTS 神经引擎，免费、无需 API Key、高自然度。
网络层使用自研 websockets 客户端（edge_tts_ws），绕过 edge-tts 库
内部 aiohttp 的代理兼容性 bug。

端点：
  GET /api/tts?text=...&voice=...&rate=+0%  → 音频流（audio/mpeg）
  GET /api/tts/voices                          → 可用音色列表

代理支持：国内访问微软 TTS 服务器需走代理，自动探测本地 V2RayN/Clash 代理。
"""
import logging
import os
import socket
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.edge_tts_ws import synthesize_stream

logger = logging.getLogger(__name__)

router = APIRouter()

# 默认音色：云希（男声，阳光少年，微软神经引擎高质量）
DEFAULT_VOICE = "zh-CN-YunxiNeural"
DEFAULT_RATE = "+0%"
MAX_CHARS = 2000

# 本地常见代理端口（协议, 主机, 端口, 描述）
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


@router.get("")
async def text_to_speech(
    text: str = Query(..., min_length=1, max_length=MAX_CHARS),
    voice: str = Query(DEFAULT_VOICE),
    rate: str = Query(DEFAULT_RATE),
):
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文本不能为空")

    proxy = _get_proxy()
    if proxy:
        logger.info("[tts] 使用代理: %s", proxy)
    else:
        logger.warning("[tts] 未配置代理，直连微软服务器（国内可能失败）")

    audio_received = False

    async def audio_generator():
        nonlocal audio_received
        try:
            async for chunk in synthesize_stream(text, voice, rate=rate, proxy=proxy):
                audio_received = True
                yield chunk
        except ValueError as e:
            logger.error("[tts] 合成失败: %s", e)
        except Exception as e:
            logger.error("[tts] 合成异常: %s", e, exc_info=True)
        if not audio_received:
            logger.error("[tts] 无音频产出 voice=%s text_len=%d proxy=%s", voice, len(text), proxy)

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
    """精选中文音色列表（仅包含微软 Edge TTS 实际支持的音色）。"""
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
    return {"voices": CURATED_VOICES, "default": DEFAULT_VOICE}
