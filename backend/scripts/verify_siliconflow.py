"""验证硅基流动集成 — 测试模型加载和 API 调用
用法: cd backend && python scripts/verify_siliconflow.py
"""
import sys
sys.path.insert(0, ".")

import asyncio
from app.services.model import model_service

async def main():
    all_ok = True

    # 1. 检查模型是否注册
    print("=" * 60)
    print("1. 检查 SiliconFlow 模型注册")
    print("=" * 60)
    models = model_service.get_available_models()
    sf_models = [m for m in models if m["id"].startswith("siliconflow-")]
    for m in sf_models:
        print(f"  [OK] {m['id']} -> provider={m['provider']}")

    if not sf_models:
        print("  [FAIL] 未找到 SiliconFlow 模型！请先通过 API 配置 Key")
        all_ok = False
        return

    # 2. 测试 DeepSeek-V4-Flash
    print("\n" + "=" * 60)
    print("2. 测试 siliconflow-deepseek-v4-flash")
    print("=" * 60)
    try:
        result = await model_service.call_once(
            model_id="siliconflow-deepseek-v4-flash",
            messages=[{"role": "user", "content": "你好，请介绍一下你自己，并说明当前模型名称。"}],
            max_tokens=200,
        )
        print(f"  [OK] 回复: {result.content[:200]}")
        print(f"  finish_reason: {result.finish_reason}")
        print(f"  usage: {result.usage}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        all_ok = False

    # 3. 测试 DeepSeek-V4-Pro
    print("\n" + "=" * 60)
    print("3. 测试 siliconflow-deepseek-v4-pro")
    print("=" * 60)
    try:
        result = await model_service.call_once(
            model_id="siliconflow-deepseek-v4-pro",
            messages=[{"role": "user", "content": "1+1等于几？"}],
            max_tokens=50,
        )
        print(f"  [OK] 回复: {result.content[:200]}")
        print(f"  usage: {result.usage}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        all_ok = False

    # 4. 测试 GLM-Z1-9B (免费模型)
    print("\n" + "=" * 60)
    print("4. 测试 siliconflow-glm-z1-9b (免费)")
    print("=" * 60)
    try:
        result = await model_service.call_once(
            model_id="siliconflow-glm-z1-9b",
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=50,
        )
        print(f"  [OK] 回复: {result.content[:200]}")
        print(f"  usage: {result.usage}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("全部验证通过")
    else:
        print("部分验证失败，请检查上方输出")
    print("=" * 60)

asyncio.run(main())