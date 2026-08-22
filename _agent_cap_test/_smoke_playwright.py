# -*- coding: utf-8 -*-
"""冒烟测试：验证 playwright 从 .py_deps 导入并能打开本地前端页面。"""
import os
import sys

sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend\.py_deps")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = r"E:\智慧项目\Mfkagent\backend\.py_deps\ms-playwright"

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto("http://localhost:3000", wait_until="domcontentloaded", timeout=15000)
        title = page.title()
        h = page.evaluate("() => document.body ? document.body.scrollHeight : 0")
        print(f"[OK] title={title!r} bodyScrollHeight={h}")
    except Exception as e:
        print(f"[FAIL] goto: {type(e).__name__}: {e}")
    finally:
        browser.close()
