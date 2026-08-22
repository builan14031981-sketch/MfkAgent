import asyncio, time, sys
sys.path.insert(0, r'E:/智慧项目/Mfkagent/backend')

WRITE_TOOL = {"type": "function", "function": {
    "name": "write_file",
    "description": "写入/覆写本地项目文件",
    "parameters": {"type": "object", "properties": {
        "relative_path": {"type": "string", "description": "相对项目根目录的文件路径"},
        "content": {"type": "string", "description": "文件完整内容"},
    }, "required": ["relative_path", "content"]},
}}

BIG_SYSTEM = "你是前端开发工程师，负责修改项目的 React 组件。你必须严格遵循项目设计规范：间距使用4px增量（4/8/12/16px），颜色必须复用CSS变量（var(--bg-level-1..4)、var(--text-level-1..4)、var(--border-primary)、var(--color-primary)），圆角用 var(--radius-xs/md/full)，禁止硬编码色值与圆角，行高紧凑1.3~1.5，配色克制中性为主色点缀，禁止高饱和撞色与渐变堆砌。每个可交互元素必须有hover/focus/active三态。" + "本规则非常重要。" * 20

async def main():
    from app.services.model import model_service
    t0 = time.time()
    try:
        async def consume():
            n_text = n_think = 0
            calls = None
            async for ev in model_service.stream_once(
                model_id='GLM-4.7-Flash',
                messages=[
                    {'role': 'system', 'content': BIG_SYSTEM},
                    {'role': 'user', 'content': '请修改前端安全中心页面文件，让它更紧凑。先读取文件。'},
                ],
                temperature=0.7, max_tokens=4096,
                tools=[WRITE_TOOL],
            ):
                if ev.get('type') == 'text': n_text += len(ev.get('content') or '')
                if ev.get('type') == 'thinking': n_think += len(ev.get('content') or '')
                if ev.get('type') == 'tool_calls': calls = ev.get('calls')
                if ev.get('type') == 'finish':
                    print('finish:', ev.get('finish_reason'), 'usage:', ev.get('usage'))
            print(f'text={n_text} think={n_think} tool_calls={calls is not None}')
            if calls:
                for c in calls[:3]:
                    print('  tool:', c.get('function', {}).get('name'), '| args:', c.get('function', {}).get('arguments', '')[:120])
        await asyncio.wait_for(consume(), timeout=120)
        print(f'AGENT_STYLE_OK total={time.time()-t0:.1f}s')
    except asyncio.TimeoutError:
        print(f'AGENT_STYLE_TIMEOUT after {time.time()-t0:.1f}s')
    except Exception as e:
        print(f'AGENT_STYLE_ERR ({time.time()-t0:.1f}s):', type(e).__name__, str(e)[:300])

asyncio.run(main())
