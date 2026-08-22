# -*- coding: utf-8 -*-
"""从 summary.json 提取紧凑的 A/B 对比（带提示词 vs 无提示词），用于人工判定。"""
import json, os, sys

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "summary.json")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 100)
print("【差异度测试】同一问题 '请用一句话说明你是谁...' × 11 Agent")
print("=" * 100)
for d in data.get("diff", []):
    content = (d.get("content") or "").strip().replace("\n", " ")
    ok = "OK" if d.get("ok") else f"FAIL:{d.get('error')}"
    print(f"\n--- {d['agent']} ({ok}) ---")
    print(f"  {content[:220]}")

print("\n\n" + "=" * 100)
print("【A/B 对比】每个 Agent 的每个场景：带提示词(顶层) vs 无提示词(顶层)")
print("=" * 100)
for ab in data.get("ab", []):
    agent = ab["agent"]
    print(f"\n\n########## Agent: {agent} ##########")
    for sc in ab.get("scenarios", []):
        print(f"\n  >>> 场景: {sc['scenario']}")
        print(f"      消息: {sc['message'][:80]}")
        w = sc.get("with_agent") or {}
        wo = sc.get("without_agent") or {}
        wc = (w.get("content") or "").strip().replace("\n", " ")
        woc = (wo.get("content") or "").strip().replace("\n", " ")
        print(f"  [带提示词]   {wc[:260]}")
        print(f"  [无提示词]   {woc[:260]}")

print("\n\n" + "=" * 100)
print("【总 token 消耗】")
print("=" * 100)
print(json.dumps(data.get("total_usage", {}), ensure_ascii=False))
