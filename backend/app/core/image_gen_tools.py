"""文生图工具 —— 千问图像生成（qwen-image）API 接入，供 LLM Function Calling 使用。

Phase H (super_enhance_20260818) 新增，2026-08-18 实测修正（用户 key 实测通过）：
- 实测确认：该账号（sk-ws-* 千问聚合 key）可用模型为 qwen-image-3.0 / qwen-image-3.0-pro
  （wanx 系列在此账号返回 AccessDenied / Model not exist，勿回退 wanx 端点）。
- 调用方式（千问图像生成 3.0 文档）：
  1. POST /api/v1/services/aigc/image-generation/generation 提交任务，
     请求头必须带 X-DashScope-Async: enable（否则报 "current user api does not support synchronous calls"）。
  2. 轮询 GET /api/v1/tasks/{task_id} 直至 SUCCEEDED。
  3. 结果在 output.choices[].message.content[].image（OpenAI 兼容 messages 结构）。
- 实测单张 1024*1024 生成耗时约 9 分钟（prompt_extend + enable_thinking 默认开启），
  因此轮询上限放宽至 900s、间隔 5s。
- API Key 读取：settings 表 api_key_qwen > .env 的 QWEN_API_KEY（复用 ModelConfigAdapter）。
- 无 project_path 时仅返回图片 URL（不落盘）。
- 所有异常/失败返回以 "错误:" 开头（与既有工具约定一致，executor 判定 failed）。
"""
import json
import logging
import os
import time
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
    save_to_project: bool = True,
    chat_id: Optional[int] = None,
) -> str:
    """根据提示词生成图片，返回 Markdown 可渲染的图片引用（本地路径或 URL）。

    Args:
        prompt: 图片描述提示词（必填，中英文均可）
        size: 尺寸，宽*高（如 1024*1024），面积范围 512*512 ~ 2048*2048
        n: 生成张数（1-6，默认 1）
        model: 千问图像模型（默认 qwen-image-3.0-pro；可用 qwen-image-3.0）
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

    api_key = _resolve_qwen_key()
    if not api_key:
        return "错误: 未配置 QWEN_API_KEY（settings 表 api_key_qwen 或 .env），无法调用千问文生图"

    # 主模型提交失败时依次尝试回退模型
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
        return "错误: 文生图任务提交失败（所有可用模型均失败），请检查 API Key 权限或稍后重试"

    results = _poll_results(task_id, api_key)
    if not results:
        return f"错误: 文生图任务未返回结果（模型 {used_model}，可能超时/失败，请稍后重试）"

    # 下载并保存到项目（可选）
    local_paths: List[str] = []
    if save_to_project and project_path:
        from app.core.sandbox import resolve_sandbox_path

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
                img_resp = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True)
                if img_resp.status_code != 200:
                    logger.warning("[image_gen] 图片下载失败 %s: %s", url, img_resp.status_code)
                    continue
                fname = f"qwen_image_{int(time.time())}_{i + 1}.png"
                fpath = out_dir / fname
                fpath.write_bytes(img_resp.content)
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
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": (
                "根据提示词生成图片（千问 qwen-image 文生图）。"
                "图片会保存到项目 output/generated_images/ 目录并返回本地路径"
                "（未绑定项目时只返回 URL）。"
                "注意：生成耗时较长（通常 3-10 分钟），提交后需耐心等待结果。"
                "适合需要配图、示意图、产品图等场景。"
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
                        "description": "图片尺寸 宽*高（如 1024*1024），面积范围 512*512 ~ 2048*2048，默认 1024*1024",
                    },
                    "n": {
                        "type": "integer",
                        "description": "生成张数 1-6，默认 1",
                    },
                    "model": {
                        "type": "string",
                        "description": "千问图像模型：qwen-image-3.0-pro（默认，质量优先）或 qwen-image-3.0（速度更快）",
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