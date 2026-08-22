# -*- coding: utf-8 -*-
"""只读查询 models 表（CustomModel）与 enabled_models 池比对。"""
import sqlite3

DB = r"E:\智慧项目\Mfkagent\backend\mfkagent.db"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== models 表结构 ===")
cols = [d[1] for d in cur.execute("PRAGMA table_info(models)")]
print("cols:", cols)

print()
print("=== models 全部行 ===")
rows = cur.execute("select * from models").fetchall()
for r in rows:
    print(r)

print()
print("=== enabled_models (glm) ===")
row = cur.execute("select value from settings where key='enabled_models'").fetchone()
if row:
    import json
    d = json.loads(row[0])
    print("glm list:", d.get("glm"))
con.close()
