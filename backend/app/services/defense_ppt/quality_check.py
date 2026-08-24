"""模块5：质量检查 — 页数/空白/字数/标题/数据溯源，输出报告。"""
from __future__ import annotations

import os
from typing import Dict, List

from app.services.defense_ppt.read_doc import count_chars

DURATION_PAGES = {5: 9, 10: 13, 15: 16, 20: 20}


def _digits(text: str) -> set:
    return set("".join(ch) for ch in text if ch.isdigit())


def check_pptx(
    pptx_path: str,
    content: Dict,
    doc_info: Dict,
    duration_min: int,
) -> Dict:
    issues: List[Dict] = []
    slides = content.get("slides", [])
    actual = len(slides)
    expected = DURATION_PAGES.get(int(duration_min), 13)

    # 1) 页数
    if abs(actual - expected) > 1:
        issues.append({
            "level": "error",
            "slide": "all",
            "message": f"页数不符：实际 {actual} 页，时长 {duration_min} 分钟应约 {expected} 页（±1）",
        })

    markers = (doc_info or {}).get("markers", {})

    for i, s in enumerate(slides, start=1):
        role = s.get("role")
        bullets = s.get("bullets", []) or []
        body = "\n".join(bullets)
        char_cnt = count_chars(body)

        # 2) 每页正文≤150字
        if char_cnt > 150:
            issues.append({
                "level": "error",
                "slide": i,
                "message": f"第{i}页正文 {char_cnt} 字，超过 150 字上限",
            })
        # 3) 要点≤3
        if len(bullets) > 3:
            issues.append({
                "level": "error",
                "slide": i,
                "message": f"第{i}页要点 {len(bullets)} 条，超过 3 条上限",
            })
        # 4) 标题
        if role not in ("cover", "closing") and not s.get("title", "").strip():
            issues.append({
                "level": "warning",
                "slide": i,
                "message": f"第{i}页缺少标题",
            })
        # 5) 空白页（章节分隔页允许无要点）
        if role not in ("cover", "closing", "section") and not bullets and not s.get("note", "").strip():
            issues.append({
                "level": "error",
                "slide": i,
                "message": f"第{i}页内容为空",
            })
        # 6) 数据溯源
        for ref in s.get("source_refs", []) or []:
            if ref == "待补充":
                issues.append({
                    "level": "warning",
                    "slide": i,
                    "message": f"第{i}页存在待补充数据（source_refs=待补充）",
                })
                continue
            if ref not in markers:
                issues.append({
                    "level": "warning",
                    "slide": i,
                    "message": f"第{i}页 source_refs '{ref}' 在源文档中找不到",
                })
                continue
            # 数字一致性：若本页含数字，源段落也应含相同数字
            bd = _digits(body)
            sd = _digits(markers.get(ref, ""))
            if bd and not bd & sd:
                issues.append({
                    "level": "warning",
                    "slide": i,
                    "message": f"第{i}页数字与出处 {ref} 不一致，疑似编造/错位",
                })

    ok = not any(it["level"] == "error" for it in issues)
    summary = (
        f"质检{'通过' if ok else '发现问题'}：{actual}页 / 目标{expected}页，"
        f"错误 {sum(1 for x in issues if x['level']=='error')} 项，"
        f"警告 {sum(1 for x in issues if x['level']=='warning')} 项。"
    )
    return {
        "ok": ok,
        "actual_pages": actual,
        "expected_pages": expected,
        "issues": issues,
        "summary": summary,
    }
