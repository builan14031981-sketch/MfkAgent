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


class FileContent(BaseModel):
    path: str
    content: str
    size: int
    encoding: str


MAX_FILE_SIZE = 100 * 1024  # 100KB
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".exe", ".dll", ".so", ".dylib",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".db", ".sqlite", ".sqlite3",
}


@router.get("/{project_id}/file")
async def read_file(project_id: int, path: str):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    base_path = project.path
    file_path = os.path.join(base_path, path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Not a file")

    ext = os.path.splitext(file_path)[1].lower()
    if ext in BINARY_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Binary file not supported")

    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 100KB)")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        encoding = "utf-8"
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="gbk") as f:
                content = f.read()
            encoding = "gbk"
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unable to decode file")

    return FileContent(
        path=path,
        content=content,
        size=file_size,
        encoding=encoding,
    )


class SearchResult(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int


@router.get("/{project_id}/search")
async def search_files(project_id: int, q: str, limit: int = 20):
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    base_path = project.path
    results = []
    query = q.lower()

    for root, dirs, files in os.walk(base_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for name in dirs:
            if query in name.lower():
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, base_path)
                results.append(SearchResult(
                    name=name,
                    path=rel_path,
                    is_dir=True,
                    size=0,
                ))
                if len(results) >= limit:
                    return results

        for name in files:
            if name.startswith("."):
                continue
            if query in name.lower():
                full_path = os.path.join(root, name)
                rel_path = os.path.relpath(full_path, base_path)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    size = 0
                results.append(SearchResult(
                    name=name,
                    path=rel_path,
                    is_dir=False,
                    size=size,
                ))
                if len(results) >= limit:
                    return results

    return results
