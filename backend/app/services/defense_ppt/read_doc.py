"""模块1：文档理解 — 读取 docx/pdf/txt，提取文本并标注出处标记。

输出结构：
  {
    "meta": {"title": str, "path": str, "ext": str},
    "markers": { "P1-2": "该段原文...", ... },      # 出处标记 -> 原文
    "annotated": "[P1-1] ...\n[P1-2] ...",          # 带标记的全文，喂给大模型
  }
标记格式 P{页码}-{段号}，与 prompts/schema.md 中 source_refs 对齐。
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

# docx / pdf 为可选依赖，缺失时给出清晰报错
try:
    from docx import Document as DocxDocument
except Exception:  # pragma: no cover
    DocxDocument = None

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def _sanitize(text: str) -> str:
    return (text or "").strip()


def _split_paragraphs(text: str) -> List[str]:
    """把一段文本切成非空"段落"（按换行），用于 txt / pdf 行。"""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            out.append(line)
    return out


def _extract_docx(path: str) -> Dict:
    if DocxDocument is None:
        raise RuntimeError("未安装 python-docx，无法读取 .docx")
    doc = DocxDocument(path)
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    markers: Dict[str, str] = {}
    annotated_parts: List[str] = []
    title = ""
    counter = 0
    for p in paras:
        # 粗略分页：每 35 段计为一页（docx 无可靠页码）
        page = counter // 35 + 1
        local = counter % 35 + 1
        marker = f"P{page}-{local}"
        markers[marker] = p
        annotated_parts.append(f"[{marker}] {p}")
        if not title and len(p) <= 60:
            title = p
        counter += 1
    return {
        "meta": {"title": title, "path": path, "ext": "docx"},
        "markers": markers,
        "annotated": "\n".join(annotated_parts),
    }


def _extract_pdf(path: str) -> Dict:
    if PdfReader is None:
        raise RuntimeError("未安装 pypdf，无法读取 .pdf")
    reader = PdfReader(path)
    markers: Dict[str, str] = {}
    annotated_parts: List[str] = []
    title = ""
    for pi, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = _split_paragraphs(text)
        for li, line in enumerate(lines, start=1):
            marker = f"P{pi}-{li}"
            markers[marker] = line
            annotated_parts.append(f"[{marker}] {line}")
            if not title and 4 <= len(line) <= 60:
                title = line
    return {
        "meta": {"title": title, "path": path, "ext": "pdf"},
        "markers": markers,
        "annotated": "\n".join(annotated_parts),
    }


def _extract_txt(path: str) -> Dict:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    lines = _split_paragraphs(text)
    markers: Dict[str, str] = {}
    annotated_parts: List[str] = []
    title = ""
    for li, line in enumerate(lines, start=1):
        marker = f"P1-{li}"
        markers[marker] = line
        annotated_parts.append(f"[{marker}] {line}")
        if not title and 4 <= len(line) <= 60:
            title = line
    return {
        "meta": {"title": title, "path": path, "ext": "txt"},
        "markers": markers,
        "annotated": "\n".join(annotated_parts),
    }


def extract_text(path: str) -> Dict:
    """读取文档，返回带出处标记的提取结果。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext in (".txt", ".md", ".text"):
        return _extract_txt(path)
    raise ValueError(f"不支持的文档类型: {ext}（仅支持 .docx/.pdf/.txt）")


def count_chars(text: str) -> int:
    """统计中文字符数（用于每页≤150字约束，按汉字计更直观）。"""
    return len(re.findall(r"[一-鿿]", text))


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("用法: python read_doc.py <文档路径>")
        sys.exit(1)
    info = extract_text(sys.argv[1])
    print(json.dumps(info, ensure_ascii=False, indent=2)[:2000])
