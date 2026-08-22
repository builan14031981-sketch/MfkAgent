import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal

db = SessionLocal()
print("--- agents schema ---")
cols = [r[1] for r in db.execute(text("PRAGMA table_info(agents)")).fetchall()]
print(cols)
r = db.execute(text("SELECT * FROM agents WHERE agent_id='general'")).fetchone()
print("general agent:", r)
print("--- settings (masked) ---")
for row in db.execute(text("SELECT key, value FROM settings WHERE key IN ('enabled_models','glm_api_key','siliconflow_api_key','openai_api_key','model_provider_config')")).fetchall():
    v = str(row[1]) if row[1] else ""
    print(row[0], "=", v[:80] + ("..." if len(v) > 80 else ""))
db.close()