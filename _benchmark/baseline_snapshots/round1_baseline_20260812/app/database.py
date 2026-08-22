"""SQLAlchemy 引擎 / 会话管理。

测试时可通过 set_database_url 切换到内存库。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import config

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(config.DB_URL, connect_args={"check_same_thread": False})
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def set_database_url(url: str) -> None:
    """测试专用：切换数据库连接（调用后需重建 session）。

    SQLite 内存库需要 StaticPool 共享同一连接，否则每个连接各自独立
    （create_all 在一个连接、会话在另一个连接，会互相看不到表）。
    """
    global _engine, _SessionLocal
    connect_args = {"check_same_thread": False}
    if url == "sqlite://" or url == "sqlite:///:memory:":
        from sqlalchemy.pool import StaticPool
        _engine = create_engine("sqlite://", connect_args=connect_args, poolclass=StaticPool)
    else:
        _engine = create_engine(url, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def create_session() -> Session:
    return get_session_factory()()