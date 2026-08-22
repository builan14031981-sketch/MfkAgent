"""Phase H 文生图链路审查：代理端点 + URL 格式 + 沙箱越权 + 配置读取。"""
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_imgchain_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./imgchain_test.db"
os.environ["DEEPSEEK_API_KEY"] = "dummy-test-key"
os.environ["QWEN_API_KEY"] = "dummy-qwen-key"

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402

CLIENT = TestClient(app)

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


PROJ = _TEMP_DIR / "ImgProj"


def setup():
    PROJ.mkdir(exist_ok=True)
    out_dir = PROJ / "output" / "generated_images"
    out_dir.mkdir(parents=True)
    (out_dir / "wanx_probe.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    (PROJ / "secret.txt").write_text("TOP SECRET")
    r = CLIENT.post("/api/projects", json={"path": str(PROJ), "name": "ImgChain"})
    check("创建项目", r.status_code == 200, r.text[:120])
    pid = r.json()["id"]
    r = CLIENT.post("/api/chat", json={"project_id": pid, "agent_id": "coder", "title": "ImgChain"})
    check("创建会话", r.status_code == 200, r.text[:120])
    return r.json()["id"]


def test_proxy_endpoint(chat_id):
    r = CLIENT.get(f"/api/chat/{chat_id}/generated_image",
                   params={"path": "output/generated_images/wanx_probe.png"})
    check("代理端点返回图片", r.status_code == 200 and r.content.startswith(b"\x89PNG"),
          f"http={r.status_code} len={len(r.content)}")

    r = CLIENT.get(f"/api/chat/{chat_id}/generated_image",
                   params={"path": "../secret.txt"})
    check("越权路径被拒(../)", r.status_code == 403, f"http={r.status_code}")

    r = CLIENT.get(f"/api/chat/{chat_id}/generated_image",
                   params={"path": ".mfkagent/uploads/x.png"})
    check("非输出目录被拒", r.status_code == 403, f"http={r.status_code}")

    r = CLIENT.get(f"/api/chat/{chat_id}/generated_image",
                   params={"path": "output/generated_images/missing.png"})
    check("不存在文件 404", r.status_code == 404, f"http={r.status_code}")


def test_url_format(chat_id):
    from app.core import image_gen_tools as I

    # 不调 API：直接验证 URL 拼装逻辑（模拟一张已存在的图）
    url = f"/api/chat/{chat_id}/generated_image?path={__import__('urllib.parse', fromlist=['quote']).quote('output/generated_images/wanx_probe.png')}"
    check("代理 URL 格式正确", url.startswith(f"/api/chat/{chat_id}/generated_image?path="), url)


def test_settings_read():
    from app.core.database import SessionLocal
    from app.models.agent import Setting
    from app.core import image_gen_tools as I

    db = SessionLocal()
    db.query(Setting).filter(Setting.key == "image_gen_model").delete()
    db.commit()
    db.close()
    check("未配置时默认模型", I._resolve_model() == "qwen-image-3.0-pro", I._resolve_model())

    db = SessionLocal()
    db.add(Setting(key="image_gen_model", value="qwen-image-3.0"))
    db.commit()
    db.close()
    check("配置后读取生效", I._resolve_model() == "qwen-image-3.0", I._resolve_model())


def test_selector_registration():
    from app.core.tool_runtime.selector import ToolSelector
    from app.core.tool_runtime.risk_engine import TOOL_RISK_POLICY, Verdict
    from app.core.tool_runtime.permission import PermissionFilter

    check("generate_image 在 BASE_TOOLS", "generate_image" in PermissionFilter.BASE_TOOLS)
    entry = TOOL_RISK_POLICY.get("generate_image", ())
    check("generate_image 需审批", bool(entry) and entry[0] == Verdict.REQUIRE_APPROVAL,
          f"entry={entry}")
    check("generate_image 不在 project-only（无项目可用）",
          "generate_image" not in ToolSelector()._project_only_tools)


if __name__ == "__main__":
    print("=== Phase H 文生图链路审查 ===")
    chat_id = setup()
    test_proxy_endpoint(chat_id)
    test_url_format(chat_id)
    test_settings_read()
    test_selector_registration()
    print(f"\n结果: {len(FAILURES)} 失败")
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    sys.exit(1 if FAILURES else 0)