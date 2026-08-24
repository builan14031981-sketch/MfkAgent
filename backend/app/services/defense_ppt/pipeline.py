"""流水线编排：读文档 → 生成内容 → 渲染 pptx → 质检 → 落盘。"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, Optional

from app.services.defense_ppt.read_doc import extract_text
from app.services.defense_ppt.generate_content import generate_content
from app.services.defense_ppt.build_pptx import build_pptx
from app.services.defense_ppt.quality_check import check_pptx


def _safe_name(name: str) -> str:
    name = (name or "答辩PPT").strip()
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", name)
    return name[:60] or "答辩PPT"


async def run_pipeline(
    doc_path: str,
    discipline: str,
    style: str,
    duration_min: int,
    out_dir: Optional[str] = None,
    model_id: Optional[str] = None,
    content_json: Optional[str] = None,
    assets_dir: Optional[str] = None,
) -> Dict:
    doc_info = extract_text(doc_path)

    if content_json and os.path.exists(content_json):
        with open(content_json, "r", encoding="utf-8") as f:
            content = json.load(f)
    else:
        content = await generate_content(doc_info, discipline, style, duration_min, model_id)

    title = _safe_name(content.get("title") or doc_info.get("meta", {}).get("title"))
    out_dir = out_dir or os.path.dirname(os.path.abspath(doc_path))
    out_path = os.path.join(out_dir, f"{title}.pptx")

    build_pptx(content, style, out_path, assets_dir)
    report = check_pptx(out_path, content, doc_info, duration_min)

    return {
        "pptx_path": out_path,
        "title": title,
        "content": content,
        "report": report,
    }


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 5:
        print("用法: python pipeline.py <doc> <discipline> <style> <duration> [--out-dir DIR] [--content-json F] [--assets DIR]")
        sys.exit(1)
    res = asyncio.run(run_pipeline(
        sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]),
        out_dir=sys.argv[5] if len(sys.argv) > 5 else None,
    ))
    print(json.dumps({k: v for k, v in res.items() if k != "content"}, ensure_ascii=False, indent=2))
