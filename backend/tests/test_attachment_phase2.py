"""MfkAgent Phase 2 附件接收与上下文注入单元测试（严密版加固）。

覆盖：
  A. SendRequest 解析 attachments（Pydantic 模型校验）
  B. AttachmentItem 字段默认值
  C. _build_attachment_prompt 三种 kind 行为（严密版格式断言）
  D. _build_vision_context image 提取
  E. ChatContextBuilder.build 端到端附件注入（text + image + binary）
  F. _is_path_within 安全校验
  G. text 附件阶梯解码（UTF-8 → GBK → replace 兜底，严禁 UnicodeDecodeError）
  H. upload 端点：防覆盖前缀、10MB 超限拦截、无项目 400 防护、返回原始名

运行：
  python backend/tests/test_attachment_phase2.py

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

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phase2_attach_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase2_attach_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["MIMO_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import app.models.agent as _agent_models  # noqa: F401, E402
import app.models.persona as _persona_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base, SessionLocal  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from app.models.agent import Chat, Agent, Project  # noqa: E402
from app.api.chat import (  # noqa: E402
    AttachmentItem,
    SendRequest,
    _build_unique_disk_name,
    _detect_attachment_kind,
    MAX_UPLOAD_SIZE,
    upload_attachment,
)
from app.core.agent_runtime import get_chat_context_builder, ContextBuildInput  # noqa: E402
from app.core.agent_runtime.context_builder import (  # noqa: E402
    _build_attachment_prompt,
    _build_vision_context,
    _is_path_within,
    _read_text_attachment_ladder,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AGENT_ID = "phase2_general"


def _make_agent(db) -> None:
    if db.query(Agent).filter(Agent.agent_id == AGENT_ID).first():
        return
    db.add(Agent(
        agent_id=AGENT_ID,
        name="Phase2 Test Agent",
        identity="你是测试助手。",
        capabilities=[],
    ))
    db.commit()


def _make_project(db, project_path: str) -> Project:
    proj = db.query(Project).filter(Project.path == project_path).first()
    if proj:
        return proj
    proj = Project(name="Phase2Proj", path=project_path)
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj


def _make_chat(db, project: Project) -> Chat:
    chat = Chat(
        project_id=project.id,
        project_path=project.path,
        agent_id=AGENT_ID,
        title="Phase2 Chat",
        mode="build",
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def _make_chat_no_project(db) -> Chat:
    """创建未绑定项目的 Chat（用于 upload 无项目 400 测试）。"""
    chat = Chat(
        project_id=None,
        project_path=None,
        agent_id=AGENT_ID,
        title="NoProj Chat",
        mode="build",
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def _write_text_file(project_path: str, rel_path: str, content: str) -> str:
    """在项目目录内写一个文本文件，返回相对路径（正斜杠）。"""
    abs_path = os.path.join(project_path, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return rel_path


def _write_bytes_file(project_path: str, rel_path: str, data: bytes) -> str:
    """在项目目录内写一个二进制文件，返回相对路径（正斜杠）。"""
    abs_path = os.path.join(project_path, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "wb") as f:
        f.write(data)
    return rel_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

_results: list = []


def check(name: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def test_sendrequest_parse_attachments():
    """A. SendRequest 解析 attachments 数组"""
    payload = {
        "content": "请分析附件",
        "attachments": [
            {"name": "a.py", "path": "src/a.py", "mime": "text/x-python", "kind": "text", "size": 100},
            {"name": "img.png", "path": "assets/img.png", "mime": "image/png", "kind": "image", "size": 2048},
        ],
    }
    req = SendRequest.model_validate(payload)
    check("A1: attachments 长度为 2", len(req.attachments) == 2, f"got {len(req.attachments)}")
    check("A2: 第一个是 AttachmentItem", isinstance(req.attachments[0], AttachmentItem))
    check("A3: 第一个 name=a.py", req.attachments[0].name == "a.py")
    check("A4: 第二个 kind=image", req.attachments[1].kind == "image")

    # 空 attachments 默认值
    req_empty = SendRequest.model_validate({"content": "hi"})
    check("A5: 无 attachments 时默认空列表", req_empty.attachments == [], f"got {req_empty.attachments}")


def test_attachment_item_defaults():
    """B. AttachmentItem 默认值"""
    item = AttachmentItem(name="test.txt")
    check("B1: 默认 path=None", item.path is None)
    check("B2: 默认 mime=application/octet-stream", item.mime == "application/octet-stream")
    check("B3: 默认 kind=text", item.kind == "text")
    check("B4: 默认 size=0", item.size == 0)


def test_build_attachment_prompt_text(tmp_project_path):
    """C1. text 附件读取内容注入（严密版格式）"""
    rel = _write_text_file(tmp_project_path, "notes.txt", "hello world")
    atts = [AttachmentItem(name="notes.txt", path=rel, kind="text", mime="text/plain", size=11)]
    prompt = _build_attachment_prompt(atts, tmp_project_path)
    check("C1: text 附件内容注入", "hello world" in prompt, f"prompt={prompt[:200]}")
    check("C1b: 包含 <attachments> 标签", "<attachments>" in prompt)
    check("C1c: 严密格式 [附件上下文]", "[附件上下文]" in prompt)
    check("C1d: 严密格式 [文件: name]", "[文件: notes.txt]" in prompt)
    check("C1e: 严密格式含路径", "(notes.txt)" in prompt)


def test_build_attachment_prompt_image_not_in_prompt(tmp_project_path):
    """C2. image 附件不注入文件内容（仅名称+路径提示，严密版格式）"""
    _write_text_file(tmp_project_path, "pic.png", "fake-png")
    atts = [AttachmentItem(name="pic.png", path="pic.png", kind="image", mime="image/png", size=100)]
    prompt = _build_attachment_prompt(atts, tmp_project_path)
    check("C2: image 名称出现在说明", "pic.png" in prompt)
    check("C2b: image 文件内容不注入", "fake-png" not in prompt)
    check("C2c: 严密格式 [图片附件: name]", "[图片附件: pic.png]" in prompt)
    check("C2d: 严密格式含路径", "(pic.png)" in prompt)


def test_build_attachment_prompt_binary(tmp_project_path):
    """C3. binary 附件仅注入元数据（严密版格式）"""
    atts = [AttachmentItem(name="data.zip", path="data.zip", kind="binary", mime="application/zip", size=4096)]
    prompt = _build_attachment_prompt(atts, tmp_project_path)
    check("C3: binary 元数据注入", "data.zip" in prompt and "4096" in prompt)
    check("C3b: 严密格式 [二进制/压缩包附件: name]", "[二进制/压缩包附件: data.zip]" in prompt)
    check("C3c: 严密格式含大小", "大小: 4096B" in prompt)
    check("C3d: 严密格式含类型", "类型: application/zip" in prompt)


def test_build_attachment_prompt_path_traversal_blocked(tmp_project_path):
    """C4. 路径穿越攻击被阻断（../../etc/passwd 不注入内容）"""
    atts = [AttachmentItem(name="evil.txt", path="../../etc/passwd", kind="text")]
    prompt = _build_attachment_prompt(atts, tmp_project_path)
    # 应注入"无法读取"说明，而非文件内容
    check("C4: 穿越路径不注入内容", "无法读取" in prompt, f"prompt={prompt[:200]}")


def test_build_vision_context_image(tmp_project_path):
    """D. _build_vision_context 提取 image"""
    _write_text_file(tmp_project_path, "img.png", "fake")
    atts = [
        AttachmentItem(name="img.png", path="img.png", kind="image", mime="image/png", size=100),
        AttachmentItem(name="a.py", path="a.py", kind="text"),
    ]
    vc = _build_vision_context(atts, tmp_project_path)
    check("D1: vision_context 非 None", vc is not None)
    check("D2: images 长度为 1", len(vc["images"]) == 1)
    check("D3: image 绝对路径填充", vc["images"][0]["path"] is not None)
    check("D4: image name 正确", vc["images"][0]["name"] == "img.png")


def test_build_vision_context_no_image():
    """D2. 无 image 时返回 None"""
    atts = [AttachmentItem(name="a.py", path="a.py", kind="text")]
    vc = _build_vision_context(atts, "/tmp")
    check("D5: 无 image 返回 None", vc is None)


def test_context_builder_end_to_end(tmp_project_path):
    """E. ChatContextBuilder.build 端到端：text+image+binary 附件注入"""
    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project_path)
        chat = _make_chat(db, proj)

        _write_text_file(tmp_project_path, "readme.md", "# Title\nreadme content")
        _write_text_file(tmp_project_path, "pic.png", "fake-png-bytes")

        attachments = [
            AttachmentItem(name="readme.md", path="readme.md", kind="text", mime="text/markdown", size=20),
            AttachmentItem(name="pic.png", path="pic.png", kind="image", mime="image/png", size=12),
            AttachmentItem(name="arch.zip", path="arch.zip", kind="binary", mime="application/zip", size=9999),
        ]

        built = asyncio_run(get_chat_context_builder().build(
            ContextBuildInput(
                chat_id=chat.id,
                content="分析这些附件",
                use_tools=False,  # 避免 tool_runtime 依赖外部目录
                attachments=attachments,
            )
        ))

        check("E1: system_prompt 含文本附件内容", "readme content" in built.system_prompt)
        check("E2: system_prompt 含 binary 元数据", "arch.zip" in built.system_prompt and "9999" in built.system_prompt)
        check("E3: system_prompt 含图片说明段", "pic.png" in built.system_prompt)
        check("E4: vision_context 非 None", built.context.vision_context is not None)
        check("E5: vision_context 含 1 张图", len(built.context.vision_context["images"]) == 1)
    finally:
        db.close()


def test_is_path_within():
    """F. _is_path_within 安全校验"""
    base = _TEMP_DIR
    inside = os.path.join(str(base), "sub", "file.txt")
    os.makedirs(os.path.dirname(inside), exist_ok=True)
    with open(inside, "w") as f:
        f.write("x")
    outside = os.path.join(tempfile.gettempdir(), "outside_file.txt")
    check("F1: 项目内文件 True", _is_path_within(str(base), inside))
    check("F2: 项目外文件 False", not _is_path_within(str(base), outside))
    check("F3: 空路径 False", not _is_path_within("", inside))


# ── G. 阶梯解码（UTF-8 → GBK → replace 兜底）─────────────────────────────

def test_ladder_decode_utf8(tmp_project_path):
    """G1. UTF-8 文件正确解码"""
    rel = _write_text_file(tmp_project_path, "utf8.txt", "你好世界 hello")
    abs_path = os.path.join(tmp_project_path, rel)
    text = _read_text_attachment_ladder(abs_path)
    check("G1: UTF-8 文件解码正确", text == "你好世界 hello", f"got {text!r}")


def test_ladder_decode_gbk(tmp_project_path):
    """G2. GBK 文件正确解码（UTF-8 失败 → GBK 成功）"""
    # 写入 GBK 编码的中文（UTF-8 无法解码）
    gbk_bytes = "中文GBK编码文件".encode("gbk")
    rel = _write_bytes_file(tmp_project_path, "gbk.txt", gbk_bytes)
    abs_path = os.path.join(tmp_project_path, rel)
    text = _read_text_attachment_ladder(abs_path)
    check("G2: GBK 文件解码正确", text == "中文GBK编码文件", f"got {text!r}")


def test_ladder_decode_invalid_bytes_replace(tmp_project_path):
    """G3. 无效字节兜底 replace（不抛 UnicodeDecodeError）"""
    # 构造既非合法 UTF-8 也非合法 GBK 的字节序列
    # 0xFF 0xFE 是 UTF-16 LE BOM，单独字节在 UTF-8/GBK 都非法
    invalid_bytes = b"\xff\xfe\x00\x80\x81"
    rel = _write_bytes_file(tmp_project_path, "invalid.bin", invalid_bytes)
    abs_path = os.path.join(tmp_project_path, rel)
    try:
        text = _read_text_attachment_ladder(abs_path)
        check("G3: 无效字节不抛异常", text is not None)
        # replace 兜底会含替换符，但不应是空（除非全部被跳过）
        check("G3b: 兜底返回字符串", isinstance(text, str))
    except UnicodeDecodeError:
        check("G3: 无效字节不抛异常", False, "抛出了 UnicodeDecodeError")


def test_ladder_decode_nonexistent_returns_none():
    """G4. 不存在的文件返回 None（不抛 OSError）"""
    text = _read_text_attachment_ladder("/nonexistent/path/file.txt")
    check("G4: 不存在文件返回 None", text is None)


def test_ladder_decode_via_prompt(tmp_project_path):
    """G5. GBK 文件经 _build_attachment_prompt 正确注入（端到端解码）"""
    gbk_bytes = "GBK附件内容".encode("gbk")
    rel = _write_bytes_file(tmp_project_path, "gbk_doc.txt", gbk_bytes)
    atts = [AttachmentItem(name="gbk_doc.txt", path=rel, kind="text", mime="text/plain", size=len(gbk_bytes))]
    prompt = _build_attachment_prompt(atts, tmp_project_path)
    check("G5: GBK 内容经阶梯解码注入 Prompt", "GBK附件内容" in prompt, f"prompt={prompt[:200]}")
    # 用 Unicode 转义表示替换符 U+FFFD，避免源码编码问题
    REPLACEMENT_CHAR = "\ufffd"
    content_part = prompt.split("[文件: gbk_doc.txt]")[1] if "[文件: gbk_doc.txt]" in prompt else ""
    check("G5b: 未出现乱码替换符", REPLACEMENT_CHAR not in content_part, f"content_part={content_part!r}")


# ── H. upload 端点（防覆盖前缀 + 超限拦截 + 无项目 400 + 返回原始名）─────

class _FakeUploadFile:
    """模拟 fastapi.UploadFile，供 upload_attachment 测试用。"""

    def __init__(self, filename: str, data: bytes, content_type: str = "application/octet-stream"):
        self.filename = filename
        self._data = data
        self._pos = 0
        self.content_type = content_type

    async def read(self, size: int = -1) -> bytes:
        if size <= 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
            return chunk
        chunk = self._data[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


def test_build_unique_disk_name():
    """H1. 防覆盖磁盘文件名生成（始终含 timestamp_uuid 前缀）"""
    name1 = _build_unique_disk_name("test.png")
    name2 = _build_unique_disk_name("test.png")
    check("H1a: 含原始文件名", name1.endswith("_test.png"))
    check("H1b: 含 timestamp 前缀", name1.split("_")[0].isdigit())
    check("H1c: 两次生成不同（uuid 随机）", name1 != name2, f"{name1} == {name2}")

    # 路径穿越防护
    name3 = _build_unique_disk_name("../../etc/passwd")
    check("H1d: basename 防穿越（不含路径分隔符）", "/" not in name3 and "\\" not in name3)
    check("H1e: basename 防穿越（含 passwd）", name3.endswith("_passwd"))


def test_upload_attachment_basic(tmp_project_path):
    """H2. upload 端点基本流程：落盘 + 返回原始名 + 路径含前缀"""
    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project_path)
        chat = _make_chat(db, proj)

        file_data = b"hello upload content"
        fake_file = _FakeUploadFile("upload.txt", file_data, "text/plain")

        result = asyncio_run(upload_attachment(chat.id, fake_file))

        check("H2a: 返回 name=原始文件名", result.name == "upload.txt", f"got {result.name}")
        check("H2b: 返回 path 含 .mfkagent/uploads/", ".mfkagent/uploads/" in result.path)
        check("H2c: 返回 path 含前缀（非原始名直接落盘）",
              not result.path.endswith("/upload.txt"),
              f"path={result.path}")
        check("H2d: 返回 size 正确", result.size == len(file_data))
        check("H2e: 返回 mime 正确", result.mime == "text/plain")
        check("H2f: 返回 kind=text", result.kind == "text")

        # 验证磁盘文件确实落盘且带前缀
        disk_filename = os.path.basename(result.path)
        check("H2g: 磁盘文件名含前缀", disk_filename != "upload.txt" and "upload.txt" in disk_filename)
        disk_abs = os.path.join(tmp_project_path, result.path.replace("/", os.sep))
        with open(disk_abs, "rb") as f:
            disk_content = f.read()
        check("H2h: 磁盘内容正确", disk_content == file_data)
    finally:
        db.close()


def test_upload_attachment_no_overwrite(tmp_project_path):
    """H3. 同名文件上传两次不覆盖（始终加唯一前缀）"""
    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project_path)
        chat = _make_chat(db, proj)

        # 第一次上传
        fake1 = _FakeUploadFile("same.txt", b"first content", "text/plain")
        result1 = asyncio_run(upload_attachment(chat.id, fake1))

        # 第二次上传同名文件
        fake2 = _FakeUploadFile("same.txt", b"second content", "text/plain")
        result2 = asyncio_run(upload_attachment(chat.id, fake2))

        check("H3a: 两次返回 name 相同（原始名）", result1.name == result2.name == "same.txt")
        check("H3b: 两次 path 不同（防覆盖）", result1.path != result2.path,
              f"path1={result1.path} path2={result2.path}")

        # 验证两个磁盘文件都存在，内容各自正确
        disk1 = os.path.join(tmp_project_path, result1.path.replace("/", os.sep))
        disk2 = os.path.join(tmp_project_path, result2.path.replace("/", os.sep))
        with open(disk1, "rb") as f:
            check("H3c: 第一次文件内容保留", f.read() == b"first content")
        with open(disk2, "rb") as f:
            check("H3d: 第二次文件内容正确", f.read() == b"second content")
    finally:
        db.close()


def test_upload_attachment_oversized(tmp_project_path):
    """H4. 超过 10MB 上限被拦截（返回 400，残留文件清理）"""
    from fastapi import HTTPException

    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project_path)
        chat = _make_chat(db, proj)

        # 构造 11MB 数据（超过 10MB 上限）
        oversized_data = b"x" * (MAX_UPLOAD_SIZE + 1024)
        fake_file = _FakeUploadFile("big.bin", oversized_data, "application/octet-stream")

        try:
            asyncio_run(upload_attachment(chat.id, fake_file))
            check("H4: 超限文件应抛 400", False, "未抛异常")
        except HTTPException as e:
            check("H4: 超限文件抛 400", e.status_code == 400, f"got {e.status_code}")
            check("H4b: 错误信息含大小提示", "过大" in e.detail or "10MB" in str(e.detail))

        # 验证残留文件已清理（uploads 目录下不应有大文件）
        upload_dir = os.path.join(tmp_project_path, ".mfkagent", "uploads")
        if os.path.isdir(upload_dir):
            for fname in os.listdir(upload_dir):
                fpath = os.path.join(upload_dir, fname)
                check("H4c: 残留文件已清理", os.path.getsize(fpath) <= MAX_UPLOAD_SIZE,
                      f"{fname} 仍存在且超大")
    finally:
        db.close()


def test_upload_attachment_no_project(tmp_project_path):
    """H5. 未关联项目的 Chat 上传走全局上传目录（功能变更：不再 400）"""
    db = SessionLocal()
    try:
        _make_agent(db)
        chat = _make_chat_no_project(db)

        fake_file = _FakeUploadFile("no_proj.txt", b"some content", "text/plain")

        result = asyncio_run(upload_attachment(chat.id, fake_file))
        # 无项目时落盘到 backend/data/uploads/{chat_id}/，返回绝对路径
        check("H5a: 无项目上传成功", result.name == "no_proj.txt")
        check("H5b: 无项目 path 为绝对路径", os.path.isabs(result.path),
              f"path={result.path}")
        check("H5c: 无项目 path 含 uploads/{chat_id}",
              f"uploads/{chat.id}" in result.path.replace(os.sep, "/"),
              f"path={result.path}")
        check("H5d: 磁盘文件存在", os.path.isfile(result.path))
    finally:
        db.close()


def test_upload_attachment_image_kind(tmp_project_path):
    """H6. 图片附件 kind 推断正确"""
    db = SessionLocal()
    try:
        _make_agent(db)
        proj = _make_project(db, tmp_project_path)
        chat = _make_chat(db, proj)

        # 最小合法 PNG（8 字节头）
        png_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        fake_file = _FakeUploadFile("photo.png", png_data, "image/png")

        result = asyncio_run(upload_attachment(chat.id, fake_file))
        check("H6a: 图片 kind=image", result.kind == "image")
        check("H6b: 返回 name=原始名", result.name == "photo.png")
        check("H6c: path 含 .mfkagent/uploads/", ".mfkagent/uploads/" in result.path)
    finally:
        db.close()


# ── I. _detect_attachment_kind 回归测试（MIME 优先 + 扩展名兜底）──────────

def test_detect_kind_mime_png():
    """I1. image/png MIME 直接识别为 image（标准情况）"""
    kind = _detect_attachment_kind("photo.png", "image/png")
    check("I1: image/png -> image", kind == "image", f"got {kind}")


def test_detect_kind_octet_stream_png_fallback():
    """I2. application/octet-stream + xxx.png 扩展名兜底识别为 image

    复现场景：部分浏览器/代理上传图片时 MIME 退化为 octet-stream，
    原逻辑返回 binary，导致 vision_context 为 None。修复后必须按扩展名兜底。
    """
    kind = _detect_attachment_kind("photo.png", "application/octet-stream")
    check("I2: octet-stream + xxx.png -> image", kind == "image", f"got {kind}")


def test_detect_kind_txt():
    """I3. 纯文本附件识别为 text"""
    kind = _detect_attachment_kind("notes.txt", "text/plain")
    check("I3: txt -> text", kind == "text", f"got {kind}")


def test_detect_kind_image_extensions():
    """I4. 常见图片扩展名均识别为 image（覆盖 jpg/jpeg/gif/webp/bmp）"""
    cases = [
        ("a.jpg", "application/octet-stream"),
        ("a.jpeg", "application/octet-stream"),
        ("a.gif", "application/octet-stream"),
        ("a.webp", "application/octet-stream"),
        ("a.bmp", "application/octet-stream"),
        ("a.svg", "application/octet-stream"),
    ]
    for fname, mime in cases:
        kind = _detect_attachment_kind(fname, mime)
        check(f"I4: {fname} -> image", kind == "image", f"got {kind}")


def test_detect_kind_text_extensions_preserved():
    """I5. text 扩展名分类逻辑保持不变（py/md/json 仍为 text）"""
    cases = [
        ("a.py", "text/x-python"),
        ("a.py", "application/octet-stream"),
        ("a.md", "text/markdown"),
        ("a.json", "application/json"),
    ]
    for fname, mime in cases:
        kind = _detect_attachment_kind(fname, mime)
        check(f"I5: {fname}({mime}) -> text", kind == "text", f"got {kind}")


def test_detect_kind_binary_preserved():
    """I6. 非图片/非文本扩展名仍归为 binary（zip/exe/未知）"""
    cases = [
        ("a.zip", "application/zip"),
        ("a.zip", "application/octet-stream"),
        ("a.exe", "application/octet-stream"),
        ("unknown", "application/octet-stream"),
    ]
    for fname, mime in cases:
        kind = _detect_attachment_kind(fname, mime)
        check(f"I6: {fname}({mime}) -> binary", kind == "binary", f"got {kind}")


def test_detect_kind_case_insensitive_ext():
    """I7. 扩展名大小写不敏感（.PNG/.Jpg 均识别为 image）"""
    cases = [("PHOTO.PNG", "application/octet-stream"),
             ("Photo.Jpg", "application/octet-stream")]
    for fname, mime in cases:
        kind = _detect_attachment_kind(fname, mime)
        check(f"I7: {fname} -> image", kind == "image", f"got {kind}")


def test_detect_kind_empty_mime():
    """I8. 空 MIME 时按扩展名兜底（png -> image, txt -> text）"""
    check("I8a: 空 mime + png -> image",
          _detect_attachment_kind("a.png", "") == "image")
    check("I8b: 空 mime + txt -> text",
          _detect_attachment_kind("a.txt", "") == "text")
    check("I8c: 空 mime + zip -> binary",
          _detect_attachment_kind("a.zip", "") == "binary")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

def asyncio_run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已有运行中 loop（罕见），新建线程跑
            import threading
            result = [None]
            def _run():
                new_loop = asyncio.new_event_loop()
                result[0] = new_loop.run_until_complete(coro)
                new_loop.close()
            t = threading.Thread(target=_run)
            t.start()
            t.join()
            return result[0]
    except RuntimeError:
        pass
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Phase 2 附件单元测试（严密版加固）")
    print("=" * 60)

    # 独立临时项目目录（供 C/D/G/H 组测试用）
    proj_dir = _TEMP_DIR / "proj"
    proj_dir.mkdir(exist_ok=True)
    tmp_project_path = str(proj_dir)

    test_sendrequest_parse_attachments()
    test_attachment_item_defaults()
    test_build_attachment_prompt_text(tmp_project_path)
    test_build_attachment_prompt_image_not_in_prompt(tmp_project_path)
    test_build_attachment_prompt_binary(tmp_project_path)
    test_build_attachment_prompt_path_traversal_blocked(tmp_project_path)
    test_build_vision_context_image(tmp_project_path)
    test_build_vision_context_no_image()
    test_context_builder_end_to_end(tmp_project_path)
    test_is_path_within()

    # G 组：阶梯解码
    test_ladder_decode_utf8(tmp_project_path)
    test_ladder_decode_gbk(tmp_project_path)
    test_ladder_decode_invalid_bytes_replace(tmp_project_path)
    test_ladder_decode_nonexistent_returns_none()
    test_ladder_decode_via_prompt(tmp_project_path)

    # H 组：upload 端点
    test_build_unique_disk_name()
    test_upload_attachment_basic(tmp_project_path)
    test_upload_attachment_no_overwrite(tmp_project_path)
    test_upload_attachment_oversized(tmp_project_path)
    test_upload_attachment_no_project(tmp_project_path)
    test_upload_attachment_image_kind(tmp_project_path)

    # I 组：_detect_attachment_kind 回归（MIME 优先 + 扩展名兜底）
    test_detect_kind_mime_png()
    test_detect_kind_octet_stream_png_fallback()
    test_detect_kind_txt()
    test_detect_kind_image_extensions()
    test_detect_kind_text_extensions_preserved()
    test_detect_kind_binary_preserved()
    test_detect_kind_case_insensitive_ext()
    test_detect_kind_empty_mime()

    print("=" * 60)
    passed = sum(1 for s, _, _ in _results if s == "PASS")
    failed = sum(1 for s, _, _ in _results if s == "FAIL")
    total = len(_results)
    print(f"总计: {total} | 通过: {passed} | 失败: {failed}")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
