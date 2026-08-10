from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import os
import base64
from app.core.database import SessionLocal
from app.models.agent import Project, Chat
from app.core.pagination import paginate
from app.core.sandbox import SandboxViolation, resolve_sandbox_path

router = APIRouter()


class ProjectCreate(BaseModel):
    path: str
    name: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    path: str
    is_pinned: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


def _validate_project_path(raw_path: str) -> str:
    """校验并规范化本地目录绝对路径：必须为绝对路径、目录存在，返回 realpath 规范化值"""
    if not raw_path or not raw_path.strip():
        raise HTTPException(status_code=400, detail="路径不能为空")
    path = raw_path.strip().strip('"').strip("'")

    if not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="必须提供本地目录绝对路径")

    real_path = os.path.realpath(path)
    if not os.path.exists(real_path):
        raise HTTPException(status_code=404, detail=f"目录不存在: {real_path}")
    if not os.path.isdir(real_path):
        raise HTTPException(status_code=400, detail=f"不是目录: {real_path}")
    return real_path


@router.get("")
async def list_projects(page: int = 1, limit: int = 20):
    db = SessionLocal()
    try:
        query = db.query(Project).filter(Project.is_deleted == False).order_by(Project.is_pinned.desc(), Project.updated_at.desc())
        result = paginate(query, page, limit)
        result["items"] = [ProjectResponse.model_validate(p) for p in result["items"]]
        return result
    finally:
        db.close()


@router.post("", response_model=ProjectResponse)
async def create_project(project: ProjectCreate):
    db = SessionLocal()
    try:
        real_path = _validate_project_path(project.path)
        name = (project.name or "").strip() or os.path.basename(real_path.rstrip("/\\")) or real_path

        # 去重：同路径未删除项目直接返回；若唯一记录已被软删则恢复
        existing = db.query(Project).filter(Project.path == real_path).first()
        if existing:
            if existing.is_deleted:
                existing.is_deleted = False
                existing.deleted_at = None
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

        db_project = Project(name=name, path=real_path)
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
        project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    finally:
        db.close()


class ProjectUpdate(BaseModel):
    is_pinned: Optional[bool] = None


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, update: ProjectUpdate):
    """更新项目（支持置顶 / 取消置顶）"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id, Project.is_deleted == False).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        if update.is_pinned is not None:
            project.is_pinned = update.is_pinned
        project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(project)
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
        if project.is_deleted:
            raise HTTPException(status_code=400, detail="Project already in trash")
        now = datetime.utcnow()
        project.is_deleted = True
        project.deleted_at = now
        # 级联软删其下所有 Chat
        db.query(Chat).filter(Chat.project_id == project_id, Chat.is_deleted == False).update(
            {"is_deleted": True, "deleted_at": now}
        )
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


def _resolve_safe_path(base_path: str, relative_path: str) -> str:
    """安全解析项目内路径（统一沙箱校验，防绝对路径与 .. 穿越）。

    委托 app.core.sandbox.resolve_sandbox_path，越权抛 SandboxViolation，
    在此转换为 HTTP 400 响应。
    """
    try:
        return str(resolve_sandbox_path(relative_path, base_path))
    except SandboxViolation as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    target_path = _resolve_safe_path(base_path, subpath)

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
    file_path = _resolve_safe_path(base_path, path)

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


# ──────────────────────────────────────────────────────────────────────────
# Phase 2: 附件读取端点（返回 base64，供图片多模态使用）
# ──────────────────────────────────────────────────────────────────────────

# 附件端点允许的文件类型白名单扩展名（含图片与文档）
_ATTACHMENT_ALLOWED_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}
# 附件端点最大文件大小（10MB，base64 编码后约 13MB）
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

# MIME 类型推断（常用图片）
_EXT_MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".pdf": "application/pdf",
    ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class AttachmentContent(BaseModel):
    """附件读取响应：base64 编码内容 + 元数据。"""
    path: str
    content_base64: str
    mime: str
    size: int
    encoding: str = "base64"


@router.get("/{project_id}/attachment", response_model=AttachmentContent)
async def read_attachment(project_id: int, path: str):
    """读取项目内附件文件，返回 base64 编码内容（供前端图片多模态预览使用）。

    - 复用 _resolve_safe_path 沙箱校验（防路径穿越）
    - 仅允许 _ATTACHMENT_ALLOWED_EXTS 白名单扩展名
    - 文件大小上限 10MB
    - 返回 base64 编码，前端可直接用于 data URI 或解码展示
    """
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    finally:
        db.close()

    base_path = project.path
    file_path = _resolve_safe_path(base_path, path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=400, detail="Not a file")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in _ATTACHMENT_ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的附件类型: {ext}（允许: 图片/PDF/Office 文档）",
        )

    file_size = os.path.getsize(file_path)
    if file_size > MAX_ATTACHMENT_SIZE:
        raise HTTPException(status_code=400, detail="附件过大（最大 10MB）")

    try:
        with open(file_path, "rb") as f:
            raw = f.read()
    except OSError:
        raise HTTPException(status_code=500, detail="读取文件失败")

    b64 = base64.b64encode(raw).decode("ascii")
    mime = _EXT_MIME_MAP.get(ext, "application/octet-stream")

    return AttachmentContent(
        path=path,
        content_base64=b64,
        mime=mime,
        size=file_size,
        encoding="base64",
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
