import asyncio, time, sys
sys.path.insert(0, r'E:/智慧项目/Mfkagent/backend')

MODELS = ['GLM-4.7-Flash', 'glm-4', 'GLM-4.6V-Flash']

async def one(mid):
    from app.services.model import model_service
    t0 = time.time()
    try:
        r = await asyncio.wait_for(
            model_service.call_once(model_id=mid, messages=[{'role':'user','content':'你好'}], max_tokens=20),
            timeout=40,
        )
        print(f'{mid}: OK ({time.time()-t0:.1f}s) -> {str(r)[:80]!r}')
    except asyncio.TimeoutError:
        print(f'{mid}: TIMEOUT ({time.time()-t0:.1f}s)')
    except Exception as e:
        print(f'{mid}: ERR ({time.time()-t0:.1f}s) {type(e).__name__} {str(e)[:120]}')

async def main():
    for mid in MODELS:
        await one(mid)
        await asyncio.sleep(1)

asyncio.run(main())
