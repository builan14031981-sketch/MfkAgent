"""火山引擎（字节跳动）语音合成 TTS 客户端

基于火山引擎大模型语音合成 HTTP 非流式接口：
  POST https://openspeech.bytedance.com/api/v1/tts

鉴权：Header Authorization: Bearer;{access_token}
响应：JSON，data 字段为 base64 编码的音频二进制数据。

国内直连，无需代理，时延低，音色自然度高。
"""
import base64
import json
import logging
import uuid
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

API_URL = "https://openspeech.bytedance.com/api/v1/tts"
DEFAULT_CLUSTER = "volcano_tts"
DEFAULT_ENCODING = "mp3"
DEFAULT_RATE = 24000
DEFAULT_SPEED_RATIO = 1.0


async def synthesize(
    text: str,
    appid: str,
    access_token: str,
    voice_type: str,
    speed_ratio: float = DEFAULT_SPEED_RATIO,
    encoding: str = DEFAULT_ENCODING,
    rate: int = DEFAULT_RATE,
    cluster: str = DEFAULT_CLUSTER,
    timeout: float = 30.0,
) -> bytes:
    """合成语音，返回 MP3 音频字节。

    Args:
        text: 要合成的文本（建议小于 300 字符，最大 1024 字节 UTF-8）
        appid: 火山引擎应用标识
        access_token: 火山引擎访问令牌
        voice_type: 音色 ID，如 zh_female_cancan_mars_bigtts
        speed_ratio: 语速，0.1~2.0，默认 1.0
        encoding: 音频编码，mp3/wav/pcm/ogg_opus，默认 mp3
        rate: 采样率，8000/16000/24000，默认 24000
        cluster: 业务集群，默认 volcano_tts
        timeout: 请求超时秒数

    Returns:
        MP3 音频数据（bytes）

    Raises:
        ValueError: 鉴权失败、音色不存在、文本无效等业务错误
        Exception: 网络或其他异常
    """
    if not appid or not access_token:
        raise ValueError("火山引擎 TTS 未配置 AppID 或 Access Token")
    if not voice_type:
        raise ValueError("未指定音色")
    if not text or not text.strip():
        raise ValueError("文本为空")

    reqid = str(uuid.uuid4())
    payload = {
        "app": {
            "appid": appid,
            "token": "access_token",  # Fake token，实际鉴权走 Header
            "cluster": cluster,
        },
        "user": {
            "uid": "mfkagent",
        },
        "audio": {
            "voice_type": voice_type,
            "encoding": encoding,
            "speed_ratio": speed_ratio,
            "rate": rate,
        },
        "request": {
            "reqid": reqid,
            "text": text,
            "operation": "query",
        },
    }

    headers = {
        "Authorization": f"Bearer;{access_token}",
        "Content-Type": "application/json",
    }

    logger.info("[volcengine_tts] voice=%s text_len=%d reqid=%s", voice_type, len(text), reqid)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("[volcengine_tts] HTTP %d: %s", e.response.status_code, e.response.text[:500])
        raise ValueError(f"火山引擎 TTS HTTP 错误 {e.response.status_code}") from e
    except Exception as e:
        logger.error("[volcengine_tts] 请求异常: %s", e, exc_info=True)
        raise

    code = result.get("code")
    message = result.get("message", "")
    if code != 3000:
        logger.error("[volcengine_tts] 业务错误 code=%s message=%s reqid=%s", code, message, reqid)
        # 常见错误码映射
        error_map = {
            3001: "无效的请求参数",
            3003: "并发超限，请稍后重试",
            3005: "后端服务忙，请稍后重试",
            3010: "文本长度超限",
            3011: "无效文本",
            3030: "处理超时",
            3050: f"音色不存在: {voice_type}",
        }
        desc = error_map.get(code, message)
        raise ValueError(f"火山引擎 TTS 错误 [{code}]: {desc}")

    data_b64 = result.get("data", "")
    if not data_b64:
        raise ValueError("火山引擎 TTS 返回空音频")

    try:
        audio_bytes = base64.b64decode(data_b64)
    except Exception as e:
        logger.error("[volcengine_tts] base64 解码失败: %s", e)
        raise ValueError("音频数据解码失败") from e

    duration = result.get("addition", {}).get("duration", "?")
    logger.info("[volcengine_tts] 成功 size=%d duration=%sms reqid=%s", len(audio_bytes), duration, reqid)
    return audio_bytes


def get_curated_voices() -> list[dict]:
    """精选火山引擎中文音色列表（用于前端音色选择器）。

    选取常用、免费、高质量的音色，覆盖男女声、不同风格。
    """
    return [
        # 女声
        {"id": "zh_female_cancan_mars_bigtts", "name": "灿灿", "gender": "女", "style": "活泼亲切，推荐", "free": True},
        {"id": "zh_female_vv_mars_bigtts", "name": "Vivi", "gender": "女", "style": "温柔自然", "free": True},
        {"id": "zh_female_qingxinnvsheng_mars_bigtts", "name": "清新女声", "gender": "女", "style": "清新干净", "free": True},
        {"id": "zh_female_zhixingnvsheng_mars_bigtts", "name": "知性女声", "gender": "女", "style": "知性沉稳", "free": True},
        {"id": "zh_female_tianmeixiaoyuan_moon_bigtts", "name": "甜美小源", "gender": "女", "style": "甜美可爱", "free": True},
        {"id": "zh_female_linjianvhai_moon_bigtts", "name": "邻家女孩", "gender": "女", "style": "亲切邻家", "free": True},
        {"id": "zh_female_wenrouxiaoya_moon_bigtts", "name": "温柔小雅", "gender": "女", "style": "温柔甜美", "free": True},
        {"id": "zh_female_kailangjiejie_moon_bigtts", "name": "开朗姐姐", "gender": "女", "style": "开朗明快", "free": True},
        # 男声
        {"id": "zh_male_qingyiyuxuan_mars_bigtts", "name": "阳光阿辰", "gender": "男", "style": "阳光青年，推荐男声", "free": True},
        {"id": "zh_male_qingshuangnanda_mars_bigtts", "name": "清爽男大", "gender": "男", "style": "清爽大学生", "free": True},
        {"id": "zh_male_yangguangqingnian_moon_bigtts", "name": "阳光青年", "gender": "男", "style": "阳光活力", "free": True},
        {"id": "zh_male_ruyayichen_saturn_bigtts", "name": "儒雅逸辰", "gender": "男", "style": "儒雅沉稳", "free": True},
        {"id": "zh_male_m191_uranus_bigtts", "name": "云舟 2.0", "gender": "男", "style": "清爽沉稳，2.0大模型", "free": True},
        {"id": "zh_male_taocheng_uranus_bigtts", "name": "小天 2.0", "gender": "男", "style": "清爽磁性，2.0大模型", "free": True},
        # 2.0 女声
        {"id": "zh_female_xiaohe_uranus_bigtts", "name": "小何 2.0", "gender": "女", "style": "甜美活泼，2.0大模型", "free": True},
        {"id": "zh_female_vv_uranus_bigtts", "name": "Vivi 2.0", "gender": "女", "style": "温柔自然，2.0大模型", "free": True},
    ]
