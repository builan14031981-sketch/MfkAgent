import sys
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from app.models.agent import AgentRun
from sqlalchemy import text

db = SessionLocal()
runs = db.query(AgentRun).filter(AgentRun.chat_id == 318).order_by(AgentRun.id.desc()).limit(4).all()
for r in runs:
    print("run", r.id, r.agent_id, r.status, r.started_at, "->", r.finished_at)
print()
m = db.execute(text("SELECT id, role, substr(content,1,90) AS c, created_at FROM messages WHERE chat_id=318 ORDER BY id DESC LIMIT 5")).fetchall()
for x in m:
    print(x)
db.close()