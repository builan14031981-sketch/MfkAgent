"""迁移脚本：给 agents 表加 skills JSON 列（幂等，可重复执行）。

用法：
    python backend/migrate_add_agent_skills.py
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "backend" / "mfkagent.db"
if not DB.exists():
    # 若从 backend/ 目录执行
    DB = Path(__file__).parent / "mfkagent.db"

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

# 检查列是否已存在
cur.execute("PRAGMA table_info(agents)")
cols = {row[1] for row in cur.fetchall()}
if "skills" not in cols:
    cur.execute("ALTER TABLE agents ADD COLUMN skills TEXT DEFAULT '[]'")
    conn.commit()
    print("✅ 已添加 agents.skills 列")
else:
    print("✅ agents.skills 列已存在，跳过")

conn.close()
