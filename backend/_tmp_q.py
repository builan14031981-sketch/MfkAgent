import json
import sqlite3

db = sqlite3.connect(r"e:\智慧项目\Mfkagent\backend\mfkagent.db")
db.row_factory = sqlite3.Row

print("### 1) models 表：名字含 glm 或 provider=qwen 的所有记录 ###")
for r in db.execute(
    "select id, model_id, name, provider, model_name, api_base, api_key, enabled, source "
    "from models where lower(model_id) like '%glm%' or lower(name) like '%glm%' or provider='qwen' "
    "order by provider, id"
):
    d = dict(r)
    print(
        f"  id={d['id']} | {d['model_id']} | name={d['name']} | provider={d['provider']} "
        f"| model_name={d['model_name']} | enabled={d['enabled']} | source={d['source']} "
        f"| key_len={len(d['api_key'] or '')}"
    )

print()
print("### 2) enabled_models 完整内容 ###")
em = json.loads(db.execute("select value from settings where key='enabled_models'").fetchone()[0])
for k, v in em.items():
    print(f"  {k}: {v}")

print()
print("### 3) 是否在 enabled_models['qwen'] 里含 glm 开头的模型 ###")
for k, v in em.items():
    glm_items = [x for x in v if x.lower().startswith("glm")]
    if glm_items:
        print(f"  provider={k} 下含 glm 前缀: {glm_items}")

print()
print("### 4) provider_disabled ###")
pd = json.loads(db.execute("select value from settings where key='provider_disabled'").fetchone()[0])
print(" ", pd)

db.close()
