from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api import models, agents, chat, memory, projects, settings as settings_api, backup, knowledge, fonts
from app.core.config import settings
from app.core.database import engine, Base
from app.core.errors import APIError, api_error_handler, http_exception_handler, validation_exception_handler

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

# 错误处理
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# 注册路由
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(backup.router, prefix="/api/backup", tags=["backup"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(fonts.router, prefix="/api/fonts", tags=["fonts"])

@app.get("/")
async def root():
    return {"message": "MfkAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
