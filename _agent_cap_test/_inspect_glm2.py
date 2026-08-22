import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row
print('=== models 表里所有 glm / 备选模型 ===')
for r in db.execute("SELECT id, model_id, provider, api_base, enabled, "
                    "CASE WHEN api_key IS NOT NULL AND api_key!='' THEN 1 ELSE 0 END AS has_key "
                    "FROM models "
                    "WHERE model_id LIKE '%glm%' OR model_id LIKE '%GLM%' OR model_id IN ('glm-5','qwen3.7-plus','qwen-plus','qwen-max') "
                    "ORDER BY provider"):
    d = dict(r)
    d['api_base'] = (d['api_base'] or '')[:50]
    print(d)
print()
print('=== enabled_models ===')
for r in db.execute("SELECT key, value FROM settings WHERE key='enabled_models'"):
    print(r['value'])
