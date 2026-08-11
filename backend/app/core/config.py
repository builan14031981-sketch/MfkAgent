from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os
import sys

# Phase 9 P1: 跨平台长路径兼容
from app.core.path_utils import ensure_long_path, IS_WINDOWS

# ── 后端根目录：基于本文件位置自动计算，与进程启动目录(CWD)彻底解耦 ──
# config.py 位于 backend/app/core/config.py → 向上三级即为 backend/
_BACKEND_DIR_RAW = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = _BACKEND_DIR_RAW

# 数据文件统一锚定到 backend/ 下的绝对路径（数据库 / 上传 / 向量库 / 备份），
# 无论从哪个目录启动 uvicorn / Electron，都不会在根目录遗留散落的 db / uploads。
# Phase 9: Windows 下挂载长路径前缀，突破 260 字符限制
_DATABASE_PATH_RAW = BACKEND_DIR / "mfkagent.db"
DATABASE_PATH = _DATABASE_PATH_RAW
DATA_DIR = BACKEND_DIR

# 如果 backend 目录路径超过 200 字符，提前启用长路径前缀
if IS_WINDOWS:
    _backend_str = str(BACKEND_DIR)
    if len(_backend_str) > 200:
        BACKEND_DIR = Path(ensure_long_path(BACKEND_DIR))
        DATABASE_PATH = Path(ensure_long_path(_DATABASE_PATH_RAW))
        DATA_DIR = BACKEND_DIR

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "MfkAgent"
    DEBUG: bool = True
    
    # 数据库配置（绝对路径，as_posix 保证 SQLAlchemy Windows 兼容）
    DATABASE_URL: str = f"sqlite:///{DATABASE_PATH.as_posix()}"
    
    # 小米MiMo配置
    MIMO_API_KEY: str = ""
    MIMO_API_BASE: str = "https://token-plan-cn.xiaomimimo.com/v1"
    
    # DeepSeek配置
    DEEPSEEK_API_KEY: str = ""
    
    # 通义千问配置
    QWEN_API_KEY: str = ""
    
    # 智谱AI配置
    GLM_API_KEY: str = ""
    
    # 文心一言配置
    WENXIN_API_KEY: str = ""
    WENXIN_SECRET_KEY: str = ""
    
    # 讯飞星火配置
    SPARK_API_KEY: str = ""
    SPARK_API_SECRET: str = ""
    
    # Moonshot配置
    MOONSHOT_API_KEY: str = ""
    
    # MiniMax配置
    MINIMAX_API_KEY: str = ""
    MINIMAX_GROUP_ID: str = ""
    
    # FreeLLMAPI 本地聚合网关配置
    FREELLMAPI_API_KEY: str = "freellmapi-928ea815aac47d9db52bbf3a9029541d13e2afa78ba5297a"
    FREELLMAPI_API_BASE: str = "http://127.0.0.1:31415/v1"

    # 硅基流动配置
    SILICONFLOW_API_KEY: str = ""

    # G6-B 会话压缩：摘要模型 ID（留空则使用默认便宜模型）
    COMPRESSION_MODEL: str = ""

    # GitHub Token（用于 GitHub API 工具，如 github_create_pr）
    GITHUB_TOKEN: str = ""

    # Google Gemini 配置
    GOOGLE_API_KEY: str = ""
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"]
    
    # 文件上传配置
    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # 向量数据库配置
    CHROMA_PERSIST_DIR: str = str(BACKEND_DIR / "chroma_db")
    
    class Config:
        env_file = str(BACKEND_DIR / ".env")
        case_sensitive = True

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
