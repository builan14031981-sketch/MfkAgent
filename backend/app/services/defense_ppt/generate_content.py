"""模块2：分学科内容生成 — 调平台大模型，按学科 prompt + schema 产出结构化 JSON。

入口：async generate_content(doc_info, discipline, style, duration_min, model_id=None)
依赖：backend 的 ModelService.call_once（与聊天共用同一模型与 Key）。
"""
from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from app.services.model import ModelService

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_HERE, "prompts")

DISCIPLINE_FILES = {
    "gongke": "engineering.md",
    "liberal": "liberal.md",
    "science": "science.md",
    "medical": "medical.md",
    "art_design": "art_design.md",
}

# 时长 -> 目标页数（与 schema.md 对齐）
DURATION_PAGES = {5: 9, 10: 13, 15: 16, 20: 20}

# role -> 兜底 layout（当大模型未给 layout 时使用）
ROLE_LAYOUT = {
    "cover": "cover",
    "section": "section",
    "closing": "closing",
    "background": "two_column",
    "status": "bullets",
    "method": "image_right",
    "result": "image_right",
    "innovation": "bullets",
    "conclusion": "bullets",
    "literature": "bullets",
    "theory": "bullets",
    "analysis": "two_column",
    "data": "image_right",
    "concept": "bullets",
    "process": "two_column",
    "works": "image_right",
    "summary": "bullets",
}


def _default_model_id() -> Optional[str]:
    try:
        ms = ModelService()
        models = ms.get_available_models()
        for m in models:
            if "qwen" in str(m.get("id", "")).lower():
                return m["id"]
        if models:
            return models[0]["id"]
    except Exception:
        return None
    return None


def _load_prompt(discipline: str) -> str:
    fname = DISCIPLINE_FILES.get(discipline)
    if not fname:
        raise ValueError(f"未知学科: {discipline}（可选: {list(DISCIPLINE_FILES)}）")
    with open(os.path.join(_PROMPTS_DIR, "schema.md"), "r", encoding="utf-8") as f:
        schema = f.read()
    with open(os.path.join(_PROMPTS_DIR, fname), "r", encoding="utf-8") as f:
        disc = f.read()
    return f"{schema}\n\n---\n\n{disc}"


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        return text[s : e + 1]
    return text


def _normalize(content: Dict, doc_title: str) -> Dict:
    """补全结构、强制红线（封面/结尾、要点≤3、layout 兜底）。"""
    slides = content.get("slides") or []
    if not isinstance(slides, list):
        slides = []

    if not slides or slides[0].get("role") != "cover":
        slides.insert(0, {
            "role": "cover",
            "layout": "cover",
            "title": content.get("title") or doc_title or "毕业答辩",
            "bullets": [],
            "note": "",
            "source_refs": [],
        })
    if not slides or slides[-1].get("role") != "closing":
        slides.append({
            "role": "closing",
            "layout": "closing",
            "title": "感谢聆听，请批评指正",
            "bullets": [],
            "note": "",
            "source_refs": [],
        })

    for s in slides:
        s.setdefault("bullets", [])
        if len(s["bullets"]) > 3:
            s["bullets"] = s["bullets"][:3]
        if not s.get("layout"):
            s["layout"] = ROLE_LAYOUT.get(s.get("role"), "bullets")
        s.setdefault("note", "")
        s.setdefault("source_refs", [])
        s.setdefault("title", "")
    return content


async def generate_content(
    doc_info: Dict,
    discipline: str,
    style: str,
    duration_min: int,
    model_id: Optional[str] = None,
) -> Dict:
    """调大模型，返回结构化内容 JSON。"""
    target_pages = DURATION_PAGES.get(int(duration_min), 13)
    system_prompt = _load_prompt(discipline)
    system_prompt += (
        f"\n\n## 本次任务约束\n"
        f"- 答辩时长：{duration_min} 分钟，目标总页数约 {target_pages} 页（含封面/章节/结尾页，允许±1）。\n"
        f"- 所选模板风格：{style}。\n"
        f"- 只输出 JSON，不要任何解释性文字。所有数字/专有名词必须带 source_refs 且能在文档标记中找到。\n"
    )
    user_prompt = (
        "以下是用户论文的提取内容，已用 [P页码-段号] 标注出处。"
        "请严格按你的学科结构与 schema 生成答辩 PPT 内容 JSON：\n\n"
        + doc_info.get("annotated", "")
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    mid = model_id or _default_model_id()
    if not mid:
        raise RuntimeError(
            "未配置可用的大模型（ModelService 无可用模型）。请先在平台设置中配置模型与 API Key，"
            "或提供 --content-json 直接传入已生成的内容。"
        )

    result = await ModelService().call_once(
        mid, messages, temperature=0.3, max_tokens=4096
    )
    raw = getattr(result, "content", None) or ""
    try:
        data = json.loads(_strip_fences(raw))
    except Exception as e:
        raise RuntimeError(f"大模型返回内容无法解析为 JSON: {e}\n原始返回:\n{raw[:1000]}")

    data = _normalize(data, doc_info.get("meta", {}).get("title", ""))
    return data


if __name__ == "__main__":
    import asyncio
    import sys

    if len(sys.argv) < 3:
        print("用法: python generate_content.py <文档路径> <学科> [风格] [时长]")
        sys.exit(1)
    from app.services.defense_ppt.read_doc import extract_text
    info = extract_text(sys.argv[1])
    disc = sys.argv[2]
    style = sys.argv[3] if len(sys.argv) > 3 else "minimal_academic"
    dur = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    out = asyncio.run(generate_content(info, disc, style, dur))
    print(json.dumps(out, ensure_ascii=False, indent=2)[:3000])
