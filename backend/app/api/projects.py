from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.core.database import SessionLocal
from app.models.agent import Project, Chat

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


@router.get("", response_model=List[ProjectResponse])
async def list_projects():
    db = SessionLocal()
    try:
        projects = db.query(Project).order_by(Project.updated_at.desc()).all()
        return projects
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
