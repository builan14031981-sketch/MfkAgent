import sys
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from app.models.agent import RuntimeEvent
from sqlalchemy import text

db = SessionLocal()
# sub_architecture 1267 的最终内容（看计划怎么说）
print("========== run 1267 sub_architecture 计划 ==========")
evs = db.query(RuntimeEvent).filter(RuntimeEvent.run_id == 1267).order_by(RuntimeEvent.id).all()
for e in evs:
    p = e.payload or {}
    if e.event_type == "agent_message":
        print(str(p)[:4000])
print()
# 主 Agent 1266 最终报告（简报+计划要点）
print("========== run 1266 general 最终消息 ==========")
m = db.execute(text("SELECT content FROM messages WHERE chat_id=318 AND role='assistant' ORDER BY id DESC LIMIT 1")).fetchone()
if m:
    c = m[0] or ""
    print(c[:6000])
db.close()