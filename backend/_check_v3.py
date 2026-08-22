import pathlib, re

p = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html")
c = p.read_text(encoding="utf-8", errors="ignore")
print("size:", p.stat().st_size)
print("has </html>:", "</html>" in c)
t = re.search(r"<title>([^<]+)</title>", c)
print("title:", t.group(1) if t else None)
print("--- content ---")
for kw in ["MfkAgent", "人格滑块", "三级记忆", "模型接入", "一键拉取", "JetBrains Mono", "IBM Plex Mono", "Noto Serif", "Fraunces", "Playfair", "严志辉"]:
    print(kw, "=", c.count(kw))
print("--- colors ---")
for col in ["#12141C", "#EDE8E0", "#C0392B", "#22C55E", "#0A0E16", "#22D3EE", "#6366F1"]:
    print(col, "=", c.upper().count(col))
print("--- 交互 ---")
for kw in ["IntersectionObserver", "slider", "data-step", "addEventListener", "setTimeout", "setInterval", "requestAnimationFrame", "typewriter"]:
    print(kw, "=", c.count(kw))
print("opacity gating:", c.count("opacity: '0'") + c.count("opacity:'0'") + c.count("el.style.opacity = '0'"))
print("--- 禁词 ---")
for kw in ["赋能", "解锁", "无缝", "颠覆", "极简", "强大功能"]:
    n = c.count(kw)
    if n:
        print("禁词残留:", kw, n)
print("has serif font-family:", bool(re.search(r"serif", c, re.I)))