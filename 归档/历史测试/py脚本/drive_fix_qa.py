"""QA 轮：把验收发现的缺陷清单派回 agent 修复（我只当甲方/QA，不亲自改）。"""
import httpx

BASE = "http://127.0.0.1:8001/api/chat/318/send"

QA_TASK = """【QA 验收反馈 · 上一轮构建需修复】你上一轮构建的 E:\\智慧项目\\portfolio-mfkagent\\index.html 已完成代码审查+视觉判读，发现以下必须修复的问题。请安排修复（可继续委派子代理），修复完 read_file 验证。

【P0 · 滑块卡顿（用户点名问题）】
- 现在 handleSliderMove 在每次 mousemove 事件里都执行 2 次 style 写入 + 2 次 textContent 写入，无 rAF 节流，用 left/width 属性（触发布局重排），且吸附只发生在 mouseup。
- 修复要求：① 拖动/点击期间只在档位切换时更新 UI（Math.round 前后不一致才写）；② 用 transform: translateX 移动 thumb、scaleX 或 width 用变量缓存避免每帧读布局；③ mousemove 处理器内先缓存 rect（mousedown 时读一次），不再每次 getBoundingClientRect；④ 拖动过程中实时吸附到最近档位，不必等 mouseup；⑤ 保证正好 5 档（专业/友好/中性/创意/幽默），不得增减。

【P0 · 自定义光标】
- 光标圆点和拖尾用 left/top 每帧写入 → 改 transform: translate3d（GPU 合成）。
- 检查原生光标是否隐藏：自定义光标层必须 pointer-events:none，且 body/可交互区要隐藏原生光标（cursor:none），否则出现双光标。

【P1 · 视差性能】
- 视差的 mousemove 监听器未节流、未用 lerp、每次事件都 querySelectorAll → 改为：初始化时缓存层列表，rAF 循环 + lerp 平滑，translate3d。

【P1 · 磁吸按钮】mousemove 需节流（rAF），transform 保持。

【P1 · prefers-reduced-motion】目前完全没有 → 增加：媒体查询下禁用自定义光标/视差/磁吸/滑块动画（功能仍可用）。

【P1 · 字体违规】
- 你的调研简报自己写了"避免 AI 模板化设计"，但 body 用了 Inter（AI 味头号字体），且 @import 拉取 fonts.googleapis.com（大陆网络不可达，页面字体直接降级，且违背单文件自包含）。
- 修复：移除 Google Fonts @import；正文用系统中文栈（如 -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif），标题用衬线/编辑感字体栈（如 Georgia, 'Songti SC', serif），等宽保留 JetBrains Mono 的本地降级（monospace）。标题字体不落网不降级则用系统衬线。

【P1 · 布局 AI 模板味】
- 三栏等宽功能卡 + 小图标 + 居中小标题是典型 AI 模板（你自己调研也说要避免过度规整网格）。
- 修复：改为非对称/编辑感布局（如错落排列、编号标题 01/02/03、错落行距、大小对比），保留 3 个能力但不再三栏等宽居中。

【P1 · 背景配色】
- 当前浅粉渐变被视觉判读为"网红风/甜腻"，与 MiMo 深色编辑风不符。
- 修复：改中性深底（暖炭深色如 #12141C）+ 暖纸白文字 + 单一朱红强调（#C0392B 类），去掉粉色渐变。

【完成后回报】逐条列出 P0-P1 每项的修复方式与最终验证结果（read_file 确认含 </html>）。"""