# -*- coding: utf-8 -*-
"""临时脚本：查当前 DB 全部 api_key / provider 状态 / models 计数（仅读）"""
import sqlite3

conn = sqlite3.connect(r"e:\智慧项目\Mfkagent\backend\mfkagent.db")
cur = conn.cursor()

print("=== settings: 所有 api_key*/provider_disabled/default_model ===")
for r in cur.execute(
    "select key, value from settings where key like 'api_key%' or key in ('provider_disabled','default_model')"
).fetchall():
    key, val = r
    if "api_key" in key and val:
        print(key, "=> [已配置 len=%d]" % len(val))
    else:
        print(key, "=>", repr(val))

print("\n=== models 计数（按 provider） ===")
for r in cur.execute("select provider, count(*) from models group by provider").fetchall():
    print(r)

conn.close()
