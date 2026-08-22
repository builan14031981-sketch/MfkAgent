import sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal

db = SessionLocal()
print("--- projects ---")
for r in db.execute(text("SELECT id, name, path FROM projects")).fetchall():
    print(r)
print("--- chats with project_path set but project_id null ---")
q = text("SELECT id, project_id, project_path, title FROM chats WHERE project_path IS NOT NULL AND project_path<>'' AND project_id IS NULL")
for r in db.execute(q).fetchall():
    print(r)
db.close()