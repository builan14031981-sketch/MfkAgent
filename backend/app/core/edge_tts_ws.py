"""Edge TTS 客户端 —— 用 websockets 库替代 edge-tts 内部的 aiohttp

背景：edge-tts 库内部用 aiohttp 的 WebSocket，通过 HTTP 代理时存在兼容性 bug
（NoAudioReceived）。本模块复用 edge-tts 的协议参数（DRM/SSML/常量），
仅用 websockets 库替换网络层，websockets 对 HTTP 代理的 WebSocket 支持良好。
"""
import asyncio
import logging
from typing import AsyncGenerator, Optional

import websockets
from edge_tts.constants import WSS_URL, WSS_HEADERS, SEC_MS_GEC_VERSION
from edge_tts.drm import DRM
from edge_tts.communicate import (
    connect_id,
    date_to_string,
    mkssml,
    ssml_headers_plus_data,
    remove_incompatible_characters,
    split_text_by_byte_length,
    TTSConfig,
)
from html import escape

logger = logging.getLogger(__name__)


async def synthesize_stream(
    text: str,
    voice: str,
    rate: str = "+0%",
    proxy: Optional[str] = None,
) -> AsyncGenerator[bytes, None]:
    """合成语音，逐块 yield MP3 音频字节。

    Args:
        text: 要合成的文本
        voice: 音色 ID，如 zh-CN-YunxiNeural
        rate: 语速，如 +0% / -10% / +20%
        proxy: HTTP 代理 URL，如 http://127.0.0.1:10808

    Yields:
        MP3 音频数据块（bytes）
    """
    config = TTSConfig(voice, rate, "+0%", "+0Hz", "SentenceBoundary")
    clean_text = remove_incompatible_characters(text)
    text_chunks = split_text_by_byte_length(escape(clean_text), 4096)

    conn_id = connect_id()
    sec_ms_gec = DRM.generate_sec_ms_gec()
    url = (
        f"{WSS_URL}"
        f"&ConnectionId={conn_id}"
        f"&Sec-MS-GEC={sec_ms_gec}"
        f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
    )

    # websockets 自动设置 WebSocket 协议头，只需业务头，避免冲突
    headers = {
        "User-Agent": WSS_HEADERS["User-Agent"],
        "Accept-Language": WSS_HEADERS["Accept-Language"],
        "Origin": WSS_HEADERS["Origin"],
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
    }
    headers = DRM.headers_with_muid(headers)

    logger.info("[edge_tts_ws] voice=%s rate=%s proxy=%s text_len=%d",
                voice, rate, proxy, len(text))

    try:
        async with websockets.connect(
            url,
            proxy=proxy,
            additional_headers=headers,
            max_size=None,
            open_timeout=30,
            close_timeout=10,
        ) as ws:
            # 1. 发送 speech.config
            ts = date_to_string()
            config_msg = (
                f"X-Timestamp:{ts}\r\n"
                "Content-Type:application/json; charset=utf-8\r\n"
                "Path:speech.config\r\n\r\n"
                '{"context":{"synthesis":{"audio":{"metadataoptions":{'
                '"sentenceBoundaryEnabled":"true","wordBoundaryEnabled":"false"'
                '},"outputFormat":"audio-24khz-48kbitrate-mono-mp3"'
                "}}}}\r\n"
            )
            await ws.send(config_msg)

            # 2. 发送 SSML（文本可能被切成多块）
            for chunk in text_chunks:
                ssml = mkssml(config, chunk)
                msg = ssml_headers_plus_data(conn_id, date_to_string(), ssml)
                await ws.send(msg)

            # 3. 接收音频
            # 微软 TTS 二进制帧结构：
            # [2字节头部][文本headers(可打印ASCII, 以\r\n分行)][MP3音频数据]
            # headers 以 "Path:audio\r\n" 结束，后面直接跟音频数据（无空行分隔）
            # 需要跳过头部和 headers，只 yield 真正的音频数据
            audio_bytes = 0
            async for message in ws:
                if isinstance(message, bytes):
                    # 跳过前 2 字节帧头部
                    # 找到第一个非可打印 ASCII 字节（>=0x80 或 <0x20 且不是 \r\n\t），即音频数据开始
                    audio_start = None
                    for i in range(2, len(message)):
                        b = message[i]
                        if 0x20 <= b < 0x7f or b in (0x0d, 0x0a, 0x09):
                            continue
                        audio_start = i
                        break
                    if audio_start is not None:
                        audio_data = message[audio_start:]
                        if audio_data:
                            audio_bytes += len(audio_data)
                            yield audio_data
                    else:
                        logger.warning("[edge_tts_ws] 未找到音频数据起始位置，帧长=%d", len(message))
                elif isinstance(message, str) and "Path:turn.end" in message:
                    break

            logger.info("[edge_tts_ws] done, total_audio=%d bytes", audio_bytes)

    except websockets.exceptions.ConnectionClosedError as e:
        # 服务器主动关闭，通常是音色不支持或参数错误
        logger.error("[edge_tts_ws] connection closed: %s", e)
        raise ValueError(f"TTS 合成失败：{e}") from e
    except Exception as e:
        logger.error("[edge_tts_ws] error: %s", e, exc_info=True)
        raise
