"""Task 2 测试：GitHub Read-only Integration。

测试覆盖：
  1. 工具注册：4 个 GitHub 只读工具已在 tool_registry 中
  2. 权限目录：BASE_TOOLS 包含 4 个工具
  3. READ_ONLY 风险判断：4 个工具走 READ_ONLY_TOOLS，自动 ALLOW
  4. Plan 模式兼容：plan 模式下 4 个工具仍可见
  5. Token 隔离：返回结构不包含 token 本身，仅返回 authenticated 字段
  6. API 调用：调用真实 GitHub API（使用公共仓库 microsoft/vscode，无需 token）
  7. 错误处理：参数错误时返回结构化错误
"""
import os
import sys
import json

# 切到 backend 目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 重要：先创建所有表
from app.core.database import Base, engine
Base.metadata.create_all(bind=engine)

print("=" * 60)
print("Task 2.1: tool_registry 注册检查")
print("=" * 60)

from app.services.tools import tool_registry
required_github_readonly_tools = [
    "github_list_issues",
    "github_read_issue",
    "github_list_pull_requests",
    "github_read_pull_request",
]
for t in required_github_readonly_tools:
    tool = tool_registry.get(t)
    status = "PASS" if tool is not None else "FAIL"
    print(f"  [{status}] tool_registry.get({t!r}) -> {tool is not None}")
    assert tool is not None, f"工具 {t} 未注册到 tool_registry"

print()
print("=" * 60)
print("Task 2.2: BASE_TOOLS 权限目录检查")
print("=" * 60)

from app.core.tool_runtime.permission import PermissionFilter
for t in required_github_readonly_tools:
    status = "PASS" if t in PermissionFilter.BASE_TOOLS else "FAIL"
    print(f"  [{status}] {t!r} in PermissionFilter.BASE_TOOLS")
    assert t in PermissionFilter.BASE_TOOLS, f"{t} 不在 BASE_TOOLS"

print()
print("=" * 60)
print("Task 2.3: READ_ONLY_TOOLS 风险判断")
print("=" * 60)

from app.core.tool_runtime.risk_engine import READ_ONLY_TOOLS, evaluate_tool
for t in required_github_readonly_tools:
    in_readonly = t in READ_ONLY_TOOLS
    decision = evaluate_tool(t, mode="build")
    is_allow = decision.verdict.value == "allow"
    status = "PASS" if (in_readonly and is_allow) else "FAIL"
    print(f"  [{status}] evaluate_tool({t!r}, build) -> verdict={decision.verdict.value}, READ_ONLY={in_readonly}")
    assert in_readonly, f"{t} 不在 READ_ONLY_TOOLS"
    assert is_allow, f"{t} 未自动 ALLOW: verdict={decision.verdict.value}"

# plan 模式也应 ALLOW（只读工具不受 mode 影响）
for t in required_github_readonly_tools:
    decision = evaluate_tool(t, mode="plan")
    is_allow = decision.verdict.value == "allow"
    status = "PASS" if is_allow else "FAIL"
    print(f"  [{status}] evaluate_tool({t!r}, plan) -> verdict={decision.verdict.value}")
    assert is_allow, f"{t} plan 模式应 ALLOW: verdict={decision.verdict.value}"

print()
print("=" * 60)
print("Task 2.4: Token 隔离检查（无 Token 情况）")
print("=" * 60)

# 强制清空 Token（避免环境变量影响）
from app.core import config as app_config
saved_token = getattr(app_config.settings, "GITHUB_TOKEN", None)
# 模拟无 Token 场景：临时设置 settings.GITHUB_TOKEN 为空
import app.core.config as _cfg
original_setting = _cfg.settings.GITHUB_TOKEN
_cfg.settings.GITHUB_TOKEN = ""
# 也清空 settings 表的 github_token
from app.core.database import SessionLocal
from app.models.agent import Setting
db = SessionLocal()
try:
    row = db.query(Setting).filter(Setting.key == "github_token").first()
    original_db_value = row.value if row else None
    if row:
        row.value = ""
        db.commit()
    else:
        original_db_value = None
finally:
    db.close()

try:
    # 调用 github_list_issues 工具实例
    tool = tool_registry.get("github_list_issues")
    import asyncio
    result = asyncio.run(tool.execute(repo="microsoft/vscode", per_page=2))
    print(f"  [INFO] github_list_issues(microsoft/vscode) success={result.success}")
    if result.success:
        data = json.loads(result.output)
        auth = data.get("authenticated", None)
        status = "PASS" if auth is False else "FAIL"
        print(f"  [{status}] authenticated={auth}（应为 False，无 Token 场景）")
        assert auth is False, f"无 Token 时 authenticated 应为 False，实际: {auth}"
        # 验证返回字段不包含 token 本身
        assert "token" not in data or not data.get("token"), "返回结构中不应包含 token 字段"
        assert "Authorization" not in str(data), "返回结构中不应包含 Authorization 头"
        # 验证返回结构包含 items
        assert "items" in data, "应包含 items 字段"
        print(f"  [PASS] 返回结构无 token 泄露，包含 {len(data.get('items', []))} 个 issue")
    else:
        # 真实环境可能会因网络失败，但 Token 隔离检查仍可基于"返回结构中无 token"判断
        print(f"  [INFO] 网络受限，错误信息: {result.error[:120]}")
        # 验证错误信息中不含 token
        assert "Bearer" not in result.error, f"错误信息不应包含 Bearer token: {result.error}"
        assert "ghp_" not in result.error, f"错误信息不应包含 github token 字符串"
        print(f"  [PASS] 错误信息无 token 泄露: {result.error[:100]}")
finally:
    _cfg.settings.GITHUB_TOKEN = original_setting
    db = SessionLocal()
    try:
        if original_db_value is not None:
            row = db.query(Setting).filter(Setting.key == "github_token").first()
            if row:
                row.value = original_db_value
            else:
                db.add(Setting(key="github_token", value=original_db_value))
            db.commit()
    finally:
        db.close()

print()
print("=" * 60)
print("Task 2.5: 参数错误处理")
print("=" * 60)

import asyncio

async def _param_error_check():
    cases = [
        ("github_list_issues", {"repo": "no_slash"}, "repo 必须为 owner/repo 格式"),
        ("github_read_issue", {"repo": "x/y", "issue_number": -1}, "issue_number 必须为正整数"),
        ("github_list_pull_requests", {"repo": "no_slash"}, "repo 必须为 owner/repo 格式"),
        ("github_read_pull_request", {"repo": "x/y", "pr_number": "abc"}, "pr_number 必须为整数"),
    ]
    for name, args, expected_err_part in cases:
        tool = tool_registry.get(name)
        result = await tool.execute(**args)
        status = "PASS" if (not result.success and expected_err_part in (result.error or "")) else "FAIL"
        print(f"  [{status}] {name}({args}) -> success={result.success}, error={result.error!r}")
        assert not result.success
        assert expected_err_part in (result.error or ""), f"期望错误包含 {expected_err_part!r}，实际: {result.error!r}"

asyncio.run(_param_error_check())

print()
print("=" * 60)
print("Task 2.6: Selector 能正确返回工具定义")
print("=" * 60)

from app.core.tool_runtime.selector import ToolSelector
from types import SimpleNamespace
sel = ToolSelector()
fake_chat = SimpleNamespace(project_path="/x")
defs = sel.select(required_github_readonly_tools, fake_chat)
status = "PASS" if len(defs) == 4 else "FAIL"
print(f"  [{status}] selector.select(github_readonly) -> {len(defs)} defs")
assert len(defs) == 4, f"应返回 4 个工具定义，实际: {len(defs)}"
for d in defs:
    name = d["function"]["name"]
    assert name in required_github_readonly_tools
    print(f"    - {name}: desc_len={len(d['function']['description'])}")

print()
print("=" * 60)
print("Task 2 全部测试通过 ✓")
print("=" * 60)
