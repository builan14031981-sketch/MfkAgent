"""Runtime Event Recorder — Phase E2 + E5 统一事件出口。

职责：
  - AgentRun 生命周期：create_run(status=running, state=pending) → finish_run(completed/failed/cancelled)
  - AgentRun 阶段流转：transition(run_id, to_state) — 更新 state + 写 RuntimeState 审计 + 合法性校验
  - RuntimeEvent 流水：emit(run_id, event_type, payload)，sequence 同 run 内严格自增
    （E5：事件类型经 states.py 注册表软校验，未知类型仅记日志）

设计原则：
  - 事件持久化是主执行链路的「旁路副作用」：任何 DB 失败仅记录日志，
    绝不阻断 Agent 执行（与 ToolEventSource.emit 一致）。
  - sequence 自增：create_run 时以 DB 内该 run 已有最大 sequence 为起点续接
    （进程重启安全），之后进程内递增，避免每次 emit 都查询数据库。
  - 使用独立 Session：不占用请求事务，避免与主流程会话争锁。

用法：
    run_id = runtime_event_recorder.create_run(chat_id=..., agent_id=...)
    runtime_event_recorder.transition(run_id, "building_context")
    runtime_event_recorder.emit(run_id, "tool_start", {"tool": "read_file", ...})
    runtime_event_recorder.finish_run(run_id, "completed")
"""

import logging
from datetime import datetime
from typing import Dict, Optional

from app.core.database import SessionLocal
from app.models.agent import AgentRun, RuntimeEvent, RuntimeState
from app.core.agent_runtime.states import INITIAL_PHASE, is_valid_transition, is_registered_event_type

logger = logging.getLogger(__name__)


class RuntimeEventRecorder:
    """运行时事件持久化器（AgentRun 生命周期 + RuntimeState 阶段 + RuntimeEvent 流水）。"""

    def __init__(self):
        # run_id -> 下一个 sequence（进程内缓存，create_run 时从 DB 续接）
        self._next_seq: Dict[int, int] = {}

    # ──── AgentRun 生命周期 ────

    def create_run(
        self,
        chat_id: Optional[int],
        agent_id: str,
        parent_run_id: Optional[int] = None,
    ) -> Optional[int]:
        """创建运行记录（status=running, state=pending），返回 run_id。

        Phase H: parent_run_id 记录 checkpoint 血缘（本次执行从哪个 run 继续），
        不改变状态机任何行为，仅追溯。

        失败返回 None（不阻断执行），日志记录原因。
        """
        db = SessionLocal()
        try:
            run = AgentRun(
                chat_id=chat_id,
                agent_id=agent_id,
                status="running",
                state=INITIAL_PHASE,
                parent_run_id=parent_run_id,
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            run_id = run.id
            last = (
                db.query(RuntimeEvent)
                .filter(RuntimeEvent.run_id == run_id)
                .order_by(RuntimeEvent.sequence.desc())
                .first()
            )
            self._next_seq[run_id] = (last.sequence + 1) if last else 1
            return run_id
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] create_run 失败（事件持久化旁路，不阻断执行）: %s", e)
            return None
        finally:
            db.close()

    def finish_run(self, run_id: Optional[int], status: str) -> None:
        """收尾运行：completed / failed / cancelled（同步将 state 置为终态）。"""
        if not run_id:
            return
        db = SessionLocal()
        try:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if run:
                run.status = status
                run.finished_at = datetime.utcnow()
                if status in ("completed", "failed", "cancelled"):
                    run.state = status
                db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] finish_run 失败: %s", e)
        finally:
            db.close()

    def get_state(self, run_id: Optional[int]) -> Optional[str]:
        """读取 AgentRun 当前阶段（不存在返回 None）。"""
        if not run_id:
            return None
        db = SessionLocal()
        try:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            return run.state if run else None
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] get_state 失败: %s", e)
            return None
        finally:
            db.close()

    def recover_stale_runs(self) -> int:
        """回收陈旧运行：进程启动时把遗留的 status=running run 置为 failed。

        原因（证据化收尾）：模型调用挂死 / 进程崩溃重启后，run 会永远停在 running
        （如 1281 卡死、1229/1234 僵尸），既不反映真实状态也无任何失败证据。
        启动瞬间不可能存在合法 running run（执行链在进程内），因此直接全部回收。

        每个被回收的 run 补写一条 error 事件作为失败证据（sequence 续接，避免冲突）。
        """
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            stale = db.query(AgentRun).filter(AgentRun.status == "running").all()
            count = 0
            for run in stale:
                last = (
                    db.query(RuntimeEvent)
                    .filter(RuntimeEvent.run_id == run.id)
                    .order_by(RuntimeEvent.sequence.desc())
                    .first()
                )
                seq = (last.sequence + 1) if last else 1
                run.status = "failed"
                run.state = "failed"
                run.finished_at = now
                db.add(RuntimeEvent(
                    run_id=run.id,
                    event_type="error",
                    payload={"message": "进程重启，运行被中断（stale run recovery）"},
                    sequence=seq,
                ))
                count += 1
            db.commit()
            if count:
                logger.warning("[runtime-events] 回收陈旧 running run %d 个", count)
            return count
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] 回收陈旧 run 失败: %s", e)
            return 0
        finally:
            db.close()

    def transition(
        self,
        run_id: Optional[int],
        to_state: str,
        reason: Optional[str] = None,
    ) -> Optional[str]:
        """阶段流转：更新 AgentRun.state 并写入 RuntimeState 审计行。

        非法流转不抛出异常：仅记日志并拒绝更新（旁路语义）。

        Args:
            run_id: AgentRun id
            to_state: 目标阶段（states.py RuntimePhase）
            reason: 流转原因（可选，如 "context built" / "tool approved"）

        Returns:
            原阶段名（成功流转）；非法/失败返回 None。
        """
        if not run_id:
            return None
        db = SessionLocal()
        try:
            run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
            if not run:
                return None
            from_state = run.state or INITIAL_PHASE
            if from_state == to_state:
                return from_state  # 同阶段无需流转
            if not is_valid_transition(from_state, to_state):
                logger.warning(
                    "[runtime-events] 非法状态流转 %s -> %s（run=%s）已拒绝", from_state, to_state, run_id
                )
                return None
            run.state = to_state
            db.add(RuntimeState(
                run_id=run_id,
                from_state=from_state,
                to_state=to_state,
                reason=(reason or "")[:200],
            ))
            db.commit()
            return from_state
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] transition 失败: %s", e)
            return None
        finally:
            db.close()

    # ──── 事件写入 ────

    def emit(self, run_id: Optional[int], event_type: str, payload: Optional[dict] = None) -> None:
        """写入一条运行时事件（sequence 同 run 内自增 1,2,3,...）。

        事件类型经 states.py 注册表软校验：未知类型仍写入，仅记日志（向后兼容）。
        """
        if not run_id:
            return
        if not is_registered_event_type(event_type):
            logger.warning("[runtime-events] 未注册事件类型: %r（已写入但不在注册表内）", event_type)
        seq = self._next_seq.get(run_id)
        if seq is None:
            seq = 1  # create_run 已初始化，兜底
        self._next_seq[run_id] = seq + 1

        db = SessionLocal()
        try:
            db.add(RuntimeEvent(
                run_id=run_id,
                event_type=event_type,
                payload=payload or {},
                sequence=seq,
            ))
            db.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("[runtime-events] emit 失败 (%s): %s", event_type, e)
        finally:
            db.close()


# 全局单例：全流程共用（sequence 缓存保证同 run 内自增）
runtime_event_recorder = RuntimeEventRecorder()
