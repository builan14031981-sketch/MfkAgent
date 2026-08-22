import pathlib, re

p = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html")
c = p.read_text(encoding="utf-8", errors="ignore")
print("size:", p.stat().st_size, "mtime:", p.stat().st_mtime)
print("has .reveal css:", bool(re.search(r"\.reveal\s*\{", c)))
print("reveal class use:", c.count("reveal"))
print("has 1200ms fallback:", bool(re.search(r"1200", c)))
print("still sets el.style.opacity='0':", c.count("el.style.opacity = '0'") + c.count("el.style.opacity='0'"))
i = c.find("\u6eda\u52a8\u52a8\u753b")
print(c[i - 80:i + 1200] if i >= 0 else "no marker")