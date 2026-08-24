"""答辩PPT 真实模板爬取（best-effort）。

只爬可直链下载的 .pptx；失败/反爬/版权不明的一律跳过，由参数化引擎兜底。
用法：
  python scripts/crawl_templates.py            # 用内置候选列表尝试
  python scripts/crawl_templates.py urls.json  # urls.json: [{"url","discipline","style"}]

落盘：backend/app/services/defense_ppt/templates/real/<discipline>_<style>.pptx
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_REAL = os.path.join(_HERE, "..", "backend", "app", "services", "defense_ppt", "templates", "real")
_REAL = os.path.abspath(_REAL)

# 内置候选（部分站点可能反爬/改版，失败自动跳过）
STARTERS = [
    # 示例：把可直链的 .pptx 放到这里，例如高校开源答辩模板、OfficePlus 等
    # {"url": "https://example.com/defense_gongke.pptx", "discipline": "gongke", "style": "tech"},
]

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; defense-ppt-crawler/1.0)"}


def _is_pptx(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        if head != b"PK\x03\x04":
            return False
        # 简单校验内含 ppt/ 目录
        import zipfile
        with zipfile.ZipFile(path) as z:
            return any(n.startswith("ppt/") for n in z.namelist())
    except Exception:
        return False


def download_one(url: str, out_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        if len(data) < 5000:
            print(f"  SKIP 太小: {url}")
            return False
        tmp = out_path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        if _is_pptx(tmp):
            os.replace(tmp, out_path)
            print(f"  OK   -> {out_path}")
            return True
        os.remove(tmp)
        print(f"  SKIP 非pptx: {url}")
        return False
    except Exception as e:
        print(f"  FAIL {url}: {e}")
        return False


def main():
    targets = list(STARTERS)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            targets = json.load(f)
    os.makedirs(_REAL, exist_ok=True)
    if not targets:
        print("无候选 URL（内置列表为空）。把可直链 .pptx 填入 STARTERS 或传 urls.json 再跑。")
        print("爬不到不影响使用：参数化引擎已覆盖全部 20 种组合。")
        return
    ok = 0
    for t in targets:
        out = os.path.join(_REAL, f"{t['discipline']}_{t['style']}.pptx")
        print(f"爬取 {t['discipline']}/{t['style']}: {t['url']}")
        if download_one(t["url"], out):
            ok += 1
    print(f"完成：成功 {ok}/{len(targets)}。真实母版数 = {ok}（其余由参数化引擎兜底）。")


if __name__ == "__main__":
    main()
