"""模块4：PPT 生成与排版 — 用 python-pptx 把结构化内容渲染为 .pptx。

- 优先使用 templates/real/<discipline>_<style>.pptx 真实母版（克隆+填空）；
- 无真实母版时，用 styles.json + layouts 程序化生成（参数化引擎，保证字号/可读性）；
- 自动处理：字号（标题≥24、正文≥18）、对齐、图片（有素材图则插入，无则占位）、分页。
"""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Dict, List, Optional

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

_HERE = os.path.dirname(os.path.abspath(__file__))
_STYLES_PATH = os.path.join(_HERE, "templates", "styles.json")
_REAL_DIR = os.path.join(_HERE, "templates", "real")

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif")

# 16:9
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)


def _rgb(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.replace("#", ""))


def _set_font(run, name: str, size: int, color: RGBColor, bold: bool = False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = name
    # 同时设置东亚字体，保证中文显示
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find("{http://schemas.openxmlformats.org/drawingml/2006/main}ea")
    if ea is None:
        ea = rPr.makeelement(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}ea", {}
        )
        rPr.append(ea)
    ea.set("{http://schemas.openxmlformats.org/drawingml/2006/main}typeface", name)


def _load_styles() -> Dict:
    with open(_STYLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _list_images(assets_dir: Optional[str]) -> List[str]:
    if not assets_dir or not os.path.isdir(assets_dir):
        return []
    imgs = []
    for fn in sorted(os.listdir(assets_dir)):
        if fn.lower().endswith(IMAGE_EXTS):
            imgs.append(os.path.join(assets_dir, fn))
    return imgs


def _real_master(discipline: str, style: str) -> Optional[str]:
    cand = os.path.join(_REAL_DIR, f"{discipline}_{style}.pptx")
    return cand if os.path.exists(cand) else None


# ───────────────────────── 参数化渲染 ─────────────────────────

def _bg(slide, hex_color: str):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(hex_color)


def _add_textbox(slide, l, t, w, h, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(0.1)
    tf.margin_right = Inches(0.1)
    tf.margin_top = Inches(0.05)
    tf.margin_bottom = Inches(0.05)
    return tb, tf


def _title_bar(slide, style, title: str):
    # 顶部标题栏底色块
    bar = slide.shapes.add_shape(1, 0, 0, SLIDE_W, Inches(1.25))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _rgb(style["accent_soft"])
    bar.line.fill.background()
    bar.shadow.inherit = False
    # 左侧强调竖条
    accent = slide.shapes.add_shape(1, 0, 0, Inches(0.18), Inches(1.25))
    accent.fill.solid()
    accent.fill.fore_color.rgb = _rgb(style["accent"])
    accent.line.fill.background()
    accent.shadow.inherit = False
    tb, tf = _add_textbox(slide, Inches(0.5), Inches(0.18), SLIDE_W - Inches(1.0), Inches(0.95), MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = title
    _set_font(r, style["font_title"], style["font_size_title"], _rgb(style["title_color"]), bold=True)


def _bullets(tf, items: List[str], style, size=None):
    size = size or style["font_size_body"]
    first = True
    for it in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(10)
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = "• " + it
        _set_font(r, style["font_body"], size, _rgb(style["body_color"]))


def _render_cover(slide, style, content: Dict):
    _bg(slide, style["cover_bg"])
    tb, tf = _add_textbox(slide, Inches(1.0), Inches(2.3), SLIDE_W - Inches(2.0), Inches(2.2), MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = content.get("title") or "毕业答辩"
    _set_font(r, style["font_title"], 40, RGBColor(0xFF, 0xFF, 0xFF), bold=True)
    sub = slide.shapes.add_textbox(Inches(1.0), Inches(4.6), SLIDE_W - Inches(2.0), Inches(1.2))
    stf = sub.text_frame
    stf.word_wrap = True
    sp = stf.paragraphs[0]
    sp.alignment = PP_ALIGN.CENTER
    sr = sp.add_run()
    sr.text = "毕业答辩汇报"
    _set_font(sr, style["font_body"], 22, RGBColor(0xEE, 0xEE, 0xEE))
    info = slide.shapes.add_textbox(Inches(1.0), Inches(5.6), SLIDE_W - Inches(2.0), Inches(1.0))
    itf = info.text_frame
    itf.word_wrap = True
    ip = itf.paragraphs[0]
    ip.alignment = PP_ALIGN.CENTER
    ir = ip.add_run()
    ir.text = "专业：______   答辩人：______   导师：______"
    _set_font(ir, style["font_body"], 16, RGBColor(0xDD, 0xDD, 0xDD))


def _render_section(slide, style, content: Dict):
    _bg(slide, style["bg_alt"])
    tb, tf = _add_textbox(slide, Inches(1.0), Inches(2.8), SLIDE_W - Inches(2.0), Inches(1.6), MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = content.get("title", "")
    _set_font(r, style["font_title"], 36, _rgb(style["accent"]), bold=True)


def _render_bullets(slide, style, content: Dict):
    _bg(slide, style["bg"])
    _title_bar(slide, style, content.get("title", ""))
    tb, tf = _add_textbox(slide, Inches(0.9), Inches(1.7), SLIDE_W - Inches(1.8), Inches(5.2))
    _bullets(tf, content.get("bullets", []), style)


def _render_two_column(slide, style, content: Dict):
    _bg(slide, style["bg"])
    _title_bar(slide, style, content.get("title", ""))
    bullets = content.get("bullets", [])
    mid = (len(bullets) + 1) // 2
    left = bullets[:mid]
    right = bullets[mid:]
    lb, ltf = _add_textbox(slide, Inches(0.9), Inches(1.9), Inches(5.6), Inches(4.8))
    _bullets(ltf, left or ["—"], style)
    rb, rtf = _add_textbox(slide, Inches(6.9), Inches(1.9), Inches(5.6), Inches(4.8))
    _bullets(rtf, right or ["—"], style)
    # 中缝分隔
    sep = slide.shapes.add_shape(1, Inches(6.7), Inches(2.0), Inches(0.03), Inches(4.5))
    sep.fill.solid()
    sep.fill.fore_color.rgb = _rgb(style["accent_soft"])
    sep.line.fill.background()
    sep.shadow.inherit = False


def _render_image_right(slide, style, content: Dict, image: Optional[str]):
    _bg(slide, style["bg"])
    _title_bar(slide, style, content.get("title", ""))
    tb, tf = _add_textbox(slide, Inches(0.9), Inches(1.9), Inches(6.4), Inches(4.8))
    _bullets(tf, content.get("bullets", []), style)
    if image:
        try:
            slide.shapes.add_picture(image, Inches(7.6), Inches(2.0), Inches(5.0), Inches(4.6))
            return
        except Exception:
            pass
    # 占位
    ph = slide.shapes.add_shape(1, Inches(7.6), Inches(2.0), Inches(5.0), Inches(4.6))
    ph.fill.solid()
    ph.fill.fore_color.rgb = _rgb(style["accent_soft"])
    ph.line.color.rgb = _rgb(style["accent"])
    ph.shadow.inherit = False
    ptf = ph.text_frame
    ptf.word_wrap = True
    pp = ptf.paragraphs[0]
    pp.alignment = PP_ALIGN.CENTER
    pr = pp.add_run()
    pr.text = "图片占位\n（将素材图放入 assets 目录可自动填入）"
    _set_font(pr, style["font_body"], 16, _rgb(style["accent"]))


def _render_closing(slide, style, content: Dict):
    _bg(slide, style["cover_bg"])
    tb, tf = _add_textbox(slide, Inches(1.0), Inches(3.0), SLIDE_W - Inches(2.0), Inches(1.6), MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = content.get("title", "感谢聆听，请批评指正")
    _set_font(r, style["font_title"], 36, RGBColor(0xFF, 0xFF, 0xFF), bold=True)


def _blank_layout(prs):
    for lay in prs.slide_masters[0].slide_layouts:
        if len(lay.placeholders) == 0:
            return lay
    lays = prs.slide_masters[0].slide_layouts
    return lays[6] if len(lays) > 6 else lays[0]


def _open_master_prs(master_path: str, out_path: str):
    """复制真实母版为输出底稿，清空其原有幻灯片，仅保留主题/母版背景。"""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    shutil.copy(master_path, out_path)
    prs = Presentation(out_path)
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        rId = sldId.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        try:
            prs.part.drop_rel(rId)
        except Exception:
            pass
        sldIdLst.remove(sldId)
    return prs


def _card(slide, l, t, w, h):
    shp = slide.shapes.add_shape(1, l, t, w, h)
    shp.fill.solid()
    shp.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _render_master(slide, style, s, images, img_state):
    accent = _rgb(style["accent"])
    dark = RGBColor(0x22, 0x22, 0x22)
    layout = s.get("layout", "bullets")
    title = s.get("title", "")
    _card(slide, Inches(0.45), Inches(0.45), SLIDE_W - Inches(0.9), SLIDE_H - Inches(0.9))

    if layout == "cover":
        tb, tf = _add_textbox(slide, Inches(1.2), Inches(2.6), SLIDE_W - Inches(2.4), Inches(2.0), MSO_ANCHOR.MIDDLE)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = title or "毕业答辩"; _set_font(r, style["font_title"], 40, accent, bold=True)
        sub = slide.shapes.add_textbox(Inches(1.2), Inches(4.9), SLIDE_W - Inches(2.4), Inches(1.0))
        sp = sub.text_frame.paragraphs[0]; sp.alignment = PP_ALIGN.CENTER
        sr = sp.add_run(); sr.text = "毕业答辩汇报"; _set_font(sr, style["font_body"], 20, RGBColor(0x33, 0x33, 0x33))
        return
    if layout == "closing":
        tb, tf = _add_textbox(slide, Inches(1.2), Inches(3.2), SLIDE_W - Inches(2.4), Inches(1.4), MSO_ANCHOR.MIDDLE)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = title or "感谢聆听，请批评指正"; _set_font(r, style["font_title"], 36, accent, bold=True)
        return
    if layout == "section":
        tb, tf = _add_textbox(slide, Inches(1.2), Inches(3.0), SLIDE_W - Inches(2.4), Inches(1.4), MSO_ANCHOR.MIDDLE)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = title; _set_font(r, style["font_title"], 32, accent, bold=True)
        return

    tb, tf = _add_textbox(slide, Inches(0.9), Inches(0.8), SLIDE_W - Inches(1.8), Inches(0.9), MSO_ANCHOR.MIDDLE)
    p = tf.paragraphs[0]; r = p.add_run(); r.text = title
    _set_font(r, style["font_title"], style["font_size_title"], dark, bold=True)
    bar = slide.shapes.add_shape(1, Inches(0.9), Inches(1.75), Inches(2.2), Inches(0.06))
    bar.fill.solid(); bar.fill.fore_color.rgb = accent; bar.line.fill.background(); bar.shadow.inherit = False

    bullets = s.get("bullets", [])
    if layout == "two_column":
        mid = (len(bullets) + 1) // 2
        lb, ltf = _add_textbox(slide, Inches(0.9), Inches(2.1), Inches(5.6), Inches(4.6))
        _bullets(ltf, bullets[:mid] or ["—"], style, size=style["font_size_body"])
        rb, rtf = _add_textbox(slide, Inches(6.9), Inches(2.1), Inches(5.6), Inches(4.6))
        _bullets(rtf, bullets[mid:] or ["—"], style, size=style["font_size_body"])
    elif layout == "image_right":
        tb2, tf2 = _add_textbox(slide, Inches(0.9), Inches(2.1), Inches(6.4), Inches(4.6))
        _bullets(tf2, bullets, style, size=style["font_size_body"])
        img = images[img_state[0]] if img_state[0] < len(images) else None
        if img:
            try:
                slide.shapes.add_picture(img, Inches(7.6), Inches(2.1), Inches(5.0), Inches(4.4))
                img_state[0] += 1
            except Exception:
                _card(slide, Inches(7.6), Inches(2.1), Inches(5.0), Inches(4.4))
        else:
            _card(slide, Inches(7.6), Inches(2.1), Inches(5.0), Inches(4.4))
    else:
        tb2, tf2 = _add_textbox(slide, Inches(0.9), Inches(2.1), SLIDE_W - Inches(1.8), Inches(4.6))
        _bullets(tf2, bullets, style, size=style["font_size_body"])


def build_pptx(
    content: Dict,
    style_id: str,
    out_path: str,
    assets_dir: Optional[str] = None,
) -> str:
    """渲染 .pptx。优先真实母版（保留主题/背景，填空我们的内容），否则参数化引擎。"""
    styles = _load_styles()
    style = styles.get(style_id, styles["minimal_academic"])
    master = _real_master(content.get("discipline", ""), style_id)

    if master and os.path.exists(master):
        prs = _open_master_prs(master, out_path)
    else:
        prs = Presentation()
        prs.slide_width = SLIDE_W
        prs.slide_height = SLIDE_H

    images = _list_images(assets_dir)
    img_state = [0]
    slides_data = content.get("slides", [])
    blank = _blank_layout(prs)

    for s in slides_data:
        slide = prs.slides.add_slide(blank)
        layout = s.get("layout", "bullets")
        if master:
            _render_master(slide, style, s, images, img_state)
            continue
        if layout == "cover":
            _render_cover(slide, style, s)
        elif layout == "section":
            _render_section(slide, style, s)
        elif layout == "two_column":
            _render_two_column(slide, style, s)
        elif layout == "image_right":
            img = images[img_state[0]] if img_state[0] < len(images) else None
            if img:
                img_state[0] += 1
            _render_image_right(slide, style, s, img)
        elif layout == "closing":
            _render_closing(slide, style, s)
        else:
            _render_bullets(slide, style, s)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    prs.save(out_path)
    return out_path
