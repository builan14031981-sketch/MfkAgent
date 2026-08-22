"""测试基线与夹具。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

import app.database as database
from app.models import Base


@pytest.fixture()
def db():
    database.set_database_url("sqlite://")
    engine = database.get_engine()
    Base.metadata.create_all(bind=engine)
    session = database.create_session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client():
    database.set_database_url("sqlite://")
    engine = database.get_engine()
    Base.metadata.create_all(bind=engine)
    from app.main import app
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)