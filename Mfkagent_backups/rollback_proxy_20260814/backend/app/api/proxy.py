"""网络代理探测与连通性测试接口。

- GET  /api/proxy/detect  → 返回当前代理配置模式与生效地址（供前端展示"当前生效"）
- POST /api/proxy/test    → 用与真实调用相同的 build_llm_client 试连指定 URL，返回耗时/结果
                              （保证"测试结果"与"实际调用"代理行为一致）
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.proxy import resolve_proxy, proxy_mode, is_host_proxied

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/detect")
async def detect_proxy():
    """返回当前代理配置模式与生效地址（auto 模式返回探测结果，off 返回 None）。"""
    mode = proxy_mode()
    proxy = resolve_proxy() if mode != "off" else None
    no_proxy = "直连白名单: bigmodel.cn / dashscope / deepseek / moonshot 等国内模型域名"
    return {
        "mode": mode,
        "proxy": proxy or None,
        "description": (
            "手动: 使用已配置的 proxy_url；"
            "自动: 环境变量 > Windows 系统代理 > 直连；"
            "关闭: 强制直连。"
        ),
        "no_proxy_hint": no_proxy,
    }


class ProxyTestRequest(BaseModel):
    url: str
    timeout: float = 10.0


@router.post("/test")
async def test_proxy(request: ProxyTestRequest):
    """用 build_llm_client（按目标域名决定代理/直连）测试连通性。

    与真实 LLM 调用共享同一客户端构建链路，测试即实况。
    """
    from app.core.proxy import build_llm_client
    import httpx

    url = (request.url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url 必须以 http:// 或 https:// 开头")

    host = ""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:
        pass
    proxied = is_host_proxied(host)
    effective_proxy = resolve_proxy() if proxied and proxy_mode() != "off" else None

    t0 = time.perf_counter()
    try:
        async with build_llm_client(host and f"https://{host}", timeout=request.timeout) as client:
            resp = await client.get(url, timeout=request.timeout)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "ok": resp.status_code < 500,
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "proxied": bool(effective_proxy),
            "proxy": effective_proxy or None,
            "detail": (
                f"HTTP {resp.status_code}，{latency_ms}ms，"
                f"{'经代理' if effective_proxy else '直连'}"
                + (f"（{effective_proxy}）" if effective_proxy else "（命中直连白名单或未配置代理）")
            ),
        }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "proxied": bool(effective_proxy),
            "proxy": effective_proxy or None,
            "detail": f"连接超时（>{request.timeout}s）{'(经代理)' if effective_proxy else '（直连）'}",
        }
    except Exception as e:
        return {
            "ok": False,
            "status_code": 0,
            "latency_ms": int((time.perf_counter() - t0) * 1000),
            "proxied": bool(effective_proxy),
            "proxy": effective_proxy or None,
            "detail": f"连接失败: {type(e).__name__}: {e}".replace("\n", " ")[:300],
        }