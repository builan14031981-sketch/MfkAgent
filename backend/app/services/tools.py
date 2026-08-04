from typing import Dict, Any, List, Optional
import subprocess
import os
import json


class ToolResult:
    def __init__(self, success: bool, output: str, error: str = ""):
        self.success = success
        self.output = output
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


class Tool:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def get_definition(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class WebSearchTool(Tool):
    def __init__(self):
        super().__init__(
            name="web_search",
            description="搜索互联网获取信息（使用 GitHub API）",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        try:
            from app.core.proxy import build_httpx_client
            async with build_httpx_client() as client:
                response = await client.get(
                    "https://api.github.com/search/repositories",
                    params={"q": query, "per_page": 5},
                    timeout=10.0,
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    
                    total = data.get("total_count", 0)
                    results.append(f"找到 {total} 个相关项目:")
                    
                    for item in data.get("items", [])[:5]:
                        name = item.get("full_name", "")
                        desc = item.get("description", "无描述")
                        stars = item.get("stargazers_count", 0)
                        results.append(f"• {name} (⭐{stars}): {desc}")
                    
                    if results:
                        return ToolResult(success=True, output="\n".join(results))
                    else:
                        return ToolResult(success=True, output="未找到相关结果")
                else:
                    return ToolResult(success=False, output="", error="搜索请求失败")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class CodeExecutionTool(Tool):
    def __init__(self):
        super().__init__(
            name="execute_code",
            description="执行 Python 代码并返回结果",
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "要执行的 Python 代码",
                    },
                },
                "required": ["code"],
            },
        )

    async def execute(self, code: str = "", **kwargs) -> ToolResult:
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.getcwd(),
            )
            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout)
            else:
                return ToolResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr,
                )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="代码执行超时（30秒）")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileReadTool(Tool):
    def __init__(self):
        super().__init__(
            name="read_file",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, path: str = "", **kwargs) -> ToolResult:
        try:
            if not os.path.exists(path):
                return ToolResult(success=False, output="", error="文件不存在")
            if not os.path.isfile(path):
                return ToolResult(success=False, output="", error="不是文件")
            file_size = os.path.getsize(path)
            if file_size > 100 * 1024:
                return ToolResult(success=False, output="", error="文件过大（最大100KB）")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FileWriteTool(Tool):
    def __init__(self):
        super().__init__(
            name="write_file",
            description="写入文件内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容",
                    },
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, path: str = "", content: str = "", **kwargs) -> ToolResult:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output="文件写入成功")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirectoryTool(Tool):
    def __init__(self):
        super().__init__(
            name="list_directory",
            description="列出目录内容",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径",
                    },
                },
                "required": ["path"],
            },
        )

    async def execute(self, path: str = "", **kwargs) -> ToolResult:
        try:
            if not os.path.exists(path):
                return ToolResult(success=False, output="", error="目录不存在")
            if not os.path.isdir(path):
                return ToolResult(success=False, output="", error="不是目录")
            items = []
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    items.append(f"  {item}/")
                else:
                    size = os.path.getsize(full_path)
                    items.append(f"  {item} ({size} bytes)")
            return ToolResult(success=True, output="\n".join(items))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class FetchUrlTool(Tool):
    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="获取网页内容",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要获取的URL",
                    },
                },
                "required": ["url"],
            },
        )

    async def execute(self, url: str = "", **kwargs) -> ToolResult:
        try:
            from app.core.proxy import build_httpx_client
            async with build_httpx_client() as client:
                response = await client.get(url, timeout=10.0, follow_redirects=True)
                if response.status_code == 200:
                    content = response.text[:5000]
                    return ToolResult(success=True, output=content)
                else:
                    return ToolResult(success=False, output="", error=f"HTTP {response.status_code}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class DateTimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_datetime",
            description="获取当前日期和时间",
            parameters={
                "type": "object",
                "properties": {},
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        from datetime import datetime
        now = datetime.now()
        return ToolResult(success=True, output=now.strftime("%Y-%m-%d %H:%M:%S"))


class AddMemoryTool(Tool):
    def __init__(self):
        super().__init__(
            name="add_memory",
            description=(
                "将用户要求记住的信息持久化保存为记忆。"
                "当用户说「添加记忆：xxx」「记住xxx」「请牢记xxx」或类似意图时，必须调用本工具保存。"
                "scope 为 global 表示全局记忆（所有对话可见）；agent 表示只给当前 Agent 记住（跨项目生效）；"
                "project 表示与当前项目相关的记忆（仅当前项目会话可见）。agent/project 的目标由系统自动注入，无需填写。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["global", "agent", "project"],
                        "description": "global=全局记忆，agent=当前 Agent 专属，project=当前项目相关",
                    },
                    "content": {
                        "type": "string",
                        "description": "要记住的记忆内容",
                    },
                },
                "required": ["scope", "content"],
            },
        )

    async def execute(self, scope: str = "global", content: str = "", agent_id: str = None, project_id: int = None, **kwargs) -> ToolResult:
        try:
            from app.core.tools import add_memory as add_memory_fn
            result = add_memory_fn(scope=scope, content=content, agent_id=agent_id, project_id=project_id)
            if result.startswith("错误"):
                return ToolResult(success=False, output="", error=result)
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class JsonFormatTool(Tool):
    def __init__(self):
        super().__init__(
            name="format_json",
            description="格式化JSON字符串",
            parameters={
                "type": "object",
                "properties": {
                    "json_str": {
                        "type": "string",
                        "description": "要格式化的JSON字符串",
                    },
                },
                "required": ["json_str"],
            },
        )

    async def execute(self, json_str: str = "", **kwargs) -> ToolResult:
        try:
            import json
            data = json.loads(json_str)
            formatted = json.dumps(data, indent=2, ensure_ascii=False)
            return ToolResult(success=True, output=formatted)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        return list(self._tools.values())

    def get_definitions(self) -> List[Dict[str, Any]]:
        return [tool.get_definition() for tool in self._tools.values()]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, output="", error=f"工具 {name} 不存在")
        return await tool.execute(**kwargs)


tool_registry = ToolRegistry()

tool_registry.register(WebSearchTool())
tool_registry.register(CodeExecutionTool())
tool_registry.register(FileReadTool())
tool_registry.register(FileWriteTool())
tool_registry.register(ListDirectoryTool())
tool_registry.register(FetchUrlTool())
tool_registry.register(DateTimeTool())
tool_registry.register(JsonFormatTool())
tool_registry.register(AddMemoryTool())
