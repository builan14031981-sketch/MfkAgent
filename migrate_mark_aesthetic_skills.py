import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend")
from app.core.skill_catalog import IMAGE_SKILL_CATALOG

DB = Path(r"E:\智慧项目\Mfkagent\backend\mfkagent.db")
conn = sqlite3.connect(str(DB), timeout=10.0)
cur = conn.cursor()

updated_count = 0
for s in IMAGE_SKILL_CATALOG:
    skill_id = s["id"]
    cur.execute("SELECT id FROM skill_definitions WHERE name = ?", (skill_id,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE skill_definitions SET category = ?, description = ?, system_prompt_fragment = ?, enabled = 1 WHERE name = ?",
            (s["category"], s["description"], s["prompt"], skill_id)
        )
    else:
        cur.execute(
            "INSERT INTO skill_definitions (name, description, category, system_prompt_fragment, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (skill_id, s["description"], s["category"], s["prompt"])
        )
    updated_count += 1

conn.commit()
conn.close()
print(f"✅ DB 迁移成功！成功处理 {updated_count} 个 '风格化图像' 技能。")
