"""命令行入口：供「答辩PPT专家」智能体通过 run_outside_command 调用。

示例：
  python -m app.services.defense_ppt.cli \
      --doc "E:/project/论文.docx" --discipline gongke --style tech --duration 10 \
      --out-dir "E:/project" --assets "E:/project/assets"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import argparse

# 将 backend 根目录加入 sys.path，保证 `from app...` 可导入
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.defense_ppt.pipeline import run_pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="答辩PPT专家 - 生成流水线")
    ap.add_argument("--doc", required=True, help="文档绝对路径 (.docx/.pdf/.txt)")
    ap.add_argument("--discipline", required=True, choices=["gongke", "liberal", "science", "medical", "art_design"])
    ap.add_argument("--style", required=True, choices=["minimal_academic", "tech", "fresh", "formal_business"])
    ap.add_argument("--duration", required=True, type=int, choices=[5, 10, 15, 20])
    ap.add_argument("--out-dir", default=None, help="pptx 输出目录（默认文档同目录）")
    ap.add_argument("--model", default=None, help="覆盖模型 id（默认平台首选模型）")
    ap.add_argument("--content-json", default=None, help="直接传入已生成的内容 JSON，跳过 LLM")
    ap.add_argument("--assets", default=None, help="素材图目录（自动填入图片页）")
    args = ap.parse_args()

    res = asyncio.run(run_pipeline(
        doc_path=args.doc,
        discipline=args.discipline,
        style=args.style,
        duration_min=args.duration,
        out_dir=args.out_dir,
        model_id=args.model,
        content_json=args.content_json,
        assets_dir=args.assets,
    ))
    print(json.dumps({
        "pptx_path": res["pptx_path"],
        "title": res["title"],
        "report": res["report"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
