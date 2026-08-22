import asyncio, time, sys
sys.path.insert(0, r'E:/智慧项目/Mfkagent/backend')

async def main():
    from app.services.model import model_service
    t0 = time.time()
    try:
        r = await asyncio.wait_for(
            model_service.call_once(
                model_id='GLM-4.7-Flash',
                messages=[{'role': 'user', 'content': '只回复两个字：你好'}],
                temperature=0.7,
                max_tokens=50,
            ),
            timeout=60,
        )
        print(f'OK ({time.time()-t0:.1f}s):', str(r)[:200])
    except asyncio.TimeoutError:
        print(f'TIMEOUT after {time.time()-t0:.1f}s')
    except Exception as e:
        print(f'ERR ({time.time()-t0:.1f}s):', type(e).__name__, str(e)[:300])

asyncio.run(main())
