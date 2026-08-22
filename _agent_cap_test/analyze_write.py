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

# 找所有包含 tool_calls 或 tool_call 的 event
for e in events:
    t = e.get("type")
    # text 也可能包含调用信息
    if t == "text":
        content = e.get("content") or e.get("text") or ""
        if "write" in content.lower() or "tool" in content.lower():
            print(f"=== text ({t}) ===")
            print(content[:600])
            print()
    if t == "tool_calls":
        print("=== tool_calls ===")
        print(json.dumps(e, ensure_ascii=False)[:2000])
        print()
    if t == "tool_start" and e.get("tool") == "write_file":
        print("=== write_file tool_start ===")
        print(json.dumps(e, ensure_ascii=False))
        print()