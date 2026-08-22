import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

print('=== 表清单 ===')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(r['name'])

print()
print('=== 含 model 的表 ===')
for t in [r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols = [c['name'] for c in db.execute(f'PRAGMA table_info({t})')]
    if 'model' in ' '.join(cols).lower():
        print(t, '->', cols)
