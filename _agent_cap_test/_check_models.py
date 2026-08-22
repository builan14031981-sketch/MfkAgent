# -*- coding: utf-8 -*-
"""查询当前模型池：enabled_models 与 provider_disabled，确认视觉模型可用性。"""
import sqlite3

db = sqlite3.connect(r"E:\智慧项目\Mfkagent\backend\mfkagent.db")
for key in ("enabled_models", "provider_disabled"):
    rows = db.execute("select value from settings where key=?", (key,)).fetchall()
    if rows:
        print(f"== {key} ==")
        print(rows[0][0][:800])
        print()
    else:
        print(f"== {key} == (无记录)")
