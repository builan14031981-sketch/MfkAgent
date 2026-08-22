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

# 打印所有非 text/state_change/agent_state_update 的完整事件
for i, e in enumerate(events):
    t = e.get("type")
    if t in ("text", "state_change", "agent_state_update", "token_usage", "verify_result"):
        continue
    print(f"[{i}] {t}: {json.dumps(e, ensure_ascii=False)[:1500]}")
    print()
