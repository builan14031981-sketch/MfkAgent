"""MfkAgent Phase 2 多模态与附件端点单元测试。

覆盖：
  A. ProviderDef.supports_vision 能力位
  B. Message.content 多模态类型兼容（str / List[dict]）
  C. _image_to_data_uri 图片转 base64 data URI
  D. _inject_vision_into_messages 视觉注入逻辑
  E. _provider_supports_vision 查询
  F. projects.py attachment 端点（base64 返回 + 安全校验）

运行：
  python backend/tests/test_multimodal_phase2.py

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import os
import sys
import tempfile
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phase2_mm_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase2_mm_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.services.model import (  # noqa: E402
    Message,
    _image_to_data_uri,
    _inject_vision_into_messages,
    _provider_supports_vision,
)
from app.core.model_providers import PROVIDERS, PROVIDER_MAP  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_results: list = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


# ── A. ProviderDef.supports_vision ──────────────────────────────────────

def test_provider_vision_flags():
    """A. supports_vision 能力位正确设置"""
    vision_providers = {p.id for p in PROVIDERS if p.supports_vision}
    check("A1: google 支持 vision", "google" in vision_providers)
    check("A2: qwen 不支持 vision（粒度下沉到 Model 级）", "qwen" not in vision_providers)
    check("A3: glm 不支持 vision（粒度下沉到 Model 级）", "glm" not in vision_providers)
    check("A4: deepseek 不支持 vision", "deepseek" not in vision_providers)
    check("A5: mimo 不支持 vision", "mimo" not in vision_providers)


# ── B. Message.content 多模态类型 ───────────────────────────────────────

def test_message_content_types():
    """B. Message.content 兼容 str 与 List[dict]"""
    # str 赋值（现有用法）
    m1 = Message(role="user", content="你好")
    check("B1: str content 正常", m1.content == "你好")

    # List[dict] 赋值（多模态）
    m2 = Message(role="user", content=[
        {"type": "text", "text": "看这张图"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxx"}},
    ])
    check("B2: List[dict] content 正常", isinstance(m2.content, list) and len(m2.content) == 2)
    check("B3: 第一项是 text", m2.content[0]["type"] == "text")
    check("B4: 第二项是 image_url", m2.content[1]["type"] == "image_url")


# ── C. _image_to_data_uri ───────────────────────────────────────────────

def test_image_to_data_uri():
    """C. 图片文件转 base64 data URI"""
    # 创建一个假 PNG 文件（8 字节头 + 数据）
    img_path = str(_TEMP_DIR / "test.png")
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake_image_data"
    with open(img_path, "wb") as f:
        f.write(png_bytes)

    data_uri = _image_to_data_uri(img_path, "image/png")
    check("C1: data_uri 非 None", data_uri is not None)
    check("C2: data_uri 前缀正确", data_uri.startswith("data:image/png;base64,"))
    check("C3: base64 内容非空", len(data_uri) > len("data:image/png;base64,"))

    # 不存在的文件
    check("C4: 不存在文件返回 None", _image_to_data_uri("/nonexistent/x.png", "image/png") is None)


# ── D. _inject_vision_into_messages ─────────────────────────────────────

def test_inject_vision_str_content():
    """D1. str content → 多模态数组"""
    img_path = str(_TEMP_DIR / "inj1.png")
    with open(img_path, "wb") as f:
        f.write(b"png-data")

    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "分析这张图"},
    ]
    vision_ctx = {"images": [{"path": img_path, "mime": "image/png"}]}

    result = _inject_vision_into_messages(messages, vision_ctx, True)
    check("D1a: 消息数量不变", len(result) == 2)
    user_msg = result[1]
    check("D1b: user content 变为 list", isinstance(user_msg["content"], list))
    check("D1c: 第一项是 text", user_msg["content"][0]["type"] == "text")
    check("D1d: 文本内容保留", user_msg["content"][0]["text"] == "分析这张图")
    check("D1e: 第二项是 image_url", user_msg["content"][1]["type"] == "image_url")
    check("D1f: image_url 含 data URI", user_msg["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))


def test_inject_vision_no_user_message():
    """D2. 无 user 消息时不改动"""
    messages = [{"role": "system", "content": "sys"}]
    vision_ctx = {"images": [{"path": str(_TEMP_DIR / "inj1.png"), "mime": "image/png"}]}
    result = _inject_vision_into_messages(messages, vision_ctx, True)
    check("D2: 无 user 时不改动", result[0]["content"] == "sys")


def test_inject_vision_provider_not_supported():
    """D3. provider 不支持 vision 时不改动"""
    messages = [{"role": "user", "content": "hello"}]
    vision_ctx = {"images": [{"path": str(_TEMP_DIR / "inj1.png"), "mime": "image/png"}]}
    result = _inject_vision_into_messages(messages, vision_ctx, False)
    check("D3: 不支持 vision 时 content 保持 str", result[0]["content"] == "hello")


def test_inject_vision_empty_context():
    """D4. vision_context 为空时不改动"""
    messages = [{"role": "user", "content": "hello"}]
    check("D4a: None 不改动", _inject_vision_into_messages(messages, None, True) == messages)
    check("D4b: 空 images 不改动", _inject_vision_into_messages(messages, {"images": []}, True) == messages)


def test_inject_vision_list_content():
    """D5. content 已是 list 时追加图片"""
    img_path = str(_TEMP_DIR / "inj2.png")
    with open(img_path, "wb") as f:
        f.write(b"png2")
    messages = [{"role": "user", "content": [{"type": "text", "text": "已有文本"}]}]
    vision_ctx = {"images": [{"path": img_path, "mime": "image/png"}]}
    result = _inject_vision_into_messages(messages, vision_ctx, True)
    check("D5: list content 追加图片", len(result[0]["content"]) == 2)
    check("D5b: 追加项是 image_url", result[0]["content"][1]["type"] == "image_url")


def test_inject_vision_file_not_found():
    """D6. 图片文件不存在时跳过，不中断"""
    messages = [{"role": "user", "content": "hello"}]
    vision_ctx = {"images": [{"path": "/nonexistent/x.png", "mime": "image/png"}]}
    result = _inject_vision_into_messages(messages, vision_ctx, True)
    check("D6: 文件不存在时 content 不改动", result[0]["content"] == "hello")


def test_inject_vision_original_messages_unchanged():
    """D7. 注入不修改原 messages 列表（深拷贝）"""
    img_path = str(_TEMP_DIR / "inj1.png")
    messages = [{"role": "user", "content": "原始"}]
    vision_ctx = {"images": [{"path": img_path, "mime": "image/png"}]}
    _ = _inject_vision_into_messages(messages, vision_ctx, True)
    check("D7: 原 messages 不被修改", messages[0]["content"] == "原始")


# ── E. _provider_supports_vision ────────────────────────────────────────

def test_provider_supports_vision_query():
    """E. _provider_supports_vision 查询"""
    check("E1: google 支持", _provider_supports_vision("google") is True)
    check("E2: qwen 不支持（粒度下沉到 Model 级）", _provider_supports_vision("qwen") is False)
    check("E3: glm 不支持（粒度下沉到 Model 级）", _provider_supports_vision("glm") is False)
    check("E4: deepseek 不支持", _provider_supports_vision("deepseek") is False)
    check("E5: 未知 provider 不支持", _provider_supports_vision("unknown") is False)


# ── F. attachment 端点 ──────────────────────────────────────────────────

def test_attachment_endpoint():
    """F. projects.py attachment 端点（base64 返回）"""
    from app.api.projects import read_attachment, _ATTACHMENT_ALLOWED_EXTS
    from app.models.agent import Project
    import asyncio

    db = SessionLocal()
    try:
        # 创建项目
        proj_dir = _TEMP_DIR / "attach_proj"
        proj_dir.mkdir(exist_ok=True)
        proj = db.query(Project).filter(Project.path == str(proj_dir)).first()
        if not proj:
            proj = Project(name="AttachProj", path=str(proj_dir))
            db.add(proj)
            db.commit()
            db.refresh(proj)

        # 写入测试图片
        img_rel = "test.png"
        img_abs = str(proj_dir / img_rel)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"attachment_test"
        with open(img_abs, "wb") as f:
            f.write(png_bytes)

        # 调用端点
        result = asyncio.run(
            read_attachment(proj.id, img_rel)
        )
        check("F1: 返回 path 正确", result.path == img_rel)
        check("F2: 返回 mime 正确", result.mime == "image/png")
        check("F3: 返回 size 正确", result.size == len(png_bytes))
        check("F4: 返回 encoding=base64", result.encoding == "base64")
        check("F5: content_base64 非空", len(result.content_base64) > 0)

        # 验证 base64 可解码回原文
        import base64 as b64mod
        decoded = b64mod.b64decode(result.content_base64)
        check("F6: base64 解码还原", decoded == png_bytes)

        # 白名单校验
        check("F7: .png 在白名单", ".png" in _ATTACHMENT_ALLOWED_EXTS)
        check("F8: .txt 不在白名单", ".txt" not in _ATTACHMENT_ALLOWED_EXTS)
    finally:
        db.close()


def test_attachment_security():
    """F2. attachment 端点安全校验（路径穿越 + 类型白名单）"""
    from app.api.projects import read_attachment
    from app.models.agent import Project
    from fastapi import HTTPException
    import asyncio

    db = SessionLocal()
    try:
        proj_dir = _TEMP_DIR / "attach_sec_proj"
        proj_dir.mkdir(exist_ok=True)
        proj = db.query(Project).filter(Project.path == str(proj_dir)).first()
        if not proj:
            proj = Project(name="AttachSec", path=str(proj_dir))
            db.add(proj)
            db.commit()
            db.refresh(proj)

        # 路径穿越攻击
        try:
            asyncio.run(
                read_attachment(proj.id, "../../etc/passwd")
            )
            check("F9: 路径穿越被拦截", False, "未抛异常")
        except HTTPException as e:
            check("F9: 路径穿越被拦截", e.status_code == 400)

        # 不允许的扩展名（.txt）
        txt_path = proj_dir / "evil.txt"
        with open(txt_path, "w") as f:
            f.write("not allowed")
        try:
            asyncio.run(
                read_attachment(proj.id, "evil.txt")
            )
            check("F10: .txt 被白名单拒绝", False, "未抛异常")
        except HTTPException as e:
            check("F10: .txt 被白名单拒绝", e.status_code == 400)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Phase 2 多模态与附件端点单元测试")
    print("=" * 60)

    test_provider_vision_flags()
    test_message_content_types()
    test_image_to_data_uri()
    test_inject_vision_str_content()
    test_inject_vision_no_user_message()
    test_inject_vision_provider_not_supported()
    test_inject_vision_empty_context()
    test_inject_vision_list_content()
    test_inject_vision_file_not_found()
    test_inject_vision_original_messages_unchanged()
    test_provider_supports_vision_query()
    test_attachment_endpoint()
    test_attachment_security()

    print("=" * 60)
    passed = sum(1 for s, _, _ in _results if s == "PASS")
    failed = sum(1 for s, _, _ in _results if s == "FAIL")
    total = len(_results)
    print(f"总计: {total} | 通过: {passed} | 失败: {failed}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
