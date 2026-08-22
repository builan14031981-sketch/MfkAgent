import sys, io, asyncio
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')
from app.services.model import model_service

async def probe(mid):
    try:
        r = await model_service.call_once(
            model_id=mid,
            messages=[{'role': 'user', 'content': 'ping'}],
            temperature=0, max_tokens=5,
            reasoning_effort='none', memory_text=None,
        )
        print(f'[OK] {mid}: {len(r.content)}字 usage={r.usage.get("total_tokens")}')
    except Exception as e:
        print(f'[FAIL] {mid}: {str(e)[:120]}')

asyncio.run(probe('GLM-4.7-Flash'))
asyncio.run(probe('qwen3.5-flash'))
