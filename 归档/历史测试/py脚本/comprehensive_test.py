"""
MfkAgent 综合测试：记忆模块 + 圆桌会议
模型：cliproxy-gemini-3.6-flash（用户说额度随便造）
"""
import asyncio
import json
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "http://127.0.0.1:8000"
MODEL = "cliproxy-gemini-3.6-flash"
TEST_AGENT = "general"
results = {}

# ============================================================
# 第一部分：记忆模块测试
# ============================================================

def memory_api(method, path, **kwargs):
    url = f"{API}{path}"
    try:
        r = requests.request(method, url, timeout=30, **kwargs)
        return r.status_code, r.json() if r.headers.get("content-type","").startswith("application/json") else r.text
    except Exception as e:
        return 0, str(e)

def test_memory():
    print("\n" + "="*60)
    print("  记忆模块测试")
    print("="*60)
    mresults = {}

    # --- B5 空结果 ---
    print("\n[B5] 空结果测试")
    code, data = memory_api("GET", "/api/memories", params={"agent_id": "nonexistent_agent_xyz"})
    mresults["空结果-查询不存在agent"] = {"status": code, "ok": code == 200 and isinstance(data, list)}
    print(f"  查询不存在agent: {code} -> {'PASS' if code==200 else 'FAIL'}")

    code, data = memory_api("GET", "/api/memories/detail/999999")
    mresults["空结果-查询不存在id"] = {"status": code, "ok": code == 404}
    print(f"  查询不存在id: {code} -> {'PASS' if code==404 else 'FAIL'}")

    code, data = memory_api("DELETE", "/api/memories/999999")
    mresults["空结果-删除不存在id"] = {"status": code, "ok": code == 404}
    print(f"  删除不存在id: {code} -> {'PASS' if code==404 else 'FAIL'}")

    # --- E2 参数异常 ---
    print("\n[E2] 参数异常测试")
    code, data = memory_api("POST", "/api/memories", json={"scope": "invalid", "content": "test"})
    mresults["异常-非法scope"] = {"status": code, "ok": code in (400, 422)}
    print(f"  非法scope: {code} -> {'PASS' if code in (400,422) else 'FAIL'}")

    code, data = memory_api("POST", "/api/memories", json={"scope": "global", "content": ""})
    mresults["异常-空content"] = {"status": code, "ok": code in (400, 422)}
    print(f"  空content: {code} -> {'PASS' if code in (400,422) else 'FAIL'}")

    code, data = memory_api("POST", "/api/memories", json={"scope": "agent", "content": "test", "agent_id": None})
    mresults["异常-agent scope无agent_id"] = {"status": code, "ok": code in (400, 422)}
    print(f"  agent scope无agent_id: {code} -> {'PASS' if code in (400,422) else 'FAIL'}")

    # --- B2 超长内容 ---
    print("\n[B2] 超长内容测试")
    for size_kb in [1, 10, 100]:
        content = "记忆测试内容 " * (size_kb * 100)  # 约 size_kb KB
        t0 = time.time()
        code, data = memory_api("POST", "/api/memories", json={"scope": "global", "content": content, "memory_type": "fact"})
        elapsed = time.time() - t0
        ok = code == 200 and data.get("content") == content
        mresults[f"超长-{size_kb}KB"] = {"status": code, "elapsed": round(elapsed, 3), "ok": ok, "id": data.get("id") if isinstance(data, dict) else None}
        print(f"  {size_kb}KB: {code} {elapsed:.3f}s -> {'PASS' if ok else 'FAIL'}")

    # --- B1 超大量记忆 ---
    print("\n[B1] 超大量记忆测试（100条）")
    created_ids = []
    t0 = time.time()
    for i in range(100):
        code, data = memory_api("POST", "/api/memories", json={
            "scope": "agent", "agent_id": "memory_test_agent",
            "content": f"批量测试记忆 #{i}: 这是第{i}条测试记忆，用于验证大量记忆下的查询性能。",
            "memory_type": "fact", "confidence": 0.5 + (i % 50) / 100
        })
        if code == 200 and isinstance(data, dict):
            created_ids.append(data["id"])
    create_time = time.time() - t0
    print(f"  创建100条: {create_time:.2f}s, 成功{len(created_ids)}条")

    t0 = time.time()
    code, data = memory_api("GET", "/api/memories", params={"agent_id": "memory_test_agent"})
    query_time = time.time() - t0
    count = len(data) if isinstance(data, list) else 0
    mresults["大量-创建100条"] = {"time": round(create_time,2), "ok": len(created_ids)==100}
    mresults["大量-查询100条"] = {"status": code, "time": round(query_time,3), "count": count, "ok": code==200 and count>=100}
    print(f"  查询100条: {code} {query_time:.3f}s, 返回{count}条 -> {'PASS' if code==200 and count>=100 else 'FAIL'}")

    # count端点
    code, data = memory_api("GET", "/api/memories/count", params={"agent_id": "memory_test_agent"})
    mresults["大量-count端点"] = {"status": code, "count": data.get("count") if isinstance(data,dict) else None, "ok": code==200}
    print(f"  count端点: {code} count={data.get('count') if isinstance(data,dict) else 'N/A'}")

    # --- P2 高频查询 ---
    print("\n[P2] 高频查询测试（200次）")
    t0 = time.time()
    times = []
    for _ in range(200):
        t1 = time.time()
        memory_api("GET", "/api/memories", params={"agent_id": "memory_test_agent"})
        times.append(time.time() - t1)
    elapsed = time.time() - t0
    times.sort()
    p50 = times[len(times)//2]
    p99 = times[int(len(times)*0.99)]
    mresults["高频查询-200次"] = {"total_time": round(elapsed,2), "p50": round(p50,4), "p99": round(p99,4), "ok": p99 < 1.0}
    print(f"  200次: {elapsed:.2f}s, P50={p50:.4f}s, P99={p99:.4f}s -> {'PASS' if p99<1.0 else 'WARN'}")

    # --- P1 并发读写 ---
    print("\n[P1] 并发读写测试（10线程x20次）")
    def worker_create(i):
        return memory_api("POST", "/api/memories", json={"scope": "global", "content": f"并发测试{i}", "memory_type": "fact"})
    def worker_read(i):
        return memory_api("GET", "/api/memories", params={"scope": "global"})
    def worker_delete(mid):
        return memory_api("DELETE", f"/api/memories/{mid}")

    t0 = time.time()
    errors = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = []
        for i in range(50):
            futures.append(ex.submit(worker_create, i))
            futures.append(ex.submit(worker_read, i))
        for f in as_completed(futures):
            code, _ = f.result()
            if code != 200:
                errors += 1
    elapsed = time.time() - t0
    mresults["并发-100请求"] = {"time": round(elapsed,2), "errors": errors, "ok": errors==0}
    print(f"  100并发请求: {elapsed:.2f}s, 错误{errors}个 -> {'PASS' if errors==0 else 'FAIL'}")

    # --- B6 删除状态组合 ---
    print("\n[B6] 删除状态组合测试")
    code, data = memory_api("POST", "/api/memories", json={"scope": "global", "content": "删除测试记忆", "memory_type": "fact"})
    mid = data.get("id") if isinstance(data, dict) else None
    if mid:
        # API层DELETE是物理删除
        code1, _ = memory_api("DELETE", f"/api/memories/{mid}")
        code2, _ = memory_api("DELETE", f"/api/memories/{mid}")
        mresults["删除-物理删除"] = {"first": code1, "second": code2, "ok": code1==200 and code2==404}
        print(f"  物理删除: 第一次{code1}, 第二次{code2} -> {'PASS' if code1==200 and code2==404 else 'FAIL'}")

    # --- 清理测试数据 ---
    print("\n[清理] 删除测试数据")
    code, data = memory_api("GET", "/api/memories", params={"agent_id": "memory_test_agent"})
    if isinstance(data, list):
        for item in data:
            memory_api("DELETE", f"/api/memories/{item['id']}")
    # 清理global的测试记忆
    code, data = memory_api("GET", "/api/memories", params={"scope": "global"})
    if isinstance(data, list):
        for item in data:
            if "测试" in item.get("content","") or "并发" in item.get("content",""):
                memory_api("DELETE", f"/api/memories/{item['id']}")
    print("  清理完成")

    results["memory"] = mresults
    passed = sum(1 for v in mresults.values() if v.get("ok"))
    total = len(mresults)
    print(f"\n  记忆模块: {passed}/{total} 项通过")
    return mresults

# ============================================================
# 第二部分：圆桌会议测试
# ============================================================

async def run_roundtable(agent_ids, user_task, max_rounds=2, need_summary=True):
    """运行圆桌讨论，收集所有事件"""
    from app.core.roundtable_runtime import RoundtableRuntime
    events = []
    def emit(evt):
        events.append(evt)

    rt = RoundtableRuntime(
        chat_id=99999,  # 测试用假chat_id
        agent_ids=agent_ids,
        user_content=user_task,
        model_id=MODEL,
        max_rounds=max_rounds,
        need_summary=need_summary,
        temperature=0.7,
        max_tokens=1024,
    )
    history = await rt.run(emit)
    return events, history

def test_roundtable():
    print("\n" + "="*60)
    print("  圆桌会议测试")
    print("="*60)
    rresults = {}

    # 测试场景1：技术方案讨论
    print("\n[场景1] 技术方案讨论：用户登录系统设计")
    print("  Agent: 开发者 + 前端工程师 + G审查官, 2轮+总结")
    t0 = time.time()
    try:
        events, history = asyncio.run(run_roundtable(
            ["coder", "frontend_ui", "g"],
            "请设计一个用户登录系统，包括前端表单、后端API、数据库设计和安全考虑。需要支持邮箱密码登录和第三方OAuth登录。",
            max_rounds=2, need_summary=True
        ))
        elapsed = time.time() - t0
        speaker_starts = [e for e in events if e.get("type") == "roundtable_speaker_start"]
        speaker_ends = [e for e in events if e.get("type") == "roundtable_speaker_end"]
        text_events = [e for e in events if e.get("type") == "text"]
        summary_events = [e for e in events if e.get("is_summary")]
        agent_names = set(e.get("agent_name","") for e in speaker_starts)

        rresults["场景1-登录系统"] = {
            "time": round(elapsed,1),
            "speakers": len(speaker_starts),
            "text_chunks": len(text_events),
            "agents": list(agent_names),
            "has_summary": len(summary_events) > 0,
            "history_count": len(history),
            "ok": len(speaker_starts) >= 6  # 3 agents x 2 rounds
        }
        print(f"  耗时: {elapsed:.1f}s")
        print(f"  发言次数: {len(speaker_starts)} (预期6+)")
        print(f"  参与Agent: {list(agent_names)}")
        print(f"  有总结: {'是' if len(summary_events)>0 else '否'}")
        print(f"  结果: {'PASS' if len(speaker_starts)>=6 else 'FAIL'}")

        # 打印每个Agent的发言摘要
        print("\n  各Agent发言摘要:")
        for msg in history:
            if msg.get("role") == "assistant":
                name = msg.get("name","?")
                content = msg.get("content","")[:120].replace("\n"," ")
                print(f"    [{name}]: {content}...")
    except Exception as e:
        rresults["场景1-登录系统"] = {"error": str(e), "ok": False}
        print(f"  错误: {e}")

    # 测试场景2：代码审查场景
    print("\n[场景2] 代码审查：找出代码中的问题")
    print("  Agent: G审查官 + 开发者, 1轮+总结")
    t0 = time.time()
    try:
        events, history = asyncio.run(run_roundtable(
            ["g", "coder"],
            """审查以下代码的问题：
            def process_data(data):
                result = []
                for item in data:
                    if item['status'] == 'active':
                        result.append(item)
                return result
            这段代码有什么潜在问题？如何优化？""",
            max_rounds=1, need_summary=True
        ))
        elapsed = time.time() - t0
        speaker_starts = [e for e in events if e.get("type") == "roundtable_speaker_start"]
        rresults["场景2-代码审查"] = {
            "time": round(elapsed,1),
            "speakers": len(speaker_starts),
            "ok": len(speaker_starts) >= 2
        }
        print(f"  耗时: {elapsed:.1f}s, 发言{len(speaker_starts)}次 -> {'PASS' if len(speaker_starts)>=2 else 'FAIL'}")
        for msg in history:
            if msg.get("role") == "assistant":
                name = msg.get("name","?")
                content = msg.get("content","")[:150].replace("\n"," ")
                print(f"    [{name}]: {content}...")
    except Exception as e:
        rresults["场景2-代码审查"] = {"error": str(e), "ok": False}
        print(f"  错误: {e}")

    # 测试场景3：边界-单Agent
    print("\n[场景3] 边界测试：单Agent圆桌")
    t0 = time.time()
    try:
        events, history = asyncio.run(run_roundtable(
            ["general"],
            "什么是RESTful API？",
            max_rounds=1, need_summary=False
        ))
        elapsed = time.time() - t0
        speaker_starts = [e for e in events if e.get("type") == "roundtable_speaker_start"]
        rresults["场景3-单Agent"] = {"time": round(elapsed,1), "speakers": len(speaker_starts), "ok": len(speaker_starts)>=1}
        print(f"  耗时: {elapsed:.1f}s, 发言{len(speaker_starts)}次 -> {'PASS' if len(speaker_starts)>=1 else 'FAIL'}")
    except Exception as e:
        rresults["场景3-单Agent"] = {"error": str(e), "ok": False}
        print(f"  错误: {e}")

    results["roundtable"] = rresults
    passed = sum(1 for v in rresults.values() if v.get("ok"))
    total = len(rresults)
    print(f"\n  圆桌会议: {passed}/{total} 项通过")
    return rresults

# ============================================================
# 主流程
# ============================================================

if __name__ == "__main__":
    print("MfkAgent 综合测试启动")
    print(f"模型: {MODEL}")
    print(f"后端: {API}")

    # 检查后端连通性
    try:
        r = requests.get(f"{API}/api/agents", timeout=5)
        print(f"后端连通: {r.status_code}, Agents: {len(r.json())}")
    except Exception as e:
        print(f"后端连接失败: {e}")
        exit(1)

    # 记忆模块测试
    test_memory()

    # 圆桌会议测试
    test_roundtable()

    # 保存结果
    with open("comprehensive_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 汇总
    print("\n" + "="*60)
    print("  测试汇总")
    print("="*60)
    for module, mresults in results.items():
        passed = sum(1 for v in mresults.values() if v.get("ok"))
        total = len(mresults)
        print(f"  {module}: {passed}/{total} 通过")
        for name, r in mresults.items():
            status = "PASS" if r.get("ok") else "FAIL"
            extra = ""
            if "time" in r: extra += f" {r['time']}s"
            if "p99" in r: extra += f" P99={r['p99']}s"
            if "errors" in r: extra += f" errors={r['errors']}"
            if "error" in r: extra += f" ERROR={r['error'][:50]}"
            print(f"    [{status}] {name}{extra}")

    print(f"\n结果已保存: comprehensive_test_results.json")
