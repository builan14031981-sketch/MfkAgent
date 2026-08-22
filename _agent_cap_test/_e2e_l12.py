# -*- coding: utf-8 -*-
"""验证 probe_ui（L2 数值抓取）+ 沙箱 npm 可达（L1 前置）。"""
import sys

sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend")

from app.core.ui_probe_tools import probe_ui
from app.core.sandbox import run_subprocess

PROJECT = r"E:\智慧项目\Mfkagent"

print("== probe_ui (L2) ==")
r = probe_ui(
    PROJECT,
    "http://localhost:3000",
    selectors=["body", "main", "nav, aside"],
    max_elements=2,
)
print(r[:800])

print()
print("== npm reachable in sandbox (L1 pre) ==")
proc = run_subprocess(["npm", "--version"], timeout=30)
from app.core.sandbox import decode_subprocess_output
print("npm --version ->", (decode_subprocess_output(proc.stdout) or proc.stderr.decode("utf-8", "replace")).strip())
proc2 = run_subprocess(["npx", "--version"], timeout=30)
print("npx --version ->", decode_subprocess_output(proc2.stdout).strip())
