"""用 playwright 截图作品集页面，供视觉评估。"""
import os
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer

sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend\.py_deps")

PROJECT = r"E:\智慧项目\portfolio-mfkagent"
PORT = 8399
SHOT_DIR = os.path.join(PROJECT, ".ui_selfcheck")
os.makedirs(SHOT_DIR, exist_ok=True)

os.chdir(PROJECT)
server = HTTPServer(("127.0.0.1", PORT), SimpleHTTPRequestHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
time.sleep(1)

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="networkidle")
    time.sleep(1.5)
    # 桌面端整页截图
    page.screenshot(path=os.path.join(SHOT_DIR, "portfolio_desktop.png"), full_page=True)
    print("desktop shot saved")
    # 移动端
    m = browser.new_page(viewport={"width": 390, "height": 844})
    m.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="networkidle")
    time.sleep(1.0)
    m.screenshot(path=os.path.join(SHOT_DIR, "portfolio_mobile.png"), full_page=True)
    print("mobile shot saved")
    browser.close()
server.shutdown()
print("done")