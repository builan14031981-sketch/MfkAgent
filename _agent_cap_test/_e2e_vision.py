# -*- coding: utf-8 -*-
"""端到端验证：capture_screenshot -> analyze_screenshot（vision_fallback 视觉通道）。"""
import json
import sys

sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend")

from app.core.ui_probe_tools import capture_screenshot, analyze_screenshot

PROJECT = r"E:\智慧项目\Mfkagent"

print("== step1: capture_screenshot ==")
r1 = capture_screenshot(PROJECT, "http://localhost:3000", wait_for="body", filename="e2e_selfcheck.png")
print(r1[:400])
d1 = json.loads(r1)
path = d1.get("path", "").replace("/", "\\")
print("screenshot path:", path)

if not path:
    print("FAIL: no screenshot path")
    sys.exit(1)

print()
print("== step2: analyze_screenshot ==")
r2 = analyze_screenshot(PROJECT, path)
print(r2[:1500])
