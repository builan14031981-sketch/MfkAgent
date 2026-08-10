"""Phase 4 T3: Skill Prompt Fragment 加载器。

职责（最小化原则 — Skill 不是 Plugin/Executor/Tool）：
  1. 从 skill_definitions 表加载 enabled=True 的所有 Skill
  2. 按 category 排序（保证拼接顺序稳定）
  3. 拼接为单一 system prompt 片段字符串
  4. 全部操作 try/except 兜底，Skill 加载失败不阻断主流程
  5. 严禁引入任何 Tool / Code / API / Executor 能力

Skill = Prompt Fragment：
  - SkillDefinition.name → 人类可读的 Skill 名
  - SkillDefinition.description → 用途说明
  - SkillDefinition.category → 分类（用于排序）
  - SkillDefinition.system_prompt_fragment → 注入到 system prompt 的实际文本
  - SkillDefinition.enabled → 是否启用（禁用时不加载）

使用示例：
    from app.core.skill_store import get_enabled_skills_prompt
    fragment = get_enabled_skills_prompt()  # 返回 str，无 Skill 时返回 ""
"""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _load_enabled_skills() -> List:
    """从数据库加载所有 enabled 的 Skill，按 (category, name) 稳定排序。

    Returns:
        list[SkillDefinition] — 启用 Skill 列表；异常时返回空 list
    """
    try:
        from app.core.database import SessionLocal
        from app.models.agent import SkillDefinition

        db = SessionLocal()
        try:
            skills = (
                db.query(SkillDefinition)
                .filter(SkillDefinition.enabled == True)  # noqa: E712
                .order_by(SkillDefinition.category.asc(), SkillDefinition.id.asc())
                .all()
            )
            return list(skills)
        except Exception as e:
            logger.warning("[skill_store] 加载 Skill 失败: %s", e)
            return []
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.warning("[skill_store] 初始化 Skill 会话失败: %s", e)
        return []


def get_enabled_skills_prompt() -> str:
    """拼接所有 enabled Skill 的 prompt 片段为单一字符串。

    Returns:
        str — 拼好的 prompt 片段；无 Skill 或全部异常时返回 ""

    设计要点：
      - 不修改原 Skill 内容
      - 多个 Skill 用 \n\n---\n\n 分隔
      - 包裹 XML 标签 <skill_fragments> ... </skill_fragments> 便于模型识别
    """
    skills = _load_enabled_skills()
    if not skills:
        return ""

    fragments = []
    for s in skills:
        # 缺失 fragment 字段时跳过
        content = (getattr(s, "system_prompt_fragment", "") or "").strip()
        if not content:
            continue
        name = getattr(s, "name", "")
        category = getattr(s, "category", "general")
        # 块级格式：保留原始文本，添加 header 标识 Skill 名（便于模型识别归属）
        fragments.append(
            f"<!-- skill: {name} (category: {category}) -->\n{content}"
        )

    if not fragments:
        return ""

    body = "\n\n---\n\n".join(fragments)
    return (
        "<skill_fragments>\n"
        "以下为可用的 Skill Prompt 片段，每段以 <!-- skill: name (category: x) --> 标记开头。\n"
        "Skill 仅提供行为指导，不引入任何工具/代码/API 能力。\n"
        "请按 Skill 描述规范自身的回答风格与行为准则。\n\n"
        f"{body}\n"
        "</skill_fragments>"
    )


def get_enabled_skills_summary() -> List[dict]:
    """返回当前启用的 Skill 摘要列表（用于调试 / 状态查询）。

    Returns:
        list[dict] — [{name, description, category, fragment_len}, ...]
    """
    skills = _load_enabled_skills()
    return [
        {
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "fragment_len": len((s.system_prompt_fragment or "")),
        }
        for s in skills
    ]


def upsert_skill(
    name: str,
    description: str,
    system_prompt_fragment: str,
    category: str = "general",
    enabled: bool = True,
) -> bool:
    """插入或更新一个 Skill（同名则更新）。

    Returns:
        bool — True 成功；False 失败（失败时不抛异常）
    """
    if not name or not name.strip():
        return False
    if not system_prompt_fragment or not system_prompt_fragment.strip():
        return False

    try:
        from app.core.database import SessionLocal
        from app.models.agent import SkillDefinition

        db = SessionLocal()
        try:
            row = (
                db.query(SkillDefinition)
                .filter(SkillDefinition.name == name)
                .first()
            )
            if row:
                row.description = description or ""
                row.category = category or "general"
                row.system_prompt_fragment = system_prompt_fragment
                row.enabled = enabled
            else:
                row = SkillDefinition(
                    name=name,
                    description=description or "",
                    category=category or "general",
                    system_prompt_fragment=system_prompt_fragment,
                    enabled=enabled,
                )
                db.add(row)
            db.commit()
            return True
        except Exception as e:
            logger.warning("[skill_store] upsert_skill 失败: %s", e)
            try:
                db.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.warning("[skill_store] upsert_skill 初始化失败: %s", e)
        return False
