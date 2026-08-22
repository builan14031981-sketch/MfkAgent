from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)

# 启用 SQLite WAL (Write-Ahead Logging) 模式，大幅提升多线程高并发读写性能，避免 "database is locked"
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AsyncSessionLocal:
    """异步适配的独立数据库会话工厂（无 aiosqlite 依赖）。

    用法与 sqlalchemy.ext.asyncio.AsyncSessionLocal 一致：
        async with AsyncSessionLocal() as session:
            ...
    内部每次调用开启全新的同步 SessionLocal 会话，
    供后台任务（如记忆自动提取）使用，杜绝复用主 HTTP 请求的 db 对象
    导致的 InterfaceError（请求结束后 session 被销毁）。
    """

    def __init__(self):
        self._session: Session = SessionLocal()

    async def __aenter__(self) -> Session:
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()
