"""文生图工具 —— 多后端容灾版（DashScope qwen-image 主力 + SiliconFlow 备用）。

Phase H (super_enhance_20260818) 新增，Phase CreativeAgent (2026-08-25) 扩展多后端：
- 主力：DashScope 万相 qwen-image（qwen-image-3.0-pro / qwen-image-3.0，异步轮询）
- 备用：SiliconFlow Qwen/Qwen-Image（同步，~15s，额度独立）
  触发条件：DashScope key 不存在 / HTTP 401 / 429 / 5xx 时自动降级
- API Key 读取：settings 表 api_key_qwen > .env QWEN_API_KEY；
               settings 表 api_key_siliconflow > .env SILICONFLOW_API_KEY
- 无 project_path 时仅返回图片 URL（不落盘）。
- 所有异常/失败返回以 "错误:" 开头（与既有工具约定一致，executor 判定 failed）。
"""
import json
import logging
import os
import time
import sys
import urllib.parse
from typing import Dict, List, Optional

import httpx

from app.core.model_providers import PROVIDER_MAP
from app.core.model_adapter import ModelConfigAdapter

logger = logging.getLogger(__name__)

# 千问图像生成（qwen-image 3.0）任务端点（异步：提交 + 轮询）
_SYNTHESIS_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
_TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{}"

# 必须携带：该接口仅支持异步（缺少即报 "current user api does not support synchronous calls"）
_ASYNC_HEADER = {"X-DashScope-Async": "enable"}

_DEFAULT_MODEL = "qwen-image-3.0-pro"
_FALLBACK_MODELS = ("qwen-image-3.0",)
POLL_INTERVAL = 5.0
# 实测 qwen-image-3.0-pro 生成约 9 分钟，上限放宽至 15 分钟
MAX_POLL_SECONDS = 900
HTTP_TIMEOUT = 30.0

# 生成图片落盘目录（相对项目根）
_IMAGE_OUTPUT_DIR = "output/generated_images"


def _resolve_qwen_key() -> str:
    """读取文生图使用的 API Key：settings 表 api_key_qwen > .env 的 QWEN_API_KEY。"""
    provider = PROVIDER_MAP.get("qwen")
    if provider is not None:
        try:
            return ModelConfigAdapter().resolve_api_key(provider) or ""
        except Exception as e:  # noqa: BLE001
            logger.warning("[image_gen] 解析 Qwen API Key 失败: %s", e)
    return os.environ.get("QWEN_API_KEY", "")


# ─── SiliconFlow 备用后端 ───────────────────────────────────────────────────

_SF_URL = "https://api.siliconflow.cn/v1/images/generations"
# 优先高质 Qwen-Image，失败回退快速 Z-Image-Turbo
_SF_MODELS = ("Qwen/Qwen-Image", "Tongyi-MAI/Z-Image-Turbo")
# SiliconFlow 支持的标准尺寸映射（宽*高 → 宽x高）
_SF_SIZE_MAP = {
    "1024*1024": "1024x1024",
    "768*1024": "768x1024",
    "1024*768": "1024x768",
    "768*768": "768x768",
}


def _resolve_siliconflow_key() -> str:
    """读取 SiliconFlow API Key：settings 表 api_key_siliconflow > .env SILICONFLOW_API_KEY。"""
    try:
        import sqlite3
        from pathlib import Path
        for db_path in [
            Path(__file__).parents[2] / "mfkagent.db",
            Path(__file__).parents[3] / "mfkagent.db",
            Path(__file__).parents[1] / "mfkagent.db",
        ]:
            if db_path.exists():
                con = sqlite3.connect(str(db_path))
                row = con.execute(
                    "SELECT value FROM settings WHERE key='api_key_siliconflow'"
                ).fetchone()
                con.close()
                if row and row[0]:
                    return row[0]
    except Exception as e:  # noqa: BLE001
        logger.debug("[image_gen] 读取 SiliconFlow key 失败: %s", e)
    return os.environ.get("SILICONFLOW_API_KEY", "")


def _sf_generate(prompt: str, size: str) -> Optional[List[str]]:
    """SiliconFlow 同步生图，返回图片 URL 列表（失败返回 None）。"""
    key = _resolve_siliconflow_key()
    if not key:
        logger.debug("[image_gen] 未配置 SiliconFlow key，跳过备用通道")
        return None
    sf_size = _SF_SIZE_MAP.get(size, "1024x1024")
    for model in _SF_MODELS:
        try:
            resp = httpx.post(
                _SF_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt, "n": 1, "size": sf_size},
                timeout=180.0,
            )
        except httpx.RequestError as e:
            logger.warning("[image_gen/sf] 网络错误: %s", e)
            continue
        if resp.status_code != 200:
            logger.warning("[image_gen/sf] HTTP %s model=%s: %s",
                           resp.status_code, model, resp.text[:200])
            continue
        imgs = resp.json().get("images") or []
        urls = [i["url"] for i in imgs if i.get("url")]
        if urls:
            logger.info("[image_gen/sf] 成功 model=%s size=%s", model, sf_size)
            return urls
        logger.warning("[image_gen/sf] 无图像 model=%s: %s", model, resp.text[:200])
    return None


# ─── ComfyUI 本地生图后端 (127.0.0.1:8188) ──────────────────────────────────

_COMFY_SCRIPT = r"E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\ComfyUI\workflows_opencode\comfy_call.py"


def _comfyui_generate(
    prompt: str,
    size: str = "1024*1024",
    model: Optional[str] = None,
    hires: bool = False,
    steps: int = 20,
    filename: Optional[str] = None,
) -> Optional[List[str]]:
    """调用本机 ComfyUI REST API (comfy_call.py) 出图。"""
    if not os.path.exists(_COMFY_SCRIPT):
        logger.debug("[image_gen/comfy] comfy_call.py 路径不存在，跳过本地生图")
        return None
    try:
        w, h = 1024, 1024
        if "*" in size:
            parts = size.split("*")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                w, h = int(parts[0]), int(parts[1])
        python_exe = sys.executable or "python"
        wf_name = "02_二次渲染高清_T2I_HiRes.json" if hires else "01_快捷出图_T2I.json"
        cmd = [
            python_exe,
            _COMFY_SCRIPT,
            "--workflow", wf_name,
            "--prompt", prompt,
            "--width", str(w),
            "--height", str(h),
            "--seed", str(int(time.time())),
            "--steps", str(steps or (25 if hires else 20)),
        ]
        if model:
            cmd.extend(["--model", model])
        if filename:
            cmd.extend(["--filename", filename])
        import subprocess
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            logger.warning("[image_gen/comfy] 进程退出码 %s: %s", proc.returncode, proc.stderr[:200])
            return None
        paths = []
        for line in proc.stdout.splitlines():
            s = line.strip()
            if s.endswith(".png") and os.path.exists(s):
                paths.append(s)
        if paths:
            logger.info("[image_gen/comfy] 本地生图成功: %s", paths)
            return paths
        logger.warning("[image_gen/comfy] 未输出有效图片路径: %s", proc.stdout[:200])
    except Exception as e:  # noqa: BLE001
        logger.warning("[image_gen/comfy] 本地生图异常: %s", e)
    return None


def _submit(model: str, prompt: str, size: str, n: int, api_key: str) -> Optional[str]:
    """提交文生图任务，返回 task_id（失败返回 None 并记录错误原因）。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **_ASYNC_HEADER,
    }
    body = {
        "model": model,
        "input": {
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ]
        },
        "parameters": {"prompt_extend": True, "size": size, "n": n},
    }
    try:
        resp = httpx.post(
            _SYNTHESIS_URL, headers=headers, json=body,
            timeout=HTTP_TIMEOUT, follow_redirects=True,
        )
    except httpx.RequestError as e:
        logger.warning("[image_gen] 提交文生图任务失败（网络错误）: %s", e)
        return None
    if resp.status_code != 200:
        logger.warning("[image_gen] 提交文生图任务失败: %s", _dashscope_error(resp, "提交文生图任务"))
        return None
    data = _safe_json(resp.text)
    task_id = ((data or {}).get("output") or {}).get("task_id", "")
    if not task_id:
        logger.warning("[image_gen] 文生图响应缺少 task_id: %s", resp.text[:300])
    return task_id or None


def _poll_results(task_id: str, api_key: str) -> Optional[List[str]]:
    """轮询任务直至完成，返回图片 URL 列表（失败/超时返回 None）。"""
    task_url = _TASK_URL.format(urllib.parse.quote(task_id, safe=""))
    headers = {"Authorization": f"Bearer {api_key}"}
    deadline = time.monotonic() + MAX_POLL_SECONDS
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            poll = httpx.get(task_url, headers=headers, timeout=HTTP_TIMEOUT, follow_redirects=True)
        except httpx.RequestError as e:
            logger.warning("[image_gen] 查询文生图任务状态失败（网络错误）: %s", e)
            return None
        if poll.status_code != 200:
            logger.warning("[image_gen] 查询文生图任务失败: %s", _dashscope_error(poll, "查询文生图任务"))
            return None

        poll_data = _safe_json(poll.text)
        poll_output = (poll_data or {}).get("output") or {}
        status = poll_output.get("task_status", "UNKNOWN")

        if status == "SUCCEEDED":
            urls: List[str] = []
            # 新格式（qwen-image 3.0，OpenAI 兼容 messages）：output.choices[].message.content[].image
            for choice in poll_output.get("choices") or []:
                for content in ((choice.get("message") or {}).get("content") or []):
                    if isinstance(content, dict) and content.get("image"):
                        urls.append(content["image"])
            # 旧格式兜底：output.results[].url
            if not urls:
                urls = [r.get("url", "") for r in (poll_output.get("results") or []) if r.get("url")]
            if not urls:
                logger.warning("[image_gen] 文生图任务成功但未解析到图片 URL: %s", poll.text[:400])
                return None
            return urls
        if status in ("FAILED", "CANCELED", "UNKNOWN"):
            logger.warning("[image_gen] 文生图任务失败（状态 %s）: %s", status, poll.text[:300])
            return None
        # PENDING / RUNNING 继续轮询

    logger.warning("[image_gen] 文生图任务超时（>%ss）", MAX_POLL_SECONDS)
    return None


def _resolve_model() -> str:
    """读取文生图模型：settings 表 image_gen_model > 默认 qwen-image-3.0-pro。"""
    try:
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            setting = db.query(Setting).filter(Setting.key == "image_gen_model").first()
            if setting and setting.value and setting.value.strip():
                return setting.value.strip()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("[image_gen] 读取 image_gen_model 设置失败，使用默认模型: %s", e)
    return _DEFAULT_MODEL


def generate_image(
    project_path: str,
    prompt: str,
    size: str = "1024*1024",
    n: int = 1,
    model: str = _DEFAULT_MODEL,
    hires: bool = False,
    steps: int = 20,
    filename: Optional[str] = None,
    save_to_project: bool = True,
    chat_id: Optional[int] = None,
) -> str:
    """根据提示词生成图片，返回 Markdown 可渲染的图片引用（本地路径或 URL）。

    Args:
        prompt: 图片描述提示词（必填，中英文均可）
        size: 尺寸，宽*高（如 1024*1024），面积范围 512*512 ~ 2048*2048
        n: 生成张数（1-6，默认 1）
        model: 模型选择：本地可用 realistic / counterfeit / anime；云端可用 qwen-image-3.0-pro / qwen-image-3.0
        hires: 是否开启二次高清放大与细节修复
        steps: 采样步数，默认 20（高清模式建议 25-30）
        filename: 自定义保存的最终文件名（如 【昭和浪漫_夕阳奥特曼】SHOWA_01.png）
        save_to_project: 是否下载保存到项目 output/generated_images/（需绑定项目）
        chat_id: 会话 id（有值时本地图片返回 /api/chat/{chat_id}/generated_image 代理 URL，
                 前端可直接渲染；无值时返回绝对路径文本）

    Returns:
        成功：图片路径/URL 列表文本；失败："错误: ..."
    """
    prompt = (prompt or "").strip()
    if not prompt:
        return "错误: prompt 不能为空，请描述你想生成的图片内容"
    size = (size or "").strip()
    if size and ("*" not in size or not size.replace("*", "").isdigit()):
        return f"错误: 不支持的尺寸 {size}，格式应为 宽*高（如 1024*1024）"
    n = max(1, min(int(n or 1), 6))
    model = (model or _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
    if model == _DEFAULT_MODEL:
        model = _resolve_model() or _DEFAULT_MODEL

    # ── 1. 优先尝试本地 ComfyUI 服务 (127.0.0.1:8188) ──
    comfy_results = _comfyui_generate(prompt, size or "1024*1024", model=model, hires=hires, steps=steps, filename=filename)
    if comfy_results:
        results = comfy_results
    else:
        # ── 2. 本地未开或失败时，走 DashScope 主选 ──
        api_key = _resolve_qwen_key()
        if not api_key:
            logger.info("[image_gen] 未配置 QWEN_API_KEY，尝试 SiliconFlow 备用通道")
            sf_results = _sf_generate(prompt, size or "1024*1024")
            if sf_results:
                results = sf_results
            else:
                return "错误: 未配置任何生图 API Key（QWEN_API_KEY / SILICONFLOW_API_KEY）且 ComfyUI 本地未开启"
        else:
            task_id = _submit(model, prompt, size, n, api_key)
            used_model = model
            if not task_id:
                for fb in _FALLBACK_MODELS:
                    if fb == model:
                        continue
                    task_id = _submit(fb, prompt, size, n, api_key)
                    if task_id:
                        used_model = fb
                        break
            if not task_id:
                # DashScope 全部失败 → 自动降级 SiliconFlow
                logger.warning("[image_gen] DashScope 全部失败，降级到 SiliconFlow 备用通道")
                sf_results = _sf_generate(prompt, size or "1024*1024")
                if sf_results:
                    results = sf_results
                else:
                    return "错误: 文生图任务提交失败（DashScope 与 SiliconFlow 均失败，ComfyUI 本地未响应）"
            else:
                results = _poll_results(task_id, api_key)
                if not results:
                    # DashScope 轮询失败 → 降级 SiliconFlow
                    logger.warning("[image_gen] DashScope 轮询失败，降级到 SiliconFlow 备用通道")
                    sf_results = _sf_generate(prompt, size or "1024*1024")
                    if sf_results:
                        results = sf_results
                    else:
                        return f"错误: 文生图任务未返回结果（模型 {used_model}），SiliconFlow 与 ComfyUI 均失败"

    # 下载并保存到项目（可选）
    local_paths: List[str] = []
    if save_to_project and project_path:
        from app.core.sandbox import resolve_sandbox_path
        from pathlib import Path

        try:
            out_dir = resolve_sandbox_path(_IMAGE_OUTPUT_DIR, project_path)
        except Exception as e:  # noqa: BLE001
            return f"错误: 图片输出目录路径无效: {e}"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return f"错误: 创建图片输出目录失败: {e}"

        for i, url in enumerate(results):
            try:
                url_clean = str(url).strip()
                if os.path.exists(url_clean):
                    content = Path(url_clean).read_bytes()
                else:
                    img_resp = httpx.get(url_clean, timeout=HTTP_TIMEOUT, follow_redirects=True)
                    if img_resp.status_code != 200:
                        logger.warning("[image_gen] 图片下载失败 %s: %s", url_clean, img_resp.status_code)
                        continue
                    content = img_resp.content
                fname = f"generated_image_{int(time.time())}_{i + 1}.png"
                fpath = out_dir / fname
                fpath.write_bytes(content)
                local_paths.append(str(fpath))
            except Exception as e:  # noqa: BLE001
                logger.warning("[image_gen] 图片下载/保存失败: %s", e)
                continue

    if local_paths:
        # Phase H: 有 chat_id 时返回后端代理 URL（前端可直接渲染），否则返回绝对路径文本
        if chat_id is not None:
            lines = []
            abs_project = os.path.abspath(project_path)
            for i, p in enumerate(local_paths):
                rel = os.path.relpath(p, abs_project).replace("\\", "/")
                lines.append(f"![生成图片 {i + 1}](/api/chat/{chat_id}/generated_image?path={urllib.parse.quote(rel)})")
        else:
            lines = [f"![生成图片 {i + 1}]({os.path.abspath(p).replace(os.sep, '/')})" for i, p in enumerate(local_paths)]
        note = f"已保存 {len(local_paths)} 张图片到 {_IMAGE_OUTPUT_DIR}/"
        return "\n".join(lines) + f"\n{note}"
    lines = [f"![生成图片 {i + 1}]({url})" for i, url in enumerate(results)]
    return "\n".join(lines) + "\n图片未保存到本地（未绑定项目或保存失败），请通过上方 URL 查看。"


def _safe_json(text: str) -> dict:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _dashscope_error(resp: httpx.Response, action: str) -> str:
    """解析 dashscope 错误响应（标准格式: {"code": ..., "message": ..., "request_id": ...}）。"""
    data = _safe_json(resp.text)
    code = data.get("code") or resp.status_code
    message = data.get("message") or resp.text[:200]
    request_id = data.get("request_id", "")
    suffix = f"（request_id: {request_id}）" if request_id else ""
    return f"{action}失败（{code}）: {message[:300]}{suffix}"


IMAGE_GEN_TOOLS_DEFINITIONS: List[Dict] = [
    {\
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": (
                "根据提示词生成图片。底层自动支持本地 ComfyUI 服务（自动切模/高清放大）及云端千问生图。"
                "图片会保存到项目 output/generated_images/ 目录并返回本地路径"
                "（未绑定项目时只返回 URL）。"
                "适合需要配图、示意图、产品图、海报及美学风格图等场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "图片内容描述（建议包含主体、风格、构图等细节，中文英文均可）",
                    },
                    "size": {
                        "type": "string",
                        "description": "图片尺寸 宽*高（如 1024*1024 / 768*1024 / 1024*768），默认 1024*1024",
                    },
                    "n": {
                        "type": "integer",
                        "description": "生成张数 1-6，默认 1",
                    },
                    "model": {
                        "type": "string",
                        "description": "生图底模：本地 ComfyUI 支持 realistic(写实/水墨/胶片/Pantone)、counterfeit/artistic(精细插画/概念/超现实)、anime(二次元/日漫/贴纸)；云端支持 qwen-image-3.0-pro / qwen-image-3.0",
                    },
                    "hires": {
                        "type": "boolean",
                        "description": "是否开启二次高清放大与细节修复（适用于高质量海报/印刷级大图），默认 false",
                    },
                    "steps": {
                        "type": "integer",
                        "description": "采样步数，默认 20（高清模式建议 25-30）",
                    },
                    "filename": {
                        "type": "string",
                        "description": "自定义最终输出的显式中文/英文文件名（如 【昭和浪漫_夕阳奥特曼】SHOWA_01.png）",
                    },
                    "save_to_project": {
                        "type": "boolean",
                        "description": "是否下载保存到项目目录，默认 true",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
]

IMAGE_GEN_TOOLS = {
    "generate_image": generate_image,
}


def execute_image_gen_tool(name: str, project_path: str, chat_id: Optional[int] = None, **kwargs) -> str:
    """执行文生图工具并返回文本结果（失败返回错误说明）。"""
    fn = IMAGE_GEN_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, chat_id=chat_id, **kwargs)
    except Exception as e:  # noqa: BLE001
        return f"错误: {e}"


# ─── 质量门：按技能检查表生成自检提示 ──────────────────────────────────────────

def get_quality_checklist(skill_id: str) -> str:
    """返回指定技能的质量检查清单文本，供 Agent 出图后自检使用。

    Agent 在 generate_image 成功后调用本函数，把检查项告诉用户，
    引导用户（或视觉模型）逐条核对风格是否符合技能铁律。
    """
    try:
        from app.core.skill_catalog import IMAGE_SKILL_CATALOG
        for s in IMAGE_SKILL_CATALOG:
            if s["id"] == skill_id:
                checks = s.get("quality_checks", [])
                if not checks:
                    return ""
                lines = [f"**{s['name']}** 质量检查清单："]
                for i, c in enumerate(checks, 1):
                    lines.append(f"{i}. {c}")
                lines.append("\n> 请对照以上要点核查生成图片，不符合则建议重试（调整 Prompt 或换技能）。")
                return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        logger.debug("[image_gen] get_quality_checklist 失败: %s", e)
    return ""