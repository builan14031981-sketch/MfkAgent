"""UI 自检工具 —— 供 LLM Function Calling 使用（前端 Agent 交付前自检）。

三个工具，对应三层自检能力：
1. probe_ui           — 打开页面，抓取关键元素的计算样式/尺寸（数值级验证，
                         不依赖多模态，主模型可直接分析 4px 增量/token/模块大小）
2. capture_screenshot — 打开页面截图保存到项目 .ui_selfcheck/ 目录（观感级验证前置）
3. analyze_screenshot — 将截图喂给视觉模型（qwen3-vl-plus）做观感判读

安全约束：
- 仅允许访问本机前端（localhost / 127.0.0.1），拒绝外网 URL（防 SSRF）。
- 截图写入项目沙箱目录，遵循 project_path 边界。
- 全部异常返回友好文本，绝不抛出导致 Agent 崩溃。
"""
import asyncio
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional

from app.core.tools import ToolExecutionError
from app.core.sandbox import resolve_sandbox_path

# playwright 可能被安装到项目本地依赖目录（backend/.py_deps，绕开用户级 site-packages 权限限制）。
# 启动时探测并加入 sys.path，保证后端进程能找到。
_DEPS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".py_deps"
)
if os.path.isdir(_DEPS_DIR) and _DEPS_DIR not in sys.path:
    sys.path.insert(0, _DEPS_DIR)

# 仅允许本机前端（dev server 端口），拒绝任意外网 URL（SSRF 防护）
_LOCALHOST_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/.*)?$", re.IGNORECASE)

# 与项目设计规范相关的关键 CSS 属性（probe_ui 抓取范围）
_PROBE_STYLE_PROPS = [
    "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin-top", "margin-right", "margin-bottom", "margin-left",
    "row-gap", "column-gap", "gap",
    "font-size", "line-height", "font-weight",
    "border-radius", "max-height", "max-width", "height", "width",
    "color", "background-color", "background",
    "display", "align-items", "justify-content",
]

# 截图输出子目录（相对项目根）
_SCREENSHOT_DIR = ".ui_selfcheck"

# 浏览器缓存路径（项目内，绕开用户目录权限限制）
_MS_PLAYWRIGHT_DIR = os.path.join(_DEPS_DIR, "ms-playwright")


def _prepare_playwright_env() -> None:
    """确保 playwright 能找到浏览器缓存目录（项目内 .py_deps/ms-playwright）。"""
    if os.path.isdir(_MS_PLAYWRIGHT_DIR):
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _MS_PLAYWRIGHT_DIR)

# 视觉判读默认模型（vision_fallback 未配置 vision_model 时的兜底）
_VISION_DEFAULT_MODEL = "qwen3-vl-plus"
# 视觉判读默认 API Base（vision_base_url 为空且 provider 无默认时的兜底）
_VISION_DEFAULT_BASE = "https://api.siliconflow.cn/v1"
# 视觉判读超时
_VISION_TIMEOUT = 120.0

# 截图最大宽度（超过则等比缩放，控制体积）
_SCREENSHOT_MAX_WIDTH = 1280

_UI_PROBE_PROMPT = (
    "你是资深前端视觉评审。请基于这张截图对页面做观感级评审，用中文输出，"
    "覆盖：1) 整体布局是否协调、有无明显失衡；2) 模块间距/留白是否过大或过小；"
    "3) 配色与视觉语言是否统一；4) 是否有明显视觉瑕疵（重叠、溢出、错位、文字被截断等）；"
    "5) 给出具体的改进建议（能落到数值/属性更佳）。"
)


def _validate_local_url(url: str) -> str:
    """校验 URL 必须为本机前端地址，否则抛 ToolExecutionError。"""
    url = (url or "").strip()
    if not _LOCALHOST_RE.match(url):
        raise ToolExecutionError(
            f"错误: 仅允许访问本机前端地址（http://localhost:端口 或 http://127.0.0.1:端口），拒绝: {url}"
        )
    return url


def _collect_console_errors(page) -> List[str]:
    """收集页面加载期间的 console error（最简实现：读取已记录的条目）。"""
    try:
        entries = page.evaluate(
            """() => {
                const rows = document.querySelectorAll('body *');
                return window.__ui_selfcheck_errors__ || [];
            }"""
        )
        return list(entries or [])
    except Exception:
        return []


def probe_ui(project_path: str, url: str, selectors: Optional[List[str]] = None,
             wait_for: str = "", max_elements: int = 8) -> str:
    """打开本机前端页面，抓取关键元素计算样式与页面尺寸，返回 JSON 文本。

    Args:
        url: 本机前端地址，如 http://localhost:3000/settings/security
        selectors: 要检查的 CSS 选择器列表（不传则检查主要模块容器）
        wait_for: 可选，等待某选择器出现后再抓取（SPA 渲染）
        max_elements: 每个选择器最多抓取的元素个数（默认 8）
    """
    _validate_local_url(url)
    selectors = [s for s in (selectors or []) if s and s.strip()]
    max_elements = max(1, min(int(max_elements or 8), 30))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "错误: 未安装 playwright（pip install playwright && python -m playwright install chromium）"

    _prepare_playwright_env()
    errors: List[str] = []
    page_info: Dict = {}
    elements: List[Dict] = []
    page_errors: List[str] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            # 捕获 console error
            page.on("console", lambda msg: page_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(f"pageerror: {exc}"))

            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
            except Exception as e:
                # networkidle 超时不一定代表渲染失败，继续尝试读取
                errors.append(f"goto(networkidle) 超时/异常: {e}")
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=8000)
                except Exception as e:
                    errors.append(f"等待选择器 {wait_for} 超时: {e}")

            # 页面级信息
            try:
                page_info = page.evaluate(
                    """() => ({
                        title: document.title,
                        url: location.href,
                        bodyScrollHeight: document.body ? document.body.scrollHeight : 0,
                        bodyScrollWidth: document.body ? document.body.scrollWidth : 0,
                        viewportWidth: window.innerWidth,
                        viewportHeight: window.innerHeight,
                        bodyFontSize: document.body ? getComputedStyle(document.body).fontSize : null,
                        bodyLineHeight: document.body ? getComputedStyle(document.body).lineHeight : null,
                    })"""
                )
            except Exception as e:
                errors.append(f"读取页面信息失败: {e}")

            # 元素级计算样式
            for sel in selectors:
                try:
                    nodes = page.query_selector_all(sel)
                    styles = []
                    for node in nodes[:max_elements]:
                        try:
                            st = node.evaluate(
                                """(el) => {
                                    const cs = getComputedStyle(el);
                                    const props = JSON.parse('__PROPS__');
                                    const out = {};
                                    for (const k of props) {
                                        if (k === 'gap') {
                                            out['gap'] = cs.gap;
                                        } else {
                                            out[k] = cs.getPropertyValue(k);
                                        }
                                    }
                                    const r = el.getBoundingClientRect();
                                    out['__rect'] = {x: Math.round(r.x), y: Math.round(r.y),
                                                     w: Math.round(r.width), h: Math.round(r.height)};
                                    out['__tag'] = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').slice(0,2).join('.') : '');
                                    return out;
                                }""".replace("__PROPS__", json.dumps(_PROBE_STYLE_PROPS))
                            )
                            styles.append(st)
                        except Exception as e:
                            styles.append({"__error": str(e)[:120]})
                    elements.append({"selector": sel, "count": len(nodes), "styles": styles})
                except Exception as e:
                    elements.append({"selector": sel, "count": 0, "error": str(e)[:120]})

            browser.close()
    except Exception as e:
        return f"错误: 浏览器自检失败: {type(e).__name__}: {str(e)[:300]}"

    result = {
        "url": url,
        "page": page_info,
        "consoleErrors": page_errors[:10],
        "elements": elements,
        "notes": errors,
    }
    return json.dumps(result, ensure_ascii=False, indent=1)


def capture_screenshot(project_path: str, url: str, wait_for: str = "",
                       full_page: bool = False, filename: str = "") -> str:
    """打开本机前端页面截图，保存到项目 .ui_selfcheck/ 目录。

    Returns:
        返回 JSON：截图本地路径 / 尺寸 / 文件大小（供 analyze_screenshot 使用）。
    """
    _validate_local_url(url)
    try:
        target = resolve_sandbox_path(_SCREENSHOT_DIR, project_path)
    except (ToolExecutionError, PermissionError) as e:
        return f"错误: {e}"
    os.makedirs(target, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "错误: 未安装 playwright（pip install playwright && python -m playwright install chromium）"

    _prepare_playwright_env()
    if not filename:
        filename = f"ui_{int(time.time() * 1000)}.png"
    if not filename.endswith(".png"):
        filename += ".png"
    out_path = os.path.join(target, filename)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            try:
                page.goto(url, wait_until="networkidle", timeout=15000)
            except Exception as e:
                pass  # 渲染未完全空闲也继续截图
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=8000)
                except Exception:
                    pass
            page.screenshot(path=out_path, full_page=bool(full_page))
            browser.close()
    except Exception as e:
        return f"错误: 截图失败: {type(e).__name__}: {str(e)[:300]}"

    if not os.path.isfile(out_path):
        return "错误: 截图未生成"

    size = os.path.getsize(out_path)
    # 缩放超宽截图，控制体积
    if size > 1_500_000:
        try:
            from PIL import Image
            img = Image.open(out_path)
            if img.width > _SCREENSHOT_MAX_WIDTH:
                ratio = _SCREENSHOT_MAX_WIDTH / img.width
                img = img.resize((_SCREENSHOT_MAX_WIDTH, int(img.height * ratio)))
                img.save(out_path, optimize=True)
                size = os.path.getsize(out_path)
        except Exception:
            pass

    return json.dumps({
        "path": out_path.replace("\\", "/"),
        "size_bytes": size,
        "width": 0,
        "note": "将该 path 传给 analyze_screenshot 做观感判读，或通过 read_file 查看路径确认截图内容",
    }, ensure_ascii=False)


def _read_image_data_uri(path: str) -> Optional[str]:
    """读取图片为 base64 data URI（OpenAI Vision image_url 格式）。"""
    from app.services.model import _image_to_data_uri
    return _image_to_data_uri(path, "image/png")


def _load_vision_config() -> Dict[str, str]:
    """读取 settings 里的 vision_fallback 配置（BYOK：key 存本地 settings，不硬编码）。"""
    from app.core.database import SessionLocal
    from app.models.agent import Setting

    db = SessionLocal()
    try:
        def _g(key: str) -> str:
            row = db.query(Setting).filter(Setting.key == key).first()
            return (row.value or "").strip() if row else ""
        return {
            "provider": _g("vision_provider"),
            "api_key": _g("vision_api_key"),
            "model": _g("vision_model"),
            "base_url": _g("vision_base_url"),
        }
    finally:
        db.close()


def analyze_screenshot(project_path: str, image_path: str, prompt: str = "") -> str:
    """将截图交给备用视觉模型（vision_fallback 配置）做观感判读，返回文本评审。

    视觉通道复用现有 vision_fallback 机制（vision_api_key/vision_model/vision_base_url，
    在设置中配置），与图片附件识图共用同一通道；仅做显式配置即视为授权，
    不再受 provider 启停状态影响。

    Args:
        image_path: capture_screenshot 返回的本地截图路径
        prompt: 可选，自定义判读指令（默认使用内置 UI 评审指令）
    """
    if not image_path or not os.path.isfile(image_path):
        return "错误: 截图文件不存在，请先调用 capture_screenshot 生成截图"

    data_uri = _read_image_data_uri(image_path)
    if not data_uri:
        return "错误: 截图读取失败（文件过大或不可读）"

    text_prompt = (prompt or "").strip() or _UI_PROBE_PROMPT

    # 读取 vision_fallback 配置
    cfg = _load_vision_config()
    api_key = cfg["api_key"]
    vision_model = cfg["model"]
    if not api_key or not vision_model:
        return (
            "错误: 未配置备用识图模型（vision_api_key + vision_model），"
            "请在设置中配置后再试"
        )

    # 解析 API Base URL：显式配置 > provider 默认 > 内置兜底
    api_base = cfg["base_url"]
    if not api_base:
        try:
            from app.core.model_providers import PROVIDER_MAP
            provider_def = PROVIDER_MAP.get(cfg["provider"])
            if provider_def is not None:
                api_base = provider_def.default_api_base or _VISION_DEFAULT_BASE
        except Exception:
            pass
    if not api_base:
        api_base = _VISION_DEFAULT_BASE

    # 调用视觉模型（OpenAI 兼容 vision 消息）
    try:
        from app.core.proxy import build_llm_client

        async def _call():
            async with build_llm_client(api_base, timeout=_VISION_TIMEOUT) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": vision_model,
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": text_prompt},
                                {"type": "image_url", "image_url": {"url": data_uri}},
                            ],
                        }],
                        "max_tokens": 1024,
                        "temperature": 0.3,
                    },
                )
                if resp.status_code != 200:
                    return f"错误: 视觉模型返回 {resp.status_code}: {resp.text[:200]}"
                data = resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()

        # 本工具经 executor 以 asyncio.to_thread 调用（worker 线程，无运行中的 loop）
        return asyncio.run(_call())
    except Exception as e:
        return f"错误: 视觉判读调用失败: {type(e).__name__}: {str(e)[:300]}"


# ============ OpenAI Function Calling Schema ============

UI_PROBE_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "probe_ui",
            "description": (
                "打开本机前端页面，抓取关键元素的【计算样式与尺寸】并返回 JSON（padding/margin/gap/"
                "line-height/font-size/border-radius/颜色/元素矩形等精确数值）。"
                "适合验证：间距是否符合 4px 增量、是否硬编码魔法数值、模块是否过大、行高是否过大、"
                "配色是否偏离项目 token。改完前端代码后务必调用本工具自检。"
                "注意：只返回数据本身，不负责判定，判定由你（Agent）对照规范进行。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "本机前端地址，如 http://localhost:3000/settings/security",
                    },
                    "selectors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要检查的 CSS 选择器列表，如 ['.mode-segment', '.card', '.status-row']",
                    },
                    "wait_for": {
                        "type": "string",
                        "description": "可选，等待某选择器出现后再抓取（SPA 异步渲染时用）",
                    },
                    "max_elements": {
                        "type": "integer",
                        "description": "每个选择器最多抓取的元素个数，默认 8",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "capture_screenshot",
            "description": (
                "打开本机前端页面截图，保存到项目 .ui_selfcheck/ 目录，返回本地截图路径。"
                "配合 analyze_screenshot 做观感级视觉评审。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "本机前端地址，如 http://localhost:3000/settings/security",
                    },
                    "wait_for": {
                        "type": "string",
                        "description": "可选，等待某选择器出现后再截图",
                    },
                    "full_page": {
                        "type": "boolean",
                        "description": "是否整页截图，默认 false（只截视口）",
                    },
                    "filename": {
                        "type": "string",
                        "description": "可选，截图文件名（默认自动生成）",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_screenshot",
            "description": (
                "将截图（capture_screenshot 的输出路径）交给备用视觉模型做观感级评审，"
                "返回文字版视觉意见：布局协调性、间距/留白、配色统一性、视觉瑕疵、改进建议。"
                "前置：先调用 capture_screenshot 获得截图路径；依赖设置中已配置备用识图模型"
                "（vision_api_key + vision_model）。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "capture_screenshot 返回的截图本地路径",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "可选，自定义评审指令",
                    },
                },
                "required": ["image_path"],
            },
        },
    },
]

UI_PROBE_TOOLS = {
    "probe_ui": probe_ui,
    "capture_screenshot": capture_screenshot,
    "analyze_screenshot": analyze_screenshot,
}


def execute_ui_probe_tool(name: str, project_path: str, **kwargs) -> str:
    """执行 UI 自检工具并返回文本结果（失败返回错误说明）。"""
    fn = UI_PROBE_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except (ToolExecutionError, PermissionError) as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"
