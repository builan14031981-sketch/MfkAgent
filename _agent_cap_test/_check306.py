import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

print('=== chat 306 最近 messages ===')
for r in db.execute("SELECT id, role, substr(content,1,80) AS c, created_at FROM messages WHERE chat_id=306 ORDER BY id DESC LIMIT 5"):
    print(dict(r))

print()
print('=== chat 306 agent_runs ===')
runs = list(db.execute("SELECT id, status, state, started_at, finished_at FROM agent_runs WHERE chat_id=306 ORDER BY id DESC LIMIT 5"))
for r in runs:
    print(dict(r))

if runs:
    run_id = runs[0]['id']
    print()
    print(f'=== run {run_id} 最近 events ===')
    for r in db.execute("SELECT id, event_type, substr(COALESCE(payload,''),1,200) AS p, created_at FROM runtime_events WHERE run_id=? ORDER BY id DESC LIMIT 30", (run_id,)):
        print(r['event_type'], '|', r['p'])
