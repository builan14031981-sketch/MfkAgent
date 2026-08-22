import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row
for r in db.execute("SELECT key, value FROM settings WHERE key IN ('provider_disabled','api_key_siliconflow')"):
    v = r['value']
    if 'key' in r['key'].lower() and v:
        v = v[:12] + '...'
    print(r['key'], '=', v)
