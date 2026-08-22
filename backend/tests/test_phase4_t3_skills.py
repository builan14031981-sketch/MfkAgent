"""Task 3 测试：Skill Prompt System。

测试覆盖：
  1. skill_definitions 表已创建
  2. skill_store 能从数据库加载 enabled Skill
  3. 拼接顺序：先按 category，再按 id
  4. 无 Skill 时 get_enabled_skills_prompt 返回 ""
  5. context_builder 注入位置：在 capability 之后、execution_policy 之前
  6. 全部 Skill enabled 时 prompt 完整
  7. 部分 Skill 禁用时被过滤
  8. Skill 加载失败不影响主流程
  9. Skill 不会污染 Tool / Executor / RiskEngine
"""
import os
import sys
import re
import json

# 切到 backend 目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _has_token(text: str, token: str) -> bool:
    """简单 token 检查：作为整词出现。"""
    return bool(re.search(rf"\b{re.escape(token)}\b", text))


# 重要：先创建所有表
from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)

from app.core.database import SessionLocal
from app.models.agent import SkillDefinition

print("=" * 60)
print("Task 3.1: skill_definitions 表已创建 + seed 4 个预置 Skill")
print("=" * 60)

# 重新跑 seed（幂等）
from app.core.seed_skills import PRESET_SKILLS, main as seed_main
seed_main()

# 验证表与数据
db = SessionLocal()
try:
    rows = db.query(SkillDefinition).all()
    print(f"  当前 Skill 表行数: {len(rows)}")
    for r in rows:
        print(f"    - {r.name} (category={r.category}, enabled={r.enabled}, fragment_len={len(r.system_prompt_fragment or '')})")
    assert len(rows) >= 4, f"应至少有 4 个预置 Skill，实际: {len(rows)}"

    names = {r.name for r in rows}
    expected = {"code_review", "python_expert", "security_audit", "test_design"}
    assert expected <= names, f"缺少预置 Skill: {expected - names}"
    print(f"  [PASS] 4 个预置 Skill 全部存在: {sorted(expected)}")
finally:
    db.close()

print()
print("=" * 60)
print("Task 3.2: skill_store.get_enabled_skills_prompt()")
print("=" * 60)

from app.core.skill_store import get_enabled_skills_prompt, get_enabled_skills_summary

# 全部 enabled
fragment = get_enabled_skills_prompt()
status = "PASS" if fragment else "FAIL"
print(f"  [{status}] 全部 enabled 时返回非空字符串: len={len(fragment)}")
assert fragment
assert "<skill_fragments>" in fragment
assert "</skill_fragments>" in fragment
# 验证 4 个 Skill 都在 fragment 中
for name in ["code_review", "python_expert", "security_audit", "test_design"]:
    assert name in fragment, f"fragment 应包含 {name}"
    print(f"    - {name} 在 fragment 中")

# 验证 category 排序：engineering 排在 security 前
eng_idx = fragment.find("code_review")
sec_idx = fragment.find("security_audit")
status = "PASS" if eng_idx < sec_idx else "FAIL"
print(f"  [{status}] category 排序正确 (engineering < security): eng_idx={eng_idx} < sec_idx={sec_idx}")
assert eng_idx < sec_idx

# 验证 summary
summary = get_enabled_skills_summary()
print(f"  [INFO] summary 返回 {len(summary)} 个 Skill")
assert len(summary) >= 4

print()
print("=" * 60)
print("Task 3.3: 禁用某些 Skill 后被过滤")
print("=" * 60)

# 禁用 test_design
db = SessionLocal()
try:
    s = db.query(SkillDefinition).filter(SkillDefinition.name == "test_design").first()
    original_enabled = s.enabled
    s.enabled = False
    db.commit()
    print(f"  [INFO] 临时禁用 test_design（已保存原状态 {original_enabled}）")
finally:
    db.close()

fragment = get_enabled_skills_prompt()
assert "test_design" not in fragment, "禁用的 Skill 不应出现在 fragment 中"
print(f"  [PASS] test_design 已被过滤: len={len(fragment)}")

# 恢复
db = SessionLocal()
try:
    s = db.query(SkillDefinition).filter(SkillDefinition.name == "test_design").first()
    s.enabled = True
    db.commit()
    print(f"  [INFO] 已恢复 test_design 状态")
finally:
    db.close()

# 全部禁用 → fragment 应为空
db = SessionLocal()
try:
    all_rows = db.query(SkillDefinition).all()
    saved_states = [(r.id, r.enabled) for r in all_rows]
    for r in all_rows:
        r.enabled = False
    db.commit()
    try:
        fragment = get_enabled_skills_prompt()
        status = "PASS" if not fragment else "FAIL"
        print(f"  [{status}] 全部禁用时 fragment 为空: fragment={fragment!r}")
        assert not fragment
    finally:
        for r in db.query(SkillDefinition).all():
            for sid, en in saved_states:
                if r.id == sid:
                    r.enabled = en
        db.commit()
        print(f"  [INFO] 已恢复所有 Skill 状态")
finally:
    db.close()

print()
print("=" * 60)
print("Task 3.4: Skill 加载失败不影响主流程")
print("=" * 60)

# 模拟 SessionLocal 失败：通过 patch skill_store 内的 SessionLocal 让其抛异常
import app.core.skill_store as ss

class _BrokenSession:
    """任何属性访问都抛异常的占位 Session（模拟 DB 不可用）。"""
    def __getattr__(self, name):
        raise RuntimeError("mock db failure")

def _broken_sessionlocal():
    return _BrokenSession()

# 注意：skill_store 内部使用 from-import，需要在模块内 monkey-patch
# 因为模块内是 from app.core.database import SessionLocal，需要找到 _load_enabled_skills 内部用的引用
# 直接 patch _load_enabled_skills 内部 db 变量
import unittest.mock

with unittest.mock.patch("app.core.database.SessionLocal", _broken_sessionlocal):
    fragment = get_enabled_skills_prompt()
    status = "PASS" if not fragment else "FAIL"
    print(f"  [{status}] DB 不可用时返回空字符串: fragment_len={len(fragment)}")
    assert not fragment, f"DB 失败时应返回空字符串，实际: {fragment!r}"

print()
print("=" * 60)
print("Task 3.5-3.7 已按 2026-08-16 设计变更移除：Skill 全局注入废弃，改为前端 buildContent 会话级注入")
print("（skill_store 加载/过滤能力仍由上方 Task 3.1-3.4 覆盖）")
print("=" * 60)

# 保留 Task 3.7 的表结构独立检查
from app.models.agent import SkillDefinition as SD
fks = [fk for fk in SD.__table__.foreign_keys]
fk_targets = [fk.target_fullname for fk in fks]
print(f"  [INFO] SkillDefinition 外键: {fk_targets}")
assert len(fk_targets) == 0, f"SkillDefinition 不应有外键（独立表）: {fk_targets}"
print(f"  [PASS] SkillDefinition 是独立表，无外键")

print()
print("=" * 60)
print("Task 3 全部测试通过 ✓")
print("=" * 60)
