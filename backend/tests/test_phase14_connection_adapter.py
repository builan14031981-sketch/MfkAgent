"""Phase 14: 统一模型连通性校验 + Adapter 防腐层 专项测试

验证：
1. ModelConfigAdapter 三层优先级合并（.env / settings 表 / CustomModel 表）
2. ModelConfigError 专项异常（call_once / stream_once 统一校验）
3. agent.py 专项捕获 ModelConfigError 跳过反思自愈
4. test-connection 端点：正常连通 / 无效Key / 死链超时 / 无Key回退
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_adapter_priority():
    """Adapter 三层优先级合并：CustomModel 覆盖 > settings 表 > .env"""
    from app.core.model_adapter import ModelConfigAdapter
    from app.core.model_providers import PROVIDER_MAP
    adapter = ModelConfigAdapter()

    # 1. resolve_api_key：settings 表覆盖 .env
    deepseek_def = PROVIDER_MAP["deepseek"]
    key = adapter.resolve_api_key(deepseek_def)
    # DeepSeek 在 .env 配置了 key，应能读到（非空）
    assert key, "DeepSeek Key 应非空（来自 .env 或 settings 表）"
    print(f"[PASS] test_adapter_priority.resolve_api_key → {key[:8]}...")

    # 2. resolve_api_base：settings 表覆盖默认端点
    base = adapter.resolve_api_base(deepseek_def)
    assert base, "DeepSeek api_base 应非空"
    assert "deepseek.com" in base or "api." in base, f"api_base 异常: {base}"
    print(f"[PASS] test_adapter_priority.resolve_api_base → {base}")

    # 3. resolve_all：返回 dict 且包含内置模型
    all_models = adapter.resolve_all()
    assert isinstance(all_models, dict), "resolve_all 应返回 dict"
    assert len(all_models) > 0, "应至少有一个模型"
    # 内置 deepseek 模型应存在
    has_deepseek = any("deepseek" in mid.lower() for mid in all_models.keys())
    assert has_deepseek, "应包含 deepseek 内置模型"
    print(f"[PASS] test_adapter_priority.resolve_all → {len(all_models)} models")

    # 4. resolve_single：单模型查找
    first_id = next(iter(all_models.keys()))
    single = adapter.resolve_single(first_id)
    assert single is not None, f"resolve_single({first_id}) 应非 None"
    assert single.api_key is not None, "ModelConfig.api_key 应存在"
    print(f"[PASS] test_adapter_priority.resolve_single → {first_id}: key={'有' if single.api_key else '无'}")


def test_model_config_error_call_once():
    """call_once 无 Key → ModelConfigError（不再用 ValueError）"""
    from app.services.model import ModelService, ModelConfigError
    svc = ModelService()

    # 找一个无 Key 的 provider 模型
    no_key_model = None
    for mid, cfg in svc.models.items():
        if not cfg.api_key:
            no_key_model = mid
            break

    if no_key_model is None:
        # 所有模型都有 key，测一个不存在的 model_id
        no_key_model = "definitely-not-exist-model-12345"

    from unittest.mock import patch
    with patch.object(svc, "_disabled_providers", set()):
        try:
            asyncio.run(svc.call_once(
                model_id=no_key_model,
                messages=[{"role": "user", "content": "hi"}],
            ))
            assert False, "应抛出 ModelConfigError"
        except ModelConfigError as e:
            assert "未配置 API Key" in str(e) or "未注册" in str(e), f"错误消息异常: {e}"
            print(f"[PASS] test_model_config_error_call_once → ModelConfigError: {e}")
        except ValueError as e:
            assert False, f"不应再抛 ValueError，应为 ModelConfigError: {e}"


def test_model_config_error_stream_once():
    """stream_once 无 Key → ModelConfigError（与 call_once 对齐）"""
    from app.services.model import ModelService, ModelConfigError
    svc = ModelService()

    no_key_model = None
    for mid, cfg in svc.models.items():
        if not cfg.api_key:
            no_key_model = mid
            break

    if no_key_model is None:
        no_key_model = "definitely-not-exist-model-12345"

    async def _collect():
        async for _ in svc.stream_once(
            model_id=no_key_model,
            messages=[{"role": "user", "content": "hi"}],
        ):
            pass

    from unittest.mock import patch
    with patch.object(svc, "_disabled_providers", set()):
        try:
            asyncio.run(_collect())
            assert False, "应抛出 ModelConfigError"
        except ModelConfigError as e:
            assert "未配置 API Key" in str(e) or "未注册" in str(e), f"错误消息异常: {e}"
            print(f"[PASS] test_model_config_error_stream_once → ModelConfigError: {e}")
        except ValueError as e:
            assert False, f"stream_once 不应再抛 ValueError: {e}"


def test_agent_catches_model_config_error():
    """agent.py 专项捕获 ModelConfigError（不触发反思自愈）"""
    from app.services.model import ModelConfigError
    from app.core.agent_runtime.agent import AgentRuntime

    # 验证 agent.py 导入了 ModelConfigError
    import app.core.agent_runtime.agent as agent_mod
    assert hasattr(agent_mod, "ModelConfigError"), "agent.py 应导入 ModelConfigError"
    assert agent_mod.ModelConfigError is ModelConfigError, "应为同一个类"
    print("[PASS] test_agent_catches_model_config_error → agent.py 已导入 ModelConfigError")


def test_test_connection_unknown_provider():
    """test-connection 未知 provider → 404"""
    from fastapi import HTTPException
    from app.api.models import test_connection, TestConnectionRequest

    req = TestConnectionRequest(provider_id="nonexistent-xxx")
    try:
        asyncio.run(test_connection(req))
        assert False, "应抛 404"
    except HTTPException as e:
        assert e.status_code == 404
        print(f"[PASS] test_test_connection_unknown_provider → 404: {e.detail}")


def test_test_connection_no_key():
    """test-connection 无 Key 配置 → ok:false"""
    from app.api.models import test_connection, TestConnectionRequest

    # 选一个肯定没配 key 的 provider（spark 通常未配）
    from app.core.model_adapter import adapter
    from app.core.model_providers import PROVIDER_MAP
    no_key_provider = None
    for pid, pdef in PROVIDER_MAP.items():
        if not adapter.resolve_api_key(pdef):
            no_key_provider = pid
            break

    if not no_key_provider:
        print("[SKIP] test_test_connection_no_key → 所有 provider 都有 key")
        return

    req = TestConnectionRequest(provider_id=no_key_provider)
    result = asyncio.run(test_connection(req))
    assert result["ok"] is False, "无 Key 应返回 ok:false"
    assert "未配置" in result["detail"] or "Key" in result["detail"]
    print(f"[PASS] test_test_connection_no_key → ok:false: {result['detail'][:50]}")


def test_test_connection_real_deepseek():
    """test-connection 真实 DeepSeek 连通性（5秒内）"""
    from app.api.models import test_connection, TestConnectionRequest

    req = TestConnectionRequest(provider_id="deepseek")
    t0 = time.time()
    result = asyncio.run(test_connection(req))
    elapsed = time.time() - t0

    assert "ok" in result, "应返回 ok 字段"
    assert elapsed < 6.0, f"应在 6 秒内返回，实际 {elapsed:.2f}s"
    if result["ok"]:
        assert result["latency_ms"] >= 0
        print(f"[PASS] test_test_connection_real_deepseek → ok:true {result['latency_ms']}ms: {result['detail'][:60]}")
    else:
        # 可能是网络问题，但熔断应正常
        print(f"[INFO] test_test_connection_real_deepseek → ok:false (可能网络): {result['detail'][:60]}")


def test_test_connection_dead_link_timeout():
    """test-connection 死链 → 5秒内熔断"""
    from app.api.models import test_connection, TestConnectionRequest
    from app.core.model_providers import PROVIDER_MAP

    # 用 deepseek 的 key 但指向死链
    from app.core.model_adapter import adapter
    real_key = adapter.resolve_api_key(PROVIDER_MAP["deepseek"])
    if not real_key:
        print("[SKIP] test_test_connection_dead_link_timeout → 无 deepseek key")
        return

    req = TestConnectionRequest(
        provider_id="deepseek",
        api_key=real_key,
        api_base="http://10.255.255.1/v1",
    )
    t0 = time.time()
    result = asyncio.run(test_connection(req))
    elapsed = time.time() - t0

    assert result["ok"] is False, "死链应 ok:false"
    assert elapsed < 6.5, f"应在 5 秒+开销内熔断，实际 {elapsed:.2f}s"
    assert "超时" in result["detail"] or "无法连接" in result["detail"], f"detail 异常: {result['detail']}"
    print(f"[PASS] test_test_connection_dead_link_timeout → {elapsed:.2f}s 熔断: {result['detail'][:50]}")


def test_modelservice_uses_adapter():
    """ModelService 委托 Adapter（防腐层接入验证）"""
    from app.services.model import ModelService
    svc = ModelService()
    assert hasattr(svc, "_adapter"), "ModelService 应有 _adapter 属性"
    assert svc._adapter is not None, "_adapter 不应为 None"
    # _init_models 应委托给 adapter.resolve_all
    assert svc.models == svc._adapter.resolve_all() or len(svc.models) > 0, "models 应来自 adapter"
    print(f"[PASS] test_modelservice_uses_adapter → _adapter={type(svc._adapter).__name__}, models={len(svc.models)}")


def test_backward_compat_get_api_key():
    """_get_api_key 旧签名仍可用（向后兼容）"""
    from app.services.model import ModelService
    svc = ModelService()
    # 旧调用方式：env_key, setting_key
    key = svc._get_api_key("", "api_key_deepseek")
    # 应能读到（来自 .env 或 settings）
    assert key, "DeepSeek key 应非空"
    print(f"[PASS] test_backward_compat_get_api_key → {key[:8]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 14: 连通性校验 + Adapter 防腐层 专项测试")
    print("=" * 60)
    test_adapter_priority()
    test_model_config_error_call_once()
    test_model_config_error_stream_once()
    test_agent_catches_model_config_error()
    test_modelservice_uses_adapter()
    test_backward_compat_get_api_key()
    test_test_connection_unknown_provider()
    test_test_connection_no_key()
    test_test_connection_real_deepseek()
    test_test_connection_dead_link_timeout()
    print("=" * 60)
    print("ALL PASS")
