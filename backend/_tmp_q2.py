# -*- coding: utf-8 -*-
import sqlite3
db = sqlite3.connect(r"e:\智慧项目\Mfkagent\backend\mfkagent.db")
rows = db.execute(
    "select key, value from settings "
    "where key in ('vision_provider','vision_api_key','vision_model','vision_base_url','agent_permission_mode')"
).fetchall()
for k, v in rows:
    print(k, "=>", (v or "")[:120])
db.close()
