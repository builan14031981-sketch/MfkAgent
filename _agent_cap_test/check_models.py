"""检查 settings 表中模型相关配置 + 模型注册表"""
import sqlite3
import json

DB = r"e:\智慧项目\Mfkagent\backend\mfkagent.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=== settings 中模型相关 key ===")
rows = c.execute("SELECT key, value FROM settings WHERE key LIKE '%model%' OR key LIKE '%tool%' OR key LIKE '%agent%'").fetchall()
for r in rows:
    print(f"{r['key']} = {str(r['value'])[:400]}")

print()
print("=== enabled_models / provider 相关 ===")
for key in ["enabled_models", "provider_disabled", "providers", "model_providers"]:
    r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if r:
        print(f"{key}: {str(r['value'])[:800]}")
c.close()
