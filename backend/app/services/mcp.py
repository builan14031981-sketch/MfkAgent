from typing import Dict, Any, List, Optional, Callable
import json
import asyncio


class MCPResource:
    def __init__(self, uri: str, name: str, description: str = "", mime_type: str = "text/plain"):
        self.uri = uri
        self.name = name
        self.description = description
        self.mime_type = mime_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


class MCPTool:
    def __init__(self, name: str, description: str, input_schema: Dict[str, Any]):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class MCPPrompt:
    def __init__(self, name: str, description: str, arguments: List[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.arguments = arguments or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments,
        }


class MCPServer:
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.resources: Dict[str, MCPResource] = {}
        self.tools: Dict[str, MCPTool] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self.external_executors: Dict[str, Callable] = {}

    def add_resource(self, resource: MCPResource):
        self.resources[resource.uri] = resource

    def add_tool(self, tool: MCPTool):
        self.tools[tool.name] = tool

    def add_prompt(self, prompt: MCPPrompt):
        self.prompts[prompt.name] = prompt

    def get_capabilities(self) -> Dict[str, Any]:
        capabilities = {}
        if self.resources:
            capabilities["resources"] = {"listChanged": True}
        if self.tools:
            capabilities["tools"] = {"listChanged": True}
        if self.prompts:
            capabilities["prompts"] = {"listChanged": True}
        return capabilities

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        method = request.get("method")
        params = request.get("params", {})

        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "resources/list":
            return self._handle_resources_list()
        elif method == "resources/read":
            return self._handle_resources_read(params)
        elif method == "tools/list":
            return self._handle_tools_list()
        elif method == "tools/call":
            return await self._handle_tools_call(params)
        elif method == "prompts/list":
            return self._handle_prompts_list()
        elif method == "prompts/get":
            return self._handle_prompts_get(params)
        else:
            return {"error": {"code": -32601, "message": f"Method not found: {method}"}}

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": self.get_capabilities(),
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
        }

    def _handle_resources_list(self) -> Dict[str, Any]:
        return {
            "result": {
                "resources": [r.to_dict() for r in self.resources.values()]
            }
        }

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params.get("uri")
        if uri not in self.resources:
            return {"error": {"code": -32602, "message": f"Resource not found: {uri}"}}
        resource = self.resources[uri]
        return {
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": f"Resource content for {resource.name}",
                    }
                ]
            }
        }

    def _handle_tools_list(self) -> Dict[str, Any]:
        return {
            "result": {
                "tools": [t.to_dict() for t in self.tools.values()]
            }
        }

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if name not in self.tools:
            return {"error": {"code": -32602, "message": f"Tool not found: {name}"}}
        arguments = params.get("arguments", {})

        # 优先走外部插件执行器
        # 外部执行器签名：async def executor(tool_name: str, args: dict) -> Any
        if name in self.external_executors:
            try:
                executor = self.external_executors[name]
                result = await executor(name, arguments) if asyncio.iscoroutinefunction(executor) else executor(name, arguments)
                result_dict = {"status": "ok", "result": result}
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result_dict, ensure_ascii=False),
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False),
                            }
                        ],
                        "isError": True,
                    }
                }

        # 内置工具：走 executor.execute_tool 流水线
        from app.core.tool_runtime.executor import execute_tool

        tool_call = {
            "function": {"name": name, "arguments": json.dumps(arguments)},
            "id": f"mcp-{name}",
        }
        try:
            record = await execute_tool(
                tool_call=tool_call,
                project_path=None,
                read_only=False,
                ctx={},
                emit=None,
                auto_approve=False,
            )
            success = record.get("success", False)
            result_text = record.get("result", "")
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result_text,
                        }
                    ],
                    "isError": not success,
                }
            }
        except Exception as e:
            return {
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: {e}",
                        }
                    ],
                    "isError": True,
                }
            }

    def _handle_prompts_list(self) -> Dict[str, Any]:
        return {
            "result": {
                "prompts": [p.to_dict() for p in self.prompts.values()]
            }
        }

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if name not in self.prompts:
            return {"error": {"code": -32602, "message": f"Prompt not found: {name}"}}
        prompt = self.prompts[name]
        return {
            "result": {
                "description": prompt.description,
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Prompt: {prompt.name}",
                        },
                    }
                ],
            }
        }


mcp_server = MCPServer("MfkAgent", "1.0.0")

mcp_server.add_tool(
    MCPTool(
        name="web_search",
        description="搜索互联网获取信息",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
            },
            "required": ["query"],
        },
    )
)

mcp_server.add_tool(
    MCPTool(
        name="execute_code",
        description="执行 Python 代码",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python 代码"},
            },
            "required": ["code"],
        },
    )
)

mcp_server.add_resource(
    MCPResource(
        uri="mfkagent://projects",
        name="项目列表",
        description="所有项目",
        mime_type="application/json",
    )
)

mcp_server.add_prompt(
    MCPPrompt(
        name="code_review",
        description="代码审查提示词",
        arguments=[
            {"name": "code", "description": "要审查的代码", "required": True},
        ],
    )
)
