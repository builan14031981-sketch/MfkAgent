import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_get_todos_initial_empty():
    """测试初始 GET /todos 为空"""
    response = client.get("/todos")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_post_create_todo():
    """测试 POST 新增一条待办"""
    response = client.post("/todos", json={"text": "Test Todo"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["text"] == "Test Todo"
    todo_id = data["id"]

    # 验证 GET 能查到
    response = client.get("/todos")
    assert response.status_code == 200
    todos = response.json()
    assert len(todos) == 1
    assert todos[0]["id"] == todo_id
    assert todos[0]["text"] == "Test Todo"

    # 删除后消失
    response = client.delete(f"/todos/{todo_id}")
    assert response.status_code == 200

    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []


def test_delete_nonexistent_todo():
    """测试删除不存在的待办返回 404"""
    response = client.delete("/todos/999")
    assert response.status_code == 404


def test_health_check():
    """测试健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint():
    """测试根路由说明"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
