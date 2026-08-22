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

print("=== tool_start 事件（含参数） ===")
for e in events:
    if e.get("type") == "tool_start":
        print(json.dumps(e, ensure_ascii=False)[:800])
        print("----")

print()
print("=== tool_calls 事件 ===")
for e in events:
    if e.get("type") == "tool_calls":
        print(json.dumps(e, ensure_ascii=False)[:1200])
        print("----")
