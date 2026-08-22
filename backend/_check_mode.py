import sys
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
r = db.execute(text("SELECT value FROM settings WHERE key='agent_permission_mode'")).scalar()
print("agent_permission_mode =", r)
db.close()