"""
记忆防乱加功能验证脚本
直接调用 add_memory 函数测试：长度下限、去重、相似度去重
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.core.tools import add_memory
from app.core.database import SessionLocal
from app.models.agent import MemoryItem

def count_memories(scope="global", agent_id=None):
    db = SessionLocal()
    try:
        q = db.query(MemoryItem).filter(MemoryItem.scope == scope, MemoryItem.is_active == True)
        if agent_id:
            q = q.filter(MemoryItem.agent_id == agent_id)
        return q.count()
    finally:
        db.close()

def cleanup_test_memories():
    """清理测试产生的记忆"""
    db = SessionLocal()
    try:
        db.query(MemoryItem).filter(MemoryItem.content.like("%防乱加测试%")).delete()
        db.query(MemoryItem).filter(MemoryItem.content.like("%memory_dedup_test%")).delete()
        db.commit()
        print("  清理完成")
    finally:
        db.close()

print("="*60)
print("  记忆防乱加功能验证")
print("="*60)

# 清理之前的测试数据
cleanup_test_memories()

# 测试1：长度下限
print("\n[测试1] 内容长度下限（<10字拒绝）")
result = add_memory(scope="global", content="短记忆")
print(f"  输入'短记忆'(3字): {result}")
assert "错误" in result, "短内容应该被拒绝"
print("  PASS: 短内容被拒绝")

# 测试2：正常添加
print("\n[测试2] 正常添加记忆（>=10字）")
before = count_memories("global")
result = add_memory(scope="global", content="防乱加测试：这是一条正常长度的记忆内容用于测试")
print(f"  结果: {result}")
after = count_memories("global")
assert after == before + 1, f"应该新增1条，实际新增{after-before}"
print(f"  PASS: 新增成功，总数 {before} -> {after}")

# 测试3：完全相同内容去重（更新不新增）
print("\n[测试3] 完全相同内容去重（更新不新增）")
before = count_memories("global")
result = add_memory(scope="global", content="防乱加测试：这是一条正常长度的记忆内容用于测试")
print(f"  结果: {result}")
after = count_memories("global")
assert after == before, f"应该不新增，实际新增{after-before}"
assert "更新" in result, "应该返回更新信息"
print(f"  PASS: 重复内容被更新，总数不变 {before} -> {after}")

# 测试4：相似内容去重（相似度>0.8）
print("\n[测试4] 相似内容去重（相似度>0.8更新不新增）")
before = count_memories("global")
# 只改几个字，相似度应该>0.8
result = add_memory(scope="global", content="防乱加测试：这是一条正常长度的记忆内容用于测试修改版")
print(f"  结果: {result}")
after = count_memories("global")
assert after == before, f"应该不新增，实际新增{after-before}"
print(f"  PASS: 相似内容被更新，总数不变 {before} -> {after}")

# 测试5：不同内容正常新增
print("\n[测试5] 不同内容正常新增")
before = count_memories("global")
result = add_memory(scope="global", content="防乱加测试：这是另一条完全不同的记忆内容用于验证去重不会误杀")
print(f"  结果: {result}")
after = count_memories("global")
assert after == before + 1, f"应该新增1条，实际新增{after-before}"
print(f"  PASS: 不同内容新增成功，总数 {before} -> {after}")

# 测试6：默认scope=agent（需要agent_id）
print("\n[测试6] 默认scope=agent（不传scope时）")
try:
    result = add_memory(content="防乱加测试：默认scope测试内容用于验证默认值")
    print(f"  结果: {result}")
    # 没有agent_id应该报错
    assert "错误" in result, "没有agent_id应该报错"
    print("  PASS: 默认agent scope，无agent_id时报错（符合预期）")
except Exception as e:
    print(f"  异常: {e}")

# 测试7：agent scope正常添加+去重
print("\n[测试7] agent scope添加+去重")
before = count_memories("agent", agent_id="test_agent")
result = add_memory(scope="agent", agent_id="test_agent", content="防乱加测试：agent专属记忆内容用于测试隔离")
print(f"  第一次: {result}")
after1 = count_memories("agent", agent_id="test_agent")
result2 = add_memory(scope="agent", agent_id="test_agent", content="防乱加测试：agent专属记忆内容用于测试隔离")
print(f"  第二次(重复): {result2}")
after2 = count_memories("agent", agent_id="test_agent")
assert after1 == before + 1, "第一次应该新增"
assert after2 == after1, "第二次应该不新增"
print(f"  PASS: agent scope隔离正常，新增后重复不新增 {before} -> {after1} -> {after2}")

# 清理
print("\n[清理] 清理测试数据")
cleanup_test_memories()

print("\n" + "="*60)
print("  全部测试通过！")
print("="*60)
