import sqlite3

db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

def cols(table):
    try:
        return [r['name'] for r in db.execute(f'PRAGMA table_info({table})')]
    except Exception as e:
        return f'err {e}'

print('agent_runs cols:', cols('agent_runs'))
print('runtime_events cols:', cols('runtime_events'))

print('\n=== agent_runs latest ===')
try:
    for r in db.execute('SELECT * FROM agent_runs ORDER BY id DESC LIMIT 5'):
        print(dict(r))
except Exception as e:
    print('err', e)

print('\n=== runtime_events latest for runs of chat 304 ===')
try:
    for r in db.execute('SELECT * FROM runtime_events ORDER BY id DESC LIMIT 10'):
        d = dict(r)
        for k in list(d.keys()):
            if isinstance(d[k], str) and len(d[k]) > 180:
                d[k] = d[k][:180]
        print(d)
except Exception as e:
    print('err', e)
