"""答辩PPT专家 - 后端 API。

POST /api/defense-ppt/generate  一键生成
GET  /api/defense-ppt/options    学科/风格/时长选项
GET  /api/defense-ppt/templates  20 种组合的母版覆盖情况
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.database import SessionLocal
from app.models.agent import Project
from app.services.defense_ppt.pipeline import run_pipeline

router = APIRouter()

DISCIPLINES = [
    {"id": "gongke", "name": "工科"},
    {"id": "liberal", "name": "文科"},
    {"id": "science", "name": "理科"},
    {"id": "medical", "name": "医科"},
    {"id": "art_design", "name": "艺术设计"},
]
STYLES = [
    {"id": "minimal_academic", "name": "简约学术"},
    {"id": "tech", "name": "科技感"},
    {"id": "fresh", "name": "清新"},
    {"id": "formal_business", "name": "正式商务"},
]
DURATIONS = [5, 10, 15, 20]


class GenerateRequest(BaseModel):
    project_id: int
    doc_path: str            # 相对于项目目录的文档路径
    discipline: str
    style: str
    duration: int
    assets_path: Optional[str] = None   # 相对于项目目录的素材图目录（可选）
    model: Optional[str] = None
    content_json: Optional[str] = None  # 相对项目目录，传入则跳过 LLM


def _resolve_project_path(project_id: int) -> str:
    db = SessionLocal()
    try:
        proj = db.query(Project).filter(Project.id == project_id).first()
        if not proj:
            raise HTTPException(status_code=404, detail="项目不存在")
        return proj.path
    finally:
        db.close()


@router.get("/options")
async def options():
    return {"disciplines": DISCIPLINES, "styles": STYLES, "durations": DURATIONS}


@router.get("/templates")
async def templates():
    from app.services.defense_ppt.build_pptx import _REAL_DIR
    combos = []
    for d in DISCIPLINES:
        for s in STYLES:
            has = os.path.exists(os.path.join(_REAL_DIR, f"{d['id']}_{s['id']}.pptx"))
            combos.append({"discipline": d["id"], "style": s["id"], "real_master": has})
    return {"combos": combos, "real_count": sum(1 for c in combos if c["real_master"])}


@router.post("/generate")
async def generate(req: GenerateRequest):
    base = _resolve_project_path(req.project_id)
    doc_abs = os.path.join(base, req.doc_path)
    if not os.path.exists(doc_abs):
        raise HTTPException(status_code=400, detail=f"文档不存在: {req.doc_path}")
    out_dir = base
    assets_abs = os.path.join(base, req.assets_path) if req.assets_path else None
    content_abs = os.path.join(base, req.content_json) if req.content_json else None

    try:
        res = await run_pipeline(
            doc_path=doc_abs,
            discipline=req.discipline,
            style=req.style,
            duration_min=req.duration,
            out_dir=out_dir,
            model_id=req.model,
            content_json=content_abs,
            assets_dir=assets_abs,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    rel = os.path.relpath(res["pptx_path"], base).replace("\\", "/")
    return {
        "pptx_path": rel,
        "title": res["title"],
        "report": res["report"],
    }


@router.get("/download")
async def download(project_id: int, path: str):
    base = _resolve_project_path(project_id)
    abs_path = os.path.join(base, path)
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(abs_path, filename=os.path.basename(abs_path), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
