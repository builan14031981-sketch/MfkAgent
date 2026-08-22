"""本地代理探测与 httpx 客户端工厂。

解决"Agent 平台联网工具（web_search / fetch_url）是否走本地代理"问题：
遵循 环境变量 > Windows 系统代理 > 直连 的优先级，让联网工具在常见代理环境下
（如 127.0.0.1:10808 等）也能稳定访问被墙站点。
"""
import os
from typing import Optional

# 默认浏览器 User-Agent：避免 fetch_url / web_search 请求被反爬站点直接拒绝（412/403）
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


def _detect_windows_proxy() -> Optional[str]:
    """读取 Windows 系统代理设置（Internet Options → Connections → LAN 代理）。

    仅在"为 LAN 使用代理服务器(ProxyEnable=1)"时返回代理地址；支持
    "127.0.0.1:10809"、"http=..;https=.." 两种形式；无则返回 None。
    """
    try:
        import winreg

        key = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            enable, _ = winreg.QueryValueEx(k, "ProxyEnable")
            server, _ = winreg.QueryValueEx(k, "ProxyServer")
        if not enable or not server:
            return None
        # 分协议形式：优先 https 段，其次 http 段
        if "=" in server:
            parts = server.split(";")
            for part in parts:
                if part.lower().startswith("https="):
                    server = part.split("=", 1)[1].rstrip()
                    break
            else:
                for part in parts:
                    if part.lower().startswith("http="):
                        server = part.split("=", 1)[1].rstrip()
                        break
                else:
                    server = parts[0].rstrip()
        if server and not server.lower().startswith(("http://", "https://", "socks")):
            server = "http://" + server
        return server or None
    except Exception:
        return None


def resolve_proxy() -> Optional[str]:
    """按优先级返回代理地址：环境变量 > Windows 系统代理 > None(直连)。"""
    for env_key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(env_key)
        if v:
            return v
    return _detect_windows_proxy()


def build_httpx_client(timeout: float = 10.0, **kwargs):
    """构造带代理的 httpx.AsyncClient。无代理时等价于直连。

    默认携带浏览器 User-Agent（DEFAULT_USER_AGENT），避免部分网站因缺少浏览器标识
    返回 412 Precondition Failed / 403 Forbidden；调用方可传入 headers 覆盖默认 UA。
    """
    import httpx

    headers = kwargs.pop("headers", None) or {}
    headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
    kwargs["headers"] = headers

    proxy = resolve_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(timeout=timeout, **kwargs)