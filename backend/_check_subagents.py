import sys
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
rows = db.execute(text("SELECT agent_id, allowed_tools, identity FROM agents WHERE agent_id IN ('sub_frontend','sub_architecture','sub_backend','sub_researcher')")).fetchall()
for r in rows:
    print("===", r[0], "===")
    print("allowed:", r[1])
    print("identity:", (r[2] or "")[:400])
    print()
db.close()