"""第五轮：把 index.html 全量重写为「严志辉」个人求职作品集 · 编辑杂志风（浅色纸感 + 朱红强调）。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

SPEC = """把 E:\\智慧项目\\portfolio-mfkagent\\index.html 全量重写为「严志辉」个人求职作品集页。委派 delegate_sub_agent(sub_agent_id=sub_frontend, max_tokens=16384, max_tool_rounds=10, reasoning_effort=medium) 执行，写回后 read_file 验证。

【一、内容硬约束】必须完整使用以下真实信息，一个标点都不得增删改：
- 姓名：严志辉
- 职位定位：新媒体运营 · 电商视觉设计 · 短视频剪辑
- 联系方式：187 5707 3254 ｜ 3220389580@qq.com
- 所在地：浙江 · 乐清 ｜ 可到岗 ｜ 求职：美工 / 视频 / 运营
- PROFILE一句话定位：环境艺术（软装）出身的美术生，运营抖音五年，单条爆款播放 41.2 万，另有 20.7 万、19.7 万、12.3 万等多条爆款。最擅长「AI 落地」——用 AI 图像生成（字节即梦 / GPT）批量产出商品图、主图、效果图，帮公司高效降本；独立开发过 AI Agent 智能体平台，聚焦产品体验优化。懂审美、会落地、能提效的复合型内容人。
- 核心优势标签：AI 落地提效 ｜ 短视频爆款 41.2W ｜ 5 年抖音实战 ｜ 独立开发 Agent 平台 ｜ 设计+技术复合
- 项目1 AI Agent 智能体平台（独立开发 · 从零到一）：针对市面 Agent 产品普遍存在的体验痛点，独立设计并开发完整智能体平台，覆盖需求、架构、前后端、部署全流程。三条要点：人格滑块·Agent 人格交互（五档人格滑块可视化控制系统提示词注入，把复杂 Prompt 配置变成简单滑块操作，降低非技术用户门槛）；三级记忆体系（设计全局/Agent 专属/项目记忆三级体系，实现多 Agent 协作时记忆共享与隔离兼顾）；模型接入优化（内置常用模型官方入口 +「一键拉取官方最新模型」，减少手动配置、降低接入门槛）。技术栈：Python · FastAPI · Electron · AI Agent
- 项目2 抖音运营：独立运营（2021至今）｜独立运营抖音五年，代表作单条播放 41.2 万；另有 20.7 万、19.7 万、12.3 万等多条爆款——证明内容流量稳定，非单条侥幸。方法论｜懂选题策划、内容包装与流量逻辑，会用 AI 辅助文案与出图提效，能沉淀可复用的内容生产思路。
- 工作经历：软装设计公司 · 项目助理（2 个月）｜效果图/CAD 制图、接待客户、材料讲解，项目现场经验与审美落地能力。
- 教育：浙江纺织服装职业技术学院 · 环境艺术设计（软装设计方向）· 大专｜美术生出身，有扎实视觉审美与空间设计基础。
- 技能四组：AI 落地｜AI 图像生成商品图/主图/效果图（字节即梦·GPT 实操）；设计｜PS 修图调色 · 软装审美 · 室内效果图 · CAD；短视频｜抖音运营 · 选题策划 · 内容包装 · 爆款 41.2W；技术｜Python · FastAPI · Electron · AI Agent · H5/落地页

【二、编辑杂志风硬约束】
1. 背景 #F7F4EE（纸感米白）；正文主色 #1A1A1A；次级 #4A4A4A；弱化 #8A8A8A；细线分隔 #E5E0D6（1px）
2. 强调色全局唯一：朱红 #C0392B，只能用于：关键数字（41.2W/20.7W/5年等）、高亮词、姓名首字母标识、竖线/分隔元素、链接 hover、重点标签
3. 标题字体：serif 中文（font-family: 'Noto Serif SC','Source Han Serif SC',SimSun,serif）；正文：'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif；标题与正文字号/字重拉开层级（大标题至少 3rem、区块标题 1.5rem 加粗）
4. 排版：编辑杂志式大留白（区块垂直间距 ≥ 96px、左右留白 ≥ 8%）、章节用细横线分隔、左对齐、清晰栅格（关键数字可大字展示）；禁止卡片堆砌的 SaaS 模板感
5. 禁止任何把内容初始设为 opacity:0 的滚动渐显（默认必须全部可见）；如保留交互动效必须带 1.2 秒强制显示兜底
6. 单文件自包含、无外部图片依赖（头像用 CSS 圆形容器 + 文字「严」）；`<title>` 为「严志辉 · 新媒体运营 / 电商视觉设计 / 短视频剪辑」
7. 移动端自适应（max-width 媒体查询）

执行完用 read_file 验证文件完整（含 </html>），并回报：实际使用的色值清单 + 段落结构标题列表。"""

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
    print("sending editorial redesign spec...")
    try:
        resp = httpx.post(BASE, json=payload, timeout=900)
        print("HTTP", resp.status_code)
        data = resp.json()
        ai = data.get("ai_message") or {}
        print("first reply:", (ai.get("content") or "")[:600])
    except httpx.HTTPError as e:
        print("client-side disconnect (run continues in background):", type(e).__name__)