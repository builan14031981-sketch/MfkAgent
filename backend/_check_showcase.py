import pathlib, re

p = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html")
c = p.read_text(encoding="utf-8", errors="ignore")
print("size:", p.stat().st_size)
print("has </html>:", "</html>" in c)
t = re.search(r"<title>([^<]+)</title>", c)
print("title:", t.group(1) if t else None)
for kw in ["严志辉", "MfkAgent", "mfkagent", "人格滑块", "三级记忆", "模型接入", "一键拉取", "FastAPI", "Electron", "智能体"]:
    print(kw, "=", c.count(kw))
print("--- colors ---")
for col in ["#0A0E16", "#101624", "#22D3EE", "#6366F1", "#00C2A8", "#F5F5F7", "#A1A1AA", "#22C55E"]:
    print(col, "=", c.upper().count(col))
print("--- 炫技交互 ---")
for kw in ["IntersectionObserver", "requestAnimationFrame", "setInterval", "addEventListener('input'", "typewriter", "addEventListener('mousemove'", "setTimeout", "range", "drag"]:
    print(kw, "=", c.count(kw))
print("opacity gating (style.opacity='0'):", c.count("el.style.opacity = '0'") + c.count("el.style.opacity='0'"))
