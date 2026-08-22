import pathlib, re

p = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html")
c = p.read_text(encoding="utf-8", errors="ignore")
print("size:", p.stat().st_size)
print("has </html>:", "</html>" in c)
t = re.search(r"<title>([^<]+)</title>", c)
print("title:", t.group(1) if t else None)
for kw in ["严志辉", "41.2", "乐清", "187 5707", "3220389580", "浙江·乐清", "美工", "AI Agent", "人格滑块", "三级记忆", "软装", "浙江纺织服装"]:
    print(kw, "=", c.count(kw))
print("colors: #F7F4EE=", c.upper().count("#F7F4EE"), "#C0392B=", c.upper().count("#C0392B"), "#1A1A1A=", c.upper().count("#1A1A1A"))
print("dark remnants: #0A0A0F=", c.upper().count("#0A0A0F"), "#4F8CFF=", c.upper().count("#4F8CFF"))
print("Codex remnant:", c.lower().count("codex"))
print("opacity0 gating:", c.count("opacity: '0'") + c.count("opacity:'0'") + c.count("opacity: 0"))
print("avatar 严:", c.count('>严<') + c.count('"严"'))
