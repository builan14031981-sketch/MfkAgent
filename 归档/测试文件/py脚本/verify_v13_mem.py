import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.core.agent_runtime.context_builder import _build_memory_text
from app.models.agent import Chat

db = SessionLocal()
try:
    chat = db.query(Chat).filter(Chat.id == 154).first()
    print('chat agent_id:', chat.agent_id, 'project_id:', chat.project_id)
    mt = _build_memory_text(db, chat.project_id, chat.agent_id)
    print('=== memory_text ===')
    print(repr(mt))
finally:
    db.close()