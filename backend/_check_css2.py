import pathlib, re

c = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html").read_text(encoding="utf-8", errors="ignore")
for sel in ["ecosystem-card", "ecosystem-grid", "ecosystem-name", "ecosystem-description",
            "scenario-card", "scenarios-grid", "scenario-title", "scenario-subtitle",
            "scenario-step", "step-number", "step-text"]:
    for m in re.finditer(r"(\.%s[^{}]*)\{([^}]*)\}" % re.escape(sel), c):
        print("=== ", m.group(1).strip()[:60], " ===")
        print(m.group(2).strip()[:500])
        print()