from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import models, agents, chat, memory, projects, settings as settings_api
from app.core.config import settings
from app.core.database import engine, Base

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MfkAgent API",
    description="智能Agent平台后端API",
    version="0.1.0",
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])

@app.get("/")
async def root():
    return {"message": "MfkAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
