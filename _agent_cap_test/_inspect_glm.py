import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row
print('=== GLM-4.7-Flash 配置 ===')
for r in db.execute("SELECT id, model_id, model_name, provider, api_base, api_key, enabled "
                    "FROM models WHERE model_id='GLM-4.7-Flash'"):
    d = dict(r)
    d['api_key'] = (d['api_key'] or '')[:8] + '...' if d['api_key'] else None
    print(d)
print()
print('=== settings 中 glm 相关 key ===')
for r in db.execute("SELECT key, value FROM settings WHERE key LIKE '%glm%' OR key LIKE '%GLM%'"):
    v = r['value']
    if 'key' in r['key'].lower():
        v = (v or '')[:8] + '...' if v else v
    print(r['key'], '=', v)
