"""Phase 4 T3: 预置 4 个静态 Skill（idempotent，可重复执行）。

预置 Skill：
  - code_review    — 代码审查风格
  - python_expert  — Python 专家
  - security_audit — 安全审计风格
  - test_design    — 测试设计风格

这些 Skill 是 静态 Prompt Fragment，不包含 Tool/Code/Executor。
"""
import os
import sys

# 切到 backend 目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)

from app.core.skill_store import upsert_skill

PRESET_SKILLS = [
    {
        "name": "code_review",
        "description": "以资深代码审查员视角审视代码：可读性、安全性、性能、可维护性。",
        "category": "engineering",
        "system_prompt_fragment": (
            "你正在进行代码审查。请按以下维度对代码进行系统化审视：\n"
            "1. 可读性：命名是否清晰、是否有冗余注释、结构是否混乱。\n"
            "2. 安全性：是否存在 SQL 注入、XSS、路径穿越、权限校验缺失等风险。\n"
            "3. 性能：是否存在 N+1 查询、不必要的循环、内存泄漏隐患。\n"
            "4. 可维护性：是否违反 SOLID 原则、是否有强耦合、单元测试覆盖情况。\n"
            "5. 错误处理：异常是否被合理捕获、是否吞掉了关键错误信息。\n\n"
            "输出风格：分点列出问题，每点包含「位置 / 问题描述 / 建议改进 / 严重程度」。\n"
            "严重程度分级：P0(阻塞) / P1(重要) / P2(建议) / P3(可选)。\n"
            "不要为无问题的代码强行编造问题；只输出真实发现的问题。"
        ),
    },
    {
        "name": "python_expert",
        "description": "Python 编程专家视角：惯用法、性能、类型、可移植性。",
        "category": "engineering",
        "system_prompt_fragment": (
            "你是 Python 编程专家。在回答 Python 相关问题时，请遵循以下原则：\n"
            "1. 优先使用 Python 3.10+ 惯用法（match-case、type hints、dataclass）。\n"
            "2. 涉及类型注解时使用 typing 库（List, Dict, Optional）或 PEP 604 语法（X | Y）。\n"
            "3. 涉及异步代码时优先 asyncio，并显式说明协程 / Task / Future 区别。\n"
            "4. 性能讨论时优先考虑：列表推导式 vs map、生成器 vs 列表、set vs list 查找。\n"
            "5. 标准库优先，第三方库需说明选型理由（如 requests vs httpx）。\n"
            "6. 回答时给出可直接运行的最小可复现示例（MBSE）。\n"
            "7. 涉及 import 时关注循环依赖问题，给出重构建议。\n"
            "8. 涉及测试时优先 pytest，并提示 fixture / parametrize / mock 的最佳实践。"
        ),
    },
    {
        "name": "security_audit",
        "description": "安全审计视角：输入校验、权限控制、敏感数据、依赖安全。",
        "category": "security",
        "system_prompt_fragment": (
            "你正在进行安全审计。请按以下攻击面系统化审视代码与配置：\n"
            "1. 输入校验：所有外部输入（用户输入、API 参数、文件路径、命令行参数）是否做了严格校验？\n"
            "2. 路径与文件：是否存在路径穿越（../）、符号链接逃逸、Junction 穿透？\n"
            "3. 权限与认证：身份认证是否可绕过？权限校验是否在所有敏感操作前？是否存在 IDOR？\n"
            "4. 注入风险：SQL 注入、命令注入、模板注入、NoSQL 注入。\n"
            "5. 敏感数据：日志是否记录了 token / 密码 / 个人信息？数据库字段是否明文存储？\n"
            "6. 依赖安全：是否使用了过时版本？是否引入了已知 CVE 库？\n"
            "7. 加密与传输：密码是否使用 bcrypt/argon2？网络传输是否强制 HTTPS？\n"
            "8. 错误信息：异常堆栈是否对外暴露？错误信息是否泄露内部路径？\n\n"
            "输出风格：分点列出风险，每点包含「攻击面 / 风险描述 / 复现路径 / 修复建议 / 严重程度」。\n"
            "严重程度分级：Critical / High / Medium / Low / Info。"
        ),
    },
    {
        "name": "test_design",
        "description": "测试设计视角：边界、等价类、异常路径、覆盖率、回归策略。",
        "category": "engineering",
        "system_prompt_fragment": (
            "你正在进行测试设计。请按以下方法论系统化设计测试用例：\n"
            "1. 等价类划分：把输入域划分为若干等价类，每类取一个代表值。\n"
            "2. 边界值分析：特别关注 0/1、MIN/MAX、空字符串、None、负数、超大输入。\n"
            "3. 异常路径：所有 raise / return error 路径必须可被测试触发。\n"
            "4. 状态机：包含状态的代码（如订单/工作流）需覆盖所有合法迁移 + 至少一个非法迁移。\n"
            "5. 并发与时序：涉及锁/异步/超时的代码需覆盖竞态场景。\n"
            "6. 集成测试：除单测外，至少一个端到端用例覆盖主流程。\n"
            "7. 回归保护：每个修复 bug 的 PR 至少添加 1 个回归测试。\n\n"
            "输出格式：\n"
            "- 描述被测目标：<func/feature>\n"
            "- 覆盖维度：<等价类/边界/异常/状态/并发/集成>\n"
            "- 用例列表：每条用例写明「输入 / 前置条件 / 操作步骤 / 预期结果」\n"
            "- 优先级：P0(必跑) / P1(常规) / P2(补充)。\n\n"
            "测试设计需明确说明未覆盖的盲区与原因（如：依赖外部系统、需手工验证）。"
        ),
    },
]


def main():
    print("=" * 60)
    print("Phase 4 T3: 预置 Skill Seed")
    print("=" * 60)
    for skill in PRESET_SKILLS:
        ok = upsert_skill(
            name=skill["name"],
            description=skill["description"],
            system_prompt_fragment=skill["system_prompt_fragment"],
            category=skill["category"],
            enabled=True,
        )
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {skill['name']} (category={skill['category']})")
    print()
    print("全部预置 Skill 已写入。")


if __name__ == "__main__":
    main()
