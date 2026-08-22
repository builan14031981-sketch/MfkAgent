import sys, io, asyncio, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')
from app.services.model import model_service
from app.services.model import Message

CANDIDATES = ["qwen3.5-flash", "qwen-max", "qwen-flash-character-2026-02-26", "qwen-mt-flash", "siliconflow-glm-z1-9b", "glm-5.2-fast-preview", "GLM-4.7-Flash"]

async def probe():
    print("registered models:", list(model_service.models.keys()))
    print()
    for m in CANDIDATES:
        if m not in model_service.models:
            print(f"[{m}] NOT REGISTERED")
            continue
        try:
            r = await asyncio.wait_for(model_service.call_once(model_id=m, messages=[{"role": "user", "content": "说一个字"}], temperature=0.2, max_tokens=50), timeout=30)
            txt = (r.content or '')[:40].replace('\n',' ')
            print(f"[{m}] OK -> {txt}")
        except asyncio.TimeoutError:
            print(f"[{m}] TIMEOUT")
        except Exception as e:
            msg = str(e)[:120]
            print(f"[{m}] FAIL -> {msg}")

asyncio.run(probe())