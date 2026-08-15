"""语音转写 API — /api/voice/transcribe

接收前端上传的音频文件 (WebM/PCM/WAV)，调用用户配置的 STT API 进行转录，
并通过 LLM 提炼为简洁的代码编写指令。

BYOK 原则：配置存储于 settings 表（stt_provider / stt_api_key / stt_model / stt_base_url）。
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

from app.core.database import SessionLocal
from app.models.agent import Setting

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 允许的音频格式 ──
_ALLOWED_CONTENT_TYPES = {
    "audio/webm", "audio/wav", "audio/wave", "audio/x-wav",
    "audio/pcm", "audio/mpeg", "audio/mp3", "audio/ogg",
    "audio/mp4", "audio/x-m4a",
}
_ALLOWED_EXTENSIONS = (".webm", ".wav", ".pcm", ".mp3", ".ogg", ".m4a")
_MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB（与 OpenAI Whisper 一致）


class TranscribeResponse(BaseModel):
    text: str
    raw: Optional[str] = None  # 原始转录文本（提炼前）


def _get_stt_config() -> dict:
    """从 settings 表读取 STT 配置。"""
    db = SessionLocal()
    try:
        def _get(key: str) -> str:
            row = db.query(Setting).filter(Setting.key == key).first()
            return row.value if row else ""

        return {
            "provider": _get("stt_provider"),
            "api_key": _get("stt_api_key"),
            "model": _get("stt_model") or "whisper-1",
            "base_url": _get("stt_base_url"),
        }
    finally:
        db.close()


async def _call_stt_api(audio_bytes: bytes, filename: str, content_type: str, config: dict) -> str:
    """调用 OpenAI 兼容的 /audio/transcriptions 端点，返回转录文本。"""
    base_url = config["base_url"]
    if not base_url:
        base_url = "https://api.openai.com/v1"

    url = f"{base_url.rstrip('/')}/audio/transcriptions"

    files = {
        "file": (filename, audio_bytes, content_type or "audio/webm"),
    }
    data = {"model": config["model"]}
    headers = {"Authorization": f"Bearer {config['api_key']}"}

    from app.core.proxy import build_llm_client

    async with build_llm_client(base_url, timeout=60.0) as client:
        resp = await client.post(url, files=files, data=data, headers=headers)
        resp.raise_for_status()
        result = resp.json()
        return result.get("text", "").strip()


async def _refine_intent(raw_text: str) -> str:
    """通过 LLM 将原始转录文本提炼为简洁指令。

    使用 model_service.call_once() 调用用户默认模型，失败时回退返回原始文本。
    """
    if not raw_text:
        return raw_text

    try:
        from app.services.model import model_service
        from app.core.database import SessionLocal as _SL
        from app.models.agent import Setting as _Setting

        # 读取默认模型
        db = _SL()
        try:
            row = db.query(_Setting).filter(_Setting.key == "default_model").first()
            model_id = row.value if row else "qwen-flash"
        finally:
            db.close()

        messages = [
            {
                "role": "system",
                "content": (
                    "你是语音指令提炼助手。用户通过语音输入了一段话，"
                    "请将其提炼为一条简洁、明确的代码编写或开发指令。"
                    "去除语气词、重复内容和无关描述，保留核心意图。"
                    "只输出提炼后的指令文本，不要加引号、解释或前缀。"
                ),
            },
            {"role": "user", "content": raw_text},
        ]

        result = await model_service.call_once(
            model_id=model_id,
            messages=messages,
            temperature=0.3,
            max_tokens=512,
        )
        refined = result.content.strip() if result.content else raw_text
        return refined if refined else raw_text
    except Exception as e:
        logger.warning("Intent refinement failed, returning raw transcript: %s", e)
        return raw_text


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """接收音频文件，调用 STT API 转录并提炼为指令文本。

    BYOK：需在 settings 中配置 stt_api_key / stt_model / stt_base_url。

    返回:
        {"text": "提炼后的指令", "raw": "原始转录文本"}
    """
    # ── 校验文件类型 ──
    filename = file.filename or "audio.webm"
    content_type = file.content_type or ""
    ext_ok = filename.lower().endswith(_ALLOWED_EXTENSIONS)
    ct_ok = content_type in _ALLOWED_CONTENT_TYPES
    if not ext_ok and not ct_ok:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的音频格式: {content_type or filename}。支持: WebM/WAV/PCM/MP3/OGG/M4A",
        )

    # ── 读取音频数据 ──
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="音频文件为空")
    if len(audio_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"音频文件过大 ({len(audio_bytes) // 1024 // 1024}MB)，上限 25MB",
        )

    # ── 读取 STT 配置 ──
    config = _get_stt_config()
    if not config["api_key"]:
        raise HTTPException(
            status_code=400,
            detail="语音转写未配置：请在设置中配置 stt_api_key（BYOK）",
        )

    # ── 调用 STT API ──
    try:
        raw_text = await _call_stt_api(audio_bytes, filename, content_type, config)
    except httpx.HTTPStatusError as e:
        logger.error("STT API HTTP error: %s %s", e.response.status_code, e.response.text[:200])
        raise HTTPException(
            status_code=502,
            detail=f"语音 API 返回错误 ({e.response.status_code}): {e.response.text[:200]}",
        )
    except httpx.RequestError as e:
        logger.error("STT API request error: %s", e)
        raise HTTPException(status_code=504, detail=f"语音 API 请求失败: {e}")
    except Exception as e:
        logger.error("STT API unexpected error: %s", e)
        raise HTTPException(status_code=500, detail=f"语音转写失败: {e}")

    if not raw_text:
        raise HTTPException(status_code=422, detail="语音转写结果为空，请检查音频内容")

    # ── LLM 提炼意图 ──
    refined = await _refine_intent(raw_text)

    return TranscribeResponse(text=refined, raw=raw_text)
