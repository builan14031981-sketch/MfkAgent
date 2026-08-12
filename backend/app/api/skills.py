"""Skill 市场 REST API。

对应「Skill 与 MCP 市场扩展计划 V2」后端 API 设计的 Skill 部分：
  GET  /api/skills/builtin    → 内置目录（含安装状态）
  GET  /api/skills/installed  → 已安装 skill id 列表
  POST /api/skills/install    → 安装（body: {skill_id}）
  POST /api/skills/uninstall  → 卸载（body: {skill_id}）

可回滚约定：卸载仅置 enabled=False，记录保留，可随时重装。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import skill_catalog

router = APIRouter()


class SkillAction(BaseModel):
    skill_id: str


@router.get("/builtin")
async def list_builtin():
    return {"skills": skill_catalog.get_builtin_with_status()}


@router.get("/installed")
async def list_installed():
    return {"skill_ids": skill_catalog.get_installed_list()}


@router.post("/install")
async def install(req: SkillAction):
    ok = skill_catalog.install_skill(req.skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Skill not found: {req.skill_id}")
    return {"status": "installed", "skill_id": req.skill_id}


@router.post("/uninstall")
async def uninstall(req: SkillAction):
    ok = skill_catalog.uninstall_skill(req.skill_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Skill not found: {req.skill_id}")
    return {"status": "uninstalled", "skill_id": req.skill_id}
