from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os
import sys

# Phase 9 P1: 跨平台长路径兼容
from app.core.path_utils import ensure_long_path, IS_WINDOWS

# ── 打包模式检测：PyInstaller 运行时 sys.frozen=True ──
_IS_FROZEN = bool(getattr(sys, "frozen", False))


def _frozen_data_root() -> Path:
    """打包模式的可写数据根目录。

    PyInstaller 运行时 __file__ 指向 _MEIPASS 临时解压目录（每次启动重建、退出清空），
    数据库 / 上传 / 备份 / 日志 / .env 等可写数据必须锚定到用户可持久化目录：
      Windows: %APPDATA%/MfkAgent    macOS: ~/Library/Application Support/MfkAgent
      Linux:   ~/.local/share/MfkAgent
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "MfkAgent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MfkAgent"
    return Path.home() / ".local" / "share" / "MfkAgent"


# ── 后端根目录：config 出口，所有下游一律引用此处，不要散落第二次 __file__ 计算 ──
# 开发模式：基于本文件位置自动计算（config.py 位于 backend/app/core/ → 向上三级），
# 与进程启动目录(CWD)彻底解耦。
# 打包模式：统一切换到可写数据根目录。config.BACKEND_DIR 的下游消费者（数据库 /
# 上传 / Archive / .env / 端口文件）全部把它当可写根用；app 包内只读资产
# （greetings.json 等）走包内 __file__ 相对读取，PyInstaller 解到 _MEIPASS 天然可用，
# 不经过本出口。
if _IS_FROZEN:
    BACKEND_DIR = _frozen_data_root()
    # sqlite 引擎在 app.core.database 导入期即按 DATABASE_PATH 连库，目录必须先存在
    os.makedirs(BACKEND_DIR, exist_ok=True)
else:
    BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BACKEND_DIR
DATABASE_PATH = BACKEND_DIR / "mfkagent.db"
# 端口文件规范出口（当前 app/core/port_manager.py 自算锚点，后续收敛到此处）
PORT_FILE = BACKEND_DIR / ".mfkagent_port"

# 如果目录路径超过 200 字符，提前启用长路径前缀（Phase 9；打包数据根通常较短，统一走出口无害）
if IS_WINDOWS:
    _backend_str = str(BACKEND_DIR)
    if len(_backend_str) > 200:
        BACKEND_DIR = Path(ensure_long_path(BACKEND_DIR))
        DATA_DIR = BACKEND_DIR
        DATABASE_PATH = Path(ensure_long_path(DATABASE_PATH))
        PORT_FILE = Path(ensure_long_path(PORT_FILE))

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

    # LongCat 配置
    LONGCAT_API_KEY: str = ""

    # G6-B 会话压缩：摘要模型 ID（留空则使用默认便宜模型）
    COMPRESSION_MODEL: str = ""

    # GitHub Token（用于 GitHub API 工具，如 github_create_pr）
    GITHUB_TOKEN: str = ""

    # Google Gemini 配置
    GOOGLE_API_KEY: str = ""

    # 飞书配置（用于飞书多维表格集成）
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_WS_ENABLED: bool = True
    
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
        extra = "allow"

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
