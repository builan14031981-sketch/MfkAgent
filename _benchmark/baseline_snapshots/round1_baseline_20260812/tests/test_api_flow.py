"""端到端 API 测试：Agent → Chat → Message → Memory。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_agent_lifecycle(client):
    r = client.post("/agents", json={
        "agent_id": "coder",
        "name": "开发者",
        "identity": "你是高级工程师",
        "capabilities": ["coding", "debug"],
        "personality_level": 50,
    })
    assert r.status_code == 200
    agent_id = r.json()["id"]

    r = client.get(f"/agents/{r.json()['agent_id']}")
    assert r.status_code == 200
    assert r.json()["capabilities"] == ["coding", "debug"]


def test_create_chat_and_send(client):
    client.post("/agents", json={
        "agent_id": "helper",
        "name": "助手",
        "identity": "你是乐于助人的助手",
        "capabilities": [],
        "personality_level": 0,
    })
    chat = client.post("/chats", json={"agent_id": "helper", "title": "测试会话", "mode": "chat"})
    assert chat.status_code == 200
    chat_id = chat.json()["id"]

    r = client.post(f"/chats/{chat_id}/send", json={"content": "帮我看看这个文件的内容"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_message"]["content"] == "帮我看看这个文件的内容"
    assert body["ai_message"]["content"]
    assert body["meta"]["intent"] == "file_operation"

    msgs = client.get(f"/chats/{chat_id}/messages")
    assert len(msgs.json()) == 2  # user + assistant


def test_chat_generates_memory(client, db):
    client.post("/agents", json={
        "agent_id": "memtest",
        "name": "记忆测试",
        "identity": "",
        "capabilities": [],
        "personality_level": 0,
    })
    chat = client.post("/chats", json={"agent_id": "memtest"}).json()

    # 长消息触发自动记忆提取
    long_msg = "这是一条超过二十个字的用户消息，关于项目架构的重要决定" * 2
    client.post(f"/chats/{chat['id']}/send", json={"content": long_msg})

    mems = client.get("/memories", params={"scope": "agent", "agent_id": "memtest"})
    assert len(mems.json()) >= 1


def test_memory_crud_api(client):
    r = client.post("/memories", json={"scope": "global", "content": "记住：反馈要简洁"})
    assert r.status_code == 200
    mem_id = r.json()["id"]

    r = client.get("/memories", params={"scope": "global"})
    assert any(m["id"] == mem_id for m in r.json())

    r = client.delete(f"/memories/{mem_id}")
    assert r.status_code == 200


def test_memory_invalid_scope(client):
    r = client.post("/memories", json={"scope": "bad", "content": "x"})
    assert r.status_code == 400