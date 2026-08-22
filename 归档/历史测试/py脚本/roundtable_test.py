"""
圆桌会议测试 - 通过流式API触发
模型：cliproxy-gemini-3.6-flash
"""
import json
import time
import requests

API = "http://127.0.0.1:8000"
MODEL = "cliproxy-gemini-3.6-flash"

def create_chat(agent_id="general", roundtable_config=None):
    body = {"agent_id": agent_id, "model": MODEL, "title": "圆桌测试"}
    if roundtable_config:
        body["mode"] = "roundtable"
        body["roundtable_config"] = roundtable_config
    r = requests.post(f"{API}/api/chat", json=body, timeout=10)
    r.raise_for_status()
    return r.json()["id"]

def run_roundtable(chat_id, user_content):
    """通过send API触发圆桌会议（非流式，等待完成）"""
    t0 = time.time()
    try:
        r = requests.post(f"{API}/api/chat/{chat_id}/send", json={
            "content": user_content,
            "model": MODEL,
            "use_tools": False,
        }, timeout=300)
        elapsed = time.time() - t0
        if r.status_code != 200:
            return [], elapsed, f"HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        return data, elapsed, None
    except Exception as e:
        return [], time.time()-t0, str(e)

def analyze_events(events):
    speaker_starts = [e for e in events if e.get("type") == "roundtable_speaker_start"]
    speaker_ends = [e for e in events if e.get("type") == "roundtable_speaker_end"]
    text_events = [e for e in events if e.get("type") == "text"]
    summary_events = [e for e in events if e.get("is_summary")]
    round_starts = [e for e in events if e.get("type") == "roundtable_round_start"]
    round_ends = [e for e in events if e.get("type") == "roundtable_round_end"]
    rt_start = [e for e in events if e.get("type") == "roundtable_start"]
    rt_end = [e for e in events if e.get("type") == "roundtable_end"]

    # 收集每个Agent的发言
    agent_speeches = {}
    current_agent = None
    current_text = []
    for e in events:
        if e.get("type") == "roundtable_speaker_start":
            current_agent = e.get("agent_name")
            current_text = []
        elif e.get("type") == "text" and current_agent:
            current_text.append(e.get("content",""))
        elif e.get("type") == "roundtable_speaker_end":
            if current_agent:
                agent_speeches.setdefault(current_agent, []).append("".join(current_text))
            current_agent = None

    return {
        "speaker_starts": len(speaker_starts),
        "speaker_ends": len(speaker_ends),
        "text_chunks": len(text_events),
        "summary_count": len(summary_events),
        "rounds": len(round_starts),
        "has_start": len(rt_start) > 0,
        "has_end": len(rt_end) > 0,
        "agents": list(agent_speeches.keys()),
        "speeches": agent_speeches,
    }

def test_scenario(name, agent_ids, user_content, max_rounds=2):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  Agents: {agent_ids}, Rounds: {max_rounds}")
    print(f"{'='*60}")

    rt_config = {
        "agent_ids": agent_ids,
        "max_rounds": max_rounds,
        "need_summary": True,
    }
    chat_id = create_chat(roundtable_config=rt_config)
    print(f"  创建会话: {chat_id} (mode=roundtable)")

    data, elapsed, error = run_roundtable(chat_id, user_content)
    if error:
        print(f"  失败: {error}")
        return {"name": name, "error": error, "ok": False}

    # 非流式send返回的是单条AI消息，但圆桌会议会把所有发言存成多条消息
    # 查询该chat的所有消息来验证
    time.sleep(1)
    msgs_r = requests.get(f"{API}/api/chat/{chat_id}/messages", timeout=10)
    messages = msgs_r.json() if msgs_r.status_code == 200 else []
    ai_msgs = [m for m in messages if m.get("role") == "assistant"]

    print(f"  耗时: {elapsed:.1f}s")
    print(f"  AI消息数: {len(ai_msgs)} (预期 {len(agent_ids)*max_rounds + 1} 条含总结)")
    print(f"  各Agent发言:")
    for m in ai_msgs:
        content = m.get("content","")[:120].replace("\n"," ")
        print(f"    - {content}...")

    ok = len(ai_msgs) >= len(agent_ids) * max_rounds
    print(f"\n  结果: {'PASS' if ok else 'FAIL'}")
    return {"name": name, "elapsed": round(elapsed,1), "ai_messages": len(ai_msgs), "ok": ok}

if __name__ == "__main__":
    print("圆桌会议测试启动")
    print(f"模型: {MODEL}")

    results = []

    # 场景1：技术方案讨论
    results.append(test_scenario(
        "场景1-登录系统设计",
        ["coder", "frontend_ui", "g"],
        "设计一个用户登录系统，包括前端表单、后端API、数据库设计和安全考虑。需要支持邮箱密码登录和OAuth登录。",
        max_rounds=2
    ))

    # 场景2：代码审查
    results.append(test_scenario(
        "场景2-代码审查",
        ["g", "coder"],
        """审查以下代码的问题并给出优化建议：
        def process_data(data):
            result = []
            for item in data:
                if item['status'] == 'active':
                    result.append(item)
            return result""",
        max_rounds=1
    ))

    # 场景3：单Agent边界
    results.append(test_scenario(
        "场景3-单Agent边界",
        ["general"],
        "什么是RESTful API？简洁说明。",
        max_rounds=1
    ))

    # 汇总
    print(f"\n{'='*60}")
    print(f"  圆桌会议测试汇总")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r.get("ok"))
    print(f"  通过: {passed}/{len(results)}")
    for r in results:
        status = "PASS" if r.get("ok") else "FAIL"
        extra = f" {r.get('elapsed','?')}s, {r.get('speaker_starts','?')}次发言"
        if "error" in r: extra = f" ERROR={r['error'][:50]}"
        print(f"    [{status}] {r['name']}{extra}")

    with open("roundtable_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: roundtable_test_results.json")
