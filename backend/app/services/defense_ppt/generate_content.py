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
from app.core.skill_catalog import get_catalog


def _parse_json_robust(raw: str):
    """尽量从大模型返回中解析出 JSON 对象，容忍常见语法瑕疵与前后多余文字。"""
    text = _strip_fences(raw or "").strip()
    # 1) 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) 截取最外层 { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass
        # 3) 去除尾随逗号后再试
        fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
        try:
            return json.loads(fixed)
        except Exception:
            pass
    # 4) 抽取第一个 {...} 块（容忍嵌套之外的噪声）
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception:
            pass
    raise ValueError("无法从返回内容中提取合法 JSON")

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROMPTS_DIR = os.path.join(_HERE, "prompts")

# 核心四件套设计 Skill：内容生成时从平台 skill_catalog 真实加载并注入，
# 用它们的纪律约束答辩 PPT 的叙事、文字与排版（而非仅靠大模型自由发挥）。
_SKILL_IDS = ["ppt-builder", "ui-impeccable", "ui-kami", "copywriting-smooth"]


def _design_skill_bundle() -> str:
    """加载核心四件套 Skill 的原始 prompt，并加一段 PPT 适配桥接。"""
    catalog = {s["id"]: s for s in get_catalog()}
    adapter = (
        "# 设计 Skill 纪律（本次答辩 PPT 内容生成必须遵循）\n"
        "你将输出结构化 PPT 内容 JSON（schema 见下文）。以下四份平台设计 Skill 的纪律，"
        "请严格映射到你的输出——把它们针对 HTML/CSS 的规则，转译为对幻灯片内容与排版的约束：\n\n"
        "【ppt-builder → 叙事与版式】\n"
        "- 全 deck 走叙事弧：封面=钩子；前1-2页=定调(背景/问题)；主体=核心内容；至少1页=转折或新观点；结尾=金句/行动建议。\n"
        "- 一套 deck 只用一套主题色（即所选 style 的 accent），中途绝不换色、不混搭第二种强调色。\n"
        "- 反 slop：每页内容量适中不堆砌；不发明 schema 之外的杂乱结构；图文比例合理。\n\n"
        "【copywriting-smooth → 文字去 AI 腔】\n"
        "- 反 AI 指纹：删「此外/然而/至关重要/深入探讨/赋能/闭环/底层逻辑」等词；系动词回归（用「是/有」而非「作为/充当」）；"
        "破三段式（不硬凑三连）；删万能结尾（「未来可期」「代表重要一步」）；减信号（少破折号、少加粗、少反问）。\n"
        "- 句子长短交错，直接叙述，信任读者；金句从内容自然生长，不硬塞格言。\n\n"
        "【ui-impeccable → 层级与叙事】\n"
        "- 层级优先：用字号/字重/间距建立清晰信息层级，scanability 第一。\n"
        "- 克制色彩：中性色为底，单一强调色点缀；避免彩虹配色。\n"
        "- 排版质感：大标题收紧字距；正文一族字体。\n\n"
        "【ui-kami → 文档排版】\n"
        "- 编辑秩序：标题有层级、章节有编号/装饰线；建立稳定版面节奏。\n"
        "- 纸墨质感：衬线大标题 + 无衬线正文（若所选风格允许）。\n\n"
        "以下是四份 Skill 的原始说明（作为权威约束参考）：\n"
    )
    parts = [adapter]
    for sid in _SKILL_IDS:
        s = catalog.get(sid)
        if s:
            parts.append(f"===== Skill: {s['name']} ({sid}) =====\n{s['prompt']}")
    return "\n\n".join(parts)

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
    system_prompt = _design_skill_bundle() + "\n\n---\n\n" + _load_prompt(discipline)
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

    last_err = None
    for attempt in range(3):
        if attempt > 0:
            messages = messages + [{
                "role": "user",
                "content": "上一次返回不是合法 JSON。请只输出一个合法的 JSON 对象（不要注释、不要多余文字、"
                           "键和字符串用双引号、逗号不能遗漏），以 { 开头、} 结尾。",
            }]
        try:
            result = await ModelService().call_once(
                mid, messages, temperature=0.3, max_tokens=8000
            )
        except Exception as e:
            last_err = e
            continue
        raw = getattr(result, "content", None) or ""
        try:
            data = _parse_json_robust(raw)
        except Exception as e:
            last_err = e
            continue
        data = _normalize(data, doc_info.get("meta", {}).get("title", ""))
        return data

    raise RuntimeError(f"大模型返回内容无法解析为 JSON（已重试）: {last_err}\n原始返回:\n{raw[:1000]}")


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
