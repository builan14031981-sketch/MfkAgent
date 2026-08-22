"""FastAPI 应用入口。"""

from fastapi import FastAPI

from app.database import get_engine
from app.models import Base
from app.api import agents, chats, memories

app = FastAPI(title="MFKChat", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=get_engine())


app.include_router(agents.router)
app.include_router(chats.router)
app.include_router(memories.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}