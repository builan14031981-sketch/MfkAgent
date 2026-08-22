import sqlite3

db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

print('=== tables like %approv% ===')
try:
    for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%approv%'"):
        print(dict(r))
except Exception as e:
    print('err', e)

print('=== approval_requests (latest) ===')
try:
    for r in db.execute('SELECT id, approval_id, agent_run_id, tool_name, status, created_at, resolved_at FROM approval_requests ORDER BY id DESC LIMIT 5'):
        print(dict(r))
except Exception as e:
    print('err', e)

print('=== agent_runs for chat 304 ===')
try:
    for r in db.execute('SELECT id, chat_id, status, model, created_at, completed_at FROM agent_runs WHERE chat_id=304 ORDER BY id DESC LIMIT 3'):
        print(dict(r))
except Exception as e:
    print('err', e)

print('=== runtime_events for chat 304 (latest) ===')
try:
    for r in db.execute('SELECT id, event_type, payload, created_at FROM runtime_events WHERE chat_id=304 ORDER BY id DESC LIMIT 8'):
        p = (r['payload'] or '')
        print({k: r[k] for k in ['id', 'event_type', 'created_at']}, 'payload:', p[:200])
except Exception as e:
    print('err', e)
