from fastapi import APIRouter
from app.core.config import settings
import shutil
import os
from datetime import datetime

router = APIRouter()

# 备份目录同样锚定到 backend/ 绝对路径，与启动目录无关
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backups")


@router.post("/backup")
async def backup_database():
    os.makedirs(BACKUP_DIR, exist_ok=True)

    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if not os.path.exists(db_path):
        return {"error": "Database file not found"}

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"mfkagent_{timestamp}.db")

    shutil.copy2(db_path, backup_path)

    backups = sorted(os.listdir(BACKUP_DIR), reverse=True)
    while len(backups) > 10:
        old_backup = backups.pop()
        os.remove(os.path.join(BACKUP_DIR, old_backup))

    return {
        "status": "success",
        "backup_path": backup_path,
        "timestamp": timestamp,
    }


@router.get("/info")
async def backup_info():
    """数据位置总览（供设置面板「数据与存储」展示）：数据库路径/大小、备份目录/数量。"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0
    backup_count = 0
    if os.path.isdir(BACKUP_DIR):
        backup_count = len([f for f in os.listdir(BACKUP_DIR) if f.endswith(".db")])
    return {
        "db_path": os.path.abspath(db_path),
        "db_name": os.path.basename(db_path),
        "db_size": db_size,
        "db_exists": db_exists,
        "backup_dir": os.path.abspath(BACKUP_DIR),
        "backup_count": backup_count,
    }


@router.get("/backups")
async def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backups = []
    for f in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if f.endswith(".db"):
            path = os.path.join(BACKUP_DIR, f)
            backups.append({
                "filename": f,
                "size": os.path.getsize(path),
                "created_at": datetime.fromtimestamp(os.path.getctime(path)).isoformat(),
            })
    return backups
