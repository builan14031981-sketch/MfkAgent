"""P0-2 记忆系统落地：MemoryService 真实实现（三作用域读写 + 预算截断 + 时间衰减）。

改造原则（对照吸收天枢七点之 P0-2 记忆落地）：
- 保留旧方法签名兼容：get_memories / create_memory / delete_memory
- 真实读写 memory_items 表（与 add_memory 工具 / memory_extractor / /api/memories 同表同字段）
- 读取按作用域过滤，按 confidence x 新鲜度降序，超 token 预算截断，避免记忆膨胀击穿上下文
- 衰减为只读排序折价，不做物理删除（数据安全、可回滚）
- 既有路径（add_memory 直写 / _build_memory_text 注入 / memories API）零改动、不受影响
"""

import logging
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# 时间衰减半衰期：30 天（用户长期偏好应更持久，不照搬天枢 7 天以免误杀长期偏好）
DECAY_HALF_LIFE_DAYS = 30.0
# 记忆读取默认 token 预算（超预算截断）
DEFAULT_MAX_TOKENS = 4000
# 中文 token 估算：约 1.2 字符/token（保守下限）
CHARS_PER_TOKEN = 1.2
# 衰减折价下限：即使极老记忆也保留 30% 权重，避免完全消失
DECAY_FLOOR = 0.3


def _decay_factor(created_at: Optional[datetime], now: Optional[datetime] = None) -> float:
    """按创建时间计算新鲜度折价系数 [DECAY_FLOOR, 1.0]，半衰期 DECAY_HALF_LIFE_DAYS。"""
    if created_at is None:
        return 1.0
    try:
        now = now or datetime.utcnow()
        days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    except Exception:  # noqa: BLE001
        return 1.0
    factor = 0.5 ** (days / DECAY_HALF_LIFE_DAYS)
    return max(DECAY_FLOOR, min(1.0, factor))


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text or "") / CHARS_PER_TOKEN))


def resolve_scope(
    suggested: str,
    agent_id: Optional[str] = None,
    project_id: Optional[int] = None,
    memory_type: Optional[str] = None,
) -> tuple:
    """归属判定：模型建议 scope + 上下文强制/降级（提取器与 add_memory 工具共用）。

    返回 (scope, needs_attribution)：
      - 关系型 Agent（pianai）→ 强制 agent（自隔离）
      - memory_type == "project"（模型明确判定为项目规则）：
          * 有项目上下文 → project
          * 无项目上下文 → 降级 global + needs_attribution=True（待认领，不污染全局）
      - 模型建议 project：
          * 有项目上下文 → project
          * 无项目上下文 → 降级 global + needs_attribution=True（待认领）
      - 模型建议 agent 且有 agent_id → agent
      - 模型建议 global → global（显式意图，信任）
      - 模型未给出有效 scope → 按会话上下文兜底：有项目 → project，否则 → global
    """
    # 子代理是无状态临时执行单元，绝对绝缘 agent 专属记忆
    if agent_id and str(agent_id).startswith("sub_"):
        agent_id = None

    if agent_id and agent_id in ("pianai",):
        return ("agent", False)
    # 强信号：模型明确判定为项目规则，即使 suggested 是 global 也强制归属校验
    if memory_type == "project":
        if project_id is not None:
            return ("project", False)
        return ("global", True)  # 降级路径：无项目上下文，暂存全局并标记待认领
    if suggested == "project":
        if project_id is not None:
            return ("project", False)
        return ("global", True)  # 降级路径：无项目上下文，暂存全局并标记待认领
    if suggested == "agent":
        if agent_id:
            return ("agent", False)
        # 建议 agent 但无 Agent 上下文：走下方兜底
    if suggested == "global":
        return ("global", False)
    # 模型未给出 scope / 建议无效：按会话上下文兜底
    if project_id is not None:
        return ("project", False)
    return ("global", False)


class MemoryService:
    async def get_memories(
        self,
        agent_id: Optional[str] = None,
        user_id: str = "default",
        scope: str = "all",
        project_id: Optional[int] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> List:
        """按作用域读取记忆，confidence x 新鲜度排序，超预算截断，软删过滤。

        scope 取值：
          all     — 全局 + 当前 Agent 专属 +（可选）当前项目，三作用域合并
          global  — 仅全局记忆
          agent   — 仅当前 Agent 专属（需 agent_id）
          project — 仅当前项目记忆（需 project_id）

        每次读取会更新 last_accessed_at 和 access_count（访问衰减）。
        """
        from sqlalchemy import or_

        from app.core.database import SessionLocal
        from app.models.agent import MemoryItem

        db = SessionLocal()
        try:
            # 子代理是无状态临时执行单元，绝不接入 agent 专属记忆
            if agent_id and str(agent_id).startswith("sub_"):
                agent_id = None

            # needs_attribution=true 的记忆是"待认领归属"的降级暂存，不参与上下文读取
            q = db.query(MemoryItem).filter(
                MemoryItem.is_active == True,
                MemoryItem.needs_attribution == False,
            )
            if scope == "all":
                conds = [MemoryItem.scope == "global"]
                if agent_id:
                    conds.append((MemoryItem.scope == "agent") & (MemoryItem.agent_id == agent_id))
                if project_id:
                    conds.append((MemoryItem.scope == "project") & (MemoryItem.project_id == project_id))
                q = q.filter(or_(*conds))
            elif scope == "agent":
                q = q.filter(MemoryItem.scope == "agent", MemoryItem.agent_id == agent_id)
            elif scope == "global":
                q = q.filter(MemoryItem.scope == "global")
            elif scope == "project":
                q = q.filter(MemoryItem.scope == "project", MemoryItem.project_id == project_id)
            else:
                return []

            items = q.order_by(MemoryItem.confidence.desc(), MemoryItem.created_at.desc()).all()
            now = datetime.utcnow()
            scored = [(m.confidence or 0.8) * _decay_factor(m.created_at, now) for m in items]
            order = sorted(range(len(items)), key=lambda i: scored[i], reverse=True)

            result = []
            budget = 0
            for i in order:
                m = items[i]
                tok = _estimate_tokens(m.content or "")
                if budget + tok > max_tokens:
                    break
                budget += tok
                result.append(m)

            # 更新访问统计（衰减用）
            if result:
                try:
                    ids = [m.id for m in result]
                    db.query(MemoryItem).filter(MemoryItem.id.in_(ids)).update(
                        {MemoryItem.access_count: MemoryItem.access_count + 1,
                         MemoryItem.last_accessed_at: now},
                        synchronize_session=False,
                    )
                    db.commit()
                except Exception:  # noqa: BLE001
                    db.rollback()
                    logger.exception("[MemoryService] 更新访问统计失败")

            return result
        finally:
            db.close()

    async def create_memory(
        self,
        agent_id: Optional[str] = None,
        key: Optional[str] = None,
        value: Optional[str] = None,
        memory_type: str = "preference",
        scope: str = "agent",
        project_id: Optional[int] = None,
        content: Optional[str] = None,
        confidence: float = 0.8,
    ) -> Optional[int]:
        """写入记忆（兼容旧 key/value 签名，也支持 content 直接传）。

        成功返回记忆 id，失败返回 None。scope 非法 / 上下文缺失返回 None。
        """
        from app.core.database import SessionLocal
        from app.models.agent import MemoryItem

        if content is None:
            content = f"{key}: {value}" if key and value else (key or value or "")
        content = (content or "").strip()
        if not content:
            return None
        if scope not in ("global", "agent", "project"):
            return None
        if scope == "agent" and (not agent_id or str(agent_id).startswith("sub_")):
            return None
        if scope == "project" and not project_id:
            return None

        db = SessionLocal()
        try:
            item = MemoryItem(
                scope=scope,
                agent_id=agent_id if scope == "agent" else None,
                project_id=project_id if scope == "project" else None,
                content=content,
                memory_type=memory_type,
                confidence=confidence,
                is_active=True,
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            return item.id
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("[MemoryService] create_memory 失败")
            return None
        finally:
            db.close()

    async def delete_memory(self, memory_id: int) -> bool:
        """软删记忆；不存在返回 False，软删成功返回 True。"""
        from app.core.database import SessionLocal
        from app.models.agent import MemoryItem

        db = SessionLocal()
        try:
            item = db.query(MemoryItem).filter(MemoryItem.id == memory_id, MemoryItem.is_active == True).first()
            if not item:
                return False
            item.is_active = False
            db.commit()
            return True
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("[MemoryService] delete_memory 软删失败")
            return False
        finally:
            db.close()

    async def delete_memory_hard(self, memory_id: int) -> bool:
        """真删记忆（谨慎使用）；不存在返回 False，删除成功返回 True。"""
        from app.core.database import SessionLocal
        from app.models.agent import MemoryItem

        db = SessionLocal()
        try:
            item = db.query(MemoryItem).filter(MemoryItem.id == memory_id).first()
            if not item:
                return False
            db.delete(item)
            db.commit()
            return True
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("[MemoryService] delete_memory_hard 真删失败")
            return False
        finally:
            db.close()


memory_service = MemoryService()
