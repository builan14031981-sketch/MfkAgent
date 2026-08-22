import sys
sys.path.insert(0, ".")
from app.core.database import SessionLocal
from app.models.agent import RuntimeEvent

db = SessionLocal()
evs = db.query(RuntimeEvent).filter(RuntimeEvent.run_id == 1266).order_by(RuntimeEvent.id).all()
for e in evs:
    p = e.payload or {}
    if e.event_type == "tool_start" and p.get("tool") == "delegate_sub_agent":
        print("===== DELEGATE TASK =====")
        print((p.get("input") or {}).get("task", "")[:1500])
        print()
    if e.event_type == "tool_result" and p.get("tool") == "delegate_sub_agent":
        print("===== DELEGATE RESULT =====")
        print(str(p.get("result"))[:4500])
        print()
db.close()