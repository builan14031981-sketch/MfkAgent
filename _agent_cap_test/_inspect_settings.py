import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row

print('=== settings (model/api/default 相关) ===')
for r in db.execute("SELECT key, value FROM settings WHERE key LIKE '%model%' OR key LIKE '%api%' OR key LIKE '%default%' OR key LIKE '%provider%' ORDER BY key"):
    print(r['key'], '=', (r['value'] or '')[:200])

print()
print('=== 所有 settings key ===')
for r in db.execute("SELECT key FROM settings ORDER BY key"):
    print(r['key'])
