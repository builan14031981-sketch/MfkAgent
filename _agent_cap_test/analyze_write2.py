# -*- coding: utf-8 -*-
import json
import sys

path = sys.argv[1]
events = []
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))

# 找 text 事件中所有内容
print("=== 所有 text 事件 ===")
for i, e in enumerate(events):
    if e.get("type") == "text":
        content = (e.get("content") or e.get("text") or "")
        print(f"[{i}] {content[:200]}")
        print()

# 查找 write_file 相关的 tool_start 上游的 assistant 消息
print("=== 在 tool_start 前的 text 事件上下文 ===")
for i in range(len(events)):
    if events[i].get("type") == "tool_start" and events[i].get("tool") == "write_file":
        # 往回找最近的 3 个 text 事件
        for j in range(max(0, i-5), i):
            if events[j].get("type") == "text":
                print(f"before write_file text[{j}]: {(events[j].get('content') or '')[:300]}")
        break

# 统计 tool_calls 事件
print()
print("=== tool_calls 事件 ===")
for e in events:
    if e.get("type") == "tool_calls":
        # 可能是 {calls: [...]} 格式
        calls = e.get("calls", [])
        if calls:
            for c in calls:
                fn = c.get("function", {})
                print(f"  name={fn.get('name')} args={fn.get('arguments', '')[:200]}")