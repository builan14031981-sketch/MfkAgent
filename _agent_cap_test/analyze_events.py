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

from collections import Counter

c = Counter(e.get("type") for e in events)
print("=== 事件统计 ===")
for k, v in c.items():
    print(f"  {k}: {v}")

print()
print("=== 工具调用序列 ===")
for e in events:
    if e.get("type") == "tool_result":
        tool = e.get("tool")
        ok = e.get("success")
        result = (e.get("result") or "")[:110].replace(chr(10), " ")
        print(f"  tool={tool} success={ok} | {result}")

print()
print("=== 完成验证 / 任务终态 ===")
for e in events:
    t = e.get("type")
    if t in ("completion_verify_started", "completion_verify_passed",
             "completion_verify_failed", "task_completed", "task_failed", "finish"):
        if t == "completion_verify_started":
            goal = (e.get("task_goal") or "")[:40]
            print(f"  [{t}] round={e.get('round_no')} goal={goal}")
        else:
            print(f"  [{t}] {json.dumps(e, ensure_ascii=False)[:280]}")
