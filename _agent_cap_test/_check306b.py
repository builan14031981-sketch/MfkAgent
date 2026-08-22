import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

print('=== run 1109 当前状态 ===')
for r in db.execute("SELECT id, status, state, started_at, finished_at FROM agent_runs WHERE id=1109"):
    print(dict(r))

print()
print('=== run 1109 events 全量（按序号）===')
rows = list(db.execute("SELECT sequence, event_type, substr(COALESCE(payload,''),1,120) AS p FROM runtime_events WHERE run_id=1109 ORDER BY sequence"))
print('event count:', len(rows))
for r in rows:
    print(r['sequence'], r['event_type'], '|', r['p'])

print()
print('=== chat 306 全部消息 ===')
for r in db.execute("SELECT id, role, substr(content,1,100) AS c, created_at FROM messages WHERE chat_id=306 ORDER BY id"):
    print(r['id'], r['role'], '|', r['c'], '|', r['created_at'])
