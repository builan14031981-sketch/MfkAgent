"""第二轮迭代：把视觉评审意见委派给 sub_frontend 重构作品集"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import httpx

BASE = "http://127.0.0.1:8001/api/devtools/tools/call"
PROJECT = r"E:\智慧项目\portfolio-mfkagent"

TASK = """
你在为资深产品设计师作品集做第七轮打磨。文件位于 E:\\智慧项目\\portfolio-mfkagent\\index.html（当前第六轮版本）。
先读取现有文件，再按以下第六轮评审意见定向修正，保持单文件自包含、虚构内容与人名不变。

【第六轮评审问题清单】
1. 蓝色仍偏饱和、工具化（配色 7/10）。
   -> 统一主色改为更柔和的蓝灰（如 #4A70B0 / #5B7FBF 系），featured 卡渐变同步柔和；
   数据标签（如"3个月""50万用户""4.9分"）统一用强调色做视觉锚点。
2. 右侧卡片排列机械、文字过小过密（排版 6 / 字体 6）。
   -> 右侧项目卡片改为阶梯式错落（高度依次变化，用 grid-row 控制），间距有节奏（gap 32/40px）；
   右侧卡片文字提到 15px、行高 1.8；副文本 13px 行高 1.7。
3. 左侧 featured 主卡内容区空白过多。
   -> 在 featured 卡片内加入内容填充：项目缩略图占位（class="thumb"，纯 CSS 渐变背景色块 + 少量装饰
   circle/线条，非真实图片）+ 数据标签行 + 更多描述，避免大面积空白。
4. 区块之间缺留白（整体 6.5）。
   -> 区块上下留白加大到 96px 左右（hero→projects、projects→about、about→contact 之间）；
   "关于我"段落行高 1.8、左右留出更多空间。
5. 微动效：卡片 hover 上浮已有，再给 featured 卡加轻微 scale(1.01) 过渡；导航锚点滚动平滑
   （scroll-behavior: smooth）。

实现后用 write_file 写回 E:\\智慧项目\\portfolio-mfkagent\\index.html（可用相对路径 index.html），
写后 read_file 读回验证。务必真正写入，不要只口述改动。
"""


def call(tool_name, arguments):
    resp = httpx.post(BASE, json={"tool_name": tool_name, "arguments": arguments}, timeout=600)
    print(f"[{tool_name}] HTTP {resp.status_code}")
    data = resp.json()
    print("success:", data.get("success"))
    out = data.get("output", "")
    print(out[:2000])
    print("error:", (data.get("error") or "")[:1000])
    return data


def verify_changes(markers):
    """校验 index.html 是否真的包含要求的标记，返回缺失列表。"""
    p = Path(PROJECT) / "index.html"
    if not p.exists():
        return ["文件不存在"]
    content = p.read_text(encoding="utf-8", errors="ignore")
    missing = [m for m in markers if m not in content]
    return missing


if __name__ == "__main__":
    # 本轮关键改动标记（驱动侧校验，防子代理谎报写入成功）
    MARKERS = ["class=\"thumb\"", "scroll-behavior"]
    for attempt in (1, 2):
        print(f"===== attempt {attempt} =====")
        start = time.time()
        data = call("delegate_sub_agent", {
            "sub_agent_id": "sub_frontend",
            "task": TASK + ("\n\n【重要】必须用 write_file 将完整新文件写回 "
                            "E:\\智慧项目\\portfolio-mfkagent\\index.html，写入后必须调用 read_file "
                            "读回文件并确认改动标记存在，确认无误后再结束。" if attempt == 1 else
                            "\n\n【重要】上次你并未真正写入文件就谎称成功。这次必须实际调用 write_file "
                            "写回 E:\\智慧项目\\portfolio-mfkagent\\index.html，然后 read_file 读回验证。"),
            "project_path": PROJECT,
            "max_tokens": 16384,
            "max_tool_rounds": 10,
            "reasoning_effort": "none",
        })
        print(f"elapsed: {time.time() - start:.1f}s")

        if data.get("success"):
            p = Path(PROJECT) / "index.html"
            print("--- index.html size:", p.stat().st_size if p.exists() else "MISSING")
        missing = verify_changes(MARKERS)
        if not missing:
            print("--- 校验通过：所有标记已写入 ✓")
            break
        print("--- 校验未通过，缺失标记:", missing)
