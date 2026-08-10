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


class GitHubSearchTool(Tool):
    """GitHub 仓库搜索：仅搜索 GitHub 代码仓库，不搜索互联网网页。"""

    def __init__(self):
        super().__init__(
            name="github_search",
            description=(
                "搜索 GitHub 开源代码仓库（仅限代码仓库搜索，不搜索互联网网页）。"
                "当用户需要查找开源项目、代码库、某个功能的现成实现时使用；"
                "普通网页/资讯/社区讨论请使用 web_search。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（用于搜索 GitHub 仓库，支持语言过滤如 'python agent'）",
                    },
                },
                "required": ["query"],
            },
        )

    async def execute(self, query: str = "", **kwargs) -> ToolResult:
        import asyncio
        import httpx
        try:
            from app.core.proxy import build_httpx_client, resolve_proxy
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MfkAgent/1.0",
            }
            params = {"q": query, "per_page": 5}
            last_error = ""

            # 优先走系统代理；代理 TLS 偶发失败时回退直连
            client_factories = []
            if resolve_proxy():
                client_factories.append(lambda: build_httpx_client(timeout=15.0))
            client_factories.append(lambda: httpx.AsyncClient(timeout=15.0))

            for factory in client_factories:
                for attempt in range(2):
                    try:
                        async with factory() as client:
                            response = await client.get(
                                "https://api.github.com/search/repositories",
                                params=params,
                                timeout=15.0,
                                headers=headers,
                            )
                            if response.status_code == 200:
                                data = response.json()
                                results = []

                                total = data.get("total_count", 0)
                                results.append(f"找到 {total} 个相关 GitHub 项目:")

                                for item in data.get("items", [])[:5]:
                                    name = item.get("full_name", "")
                                    desc = item.get("description", "无描述")
                                    stars = item.get("stargazers_count", 0)
                                    results.append(f"• {name} (⭐{stars}): {desc}")

                                if results:
                                    return ToolResult(success=True, output="\n".join(results))
                                else:
                                    return ToolResult(success=True, output="未找到相关 GitHub 项目")
                            else:
                                last_error = f"GitHub API 请求失败（{response.status_code}）"
                    except Exception as e:
                        last_error = f"搜索失败: {str(e)}"
                    if attempt < 1:
                        await asyncio.sleep(1)

            return ToolResult(success=False, output="", error=last_error or "搜索失败")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {str(e)}")


class WebSearchTool(Tool):
    """通用网页搜索：Baidu 主引擎 + DuckDuckGo 兜底，支持中文，返回结构化网页结果。"""

    def __init__(self):
        super().__init__(
            name="web_search",
            description=(
                "搜索互联网网页（通用网页搜索，支持中文）。"
                "返回结构化结果列表：title / url / snippet。"
                "当用户需要查资讯、社区讨论、百科、新闻、产品资料等真实网页信息时使用；"
                "查找开源代码仓库请用 github_search。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词（支持中文，例如：火影忍者手游 玩家 社区）",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果条数，默认 5，最大 10",
                    },
                },
                "required": ["query"],
            },
        )

    @staticmethod
    def _extract_text(html: str) -> str:
        """用 HTMLParser 提取可见文本，跳过 script/style，忽略属性噪声。"""
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.parts = []
                self.skip = 0

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style"):
                    self.skip += 1

            def handle_endtag(self, tag):
                if tag in ("script", "style") and self.skip:
                    self.skip -= 1

            def handle_data(self, data):
                if not self.skip:
                    t = data.strip()
                    if t:
                        self.parts.append(t)

        p = TextExtractor()
        p.feed(html)
        return " ".join(p.parts)

    @staticmethod
    def _clean_text(raw: str) -> str:
        return WebSearchTool._extract_text(raw)

    async def _search_baidu(self, query: str, max_results: int) -> list:
        from app.core.proxy import build_httpx_client
        import re as _re
        # Baidu 对缺少浏览器头（Accept/Accept-Language）的请求返回 302 验证码重定向
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.baidu.com/",
        }
        results: list = []
        async with build_httpx_client(timeout=20.0, headers=headers) as client:
            response = await client.get(
                "https://www.baidu.com/s",
                params={"wd": query},
                timeout=20.0,
                headers=headers,
                follow_redirects=False,
            )
            if response.status_code not in (200, 301, 302):
                raise RuntimeError(f"Baidu 搜索请求失败（HTTP {response.status_code}）")
            if response.status_code in (301, 302) or "<h3" not in response.text:
                # 兜底：跟随重定向再试一次
                redirect_url = _re.search(r'href="([^"]+)"', response.text)
                if redirect_url and "captcha" not in redirect_url.group(1):
                    response = await client.get(
                        "https://www.baidu.com/s",
                        params={"wd": query},
                        timeout=20.0,
                        headers=headers,
                        follow_redirects=True,
                    )
            if response.status_code != 200 or "<h3" not in response.text:
                raise RuntimeError("Baidu 触发安全验证，无法获取结果")
            html = response.text
            parts = html.split("<h3")[1:]
            for part in parts[: max_results * 2]:
                am = _re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', part, _re.S)
                if not am:
                    continue
                url = am.group(1)
                if url.startswith("javascript"):
                    continue
                title = self._clean_text(am.group(2))
                if not title:
                    continue
                # 摘要：取 h3 结束后的块内文本，去掉标题前缀
                after = part[part.find("</h3"):]
                snippet = self._clean_text(after)
                if snippet.startswith(title):
                    snippet = snippet[len(title):].strip()
                results.append({
                    "title": title[:150],
                    "url": url[:300],
                    "snippet": snippet[:300],
                })
                if len(results) >= max_results:
                    break
        return results

    async def _search_duckduckgo(self, query: str, max_results: int) -> list:
        from app.core.proxy import build_httpx_client
        import re as _re
        from urllib.parse import urlparse, urljoin, unquote
        results: list = []
        async with build_httpx_client(timeout=20.0) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query, "kl": "cn-zh"},
                timeout=20.0,
                follow_redirects=True,
            )
            if response.status_code != 200:
                raise RuntimeError(f"DuckDuckGo 搜索请求失败（HTTP {response.status_code}）")
            html = response.text
            blocks = _re.split(r'<div class="result results_links', html)[1:]
            for block in blocks[:max_results * 2]:
                title_m = _re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, _re.S)
                if not title_m:
                    continue
                raw_url = title_m.group(1)
                uddg = _re.search(r"uddg=([^&]+)", raw_url)
                if uddg:
                    final_url = unquote(uddg.group(1))
                else:
                    final_url = urljoin("https://html.duckduckgo.com/", raw_url)
                parsed = urlparse(final_url)
                if not parsed.scheme:
                    final_url = "https://" + final_url
                title = self._clean_text(title_m.group(2))
                snippet_m = _re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, _re.S)
                snippet = self._clean_text(snippet_m.group(1)) if snippet_m else ""
                results.append({
                    "title": title[:150],
                    "url": final_url[:300],
                    "snippet": snippet[:300],
                })
                if len(results) >= max_results:
                    break
        return results

    async def execute(self, query: str = "", max_results: int = 5, **kwargs) -> ToolResult:
        import json as _json
        try:
            if not query or not query.strip():
                return ToolResult(success=False, output="", error="搜索关键词不能为空")

            try:
                max_results = max(1, min(int(max_results), 10))
            except (TypeError, ValueError):
                max_results = 5

            last_error = ""
            # 主引擎：Baidu（中文结果质量高、国内可达）
            try:
                results = await self._search_baidu(query, max_results)
                if results:
                    return ToolResult(
                        success=True,
                        output=_json.dumps(results, ensure_ascii=False, indent=2),
                    )
                last_error = "Baidu 无结果"
            except Exception as e:
                last_error = f"Baidu 失败: {str(e)}"

            # 兜底引擎：DuckDuckGo
            try:
                results = await self._search_duckduckgo(query, max_results)
                if results:
                    return ToolResult(
                        success=True,
                        output=_json.dumps(results, ensure_ascii=False, indent=2),
                    )
                last_error += "；DuckDuckGo 无结果"
            except Exception as e:
                last_error += f"；DuckDuckGo 失败: {str(e)}"

            return ToolResult(
                success=False,
                output="",
                error=f"搜索失败: {last_error}（可尝试更换关键词或使用 fetch_url 直接访问已知网址）",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"搜索失败: {str(e)}")


class FetchUrlTool(Tool):
    def __init__(self):
        super().__init__(
            name="fetch_url",
            description="获取网页纯文本内容（仅支持静态页面，不支持 JavaScript 渲染，超时 15 秒）",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要获取的 URL（必须以 http:// 或 https:// 开头）",
                    },
                },
                "required": ["url"],
            },
        )

    async def execute(self, url: str = "", **kwargs) -> ToolResult:
        try:
            if not url.startswith(("http://", "https://")):
                return ToolResult(success=False, output="", error="URL 必须以 http:// 或 https:// 开头")
            from app.core.proxy import build_httpx_client
            async with build_httpx_client(timeout=15.0) as client:
                response = await client.get(url, timeout=15.0, follow_redirects=True)
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


class ManageTodosTool(Tool):
    """待办事项管理工具 — 供 LLM 通过 Tool Calling 管理用户待办。

    支持 action: list / create / update / delete。
    【严禁规则】list 默认仅返回 status='pending'，除非 include_completed=true。
    """

    def __init__(self):
        super().__init__(
            name="manage_todos",
            description=(
                "管理用户的待办事项（笔记本/待办清单）。"
                "action=list：读取待办列表（默认仅返回未完成项）；"
                "action=add：新增待办（需提供 title）；"
                "action=complete：完成待办（需提供 todo_id）；"
                "action=create：新增待办（add 的别名，需提供 title）；"
                "action=update：更新待办状态或标题（需提供 todo_id）；"
                "action=delete：删除待办（需提供 todo_id）。"
                "当用户说「查看待办」「记到笔记本」「添加待办」「完成待办」等意图时调用本工具。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "add", "complete", "create", "update", "delete"],
                        "description": "操作类型：list=读取列表, add/create=新增, complete=标记完成, update=更新, delete=删除",
                    },
                    "title": {
                        "type": "string",
                        "description": "待办标题（add/create 时必填，update 时可选）",
                    },
                    "todo_id": {
                        "type": "string",
                        "description": "待办 ID（complete/update/delete 时必填）",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "completed"],
                        "description": "目标状态（update 时可选）",
                    },
                    "include_completed": {
                        "type": "boolean",
                        "description": "list 时是否包含已完成的待办（默认 false，仅返回未完成）",
                    },
                },
                "required": ["action"],
            },
        )

    async def execute(self, action: str = "list", title: str = "", todo_id: str = "",
                      status: str = "", include_completed: bool = False,
                      project_id: int = None, **kwargs) -> ToolResult:
        import json as _json
        from app.core import todo_store

        try:
            if action == "list":
                # 【严禁规则】默认仅返回 pending，除非用户明确要求查看已完成
                status_filter = "all" if include_completed else "pending"
                todos = todo_store.list_todos(status=status_filter, project_id=project_id)
                result = [
                    {"id": t["id"], "title": t["title"], "status": t["status"],
                     "project_id": t.get("project_id"),
                     "created_at": t.get("created_at", "")}
                    for t in todos
                ]
                if not result:
                    return ToolResult(success=True, output="当前没有未完成的待办事项。")
                return ToolResult(success=True, output=_json.dumps(result, ensure_ascii=False))

            elif action in ("add", "create"):
                if not title or not title.strip():
                    return ToolResult(success=False, output="", error="title 不能为空")
                new_todo = todo_store.create_todo(title=title, project_id=project_id, status="pending")
                return ToolResult(success=True, output=f"已创建待办: {new_todo['title']} (id: {new_todo['id']})")

            elif action == "complete":
                if not todo_id:
                    return ToolResult(success=False, output="", error="todo_id 不能为空")
                todo = todo_store.update_todo(todo_id=todo_id, status="completed")
                if todo is None:
                    return ToolResult(success=False, output="", error=f"待办 {todo_id} 不存在")
                return ToolResult(success=True, output=f"已完成待办: {todo['title']}")

            elif action == "update":
                if not todo_id:
                    return ToolResult(success=False, output="", error="todo_id 不能为空")
                todo = todo_store.update_todo(todo_id=todo_id, title=title or None,
                                              status=status if status in ("pending", "completed") else None)
                if todo is None:
                    return ToolResult(success=False, output="", error=f"待办 {todo_id} 不存在")
                return ToolResult(success=True, output=f"已更新待办: {todo['title']} → 状态: {todo['status']}")

            elif action == "delete":
                if not todo_id:
                    return ToolResult(success=False, output="", error="todo_id 不能为空")
                todo = todo_store.get_todo(todo_id)
                if todo is None:
                    return ToolResult(success=False, output="", error=f"待办 {todo_id} 不存在")
                todo_store.delete_todo(todo_id)
                return ToolResult(success=True, output=f"已删除待办: {todo['title']}")

            else:
                return ToolResult(success=False, output="", error=f"未知 action: {action}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


tool_registry = ToolRegistry()

# 注册安全工具（所有工具都有明确的用途和限制）
tool_registry.register(GitHubSearchTool())       # GitHub 仓库搜索
tool_registry.register(WebSearchTool())          # 通用网页搜索（DuckDuckGo）
tool_registry.register(FetchUrlTool())           # 获取网页内容（有超时限制）
tool_registry.register(DateTimeTool())           # 获取当前时间
tool_registry.register(JsonFormatTool())         # 格式化 JSON
tool_registry.register(AddMemoryTool())          # 保存记忆
tool_registry.register(ManageTodosTool())        # 待办事项管理

# 注意：文件操作工具（read_file/write_file/list_files）已在 core/tools.py 中实现
# 带有沙箱保护，只在有 project_path 时通过 FILE_TOOLS_DEFINITIONS 提供
# 不在 tool_registry 中重复注册，避免安全隐患
