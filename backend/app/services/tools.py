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
            description="搜索互联网获取信息",
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
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json"},
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    results = []
                    if data.get("Abstract"):
                        results.append(data["Abstract"])
                    for result in data.get("RelatedTopics", [])[:5]:
                        if isinstance(result, dict) and result.get("Text"):
                            results.append(result["Text"])
                    if results:
                        return ToolResult(success=True, output="\n\n".join(results))
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
