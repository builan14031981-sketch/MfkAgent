"""
Timeline Persistence 真实链路验收测试

验证 Message.timeline 持久化是否真正工作。

用法（在 backend/ 目录下执行）：
    python tests/test_timeline_persistence.py

前置条件：
    1. 后端服务已启动: python -m uvicorn main:app --host 0.0.0.0 --port 8000
    2. migration 已执行（main.py 启动时会自动执行 _ensure_schema）
    3. 已配置有效的模型 API Key（Settings 中 default_model 对应 provider）

测试流程：
    Test 1: 工具调用 Agent 任务（必须触发 tool_start/tool_result）
    Test 2: 无工具普通聊天
    Test 3: 工具失败情况
"""

import requests
import json
import sys
import os
import time
import sqlite3

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api"
DB_PATH = "mfkagent.db"  # 相对于 backend/ 目录

# ──── 工具函数 ────

def api_get(path: str):
    resp = requests.get(f"{BASE_URL}{API_PREFIX}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()

def api_post(path: str, data: dict):
    resp = requests.post(f"{BASE_URL}{API_PREFIX}{path}", json=data, timeout=120)
    resp.raise_for_status()
    return resp.json()

def stream_post(path: str, data: dict):
    """SSE 流式请求，返回收集到的所有事件。"""
    events = []
    resp = requests.post(
        f"{BASE_URL}{API_PREFIX}{path}",
        json=data,
        stream=True,
        timeout=300,
        headers={"Accept": "text/event-stream"},
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("data: "):
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                events.append(json.loads(data_str))
            except json.JSONDecodeError:
                pass
    return events

def db_query(sql: str, params=()):
    """查询 SQLite 数据库。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def check_server():
    """检查服务是否可用。"""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False

def get_or_create_project():
    """获取或创建项目（工具调用需要绑定项目）。"""
    result = api_get("/projects?limit=1")
    items = result.get("items", []) if isinstance(result, dict) else result
    if items and len(items) > 0:
        pid = items[0]["id"]
        print(f"  使用已有项目: id={pid}, name={items[0].get('name')}")
        return pid
    # 创建新项目
    data = api_post("/projects", {
        "name": "Timeline Test Project",
        "path": os.path.abspath(".."),
    })
    print(f"  创建测试项目: id={data['id']}")
    return data["id"]

def create_chat(project_id=None):
    """创建一个新 Chat 并返回 chat_id。"""
    if project_id is None:
        project_id = get_or_create_project()
    data = api_post("/chat", {
        "title": f"Timeline Test {int(time.time())}",
        "project_id": project_id,
        "mode": "build",
    })
    return data["id"]

def get_latest_assistant_message(chat_id):
    """获取指定 chat 的最新一条 assistant 消息。"""
    rows = db_query(
        "SELECT * FROM messages WHERE chat_id = ? AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
        (chat_id,),
    )
    if not rows:
        return None
    msg = rows[0]
    # 解析 JSON 字段
    for field in ("tool_calls", "timeline"):
        if msg.get(field) and isinstance(msg[field], str):
            try:
                msg[field] = json.loads(msg[field])
            except json.JSONDecodeError:
                pass
    return msg

def validate_timeline(timeline, expected_checks: dict) -> dict:
    """验证 timeline 结构，返回检查结果。"""
    results = {}
    
    if not timeline:
        results["timeline 为空"] = "FAIL"
        return results
    
    results["timeline 非空"] = "PASS"
    results["timeline 条目数"] = len(timeline)
    
    # 检查类型顺序
    types = [e.get("type") for e in timeline]
    results["事件类型顺序"] = types
    
    # 按 expected_checks 逐项检查
    for check_name, expected in expected_checks.items():
        if check_name == "has_tool_start":
            has = any(e.get("type") == "tool_start" for e in timeline)
            results["包含 tool_start"] = "PASS" if has == expected else f"FAIL (expected={expected}, got={has})"
        elif check_name == "has_tool_result":
            has = any(e.get("type") == "tool_result" for e in timeline)
            results["包含 tool_result"] = "PASS" if has == expected else f"FAIL (expected={expected}, got={has})"
        elif check_name == "has_text":
            has = any(e.get("type") == "text" for e in timeline)
            results["包含 text"] = "PASS" if has == expected else f"FAIL (expected={expected}, got={has})"
        elif check_name == "has_thinking":
            has = any(e.get("type") == "thinking" for e in timeline)
            results["包含 thinking"] = "PASS" if has == expected else f"FAIL (expected={expected}, got={has})"
        elif check_name == "no_finish":
            has = any(e.get("type") == "finish" for e in timeline)
            results["无 finish 事件"] = "PASS" if not has else "FAIL (finish 不应出现在 timeline)"
        elif check_name == "no_error":
            has = any(e.get("type") == "error" for e in timeline)
            results["无 error 事件"] = "PASS" if not has else "FAIL (error 不应出现在 timeline)"
        elif check_name == "tool_result_fields":
            for e in timeline:
                if e.get("type") == "tool_result":
                    fields_ok = all(k in e for k in ("tool_call_id", "tool", "success", "result", "duration_ms"))
                    results["tool_result 字段完整"] = "PASS" if fields_ok else "FAIL"
                    break
        elif check_name == "has_failed_tool":
            has = any(
                e.get("type") == "tool_result" and e.get("success") == False
                for e in timeline
            )
            results["包含失败的工具结果"] = "PASS" if has == expected else f"FAIL (expected={expected}, got={has})"
        elif check_name == "order_check":
            # 检查顺序：thinking 应在 tool_start 之前，tool_start 应在 tool_result 之前
            order_ok = True
            last_type = None
            for e in timeline:
                t = e.get("type")
                if t == "tool_result" and last_type not in ("tool_start", "tool_result"):
                    order_ok = False
                last_type = t
            results["事件顺序正确"] = "PASS" if order_ok else "FAIL"
    
    return results


# ──── 测试用例 ────

def test_1_tool_agent():
    """Test 1: 工具调用 Agent 任务"""
    print("\n" + "=" * 60)
    print("Test 1: 工具调用 Agent 任务")
    print("=" * 60)
    
    chat_id = create_chat()
    print(f"  Created chat: {chat_id}")
    
    prompt = "请帮我分析当前项目结构。先查看项目根目录文件列表，然后读取一个核心文件（例如 README.md 或 backend/app/main.py），最后告诉我项目主要结构。"
    
    print(f"  Sending prompt: {prompt[:60]}...")
    events = stream_post(f"/chat/{chat_id}/send/stream", {
        "content": prompt,
        "use_tools": True,
    })
    
    print(f"  SSE events received: {len(events)}")
    event_types = [e.get("type") for e in events]
    print(f"  Event types: {event_types}")
    
    time.sleep(1)  # 等待数据库写入
    
    msg = get_latest_assistant_message(chat_id)
    if not msg:
        return {"status": "FAIL", "error": "未找到 assistant 消息"}
    
    print(f"  message_id: {msg['id']}")
    print(f"  content length: {len(msg.get('content', ''))}")
    print(f"  thinking: {'present' if msg.get('thinking') else 'none'}")
    print(f"  tool_calls count: {len(msg.get('tool_calls') or [])}")
    
    timeline = msg.get("timeline")
    print(f"  timeline count: {len(timeline) if timeline else 0}")
    
    results = validate_timeline(timeline, {
        "has_tool_start": True,
        "has_tool_result": True,
        "has_text": True,
        "has_thinking": True,
        "no_finish": True,
        "no_error": True,
        "tool_result_fields": True,
        "order_check": True,
    })
    
    for k, v in results.items():
        print(f"  {k}: {v}")
    
    return {
        "status": "PASS" if all("FAIL" not in str(v) for v in results.values()) else "PARTIAL",
        "message_id": msg["id"],
        "content": msg.get("content", "")[:200] + "...",
        "thinking": msg.get("thinking", "")[:100] + "..." if msg.get("thinking") else None,
        "tool_calls": msg.get("tool_calls"),
        "timeline": timeline,
        "checks": results,
    }


def test_2_normal_chat():
    """Test 2: 无工具普通聊天"""
    print("\n" + "=" * 60)
    print("Test 2: 无工具普通聊天")
    print("=" * 60)
    
    chat_id = create_chat()
    print(f"  Created chat: {chat_id}")
    
    prompt = "你好，请介绍一下自己。"
    
    print(f"  Sending prompt: {prompt}")
    events = stream_post(f"/chat/{chat_id}/send/stream", {
        "content": prompt,
        "use_tools": True,
    })
    
    print(f"  SSE events received: {len(events)}")
    event_types = [e.get("type") for e in events]
    print(f"  Event types: {event_types}")
    
    time.sleep(1)
    
    msg = get_latest_assistant_message(chat_id)
    if not msg:
        return {"status": "FAIL", "error": "未找到 assistant 消息"}
    
    print(f"  message_id: {msg['id']}")
    print(f"  content: {msg.get('content', '')[:100]}...")
    
    timeline = msg.get("timeline")
    print(f"  timeline: {json.dumps(timeline, ensure_ascii=False) if timeline else 'None'}")
    
    results = validate_timeline(timeline, {
        "has_tool_start": False,
        "has_tool_result": False,
        "has_text": True,
        "no_finish": True,
        "no_error": True,
    })
    
    for k, v in results.items():
        print(f"  {k}: {v}")
    
    return {
        "status": "PASS" if all("FAIL" not in str(v) for v in results.values()) else "PARTIAL",
        "message_id": msg["id"],
        "timeline": timeline,
        "checks": results,
    }


def test_3_tool_error():
    """Test 3: 工具失败情况"""
    print("\n" + "=" * 60)
    print("Test 3: 工具失败情况")
    print("=" * 60)
    
    chat_id = create_chat()
    print(f"  Created chat: {chat_id}")
    
    prompt = "读取一个不存在的文件 nonexistent_test_file.txt，然后告诉我结果。"
    
    print(f"  Sending prompt: {prompt}")
    events = stream_post(f"/chat/{chat_id}/send/stream", {
        "content": prompt,
        "use_tools": True,
    })
    
    print(f"  SSE events received: {len(events)}")
    event_types = [e.get("type") for e in events]
    print(f"  Event types: {event_types}")
    
    time.sleep(1)
    
    msg = get_latest_assistant_message(chat_id)
    if not msg:
        return {"status": "FAIL", "error": "未找到 assistant 消息"}
    
    print(f"  message_id: {msg['id']}")
    print(f"  content: {msg.get('content', '')[:200]}...")
    
    timeline = msg.get("timeline")
    print(f"  timeline: {json.dumps(timeline, ensure_ascii=False, indent=2) if timeline else 'None'}")
    
    results = validate_timeline(timeline, {
        "has_tool_start": True,
        "has_tool_result": True,
        "has_text": True,
        "has_failed_tool": True,
        "no_finish": True,
        "no_error": True,
        "tool_result_fields": True,
    })
    
    for k, v in results.items():
        print(f"  {k}: {v}")
    
    return {
        "status": "PASS" if all("FAIL" not in str(v) for v in results.values()) else "PARTIAL",
        "message_id": msg["id"],
        "timeline": timeline,
        "checks": results,
    }


# ──── 主函数 ────

def main():
    print("=" * 60)
    print("Timeline Persistence 真实链路验收测试")
    print("=" * 60)
    
    # 前置检查
    if not os.path.exists(DB_PATH):
        print(f"\n[ERROR] 数据库文件不存在: {DB_PATH}")
        print("请确保在 backend/ 目录下运行此脚本。")
        sys.exit(1)
    
    if not check_server():
        print(f"\n[ERROR] 后端服务未启动 ({BASE_URL})")
        print("请先启动: python -m uvicorn main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    print(f"\n[OK] 后端服务已启动: {BASE_URL}")
    
    # 检查 migration
    try:
        cols = db_query("PRAGMA table_info(messages)")
        col_names = [c["name"] for c in cols]
        if "timeline" not in col_names:
            print(f"\n[ERROR] messages 表缺少 timeline 列")
            print(f"当前列: {col_names}")
            print("请重启后端服务以触发 _ensure_schema() 自动迁移。")
            sys.exit(1)
        print(f"[OK] timeline 列已存在: {col_names}")
    except Exception as e:
        print(f"\n[ERROR] 数据库检查失败: {e}")
        sys.exit(1)
    
    # 检查 API
    try:
        api_get("/chat?limit=1")
        print("[OK] API 可正常访问")
    except Exception as e:
        print(f"\n[ERROR] API 不可用: {e}")
        sys.exit(1)
    
    # 运行测试
    report = {}
    
    try:
        report["test_1"] = test_1_tool_agent()
    except Exception as e:
        print(f"\n[ERROR] Test 1 失败: {e}")
        import traceback
        traceback.print_exc()
        report["test_1"] = {"status": "ERROR", "error": str(e)}
    
    try:
        report["test_2"] = test_2_normal_chat()
    except Exception as e:
        print(f"\n[ERROR] Test 2 失败: {e}")
        import traceback
        traceback.print_exc()
        report["test_2"] = {"status": "ERROR", "error": str(e)}
    
    try:
        report["test_3"] = test_3_tool_error()
    except Exception as e:
        print(f"\n[ERROR] Test 3 失败: {e}")
        import traceback
        traceback.print_exc()
        report["test_3"] = {"status": "ERROR", "error": str(e)}
    
    # ──── 输出报告 ────
    print("\n\n")
    print("=" * 60)
    print("## Timeline Persistence Test Report")
    print("=" * 60)
    
    for test_name, test_data in report.items():
        print(f"\n### {test_name}")
        print(f"- 是否成功: {test_data.get('status')}")
        if test_data.get("message_id"):
            print(f"- message_id: {test_data['message_id']}")
        if test_data.get("timeline") is not None:
            print(f"- timeline:")
            print(f"  {json.dumps(test_data['timeline'], ensure_ascii=False, indent=2)}")
        if test_data.get("checks"):
            print(f"- 检查结果:")
            for k, v in test_data["checks"].items():
                print(f"  - {k}: {v}")
        if test_data.get("error"):
            print(f"- error: {test_data['error']}")
    
    print(f"\n### Problems Found")
    problems = []
    for test_name, test_data in report.items():
        if test_data.get("status") != "PASS":
            if test_data.get("error"):
                problems.append(f"{test_name}: {test_data['error']}")
            if test_data.get("checks"):
                for k, v in test_data["checks"].items():
                    if "FAIL" in str(v):
                        problems.append(f"{test_name} - {k}: {v}")
    if problems:
        for p in problems:
            print(f"  - {p}")
    else:
        print("  (无问题)")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()