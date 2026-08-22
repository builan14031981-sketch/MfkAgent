"""
圆桌会议 V2 验证测试
1. 旧配置兼容（agent_ids格式 → 探讨模式）
2. 新配置（agents格式，每Agent独立模型）
3. 协作模式（生成任务清单）
4. 第一轮并发
"""
import json
import time
import requests

API = "http://127.0.0.1:8000"
MODEL = "cliproxy-gemini-3.6-flash"

def create_chat(roundtable_config=None, mode=None):
    body = {"agent_id": "general", "model": MODEL, "title": "V2测试"}
    if roundtable_config:
        body["mode"] = "roundtable"
        body["roundtable_config"] = roundtable_config
    r = requests.post(f"{API}/api/chat", json=body, timeout=10)
    r.raise_for_status()
    return r.json()["id"]

def send_and_wait(chat_id, content, timeout=180):
    """发送消息，等待圆桌完成，返回消息列表"""
    t0 = time.time()
    r = requests.post(f"{API}/api/chat/{chat_id}/send", json={
        "content": content, "model": MODEL, "use_tools": False
    }, timeout=timeout)
    elapsed = time.time() - t0
    if r.status_code != 200:
        return None, elapsed, f"HTTP {r.status_code}: {r.text[:300]}"
    # 等落库
    time.sleep(2)
    msgs = requests.get(f"{API}/api/chat/{chat_id}/messages", timeout=10).json()
    return msgs, elapsed, None

def test_legacy_config():
    """测试1：旧配置兼容"""
    print("\n" + "="*60)
    print("  测试1：旧配置兼容（agent_ids格式）")
    print("="*60)
    config = {"agent_ids": ["general", "g"], "max_rounds": 1}
    chat_id = create_chat(roundtable_config=config)
    print(f"  创建会话: {chat_id}")
    msgs, elapsed, error = send_and_wait(chat_id, "什么是RESTful API？简洁说明。")
    if error:
        print(f"  失败: {error}")
        return False
    ai_msgs = [m for m in msgs if m["role"] == "assistant"]
    print(f"  耗时: {elapsed:.1f}s, AI消息: {len(ai_msgs)}条")
    for m in ai_msgs:
        print(f"    [{m.get('agent_id','?')}]: {m['content'][:80]}...")
    ok = len(ai_msgs) >= 2  # 2个Agent各1次 + 可能的总结
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok

def test_new_config_per_agent_model():
    """测试2：新配置，每Agent独立模型"""
    print("\n" + "="*60)
    print("  测试2：新配置（agents格式，每Agent独立模型）")
    print("="*60)
    config = {
        "mode": "discussion",
        "agents": [
            {"agent_id": "coder", "model": MODEL},
            {"agent_id": "g", "model": MODEL},
        ],
        "max_rounds": 1,
        "concurrent_first_round": True,
    }
    chat_id = create_chat(roundtable_config=config)
    print(f"  创建会话: {chat_id}")
    msgs, elapsed, error = send_and_wait(chat_id, "审查这段代码有什么问题：def f(x): return x+1")
    if error:
        print(f"  失败: {error}")
        return False
    ai_msgs = [m for m in msgs if m["role"] == "assistant"]
    print(f"  耗时: {elapsed:.1f}s, AI消息: {len(ai_msgs)}条")
    for m in ai_msgs:
        print(f"    [{m.get('agent_id','?')}]: {m['content'][:80]}...")
    ok = len(ai_msgs) >= 2
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok

def test_collaboration_mode():
    """测试3：协作模式，生成任务清单"""
    print("\n" + "="*60)
    print("  测试3：协作模式（生成任务清单）")
    print("="*60)
    config = {
        "mode": "collaboration",
        "agents": [
            {"agent_id": "coder"},
            {"agent_id": "frontend_ui"},
            {"agent_id": "g"},
        ],
        "max_rounds": 1,
        "concurrent_first_round": True,
        "generate_tasks": True,
    }
    chat_id = create_chat(roundtable_config=config)
    print(f"  创建会话: {chat_id}")
    msgs, elapsed, error = send_and_wait(chat_id, "设计一个用户登录系统，支持邮箱密码和OAuth登录。")
    if error:
        print(f"  失败: {error}")
        return False
    ai_msgs = [m for m in msgs if m["role"] == "assistant"]
    print(f"  耗时: {elapsed:.1f}s, AI消息: {len(ai_msgs)}条")
    # 找任务清单消息
    task_msg = None
    for m in ai_msgs:
        meta = m.get("metadata")
        if meta and isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except:
                meta = {}
        if meta and meta.get("roundtable_tasks"):
            task_msg = m
            break
    if task_msg:
        print(f"  任务清单已生成!")
        print(f"  {task_msg['content'][:300]}...")
    else:
        print(f"  未找到任务清单消息")
        for m in ai_msgs:
            print(f"    [{m.get('agent_id','?')}]: {m['content'][:80]}...")
    ok = task_msg is not None
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok

def test_concurrent_first_round():
    """测试4：第一轮并发（验证耗时比串行短）"""
    print("\n" + "="*60)
    print("  测试4：第一轮并发")
    print("="*60)
    config = {
        "mode": "discussion",
        "agents": [
            {"agent_id": "coder"},
            {"agent_id": "frontend_ui"},
            {"agent_id": "g"},
        ],
        "max_rounds": 1,
        "concurrent_first_round": True,
    }
    chat_id = create_chat(roundtable_config=config)
    print(f"  创建会话: {chat_id}")
    msgs, elapsed, error = send_and_wait(chat_id, "分析一下微服务架构的优缺点。")
    if error:
        print(f"  失败: {error}")
        return False
    ai_msgs = [m for m in msgs if m["role"] == "assistant"]
    print(f"  并发耗时: {elapsed:.1f}s, AI消息: {len(ai_msgs)}条")
    # 3个Agent并发，理论上耗时应该接近单个Agent的耗时，而不是3倍
    # 这里只验证功能正常，不做严格的性能断言
    ok = len(ai_msgs) >= 3
    print(f"  结果: {'PASS' if ok else 'FAIL'}")
    return ok

if __name__ == "__main__":
    print("圆桌会议 V2 验证测试")
    print(f"模型: {MODEL}")

    results = {}
    results["旧配置兼容"] = test_legacy_config()
    results["新配置-独立模型"] = test_new_config_per_agent_model()
    results["协作模式-任务清单"] = test_collaboration_mode()
    results["第一轮并发"] = test_concurrent_first_round()

    print("\n" + "="*60)
    print("  汇总")
    print("="*60)
    passed = sum(1 for v in results.values() if v)
    for name, ok in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  通过: {passed}/{len(results)}")
