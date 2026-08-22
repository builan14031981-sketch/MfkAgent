"""pytest 全局夹具与测试环境隔离。

根因修复（2026-08-16）：此前 test_fetch_remote_phase13.py 未设置独立数据库，
pytest 全量运行时 engine 在模块级缓存，导致测试直接读写生产库 backend/mfkagent.db，
反复清空/覆盖用户真实 API Key（GLM key 多次"神秘消失"）。

conftest.py 在 pytest 收集任何测试文件之前加载，
此处先把 DATABASE_URL 指向独立测试库，保证 app.core.database 创建 engine 时
已绑定测试库，任何测试都不会触碰生产数据。
"""
import os
from pathlib import Path

import pytest

_TEST_DB_PATH = Path(__file__).resolve().parent / "mfkagent_test.db"

# 必须在任何 `from app.core.database import ...` 之前设置（engine 模块级单例缓存）。
# 直接运行时（python tests/xxx.py）不走 conftest，由各测试文件顶部自行兜底设置。
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH.as_posix()}")


@pytest.fixture(scope="session", autouse=True)
def _ensure_test_tables():
    """确保独立测试库表结构存在（测试库可能为空库，建表后各测试才能读写）。"""
    import app.models.agent  # noqa: F401  让模型注册到 Base.metadata
    from app.core.database import Base as _Base, engine as _Engine

    _Base.metadata.create_all(bind=_Engine)
    yield
