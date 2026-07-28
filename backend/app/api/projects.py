from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import Project, Chat
from app.core.pagination import paginate

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    path: str


class ProjectResponse(BaseModel):
    id: int
    name: str
    path: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("")
async def list_projects(page: int = 1, limit: int = 20):
    db = SessionLocal()
    try:
        query = db.query(Project).order_by(Project.updated_at.desc())
        result = paginate(query, page, limit)
        result["items"] = [ProjectResponse.model_validate(p) for p in result["items"]]
        return result
    finally:
        db.close()


@router.post("", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    db = SessionLocal()
    try:
        existing = db.query(Project).filter(Project.path == project.path).first()
        if existing:
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

        db_project = Project(name=project.name, path=project.path)
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project
    finally:
        db.close()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    finally:
        db.close()


@router.delete("/{project_id}")
async def delete_project(project_id: int):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        db.delete(project)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


import os


class FileInfo(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int


@router.get("/{project_id}/files", response_model=List[FileInfo])
async def list_project_files(project_id: int, subpath: str = ""):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    base_path = project.path
    target_path = os.path.join(base_path, subpath) if subpath else base_path

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Path not found")
    if not os.path.isdir(target_path):
        raise HTTPException(status_code=400, detail="Not a directory")

    items = []
    try:
        for entry in os.scandir(target_path):
            if entry.name.startswith("."):
                continue
            items.append(
                FileInfo(
                    name=entry.name,
                    path=os.path.relpath(entry.path, base_path),
                    is_dir=entry.is_dir(),
                    size=entry.stat().st_size if entry.is_file() else 0,
                )
            )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    items.sort(key=lambda x: (not x.is_dir, x.name.lower()))
    return items
