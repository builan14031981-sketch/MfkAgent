"""第四轮：修复 IntersectionObserver 滚动渐显导致的截图/首屏空白。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

SPEC = """index.html 存在一个渲染 bug：'滚动动画' 的 IntersectionObserver 把 .feature-card/.ecosystem-card/.scenario-card 初始设为 opacity:0，只有滚动触发才显示。
后果：全页截图不滚动时这些卡片区（完整的开发生态/典型应用场景）整块空白；JS 未触发或禁用时用户也看不到内容。

修复要求（只动 <script> 内 '滚动动画' 这一段，其余不许改）：
1. 保留渐进增强的滚动渐显，但**绝不允许初始隐藏内容**：
   改为先给这三类卡片加一个 class='reveal'，并加 CSS：.reveal { opacity: 1; transform: none; }（默认可见）。
2. 仅当支持 IntersectionObserver 且页面已滚动时才做渐显，且必须加 1.2 秒安全兜底定时器：
   setTimeout(() => { document.querySelectorAll('.reveal').forEach(el => { el.style.opacity='1'; el.style.transform='translateY(0)'; }); }, 1200);
   兜底确保无论是否触发滚动，1.2 秒后所有卡片必现。
3. 不允许再出现任何把内容初始置为 opacity:0 且无兜底的写法。
改完 read_file 验证，并回报改动后的 JS 片段。"""

if __name__ == "__main__":
    payload = {
        "content": SPEC,
        "model": None,
        "temperature": 0.5,
        "max_tokens": 16384,
        "use_tools": True,
        "reasoning_effort": "medium",
        "planning_level": 1,
    }
    print("sending scroll-reveal fix to main agent...")
    try:
        resp = httpx.post(BASE, json=payload, timeout=900)
        print("HTTP", resp.status_code)
        data = resp.json()
        ai = data.get("ai_message") or {}
        print("first reply:", (ai.get("content") or "")[:600])
    except httpx.HTTPError as e:
        print("client-side disconnect (run continues in background):", type(e).__name__)