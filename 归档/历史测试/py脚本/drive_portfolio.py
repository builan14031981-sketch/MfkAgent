"""真实场景驱动 v2：流式接口 + 短任务聚焦编排测试。

用 POST /send/stream（300s 超时），逐步驱动：
  Step 1: 让主 Agent 用 spawn_orchestration 编排设计+前端任务（不写文件，只产出方案）
  Step 2: 让主 Agent 委派前端 UI 子代理构建 index.html
"""
import json
import sys
import time
import io
import requests

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

API = "http://127.0.0.1:8001"
CHAT_ID = None  # 运行时自动创建新会话
STREAM_TIMEOUT = 900  # 流式接口给 15 分钟


def create_chat() -> int:
    body = {
        "title": "作品集编排测试",
        "agent_id": "general",
        "mode": "build",
        "project_path": r"E:\智慧项目\portfolio-mfkagent",
        "model": "glm-4.5-air",
    }
    r = requests.post(f"{API}/api/chat", json=body, timeout=15)
    r.raise_for_status()
    return r.json()["id"]

STEP1 = """接下来按这个流程执行，分两步，先只做第一步：

【第一步（现在做）】用 spawn_orchestration 工具对下面的作品集设计任务做编排，
角色建议用 architecture + frontend + researcher，让三个子代理并行给出：
- researcher：调研顶级作品集设计趋势、优秀配色方案与设计 Skill（用 web_search）
- architecture：规划作品集页面结构与视觉系统（栅格、字体、配色 token）
- frontend：给出单文件 HTML 作品集的技术实现方案（内联 CSS、响应式、动画）

这一步【不要】写任何文件，只收集三个子代理的结论，然后汇总成一份简洁的设计方案
（配色 token、字体栈、区块结构、关键效果），用中文回复。"""

STEP2 = """【第二步（现在做）】根据上面汇总的设计方案，用 delegate_sub_agent 委派
sub_frontend（前端 UI 工程师）子代理，实际构建作品集。

要求：
1. 在项目目录 E:\\智慧项目\\portfolio-mfkagent 生成 index.html（单文件、内联 CSS）
2. 内容是产品设计师作品集：我编造 6-8 个虚构作品（AI 产品设计/移动端 UI/设计系统/数据可视化），
   每个作品有名称、一句话描述、成果指标
3. 视觉：中性底色 + 单一高级强调色；衬线标题 + 无衬线正文；栅格 + 非对称排版；
   完整 hover/focus/active 交互；响应式
4. 构建完成后用 capture_screenshot 或 probe_ui 自检视觉，不满意就迭代
5. 完成后回复：构建了哪些文件、用了哪个子代理、自检结果

请立即执行第二步。"""


def send_stream(content: str) -> str:
    """发送消息并读取流式响应，返回完整 AI 输出文本。"""
    payload = {"content": content, "use_tools": True, "temperature": 0.5, "max_tokens": 16384}
    t0 = time.time()
    full = []
    with requests.post(
        f"{API}/api/chat/{CHAT_ID}/send/stream",
        json=payload,
        timeout=STREAM_TIMEOUT,
        stream=True,
    ) as resp:
        if resp.status_code != 200:
            print(f"[HTTP {resp.status_code}] {resp.text[:800]}")
            return ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if "content" in obj and isinstance(obj["content"], str):
                    full.append(obj["content"])
    dt = round(time.time() - t0, 1)
    text = "".join(full)
    print(f"[流式完成 in {dt}s, {len(text)} 字]")
    return text


def check_files():
    import os
    base = r"E:\智慧项目\portfolio-mfkagent"
    print("\n[产出物检查]")
    if not os.path.isdir(base):
        print("  目录不存在!")
        return
    found = False
    for root, dirs, files in os.walk(base):
        if ".git" in root:
            continue
        for f in files:
            found = True
            p = os.path.join(root, f)
            try:
                size = os.path.getsize(p)
            except OSError:
                size = -1
            print(f"  {os.path.relpath(p, base)}  ({size} bytes)")
    if not found:
        print("  (无文件)")


def main():
    global CHAT_ID
    CHAT_ID = create_chat()
    print(f"新建 Chat {CHAT_ID} | 绑定项目: E:\\智慧项目\\portfolio-mfkagent")
    print(f"Step1: 编排设计方案")
    out1 = send_stream(STEP1)
    print("\n===== Step1 结果 =====")
    print(out1[-2500:] if len(out1) > 2500 else out1)

    print("\n" + "=" * 70)
    print(f"Step2: 委派前端子代理构建")
    out2 = send_stream(STEP2)
    print("\n===== Step2 结果 =====")
    print(out2[-2500:] if len(out2) > 2500 else out2)

    check_files()


if __name__ == "__main__":
    main()