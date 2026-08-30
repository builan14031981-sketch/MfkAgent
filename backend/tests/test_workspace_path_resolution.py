# -*- coding: utf-8 -*-
"""workspace 路径感知解析 + 工具分级 单元测试（2026-08-11 新增）。

覆盖：
- extract_path_candidates：引号包裹 / 裸盘符 / UNC / POSIX / 无路径
- extract_workspace_path：文件→父目录 / 目录 / 不存在→None
- is_file_operation_request：扩展触发词（修改/修复/删除/查看）
- NO_PATH_TOOLS：与 PermissionFilter 无路径结果一致
"""
import os
from types import SimpleNamespace

from app.core.workspace import (
    extract_path_candidates,
    extract_workspace_path,
    is_file_operation_request,
)
from app.core.tool_runtime.permission import PermissionFilter, NO_PATH_TOOLS


class TestExtractPathCandidates:
    def test_quoted_windows_path(self):
        msg = "帮我修改一下 `e:\\智慧项目\\Mfkagent\\backend\\app\\api\\chat.py` 这个文件"
        cands = extract_path_candidates(msg)
        assert cands, "应提取到引号包裹的路径"
        assert cands[0] == "e:\\智慧项目\\Mfkagent\\backend\\app\\api\\chat.py"

    def test_bare_drive_path(self):
        cands = extract_path_candidates("e:\\智慧项目\\Mfkagent\\backend 这个路径里面有什么")
        assert cands and cands[0].startswith("e:\\")

    def test_posix_path(self):
        cands = extract_path_candidates("请分析 /home/user/project/main.py 这个文件")
        assert cands and "/home/user/project/main.py" in cands[0]

    def test_no_path(self):
        assert extract_path_candidates("你好呀今天天气不错") == []
        assert extract_path_candidates("") == []

    def test_unc_path(self):
        cands = extract_path_candidates("看看 \\\\server\\share\\docs\\readme.md 的内容")
        assert cands and cands[0].startswith("\\\\server\\")


class TestExtractWorkspacePath:
    def test_file_path_returns_parent_dir(self):
        # backend/main.py 为存在的文件 → 返回其父目录
        target = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
        ws = extract_workspace_path(f"帮我改一下 `{target}`")
        assert ws is not None
        assert os.path.isdir(ws)
        assert os.path.dirname(target) == ws

    def test_dir_path_returns_itself(self):
        target = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ws = extract_workspace_path(f"{target} 里面有什么")
        assert ws == target

    def test_nonexistent_path_returns_none(self):
        assert extract_workspace_path("e:\\不存在的路径\\abc") is None

    def test_no_path_returns_none(self):
        assert extract_workspace_path("你好呀") is None


class TestFileOperationRequest:
    def test_extended_triggers(self):
        assert is_file_operation_request("你帮我去修改一下这个文件")
        assert is_file_operation_request("帮我修复一下代码")
        assert is_file_operation_request("看一下这个目录")
        assert is_file_operation_request("新建一个文件")
        assert not is_file_operation_request("今天天气怎么样")


class TestNoPathTools:
    def test_no_path_tools_consistent_with_permission(self):
        """NO_PATH_TOOLS 应等于 PermissionFilter 在无路径时返回的工具集合"""
        chat = SimpleNamespace(mode="build", project_path=None, agent_id="general", project_id=None)
        resolved = set(PermissionFilter().resolve(chat))
        # NO_PATH_TOOLS 是模块级可变 set：外部 MCP 测试（test_mcp_external_tools）注册工具时
        # 会原地 add（permission.py:141 注释），使全局常量带上会话无关的外部工具；而 resolve()
        # 对本测试的 SimpleNamespace chat（无冻结清单）不返回这些外部工具。故此处以纯净定义
        # （BASE_TOOLS - _project_only_tools）校验一致性，避免受其他测试全局副作用污染。
        pure_no_path = {
            t for t in PermissionFilter.BASE_TOOLS if t not in PermissionFilter._project_only_tools
        }
        assert resolved == pure_no_path, (
            f"PermissionFilter 无路径结果与纯净 NO_PATH_TOOLS 定义不一致\n"
            f"diff: {resolved ^ pure_no_path}"
        )

    def test_no_path_tools_contains_add_memory(self):
        assert "add_memory" in NO_PATH_TOOLS
        assert "manage_todos" in NO_PATH_TOOLS
        assert "web_search" in NO_PATH_TOOLS

    def test_no_path_tools_excludes_project_tools(self):
        # NO_PATH_TOOLS 语义 = 无 project_path 会话保留可见的工具集
        # （permission.py:143 = BASE_TOOLS 中不属于 _project_only_tools 者）。
        # read_file 为只读文件工具，全局可用（permission.py:91 注释），无路径会话仍保留；
        # write_file / git_status 等 project_only 工具被排除。
        assert "read_file" in NO_PATH_TOOLS, "read_file 为全局只读工具，无路径会话应保留"
        assert "write_file" not in NO_PATH_TOOLS
        assert "git_status" not in NO_PATH_TOOLS
