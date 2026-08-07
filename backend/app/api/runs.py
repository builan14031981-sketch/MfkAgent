"""Runtime Replay API — Phase E7-3：AgentRun 事件回放 / 审计。

只读接口，供未来 Agent Timeline / Multi-Agent / Debug / 用户查看执行过程使用。
当前不提供前端 UI，仅 API。
"""
from fastapi import APIRouter, HTTPException

from app.core.database import SessionLocal
from app.models.agent import AgentRun, RuntimeEvent

router = APIRouter()


@router.get("/{run_id}/events")
async def get_run_events(run_id: int):
    """按 sequence ASC 返回该 AgentRun 的全部运行时事件。

    Returns:
        {
            "run_id": int,
            "run": {"status", "state", "started_at", "finished_at"},
            "events": [{"seq": int, "type": str, "created_at": str, ...payload}, ...],
        }
    """
    db = SessionLocal()
    try:
        run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="AgentRun not found")

        events = (
            db.query(RuntimeEvent)
            .filter(RuntimeEvent.run_id == run_id)
            .order_by(RuntimeEvent.sequence.asc())
            .all()
        )

        return {
            "run_id": run_id,
            "run": {
                "chat_id": run.chat_id,
                "agent_id": run.agent_id,
                "status": run.status,
                "state": run.state,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            },
            "events": [
                {
                    "seq": ev.sequence,
                    "type": ev.event_type,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                    **(ev.payload or {}),
                }
                for ev in events
            ],
        }
    finally:
        db.close()
