import asyncio, time, sys
sys.path.insert(0, r'E:/智慧项目/Mfkagent/backend')

async def main():
    from app.services.model import model_service
    # 复刻 Agent 实际路径：stream_once 流式调用
    t0 = time.time()
    try:
        async def consume():
            n_text, n_think = 0, 0
            async for ev in model_service.stream_once(
                model_id='GLM-4.7-Flash',
                messages=[{'role': 'user', 'content': '只回复三个字：你好呀'}],
                temperature=0.7,
                max_tokens=100,
            ):
                if ev.get('type') == 'text':
                    n_text += len(ev.get('content') or '')
                if ev.get('type') == 'thinking':
                    n_think += len(ev.get('content') or '')
                if ev.get('type') == 'finish':
                    print('finish:', ev.get('finish_reason'), 'usage:', ev.get('usage'))
            print(f'text_chars={n_text} think_chars={n_think}')
        await asyncio.wait_for(consume(), timeout=150)
        print(f'STREAM_OK total={time.time()-t0:.1f}s')
    except asyncio.TimeoutError:
        print(f'STREAM_TIMEOUT after {time.time()-t0:.1f}s')
    except Exception as e:
        print(f'STREAM_ERR ({time.time()-t0:.1f}s):', type(e).__name__, str(e)[:300])

asyncio.run(main())
