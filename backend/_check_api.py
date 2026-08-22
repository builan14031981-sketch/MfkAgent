import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal

db = SessionLocal()
print("--- chat 318 ---")
c = db.execute(text("SELECT id, agent_id, model FROM chats WHERE id=318")).fetchone()
print(c)
print("--- Agent general ---")
a = db.execute(text("SELECT agent_id, model, provider FROM agents WHERE agent_id='general'")).fetchone()
print(a)
print("--- enabled models / provider config (keys masked) ---")
for r in db.execute(text("SELECT key, value FROM settings WHERE key IN ('enabled_models','model_provider_config','glm_api_key','siliconflow_api_key','provider_disabled')")).fetchall():
    v = str(r[1]) if r[1] else ""
    print(r[0], "=", v[:60] + ("..." if len(v) > 60 else ""))
db.close()