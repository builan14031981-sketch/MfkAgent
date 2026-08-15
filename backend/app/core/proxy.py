"""本地代理探测与 httpx 客户端工厂（代理可配置版）。

解决"边缘出站（LLM 调用 / 联网工具 / git 子进程）是否走代理"问题：
  1. 代理三模式（settings 表 proxy_mode / proxy_url 配置）：
       - manual:  用户手动指定 proxy_url
       - auto:    环境变量 > Windows 系统代理 > 直连（默认，与旧版一致）
       - off:     无条件直连（忽略环境变量与系统代理）
  2. NO_PROXY 直连白名单：LLM 调用目标命中"国内可直连模型域名"时强制直连，
     避免代理干扰国内模型（如 bigmodel.cn / dashscope 等）。
  3. build_llm_client()：按目标 api_base 决定是否走代理的统一客户�factory；
     build_httpx_client()：联网工具的带代理客户端（保持旧行为）。
  4. resolve_proxy_env()：返回可注入 subprocess 的代理环境字典（git 用）。
  5. 配置缓存 + invalidate()：proxy_* 设置更新时热刷（settings PUT 触发）。
"""
import os
import time
from typing import Dict, Optional
from urllib.parse import urlparse

import httpx

# 默认浏览器 User-Agent：避免 fetch_url / web_search 请求被反爬站点直接拒绝（412/403）
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# 默认模式 / 默认空地址（实际取值以 settings 表 proxy_mode / proxy_url 为准）
DEFAULT_MODE = "auto"

# ── 国内可直连模型域名白名单（强制 NO_PROXY，不因代理命中而改变直连）──
# 命中这些域名（子域通配）的 LLM 调用无论代理模式为何都直连。
# 覆盖当前全部内置 Provider 的 api_base 域名；新增 Provider 可在此补充。
DEFAULT_NO_PROXY_DOMAINS = (
    "bigmodel.cn",
    "dashscope.aliyun.com",
    "dashscope.aliyuncs.com",
    "api.deepseek.com",
    "api.moonshot.cn",
    "www.moonshot.cn",
    "qianfan.baidubce.com",
    "qianfan.cloud.baidu.com",
    "xinghuo.xfyun.cn",
    "spark-api-open.xf-yun.com",
    "api.siliconflow.cn",
    "siliconflow.cn",
    "www.minimax.io",
    "token-plan-cn.xiaomimimo.com",
    "www.xiaomimimo.com",
    "localhost",
    "127.0.0.1",
)


# ── 配置缓存（惰性读 settings 表；proxy_ 键更新时由 settings.py 调 invalidate）──

_CACHE: Dict[str, object] = {"mode": None, "url": None, "t": 0.0}
_CACHE_TTL = 2.0  # 秒：热重载后的最短刷新窗口，避免高频 PUT 抖动


def _db_setting(key: str) -> str:
    """从 settings 表读取单个 key（失败返回默认值，绝不抛异常）。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            row = db.query(Setting).filter(Setting.key == key).first()
            return (row.value or "") if row else ""
        finally:
            db.close()
    except Exception:
        return ""


def invalidate() -> None:
    """清空代理配置缓存（设置更新后强制下次重读）。"""
    _CACHE["mode"] = None
    _CACHE["url"] = None
    _CACHE["t"] = 0.0


def _load_config() -> Dict[str, str]:
    """读取代理配置（带 2s 缓存）。返回 {mode, url}。"""
    now = time.monotonic()
    if _CACHE["mode"] is not None and (now - float(_CACHE["t"])) < _CACHE_TTL:
        return {"mode": _CACHE["mode"], "url": _CACHE["url"] or ""}
    mode = _db_setting("proxy_mode") or DEFAULT_MODE
    url = _db_setting("proxy_url") or ""
    if mode not in ("auto", "manual", "off"):
        mode = DEFAULT_MODE
    _CACHE["mode"] = mode
    _CACHE["url"] = url
    _CACHE["t"] = now
    return {"mode": mode, "url": url}


def proxy_mode() -> str:
    """当前代理模式：manual / auto / off。"""
    return _load_config()["mode"]


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


def _env_proxy() -> Optional[str]:
    """环境变量代理（HTTPS_PROXY 优先，其次 HTTP_PROXY）。"""
    for env_key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(env_key)
        if v:
            return v
    return None


def resolve_proxy() -> Optional[str]:
    """按配置返回代理地址；None 表示直连。

    优先级：
      - manual: proxy_url（用户显式指定）
      - auto:   环境变量 > Windows 系统代理 > None
      - off:    None（无条件直连）
    """
    cfg = _load_config()
    if cfg["mode"] == "manual":
        return cfg["url"] or None
    if cfg["mode"] == "off":
        return None
    return _env_proxy() or _detect_windows_proxy()


def _normalize_host(host: str) -> str:
    """提取规范化域名（去端口、去括号、转小写）。"""
    if not host:
        return ""
    h = host.strip().lower()
    if h.startswith("["):
        end = h.find("]")
        if end >= 0:
            h = h[1:end]
    if ":" in h and not h.startswith("[") and h.count(":") == 1:
        h = h.split(":", 1)[0]
    return h


def _host_matches_domain(host: str, domain: str) -> bool:
    """host 等于 domain 或为其子域（如 api.bigmodel.cn 命中 bigmodel.cn）。"""
    host = _normalize_host(host)
    domain = _normalize_host(domain)
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def is_host_proxied(host: str) -> bool:
    """目标域名是否应走代理。命中国内直连白名单 → False（直连）；否则 True。"""
    for domain in DEFAULT_NO_PROXY_DOMAINS:
        if _host_matches_domain(host, domain):
            return False
    return True


def no_proxy_list() -> str:
    """生成 NO_PROXY 环境值：内置白名单域名（逗号分隔，含前缀 * 通配子域形式）。"""
    return ",".join(
        d if d in ("localhost", "127.0.0.1") else f"*{d}" for d in DEFAULT_NO_PROXY_DOMAINS
    )


def resolve_proxy_env() -> Dict[str, str]:
    """返回可注入 subprocess 的代理环境字典（git 等外部命令用）。

    手动/自动模式下返回 {http_proxy, https_proxy, HTTP_PROXY, HTTPS_PROXY, NO_PROXY, no_proxy}；
    off 模式或未探测到代理时只返回 NO_PROXY 白名单（保证国内域名直连）。
    """
    proxy = resolve_proxy()
    np = no_proxy_list()
    result = {
        "NO_PROXY": np,
        "no_proxy": np,
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "http_proxy": "",
        "https_proxy": "",
    }
    if proxy:
        result.update({
            "HTTP_PROXY": proxy,
            "HTTPS_PROXY": proxy,
            "http_proxy": proxy,
            "https_proxy": proxy,
        })
    return result


def build_httpx_client(timeout: float = 10.0, **kwargs):
    """构造带代理的 httpx.AsyncClient（联网工具用，保持旧行为）。无代理时等价于直连。

    默认携带浏览器 User-Agent（DEFAULT_USER_AGENT），避免部分网站因缺少浏览器标识
    返回 412 Precondition Failed / 403 Forbidden；调用方可传入 headers 覆盖默认 UA。
    """
    headers = kwargs.pop("headers", None) or {}
    headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
    kwargs["headers"] = headers

    proxy = resolve_proxy()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(timeout=timeout, **kwargs)


def build_llm_client(api_base: str = "", timeout: float = 60.0, **kwargs):
    """构造 LLM 调用客户端，按目标域名决定是否走代理。

    - 命中白名单（国内直连域名）→ 显式 trust_env=False 纯直连，防环境变量误代理
    - 否则 → 按 resolve_proxy() 结果走代理；直连时 trust_env=False 锁定行为
    """
    host = ""
    try:
        host = urlparse(api_base or "").hostname or ""
    except Exception:
        host = ""

    proxy = None
    if is_host_proxied(host):
        proxy = resolve_proxy()

    kwargs["trust_env"] = False  # 显式锁定：只遵循 resolve_proxy 自定义链路，不读裸环境变量
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(timeout=timeout, **kwargs)