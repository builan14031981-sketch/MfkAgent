# -*- coding: utf-8 -*-
"""
Agent 能力实测脚本（A/B 对比 + 差异度测试）
- 测试 A：差异度测试（同一问题 × 11 Agent）
- 测试 B：专属场景 A/B（11 Agent × 2 场景 × 带/不带提示词）

用法: python run_test.py [--model qwen-plus] [--only diff|ab|all]
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT_DIR, exist_ok=True)

# 11 个 active Agent
AGENTS = [
    "general",      # AnGent
    "g",            # G 审查官
    "coder",        # 开发者
    "frontend_ui",  # 前端工程师
    "product",      # 产品策略师
    "writer",       # 笔神
    "writer_narrative",  # 作家
    "personal",     # 个人助理
    "spark",        # Spark
    "pianai",       # Pianai
    "research",     # 调研员
]

# 差异度测试：同一问题
DIFF_QUESTION = "请用一句话说明你是谁、你擅长什么、你能为用户解决什么问题。"

# 专属场景（每个 Agent 2 个场景，A=专长场景，B=对照场景）
SCENARIOS = {
    "general": [
        ("专长-综合任务", "帮我整理以下资料的核心要点，并说明下一步该做什么：用户想要给团队搭建一个内部知识库，团队成员有20人，分散在3个城市，希望支持搜索和权限控制。"),
        ("对照-代码", "写一个 Python 函数，判断一个字符串是否是回文。"),
    ],
    "g": [
        ("专长-治理审查", "以下是某团队的技术方案：‘直接用共享账号管理所有云资源，方便大家使用，效率最高’。请你审查这个方案。"),
        ("对照-写代码", "写一个 Python 函数，判断一个字符串是否是回文。"),
    ],
    "coder": [
        ("专长-代码修复", "这段代码有 bug，请定位并给出最小修复：def get_user(id):\n    conn = db.connect()\n    cur = conn.cursor()\n    cur.execute('SELECT * FROM users WHERE id = %s' % id)\n    return cur.fetchone()"),
        ("对照-产品方向", "你认为我们的产品应该加哪些功能？"),
    ],
    "frontend_ui": [
        ("专长-前端方案", "我想给聊天输入框加一个‘关联项目’的快捷按钮，要求悬停展开、不影响输入体验。请给出组件方案（React/TS）。"),
        ("对照-后端设计", "帮我设计用户表的数据库字段。"),
    ],
    "product": [
        ("专长-产品决策", "我们的产品想加‘工作流编排’功能，但团队只有5人。请评估是否值得做，给出建议。"),
        ("对照-写代码", "写一个 Python 函数，判断一个字符串是否是回文。"),
    ],
    "writer": [
        ("专长-精炼改写", "请将下面这段话改写得更精炼清晰：我们要在近期内推动这个项目上线，因为市场竞争非常激烈，如果慢了可能就会失去先发优势，所以大家要抓紧时间，把核心功能先做出来，其他的可以以后再说。"),
        ("对照-代码审查", "帮我审查这段代码有没有安全问题。"),
    ],
    "writer_narrative": [
        ("专长-叙事创作", "请创作一段 150 字以内的微故事，主题是‘深夜的便利店’，要有画面感和人物情绪。"),
        ("对照-技术文档", "帮我写一个 API 接口的技术文档。"),
    ],
    "personal": [
        ("专长-任务规划", "我明天有 6 件事要做：写周报、开会、修 bug、买菜、健身、给妈妈打电话。请帮我安排一天的优先级。"),
        ("对照-架构决策", "微服务还是单体架构，怎么选？"),
    ],
    "spark": [
        ("专长-行动推动", "我最近很拖延，一直没开始写毕业论文，心里很焦虑但就是不想动。请帮帮我。"),
        ("对照-冷静分析", "帮我分析一下这个项目的风险点。"),
    ],
    "pianai": [
        ("专长-陪伴支持", "今天工作好累，被领导批评了，心情很低落，不太想说话。"),
        ("对照-技术实现", "怎么用 Python 读取一个大文件而不占太多内存？"),
    ],
    "research": [
        ("专长-调研大纲", "请为‘2026 年国内大模型应用落地现状’给出一个结构化调研大纲，包括多角度分析维度。"),
        ("对照-写代码", "写一个 Python 函数，判断一个字符串是否是回文。"),
    ],
}

# 无提示词对照用相同的用户消息（只发任务本身）
CONTROL_SUFFIX = ""

def http(method, path, body=None, timeout=180):
    """发起 HTTP 请求，返回 (ok, status, data)"""
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8"))
        except Exception:
            err = {"detail": str(e)}
        return False, e.code, err
    except Exception as e:
        return False, -1, {"detail": str(e)}


def run_with_agent(agent_id, user_message, model):
    """带 Agent 提示词：创建会话 + 发送消息"""
    ok, st, chat = http("POST", "/api/chat", {"agent_id": agent_id, "title": f"[AUTOTEST]{agent_id}"}, timeout=30)
    if not ok:
        return {"ok": False, "error": f"create chat: {chat}", "step": "create"}
    chat_id = chat.get("id")
    ok, st, resp = http("POST", f"/api/chat/{chat_id}/send", {"content": user_message, "model": model})
    if not ok:
        return {"ok": False, "error": f"send: {resp}", "step": "send", "chat_id": chat_id}
    ai = resp.get("ai_message") or {}
    usage = resp.get("token_usage") or {}
    return {
        "ok": True,
        "chat_id": chat_id,
        "content": ai.get("content") or resp.get("assistant_content") or "",
        "usage": usage,
        "agent": resp.get("agent_id") or agent_id,
        "personality": resp.get("personality_level"),
    }


def cleanup_chat(chat_id):
    """删除测试会话（软删除移入回收站）"""
    if not chat_id:
        return
    try:
        http("DELETE", f"/api/chat/{chat_id}", timeout=30)
    except Exception:
        pass


def run_without_agent(user_message, model):
    """无提示词：裸模型直接调用"""
    ok, st, resp = http("POST", "/api/models/chat", {"model": model, "messages": [{"role": "user", "content": user_message}]})
    if not ok:
        return {"ok": False, "error": f"models/chat: {resp}"}
    return {
        "ok": True,
        "content": resp.get("content") or resp.get("text") or resp.get("message", {}).get("content", "") if isinstance(resp.get("message"), dict) else (resp.get("content") or ""),
        "usage": resp.get("usage") or {},
    }


def save(name, data):
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  [保存] {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--only", default="all", choices=["diff", "ab", "all"])
    parser.add_argument("--limit", type=int, default=0, help="只测前 N 个 agent（调试用）")
    args = parser.parse_args()
    model = args.model

    agents = AGENTS[:args.limit] if args.limit else AGENTS
    summary = {"model": model, "agents": [], "diff": [], "ab": [], "total_usage": {"prompt": 0, "completion": 0, "total": 0}}
    created_chat_ids = []

    # ===== 测试 A：差异度 =====
    if args.only in ("diff", "all"):
        print(f"\n===== 测试 A：差异度（同一问题 × {len(agents)} Agent）=====")
        for i, agent in enumerate(agents, 1):
            print(f"  [{i}/{len(agents)}] {agent} (带提示词) ...")
            r = run_with_agent(agent, DIFF_QUESTION, model)
            entry = {"agent": agent, "question": DIFF_QUESTION, **r}
            summary["diff"].append(entry)
            if r.get("ok"):
                created_chat_ids.append(r.get("chat_id"))
                u = r.get("usage") or {}
                summary["total_usage"]["prompt"] += u.get("prompt_tokens", 0)
                summary["total_usage"]["completion"] += u.get("completion_tokens", 0)
                summary["total_usage"]["total"] += u.get("total_tokens", 0)
                print(f"     -> {str(r.get('content'))[:80]}")
            else:
                print(f"     -> FAIL: {r.get('error')}")
            time.sleep(0.5)

    # ===== 测试 B：专属场景 A/B =====
    if args.only in ("ab", "all"):
        print(f"\n===== 测试 B：专属场景 A/B（{len(agents)} Agent × 2 场景 × 2 模式）=====")
        for i, agent in enumerate(agents, 1):
            print(f"\n  [{i}/{len(agents)}] Agent: {agent}")
            agent_ab = {"agent": agent, "scenarios": []}
            for sc_name, sc_msg in SCENARIOS.get(agent, []):
                print(f"    场景 [{sc_name}] ...")
                # 带提示词
                r_with = run_with_agent(agent, sc_msg, model)
                if r_with.get("ok"):
                    created_chat_ids.append(r_with.get("chat_id"))
                    u = r_with.get("usage") or {}
                    summary["total_usage"]["prompt"] += u.get("prompt_tokens", 0)
                    summary["total_usage"]["completion"] += u.get("completion_tokens", 0)
                    summary["total_usage"]["total"] += u.get("total_tokens", 0)
                # 无提示词
                r_without = run_without_agent(sc_msg, model)
                if r_without.get("ok"):
                    u = r_without.get("usage") or {}
                    summary["total_usage"]["prompt"] += u.get("prompt_tokens", 0)
                    summary["total_usage"]["completion"] += u.get("completion_tokens", 0)
                    summary["total_usage"]["total"] += u.get("total_tokens", 0)
                agent_ab["scenarios"].append({
                    "scenario": sc_name,
                    "message": sc_msg,
                    "with_agent": r_with,
                    "without_agent": r_without,
                })
                print(f"      with    -> {str(r_with.get('content'))[:60] if r_with.get('ok') else 'FAIL'}")
                print(f"      without -> {str(r_without.get('content'))[:60] if r_without.get('ok') else 'FAIL'}")
                time.sleep(0.5)
            summary["ab"].append(agent_ab)
            summary["agents"].append(agent)

    # ===== 汇总 =====
    print("\n===== 汇总 =====")
    print(f"模型: {model}")
    print(f"总 token: prompt={summary['total_usage']['prompt']}, completion={summary['total_usage']['completion']}, total={summary['total_usage']['total']}")
    print(f"创建并清理 {len(created_chat_ids)} 个测试会话")
    # 自动清理：所有测试创建的会话移入回收站，不污染主列表
    for cid in created_chat_ids:
        cleanup_chat(cid)
    save("summary", summary)
    print("\n完成。")


if __name__ == "__main__":
    main()
