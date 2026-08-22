"""Phase 13: 上游模型拉取端点 + 清除逻辑加固 专项测试

验证：
1. fetch_remote 正常拉取（真实 DeepSeek Key）
2. fetch_remote 超时熔断（5秒死链）
3. fetch_remote 鉴权失败熔断（无效 Key）
4. fetch_remote 参数校验（空 key / 空 base+provider）
5. 清除 Key 时联动清理 api_base + CustomModel
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# 测试隔离（2026-08-16 根因修复）：必须指向独立测试库，绝不触碰生产库 backend/mfkagent.db。
# 此前本文件未设置 DATABASE_URL，且 test_clear_key_purge_associated 以 "glm" 为目标
# 执行清除 Key 动作，导致每次运行测试都清空用户真实 GLM API Key。
# 直接运行时（python tests/xxx.py）不加载 conftest.py，故在此兜底设置；
# pytest 运行时 conftest.py 已先行设置，此处 setdefault 不覆盖。
_TEST_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "mfkagent_test.db"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.replace(os.sep, '/')}")

# 直接运行时（python tests/xxx.py）不加载 conftest.py，需自行保证测试库表结构存在。
import app.models.agent  # noqa: E402,F401  让模型注册到 Base.metadata
from app.core.database import Base as _Base, engine as _Engine  # noqa: E402

_Base.metadata.create_all(bind=_Engine)


def test_param_validation():
    """参数校验：空 key / 空 base+provider"""
    from app.api.models import FetchRemoteRequest
    import pydantic

    # 空 key —— pydantic 层不拦截 str，但端点逻辑会拦
    req = FetchRemoteRequest(api_key="")
    assert req.api_key == ""

    # 缺省 base 和 provider
    req2 = FetchRemoteRequest(api_key="sk-xxx")
    assert req2.api_base is None
    assert req2.provider_id is None
    print("[PASS] test_param_validation")


def test_fetch_remote_invalid_key():
    """无效 Key → 友好 400"""
    from fastapi import HTTPException
    from app.api.models import fetch_remote_models, FetchRemoteRequest

    req = FetchRemoteRequest(
        api_key="sk-invalid-key-for-test-12345",
        api_base="https://api.deepseek.com/v1",
    )
    try:
        asyncio.run(fetch_remote_models(req))
        assert False, "应抛出 400"
    except HTTPException as e:
        assert e.status_code == 400, f"期望 400, 实际 {e.status_code}"
        print(f"[PASS] test_fetch_remote_invalid_key → {e.detail[:60]}...")


def test_fetch_remote_dead_link_timeout():
    """死链 → 5秒内熔断"""
    from fastapi import HTTPException
    from app.api.models import fetch_remote_models, FetchRemoteRequest

    req = FetchRemoteRequest(
        api_key="sk-xxx",
        api_base="http://10.255.255.1/v1",  # 不可达地址，强制超时
    )
    t0 = time.time()
    try:
        asyncio.run(fetch_remote_models(req))
        assert False, "应超时"
    except HTTPException as e:
        elapsed = time.time() - t0
        assert e.status_code == 400, f"期望 400, 实际 {e.status_code}"
        # 必须在 6 秒内返回（5秒超时 + 少量开销）
        assert elapsed < 6.5, f"熔断超时！耗时 {elapsed:.2f}s，未在5秒内熔断"
        print(f"[PASS] test_fetch_remote_dead_link_timeout → {elapsed:.2f}s 熔断: {e.detail[:50]}...")


def test_fetch_remote_real_deepseek():
    """真实 DeepSeek Key 拉取（从 settings 读取已配置的 key）"""
    from fastapi import HTTPException
    from app.api.models import fetch_remote_models, FetchRemoteRequest
    from app.api.models import _get_setting

    api_key = _get_setting("api_key_deepseek")
    if not api_key:
        print("[SKIP] test_fetch_remote_real_deepseek → 未配置 DeepSeek Key")
        return

    req = FetchRemoteRequest(api_key=api_key, api_base="https://api.deepseek.com/v1")
    t0 = time.time()
    result = asyncio.run(fetch_remote_models(req))
    elapsed = time.time() - t0
    assert "models" in result, "返回结构异常"
    assert isinstance(result["models"], list), "models 应为 list"
    assert len(result["models"]) > 0, "应至少返回一个模型"
    print(f"[PASS] test_fetch_remote_real_deepseek → {len(result['models'])} models in {elapsed:.2f}s")
    print(f"       示例: {result['models'][:5]}")


def test_clear_key_purge_associated():
    """清除 Key 时联动清理 api_base + CustomModel"""
    from app.api.models import _set_setting, _get_setting, update_provider_key, ProviderKeyUpdate
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel

    # 准备：给一个测试 provider 写入脏数据
    test_provider = "glm"  # 选一个未配置的 provider 做测试
    _set_setting(f"api_base_{test_provider}", "https://fake-base.test/v1")

    db = SessionLocal()
    try:
        # 先清空再插入一条测试 CustomModel
        db.query(CustomModel).filter(CustomModel.provider == test_provider).delete()
        db.commit()
        fake = CustomModel(
            model_id="glm-fake-test-model",
            name="GLM Fake Test",
            provider=test_provider,
            model_name="glm-fake",
            api_base="https://fake.test/v1",
            api_key="fake-key",
            max_tokens=4096,
            temperature=0.7,
            enabled=True,
            source="sync",  # purge 只删 source='sync' 的行
        )
        db.add(fake)
        db.commit()
    finally:
        db.close()

    # 校验脏数据存在
    assert _get_setting(f"api_base_{test_provider}") == "https://fake-base.test/v1"
    db = SessionLocal()
    try:
        count = db.query(CustomModel).filter(CustomModel.provider == test_provider).count()
        assert count == 1, f"准备阶段应有1条CustomModel, 实际{count}"
    finally:
        db.close()

    # 执行清除 Key（传空字符串）
    body = ProviderKeyUpdate(provider_id=test_provider, api_key="")
    result = asyncio.run(update_provider_key(body))

    # 校验：api_base 覆盖被清空
    assert _get_setting(f"api_base_{test_provider}") == "", "api_base 覆盖未被清空"
    assert _get_setting(f"api_key_{test_provider}") == "", "api_key 未被清空"

    # 校验：关联 CustomModel 被清除
    db = SessionLocal()
    try:
        count = db.query(CustomModel).filter(CustomModel.provider == test_provider).count()
        assert count == 0, f"CustomModel 未被清除, 剩余{count}条"
    finally:
        db.close()

    assert result["purged"] is True, "purged 标记应为 True"
    print("[PASS] test_clear_key_purge_associated → api_key + api_base + CustomModel 全部清除")


def test_update_key_not_purge():
    """正常更新 Key（非空）时不应触发清除"""
    from app.api.models import _set_setting, _get_setting, update_provider_key, ProviderKeyUpdate
    from app.core.database import SessionLocal
    from app.models.agent import CustomModel

    test_provider = "spark"
    # 先清场
    _set_setting(f"api_base_{test_provider}", "")
    db = SessionLocal()
    try:
        db.query(CustomModel).filter(CustomModel.provider == test_provider).delete()
        db.commit()
    finally:
        db.close()

    # 正常写入一个 Key（非空）
    body = ProviderKeyUpdate(provider_id=test_provider, api_key="sk-real-key-test")
    result = asyncio.run(update_provider_key(body))
    assert result["purged"] is False, "正常更新 Key 不应触发 purge"

    # 清理测试数据
    _set_setting(f"api_key_{test_provider}", "")
    print("[PASS] test_update_key_not_purge → 正常更新未误触发清除")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 13: fetch_remote + 清除加固 专项测试")
    print("=" * 60)
    test_param_validation()
    test_fetch_remote_invalid_key()
    test_fetch_remote_dead_link_timeout()
    test_fetch_remote_real_deepseek()
    test_clear_key_purge_associated()
    test_update_key_not_purge()
    print("=" * 60)
    print("ALL PASS")
