"""工单B 回归测试：provider_disabled 设置保存链路。

验证目标（交接文档工单B）：
  - PUT /api/settings/provider_disabled 精确保存传入的 JSON，不篡改、不全量写 true
  - GET 回读值与写入一致
  - 增量更新（禁用一家 / 启用一家）时其余 provider 状态不变
  - 默认值为空对象 {}

运行：
  cd backend && python -m pytest tests/test_provider_disabled_regression.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app  # noqa: E402

# TestClient 的 host 硬编码为 "testclient"，会被 mobile_remote_auth_middleware 拦截 401。
# 与工单C的止血方案一致：在测试进程内豁免 loopback 判定。
import app.core.mobile_auth as _mobile_auth  # noqa: E402
_mobile_auth.is_loopback_host = lambda host: True
import main as _main_module  # noqa: E402
_main_module.is_loopback_host = lambda host: True

client = TestClient(app)

KEY = "provider_disabled"


def _put(value: dict) -> dict:
    """写入 provider_disabled 并返回响应 JSON。"""
    resp = client.put(f"/api/settings/{KEY}", json={"value": json.dumps(value)})
    assert resp.status_code == 200, f"PUT failed: {resp.status_code} {resp.text}"
    return resp.json()


def _get() -> dict:
    """读取 provider_disabled 并解析为 dict。"""
    resp = client.get(f"/api/settings/{KEY}")
    assert resp.status_code == 200, f"GET failed: {resp.status_code} {resp.text}"
    body = resp.json()
    return json.loads(body["value"])


def _get_all() -> dict:
    """从 GET /api/settings 全量接口读取 provider_disabled。"""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    raw = body.get(KEY, "{}")
    return json.loads(raw)


class TestProviderDisabledRegression:
    """工单B 核心回归：保存一家，其余不变。"""

    def test_put_single_provider_only_contains_that_provider(self):
        """禁用 deepseek → JSON 里只有 deepseek:true，不出现其他 provider。"""
        _put({"deepseek": True})
        result = _get()
        assert result == {"deepseek": True}
        assert "qwen" not in result
        assert "openai" not in result

    def test_incremental_disable_preserves_existing(self):
        """已有 deepseek:true，再禁用 qwen → 两者都在，其余不在。"""
        _put({"deepseek": True})
        current = _get()
        # 模拟前端 setProviderDisabled：复制当前 map，添加新条目
        next_map = dict(current)
        next_map["qwen"] = True
        _put(next_map)

        result = _get()
        assert result == {"deepseek": True, "qwen": True}
        assert "openai" not in result  # 未触碰的 provider 不应出现

    def test_enable_removes_only_target_provider(self):
        """已有 deepseek+qwen 禁用，启用 deepseek → 只剩 qwen。"""
        _put({"deepseek": True, "qwen": True})
        current = _get()
        # 模拟前端启用：从 map 中删除目标 key
        next_map = {k: v for k, v in current.items() if k != "deepseek"}
        _put(next_map)

        result = _get()
        assert result == {"qwen": True}
        assert "deepseek" not in result

    def test_empty_map_means_all_enabled(self):
        """写入空对象 → 所有 provider 均启用（无禁用条目）。"""
        _put({})
        result = _get()
        assert result == {}

    def test_false_values_are_not_persisted_as_disabled(self):
        """历史残留的 false 值不应被视为禁用（后端原样存储，前端过滤）。
        本测试验证后端不篡改传入值——传入什么存什么。
        false 值的净化由前端 setProviderDisabled 防御性过滤负责。"""
        _put({"deepseek": True, "qwen": False})
        result = _get()
        # 后端原样存储（不做语义转换）
        assert result["deepseek"] is True
        assert result["qwen"] is False

    def test_get_all_settings_includes_provider_disabled(self):
        """全量设置接口应包含 provider_disabled 且值正确。"""
        _put({"glm": True})
        result = _get_all()
        assert result == {"glm": True}

    def test_concurrent_style_updates_do_not_cross_contaminate(self):
        """模拟快速连续切换：A 禁用 → B 禁用 → A 启用，最终状态应只有 B。"""
        # Step 1: 禁用 A
        _put({"anthropic": True})
        # Step 2: 禁用 B（基于 Step 1 的状态）
        s1 = _get()
        s2 = dict(s1)
        s2["baichuan"] = True
        _put(s2)
        # Step 3: 启用 A（基于 Step 2 的状态）
        s2_check = _get()
        s3 = {k: v for k, v in s2_check.items() if k != "anthropic"}
        _put(s3)

        result = _get()
        assert result == {"baichuan": True}
        assert "anthropic" not in result

    def test_default_value_when_not_set(self):
        """provider_disabled 未设置时，全量接口应返回默认空对象 {}。"""
        # 先删除该设置（如果存在）
        from app.core.database import SessionLocal
        from app.models.agent import Setting

        db = SessionLocal()
        try:
            db.query(Setting).filter(Setting.key == KEY).delete()
            db.commit()
        finally:
            db.close()

        result = _get_all()
        assert result == {}
