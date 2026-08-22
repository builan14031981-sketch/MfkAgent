"""查 models 表中 qwen3-14b 等模型配置"""
import sqlite3

DB = r"e:\智慧项目\Mfkagent\backend\mfkagent.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

cols = [r["name"] for r in c.execute("PRAGMA table_info(models)")]
print("models columns:", cols)

rows = c.execute("SELECT * FROM models WHERE enabled=1 ORDER BY provider").fetchall()
for r in rows:
    d = dict(r)
    # 脱敏 key
    for k in list(d.keys()):
        if "key" in k.lower() and d[k]:
            d[k] = "SET***"
    print(d)
c.close()
