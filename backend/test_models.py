#!/usr/bin/env python
"""快速测试所有模型是否可用"""

import asyncio
import sys
from app.services.model import model_service

async def test_model(model_id: str) -> dict:
    """测试单个模型"""
    try:
        config = model_service.get_model_config(model_id)
        if not config:
            return {"model": model_id, "status": "❌ 配置不存在"}
        
        if not config.api_key:
            return {"model": model_id, "status": "❌ 无 API Key"}
        
        # 简单测试：发送一个空消息
        from app.services.model import Message
        messages = [Message(role="user", content="hi")]
        
        # 尝试非流式调用
        response = await model_service.chat(
            model_id=model_id,
            messages=messages,
            max_tokens=10,
            stream=False
        )
        
        return {"model": model_id, "status": "✅ 可用", "response": response.content[:50]}
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return {"model": model_id, "status": "❌ API Key 无效或过期"}
        elif "404" in error_msg:
            return {"model": model_id, "status": "❌ 模型不存在"}
        elif "429" in error_msg or "quota" in error_msg.lower():
            return {"model": model_id, "status": "❌ 额度用完或限流"}
        else:
            return {"model": model_id, "status": f"❌ 错误: {error_msg[:100]}"}

async def main():
    """测试所有模型"""
    models = model_service.get_available_models()
    print(f"\n开始测试 {len(models)} 个模型...\n")
    print("=" * 80)
    
    results = []
    for model_info in models:
        model_id = model_info["id"]
        print(f"测试 {model_id}...", end=" ", flush=True)
        result = await test_model(model_id)
        results.append(result)
        print(result["status"])
    
    print("\n" + "=" * 80)
    print("\n测试结果汇总：\n")
    
    available = [r for r in results if r["status"].startswith("✅")]
    unavailable = [r for r in results if r["status"].startswith("❌")]
    
    if available:
        print("✅ 可用模型：")
        for r in available:
            print(f"  - {r['model']}")
    
    if unavailable:
        print("\n❌ 不可用模型：")
        for r in unavailable:
            print(f"  - {r['model']}: {r['status']}")
    
    print(f"\n总计: {len(available)} 可用, {len(unavailable)} 不可用\n")

if __name__ == "__main__":
    asyncio.run(main())
