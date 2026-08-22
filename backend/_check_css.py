import pathlib, re

c = pathlib.Path(r"E:\智慧项目\portfolio-mfkagent\index.html").read_text(encoding="utf-8", errors="ignore")
for sel in [
    "ecosystem-grid", "ecosystem-card", "ecosystem-name", "ecosystem-description", "ecosystem-icon",
    "scenarios-grid", "scenario-card", "scenario-title", "scenario-subtitle", "scenario-step",
    "step-number", "step-text", "comparison-table", "feature-row",
]:
    css_sel = re.search(r"\.%s\s*\{" % re.escape(sel), c)
    print(sel, "css=" + ("YES" if css_sel else "NO"), "html_use=", c.count(sel))
