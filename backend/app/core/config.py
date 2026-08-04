from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "MfkAgent"
    DEBUG: bool = True
    
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./mfkagent.db"
    
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
    
    # 百川智能配置
    BAICHUAN_API_KEY: str = ""
    
    # FreeLLMAPI 本地聚合网关配置
    FREELLMAPI_API_KEY: str = "freellmapi-928ea815aac47d9db52bbf3a9029541d13e2afa78ba5297a"
    FREELLMAPI_API_BASE: str = "http://127.0.0.1:31415/v1"
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"]
    
    # 文件上传配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # 向量数据库配置
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# 确保上传目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
