"""MfkAgent 模型配置体系改造（Phase D）自动化验证脚本。

Phase D：Provider 注册表 + 自定义模型 + 密钥安全 + 默认模型收敛。

单元/集成级：
  1. 数据驱动注册表：/api/models/providers 返回 11 家（含新增 文心/星火/MiniMax/百川），free 标识正确
  2. 可用模型列表：仅含已配置 Key 的模型，mimo（无 Key）不可见
  3. 密钥安全：/api/settings 不再返回 api_key_* 明文；/api/models/config 仅返回脱敏
  4. provider-key 配置：保存 API Key / API Base 覆盖 → 热重载生效
  5. 自定义模型 CRUD：创建/更新/删除/重名校验
  6. 自定义覆盖内置：同名 model_id 覆盖内置端点，删除后回退
  7. 默认模型收敛：default_model 默认 qwen-flash，兜底函数返回 qwen-flash

运行：
  python backend/tests/test_model_config_phase_d.py [报告输出路径]

退出码：0 = 全部通过；1 = 存在失败。
"""

import io
import json
import os
import sys
import tempfile
from pathlib import Path

if __name__ == "__main__" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TEMP_DIR = Path(tempfile.mkdtemp(prefix="mfk_phaseD_"))
os.chdir(_TEMP_DIR)
os.environ["DATABASE_URL"] = "sqlite:///./phase_d_test.db"
os.environ["DEEPSEEK_API_KEY"] = "test-deepseek-key-1234"
os.environ["QWEN_API_KEY"] = "test-qwen-key-5678"
os.environ["MIMO_API_KEY"] = ""
os.environ["GLM_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["FREELLMAPI_API_KEY"] = ""
os.environ["WENXIN_API_KEY"] = ""
os.environ["SPARK_API_KEY"] = ""
os.environ["MOONSHOT_API_KEY"] = ""
os.environ["MINIMAX_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

import app.models.agent as _agent_models  # noqa: F401, E402
from app.core.database import engine as _engine, Base as _Base  # noqa: E402
_Base.metadata.create_all(bind=_engine)

from main import app  # noqa: E402

CLIENT = TestClient(app)


# ---------------------------------------------------------------------------
# 测试执行
# ---------------------------------------------------------------------------

results: list[tuple[str, bool, str]] = []


def run(name: str, fn) -> None:
    try:
        fn()
        results.append((name, True, ""))
    except AssertionError as e:
        results.append((name, False, str(e)))
    except Exception as e:  # noqa: BLE001
        results.append((name, False, f"{type(e).__name__}: {e}"))


def _get(path: str):
    resp = CLIENT.get(path)
    assert resp.status_code == 200, f"GET {path} → HTTP {resp.status_code}: {resp.text[:200]}"
    return resp.json()


def _post(path: str, body: dict):
    resp = CLIENT.post(path, json=body)
    return resp


def _put(path: str, body: dict):
    return CLIENT.put(path, json=body)


def _delete(path: str):
    return CLIENT.delete(path)


# --- 1. Provider 注册表（数据驱动，含 4 家新接入） ---
def test_providers_registry():
    data = _get("/api/models/providers")
    providers = data["providers"]
    ids = {p["id"] for p in providers}
    expected = {"deepseek", "qwen", "google", "glm", "moonshot",
                "freellmapi", "mimo", "wenxin", "spark", "minimax"}
    assert expected <= ids, f"缺少 provider: {expected - ids}"
    by_id = {p["id"]: p for p in providers}
    assert by_id["qwen"]["free"] is True, "qwen 应标记免费"
    assert by_id["deepseek"]["free"] is False, "deepseek 不应标记免费"
    assert by_id["wenxin"]["models"], "文心应带模型清单"
    assert by_id["spark"]["models"] and by_id["minimax"]["models"] and by_id["siliconflow"]["models"]
    assert by_id["deepseek"]["has_key"] is True, "deepseek 已配 Key"
    assert by_id["mimo"]["has_key"] is False, "mimo 未配 Key"


# --- 2. 可用模型列表：仅已配 Key，mimo 不可见 ---
def test_available_models_filter():
    models = _get("/api/models/models")
    ids = {m["id"] for m in models}
    assert "qwen-flash" in ids and "deepseek-v4-flash" in ids
    assert "wenxin-ernie-5.0" not in ids, "未配 Key 的文心不应出现"
    assert "glm-5.1" not in ids, "未配 Key 的 glm 不应出现"
    assert not any(i.startswith("mimo") for i in ids), "mimo 全部不应出现"


# --- 3. 密钥安全：不泄漏明文 ---
def test_key_masking():
    settings_data = _get("/api/settings")
    assert "api_key_deepseek" not in settings_data, "/api/settings 泄漏 api_key_deepseek"
    assert "api_key_qwen" not in settings_data, "/api/settings 泄漏 api_key_qwen"

    config_data = _get("/api/models/config")
    raw = json.dumps(config_data)
    assert "test-deepseek-key-1234" not in raw, "/api/models/config 泄漏明文 Key"
    assert "test-qwen-key-5678" not in raw, "/api/models/config 泄漏明文 Key"
    by_id = {c["id"]: c for c in config_data["configs"]}
    assert by_id["deepseek"]["has_key"] is True
    assert by_id["deepseek"]["api_key_masked"].endswith("1234")
    assert by_id["deepseek"]["api_key_masked"].startswith("tes")
    assert "****" in by_id["deepseek"]["api_key_masked"]
    assert by_id["mimo"]["has_key"] is False and by_id["mimo"]["api_key_masked"] == ""


# --- 4. provider-key 配置 + 热重载 ---
def test_provider_key_save_reload():
    r = _post("/api/models/provider-key", {"provider_id": "glm", "api_key": "glm-secret-9999"})
    assert r.status_code == 200, r.text[:200]

    config_data = _get("/api/models/config")
    by_id = {c["id"]: c for c in config_data["configs"]}
    assert by_id["glm"]["has_key"] is True
    assert by_id["glm"]["api_key_masked"].endswith("9999")

    models = _get("/api/models/models")
    assert any(m["id"] == "glm-5.1" for m in models), "配置 Key 后 glm-5.1 应可用"

    from app.services.model import model_service
    assert model_service.models["glm-5.1"].api_key == "glm-secret-9999"

    # API Base 覆盖
    r = _post("/api/models/provider-key", {"provider_id": "qwen", "api_base": "https://override.example.com/v1"})
    assert r.status_code == 200, r.text[:200]
    assert model_service.models["qwen-flash"].api_base == "https://override.example.com/v1", "api_base 覆盖未生效"
    config_data = _get("/api/models/config")
    by_id = {c["id"]: c for c in config_data["configs"]}
    assert by_id["qwen"]["api_base_override"] is True
    assert by_id["qwen"]["api_base"] == "https://override.example.com/v1"

    # 清空覆盖恢复默认
    r = _post("/api/models/provider-key", {"provider_id": "qwen", "api_base": ""})
    assert r.status_code == 200, r.text[:200]
    assert model_service.models["qwen-flash"].api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1", "清除覆盖后应恢复默认端点"


# --- 5. 自定义模型 CRUD ---
def test_custom_model_crud():
    body = {
        "model_id": "custom-test",
        "name": "测试模型",
        "provider": "openai",
        "model_name": "test-upstream",
        "api_base": "http://localhost:9999/v1",
        "api_key": "custom-key-abc",
        "max_tokens": 8192,
        "temperature": 0.3,
    }
    r = _post("/api/models/custom", body)
    assert r.status_code == 200, r.text[:300]
    custom_id = r.json()["id"]

    from app.services.model import model_service
    assert "custom-test" in model_service.models, "自定义模型未并入 model_service"
    assert model_service.models["custom-test"].api_base == "http://localhost:9999/v1"
    assert model_service.models["custom-test"].max_tokens == 8192

    lst = _get("/api/models/custom")
    assert any(c["model_id"] == "custom-test" for c in lst)
    raw = json.dumps(lst)
    assert "custom-key-abc" not in raw, "自定义模型列表泄漏明文 Key"

    # 更新
    r = _put(f"/api/models/custom/{custom_id}", {"max_tokens": 16384, "temperature": 0.9})
    assert r.status_code == 200, r.text[:300]
    assert model_service.models["custom-test"].max_tokens == 16384
    assert model_service.models["custom-test"].temperature == 0.9

    # 重名校验
    r = _post("/api/models/custom", body)
    assert r.status_code == 400, f"重名应 400，实际 {r.status_code}"

    # 非法 provider
    bad = dict(body)
    bad["model_id"] = "custom-bad"
    bad["provider"] = "not-a-provider"
    r = _post("/api/models/custom", bad)
    assert r.status_code == 400, f"非法 provider 应 400，实际 {r.status_code}"

    # 删除
    r = _delete(f"/api/models/custom/{custom_id}")
    assert r.status_code == 200, r.text[:300]
    assert "custom-test" not in model_service.models, "删除后应移出 model_service"


# --- 6. 自定义覆盖内置：同名 model_id ---
def test_custom_overrides_builtin():
    body = {
        "model_id": "qwen-flash",
        "name": "覆盖版千问",
        "provider": "openai",
        "model_name": "override-model",
        "api_base": "https://override-qwen.example.com/v1",
        "api_key": "",
    }
    r = _post("/api/models/custom", body)
    assert r.status_code == 200, r.text[:300]
    custom_id = r.json()["id"]

    from app.services.model import model_service
    cfg = model_service.models["qwen-flash"]
    assert cfg.api_base == "https://override-qwen.example.com/v1", "同名自定义模型应覆盖内置端点"
    assert cfg.provider.value == "openai", "覆盖后 provider 应为自定义 provider"
    assert cfg.model_name == "override-model"

    r = _delete(f"/api/models/custom/{custom_id}")
    assert r.status_code == 200
    cfg = model_service.models["qwen-flash"]
    assert cfg.api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1", "删除后应回退内置端点"


# --- 7. 默认模型收敛 qwen-flash ---
def test_default_model_converged():
    from app.api.settings import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["default_model"] == "qwen-flash", "DEFAULT_SETTINGS 默认应为 qwen-flash"

    from app.api.chat import _get_default_model
    assert _get_default_model() == "qwen-flash", "DB 无 default_model 时兜底应为 qwen-flash"


run("1. Provider 注册表（11 家含 4 家新接入）", test_providers_registry)
run("2. 可用模型过滤（无 Key 不可见，mimo 全隐藏）", test_available_models_filter)
run("3. 密钥脱敏（/api/settings 与 /api/models/config 不泄漏明文）", test_key_masking)
run("4. provider-key 配置 + 热重载 + api_base 覆盖", test_provider_key_save_reload)
run("5. 自定义模型 CRUD（含重名/非法 provider 校验）", test_custom_model_crud)
run("6. 同名自定义覆盖内置 + 删除回退", test_custom_overrides_builtin)
run("7. 默认模型收敛 qwen-flash", test_default_model_converged)


# ---------------------------------------------------------------------------
# 报告输出
# ---------------------------------------------------------------------------

def main() -> int:
    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "=" * 64)
    print(f"Phase D 模型配置验证：{passed}/{len(results)} 通过")
    print("=" * 64)
    for name, ok, detail in results:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}")
        if detail:
            print(f"      ↳ {detail}")

    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if report_path:
        report_path.write_text(
            "# Phase D 模型配置验证报告\n\n"
            f"- 结果：{passed}/{len(results)} 通过\n\n"
            + "\n".join(f"- {'✅' if ok else '❌'} {name}"
                        + (f"：{detail}" if detail else "")
                        for name, ok, detail in results)
            + "\n",
            encoding="utf-8",
        )
        print(f"\n报告已写入: {report_path}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
