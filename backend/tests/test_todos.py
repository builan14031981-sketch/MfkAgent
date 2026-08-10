"""待办事项（Todos）功能测试 — JSON 文件存储层 + REST API + Agent Tool。

覆盖：
- todo_store JSON 存储：创建 / 查询 / 更新 / 删除 / 持久化
- /api/todos CRUD：GET（默认 pending 过滤）/ POST / PATCH / DELETE
- manage_todos 工具：list（默认 pending）/ create / update / delete / add / complete
- 严禁规则验证：标记 completed 后默认 list 不再包含该 todo
- project_id 作用域过滤
"""

import sys
import os
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _isolate_store() -> Path:
    """为当前测试类创建独立临时 JSON 文件并设为存储路径。"""
    tmp = Path(tempfile.mkdtemp(prefix="todos_test_")) / "todos.json"
    os.environ["MFKAGENT_TODOS_FILE"] = str(tmp)
    from app.core import todo_store

    todo_store._migrated_marker = True  # 测试环境跳过 SQLite 迁移
    return tmp


class TestTodoStore(unittest.TestCase):
    """todo_store JSON 文件存储层单元测试。"""

    def setUp(self):
        self.store_file = _isolate_store()
        from app.core import todo_store

        self.store = todo_store

    def tearDown(self):
        os.environ.pop("MFKAGENT_TODOS_FILE", None)
        try:
            self.store_file.unlink(missing_ok=True)
        except OSError:
            pass

    def test_create_todo(self):
        """创建待办 — 字段正确写入。"""
        todo = self.store.create_todo(title="测试待办", status="pending")
        self.assertEqual(todo["title"], "测试待办")
        self.assertEqual(todo["status"], "pending")
        self.assertTrue(todo["id"])
        self.assertTrue(todo["created_at"])
        self.assertTrue(todo["updated_at"])
        self.assertIsNone(todo["project_id"])

    def test_create_todo_with_project(self):
        """创建带 project_id 的待办。"""
        todo = self.store.create_todo(title="项目待办", status="pending", project_id=42)
        self.assertEqual(todo["project_id"], 42)

    def test_update_status(self):
        """更新状态 pending → completed。"""
        todo = self.store.create_todo(title="待完成")
        updated = self.store.update_todo(todo_id=todo["id"], status="completed")
        self.assertEqual(updated["status"], "completed")

    def test_query_pending_only(self):
        """查询过滤 — 仅返回 pending。"""
        for i in range(3):
            self.store.create_todo(title=f"待办{i}")
        done = self.store.create_todo(title="已完成", status="completed")
        self.store.update_todo(todo_id=done["id"], status="completed")

        pending = self.store.list_todos(status="pending")
        self.assertEqual(len(pending), 3)

        completed = self.store.list_todos(status="completed")
        self.assertEqual(len(completed), 1)

    def test_delete_todo(self):
        """删除待办。"""
        todo = self.store.create_todo(title="待删除")
        ok = self.store.delete_todo(todo_id=todo["id"])
        self.assertTrue(ok)
        self.assertIsNone(self.store.get_todo(todo["id"]))


class TestTodosAPI(unittest.TestCase):
    """/api/todos REST API 测试。"""

    def setUp(self):
        from fastapi import FastAPI
        from app.api.todos import router

        self.store_file = _isolate_store()

        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/todos")
        from starlette.testclient import TestClient

        self.client = TestClient(self.app)

    def tearDown(self):
        os.environ.pop("MFKAGENT_TODOS_FILE", None)
        try:
            self.store_file.unlink(missing_ok=True)
        except OSError:
            pass

    def test_create_todo(self):
        """POST /api/todos — 创建待办。"""
        resp = self.client.post("/api/todos", json={"title": "API 测试待办"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["title"], "API 测试待办")
        self.assertEqual(data["status"], "pending")
        self.assertTrue(data["id"])

    def test_list_default_pending_only(self):
        """GET /api/todos — 默认仅返回 pending。"""
        # 创建 2 个 pending + 1 个 completed
        self.client.post("/api/todos", json={"title": "待办1"})
        self.client.post("/api/todos", json={"title": "待办2"})
        resp = self.client.post("/api/todos", json={"title": "已完成", "status": "completed"})
        completed_id = resp.json()["id"]

        # 默认查询 → 仅 pending
        resp = self.client.get("/api/todos")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        for item in data:
            self.assertEqual(item["status"], "pending")

    def test_list_completed(self):
        """GET /api/todos?status=completed — 仅返回已完成。"""
        self.client.post("/api/todos", json={"title": "待办1"})
        self.client.post("/api/todos", json={"title": "已完成", "status": "completed"})

        resp = self.client.get("/api/todos?status=completed")
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "已完成")

    def test_list_all(self):
        """GET /api/todos?status=all — 返回全部。"""
        self.client.post("/api/todos", json={"title": "待办1"})
        self.client.post("/api/todos", json={"title": "已完成", "status": "completed"})

        resp = self.client.get("/api/todos?status=all")
        data = resp.json()
        self.assertEqual(len(data), 2)

    def test_update_status(self):
        """PATCH /api/todos/{id} — 标记为 completed。"""
        resp = self.client.post("/api/todos", json={"title": "待完成"})
        todo_id = resp.json()["id"]

        resp = self.client.patch(f"/api/todos/{todo_id}", json={"status": "completed"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "completed")

        # 默认 list 不再包含该 todo
        resp = self.client.get("/api/todos")
        ids = [item["id"] for item in resp.json()]
        self.assertNotIn(todo_id, ids)

    def test_update_title(self):
        """PATCH /api/todos/{id} — 更新标题。"""
        resp = self.client.post("/api/todos", json={"title": "旧标题"})
        todo_id = resp.json()["id"]

        resp = self.client.patch(f"/api/todos/{todo_id}", json={"title": "新标题"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "新标题")

    def test_delete_todo(self):
        """DELETE /api/todos/{id} — 删除待办。"""
        resp = self.client.post("/api/todos", json={"title": "待删除"})
        todo_id = resp.json()["id"]

        resp = self.client.delete(f"/api/todos/{todo_id}")
        self.assertEqual(resp.status_code, 200)

        # 确认已删除
        resp = self.client.get("/api/todos?status=all")
        ids = [item["id"] for item in resp.json()]
        self.assertNotIn(todo_id, ids)

    def test_get_404(self):
        """PATCH/DELETE 不存在的 ID → 404。"""
        resp = self.client.patch("/api/todos/nonexistent", json={"status": "completed"})
        self.assertEqual(resp.status_code, 404)

        resp = self.client.delete("/api/todos/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_create_empty_title(self):
        """POST 空标题 → 422。"""
        resp = self.client.post("/api/todos", json={"title": ""})
        self.assertEqual(resp.status_code, 422)

    def test_invalid_status(self):
        """POST 无效 status → 422。"""
        resp = self.client.post("/api/todos", json={"title": "test", "status": "invalid"})
        self.assertEqual(resp.status_code, 422)

    def test_project_filter(self):
        """GET /api/todos?project_id=1 — 按项目过滤。"""
        self.client.post("/api/todos", json={"title": "项目1待办", "project_id": 1})
        self.client.post("/api/todos", json={"title": "项目2待办", "project_id": 2})

        resp = self.client.get("/api/todos?project_id=1")
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "项目1待办")

    def test_full_lifecycle(self):
        """验收标准：创建 → 标记 completed → 默认 list 不包含。"""
        # 1. 创建
        resp = self.client.post("/api/todos", json={"title": "生命周期测试"})
        self.assertEqual(resp.status_code, 200)
        todo_id = resp.json()["id"]

        # 2. 默认 list 包含
        resp = self.client.get("/api/todos")
        ids = [item["id"] for item in resp.json()]
        self.assertIn(todo_id, ids)

        # 3. 标记 completed
        resp = self.client.patch(f"/api/todos/{todo_id}", json={"status": "completed"})
        self.assertEqual(resp.status_code, 200)

        # 4. 默认 list 不再包含
        resp = self.client.get("/api/todos")
        ids = [item["id"] for item in resp.json()]
        self.assertNotIn(todo_id, ids)

        # 5. status=all 仍可见
        resp = self.client.get("/api/todos?status=all")
        ids = [item["id"] for item in resp.json()]
        self.assertIn(todo_id, ids)


class TestManageTodosTool(unittest.TestCase):
    """manage_todos Agent Tool 测试。"""

    def setUp(self):
        self.store_file = _isolate_store()

        from app.services.tools import ManageTodosTool
        self.tool = ManageTodosTool()

    def tearDown(self):
        os.environ.pop("MFKAGENT_TODOS_FILE", None)
        try:
            self.store_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _run(self, coro):
        return asyncio.run(coro)

    def test_list_empty(self):
        """list 空待办 → 友好提示。"""
        result = self._run(self.tool.execute(action="list"))
        self.assertTrue(result.success)
        self.assertIn("没有", result.output)

    def test_create_and_list(self):
        """create → list 默认包含。"""
        result = self._run(self.tool.execute(action="create", title="工具测试待办"))
        self.assertTrue(result.success)
        self.assertIn("已创建", result.output)

        result = self._run(self.tool.execute(action="list"))
        self.assertTrue(result.success)
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "工具测试待办")
        self.assertEqual(data[0]["status"], "pending")

    def test_create_empty_title(self):
        """create 空标题 → 失败。"""
        result = self._run(self.tool.execute(action="create", title=""))
        self.assertFalse(result.success)

    def test_add_action(self):
        """action='add' → 新增待办（与 create 等价）。"""
        result = self._run(self.tool.execute(action="add", title="add 动作新增"))
        self.assertTrue(result.success)
        self.assertIn("已创建", result.output)

        result = self._run(self.tool.execute(action="list"))
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "add 动作新增")
        self.assertEqual(data[0]["status"], "pending")

    def test_complete_action(self):
        """action='complete' → 标记完成 → 默认 list 不再包含。"""
        result = self._run(self.tool.execute(action="add", title="待完成"))
        self.assertTrue(result.success)

        result = self._run(self.tool.execute(action="list"))
        data = json.loads(result.output)
        todo_id = data[0]["id"]

        result = self._run(self.tool.execute(action="complete", todo_id=todo_id))
        self.assertTrue(result.success)
        self.assertIn("已完成", result.output)

        result = self._run(self.tool.execute(action="list"))
        self.assertTrue(result.success)
        self.assertIn("没有", result.output)

        result = self._run(self.tool.execute(action="list", include_completed=True))
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "completed")

    def test_complete_nonexistent(self):
        """complete 不存在的 ID → 失败。"""
        result = self._run(self.tool.execute(action="complete", todo_id="nonexistent"))
        self.assertFalse(result.success)

    def test_complete_missing_id(self):
        """complete 缺 todo_id → 失败。"""
        result = self._run(self.tool.execute(action="complete"))
        self.assertFalse(result.success)
        self.assertIn("todo_id", result.error)

    def test_update_status(self):
        """update → 标记 completed → 默认 list 不再包含。"""
        # 创建
        result = self._run(self.tool.execute(action="create", title="待完成"))
        self.assertTrue(result.success)

        # 获取 ID
        result = self._run(self.tool.execute(action="list"))
        data = json.loads(result.output)
        todo_id = data[0]["id"]

        # 标记 completed
        result = self._run(self.tool.execute(action="update", todo_id=todo_id, status="completed"))
        self.assertTrue(result.success)
        self.assertIn("completed", result.output)

        # 默认 list 不再包含
        result = self._run(self.tool.execute(action="list"))
        self.assertTrue(result.success)
        self.assertIn("没有", result.output)

        # include_completed=true 可见
        result = self._run(self.tool.execute(action="list", include_completed=True))
        self.assertTrue(result.success)
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "completed")

    def test_delete(self):
        """delete → 删除待办。"""
        result = self._run(self.tool.execute(action="create", title="待删除"))
        self.assertTrue(result.success)

        result = self._run(self.tool.execute(action="list"))
        data = json.loads(result.output)
        todo_id = data[0]["id"]

        result = self._run(self.tool.execute(action="delete", todo_id=todo_id))
        self.assertTrue(result.success)
        self.assertIn("已删除", result.output)

        # 确认已删除
        result = self._run(self.tool.execute(action="list", include_completed=True))
        self.assertTrue(result.success)
        self.assertIn("没有", result.output)

    def test_update_nonexistent(self):
        """update 不存在的 ID → 失败。"""
        result = self._run(self.tool.execute(action="update", todo_id="nonexistent", status="completed"))
        self.assertFalse(result.success)

    def test_delete_nonexistent(self):
        """delete 不存在的 ID → 失败。"""
        result = self._run(self.tool.execute(action="delete", todo_id="nonexistent"))
        self.assertFalse(result.success)

    def test_unknown_action(self):
        """未知 action → 失败。"""
        result = self._run(self.tool.execute(action="invalid"))
        self.assertFalse(result.success)

    def test_pending_filter_strict_rule(self):
        """严禁规则：多个 pending + 多个 completed → 默认 list 仅返回 pending。"""
        for i in range(3):
            self._run(self.tool.execute(action="create", title=f"待办{i}"))
        # 手动标记 2 个为 completed
        result = self._run(self.tool.execute(action="list", include_completed=True))
        data = json.loads(result.output)
        for item in data[:2]:
            self._run(self.tool.execute(action="update", todo_id=item["id"], status="completed"))

        # 默认 list → 仅 1 个 pending
        result = self._run(self.tool.execute(action="list"))
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["status"], "pending")

        # include_completed → 3 个
        result = self._run(self.tool.execute(action="list", include_completed=True))
        data = json.loads(result.output)
        self.assertEqual(len(data), 3)

    def test_project_id_filter(self):
        """project_id 作用域过滤。"""
        self._run(self.tool.execute(action="create", title="项目1", project_id=1))
        self._run(self.tool.execute(action="create", title="项目2", project_id=2))

        result = self._run(self.tool.execute(action="list", project_id=1))
        data = json.loads(result.output)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "项目1")


class TestRiskEngineTodo(unittest.TestCase):
    """manage_todos 在风险引擎中的策略验证。"""

    def test_build_mode_allow(self):
        """Build 模式 → ALLOW。"""
        from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict
        decision = evaluate_tool("manage_todos", mode="build")
        self.assertEqual(decision.verdict, Verdict.ALLOW)

    def test_plan_mode_deny(self):
        """Plan 模式 → DENY（与 add_memory 同策略）。"""
        from app.core.tool_runtime.risk_engine import evaluate_tool, Verdict
        decision = evaluate_tool("manage_todos", mode="plan")
        self.assertEqual(decision.verdict, Verdict.DENY)

    def test_in_plan_forbidden(self):
        """manage_todos 在 PLAN_FORBIDDEN_TOOLS 中。"""
        from app.core.tool_runtime.risk_engine import PLAN_FORBIDDEN_TOOLS
        self.assertIn("manage_todos", PLAN_FORBIDDEN_TOOLS)


class TestPermissionFilterTodo(unittest.TestCase):
    """manage_todos 在权限过滤器中的可见性。"""

    def test_in_base_tools(self):
        """manage_todos 在 BASE_TOOLS 中。"""
        from app.core.tool_runtime.permission import PermissionFilter
        self.assertIn("manage_todos", PermissionFilter.BASE_TOOLS)

    def test_build_mode_visible(self):
        """Build 模式可见。"""
        from app.core.tool_runtime.permission import PermissionFilter

        class FakeChat:
            mode = "build"
            project_path = None

        tools = PermissionFilter().resolve(FakeChat())
        self.assertIn("manage_todos", tools)

    def test_plan_mode_hidden(self):
        """Plan 模式不可见。"""
        from app.core.tool_runtime.permission import PermissionFilter

        class FakeChat:
            mode = "plan"
            project_path = None

        tools = PermissionFilter().resolve(FakeChat())
        self.assertNotIn("manage_todos", tools)


class TestToolRegistryTodo(unittest.TestCase):
    """manage_todos 在工具注册表中的注册验证。"""

    def test_registered(self):
        """manage_todos 已注册。"""
        from app.services.tools import tool_registry
        tool = tool_registry.get("manage_todos")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "manage_todos")

    def test_definition_valid(self):
        """工具定义格式正确。"""
        from app.services.tools import tool_registry
        tool = tool_registry.get("manage_todos")
        defn = tool.get_definition()
        self.assertEqual(defn["function"]["name"], "manage_todos")
        self.assertIn("action", defn["function"]["parameters"]["properties"])

    def test_selector_includes(self):
        """ToolSelector 包含 manage_todos 定义。"""
        from app.core.tool_runtime.selector import ToolSelector
        selector = ToolSelector()
        self.assertIn("manage_todos", selector._def_map)


if __name__ == "__main__":
    unittest.main()
