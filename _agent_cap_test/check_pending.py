import sqlite3
c = sqlite3.connect(r"e:\智慧项目\Mfkagent\backend\mfkagent.db")
print("== approval_requests 最近 ==")
for r in c.execute("SELECT approval_id, agent_run_id, tool_name, status, created_at FROM approval_requests ORDER BY created_at DESC LIMIT 6"):
    print(r)
print("\n== agent_runs 最近 ==")
try:
    cols = [d[1] for d in c.execute("SELECT * FROM agent_runs LIMIT 1").description]
    print("cols:", cols)
    for r in c.execute("SELECT * FROM agent_runs ORDER BY id DESC LIMIT 4"):
        print({k: v for k, v in zip(cols, r)})
except Exception as e:
    print("agent_runs error:", e)
c.close()
