"""飞书多维表格 Agent 工具集 — 供 LLM Function Calling 使用。

工具列表：
- feishu_list_bases      列出多维表格（只读）
- feishu_query_records   查询记录（只读，支持筛选/排序）
- feishu_write_records   创建/更新/删除记录（写入，action 区分）
- feishu_create_base     创建多维表格（写入）

依赖配置：.env 中的 FEISHU_APP_ID / FEISHU_APP_SECRET，或设置界面配置。
未配置时明确失败，不允许伪造成功结果。
"""
import json
import os
from typing import Any, Dict, List, Optional


class Tool:
    """与 app.services.tools.Tool 等价的轻量基类（避免循环导入）。

    二者均为纯数据结构，生成相同的 OpenAI Function Calling schema；
    执行器通过 tool_registry 按名称调用 execute，不依赖 isinstance 判断。
    """
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

    async def execute(self, **kwargs) -> "ToolResult":
        raise NotImplementedError


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


def _get_feishu_config():
    """获取飞书配置（settings），返回 (app_id, app_secret)。"""
    from app.core.config import settings as app_settings
    return (app_settings.FEISHU_APP_ID or "").strip(), (app_settings.FEISHU_APP_SECRET or "").strip()


def _build_service():
    """构造飞书服务实例（使用 settings 中的配置）。"""
    app_id, app_secret = _get_feishu_config()
    if not app_id or not app_secret:
        raise RuntimeError("未配置飞书 App ID 或 App Secret，请在飞书设置面板配置")
    from app.services.feishu import FeishuService
    return FeishuService(app_id=app_id, app_secret=app_secret)


class FeishuListBasesTool(Tool):
    """列出多维表格（只读）"""

    def __init__(self):
        super().__init__(
            name="feishu_list_bases",
            description=(
                "列出用户有权限访问的所有飞书多维表格（Base）。"
                "返回每个表格的 token / 名称 / 链接。"
                "当用户想查看有哪些多维表格、需要表格token，或不确定用哪个表时调用。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_size": {
                        "type": "integer",
                        "description": "返回条数，默认 20，最大 100",
                    },
                },
                "required": [],
            },
        )

    async def execute(self, page_size: int = 20, **kwargs) -> ToolResult:
        try:
            try:
                page_size = max(1, min(int(page_size), 100))
            except (TypeError, ValueError):
                page_size = 20
            service = _build_service()
            result = await service.list_bases(page_size=page_size)
            items = result.get("items", [])
            if not items:
                return ToolResult(success=True, output="没有找到可访问的飞书多维表格。")
            lines = []
            for it in items:
                lines.append({
                    "app_token": it.get("app_token", ""),
                    "name": it.get("name", ""),
                    "url": it.get("url", ""),
                })
            return ToolResult(success=True, output=json.dumps(lines, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"列出多维表格失败: {str(e)}")


class FeishuQueryRecordsTool(Tool):
    """查询记录（只读，支持筛选/排序）"""

    def __init__(self):
        super().__init__(
            name="feishu_query_records",
            description=(
                "查询飞书多维表格中某个数据表的记录（只读）。"
                "需要提供 base_token（表格token）和 table_id（数据表ID）。"
                "如果不知道 token/table_id，先调用 feishu_list_bases 获取 base_token，"
                "再调用 feishu_list_tables（本工具支持列出数据表）。"
                "返回记录列表及其字段内容。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "base_token": {
                        "type": "string",
                        "description": "飞书多维表格的 token（app_token），从表格URL中获取",
                    },
                    "table_id": {
                        "type": "string",
                        "description": "数据表 ID（tbl 开头），可先列数据表获取",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "返回条数，默认 20，最大 100",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["list_records", "list_tables"],
                        "description": "list_records=查记录（需 table_id）；list_tables=列出数据表（不需 table_id）",
                    },
                },
                "required": ["base_token"],
            },
        )

    async def execute(self, base_token: str = "", table_id: str = "", page_size: int = 20,
                      action: str = "list_records", **kwargs) -> ToolResult:
        try:
            if not base_token:
                return ToolResult(success=False, output="", error="base_token 不能为空")
            action = (action or "list_records").strip()
            service = _build_service()

            if action == "list_tables":
                tables = await service.list_tables(base_token)
                if not tables:
                    return ToolResult(success=True, output="该多维表格下没有数据表。")
                return ToolResult(success=True, output=json.dumps(tables, ensure_ascii=False, indent=2))

            # list_records
            if not table_id:
                # 没给 table_id，先列出数据表让用户/模型选
                tables = await service.list_tables(base_token)
                if tables:
                    brief = [{"table_id": t.get("table_id"), "name": t.get("name")} for t in tables]
                    return ToolResult(
                        success=False,
                        output="需要 table_id。该表格包含以下数据表，请选择其一后重试：\n" +
                               json.dumps(brief, ensure_ascii=False, indent=2),
                        error="缺少 table_id，请提供数据表 ID",
                    )
                return ToolResult(success=False, output="", error=f"该多维表格下没有数据表: {base_token}")

            try:
                page_size = max(1, min(int(page_size), 100))
            except (TypeError, ValueError):
                page_size = 20

            result = await service.list_records(base_token, table_id, page_size=page_size)
            items = result.get("items", [])
            if not items:
                return ToolResult(success=True, output="该数据表暂无记录。")
            return ToolResult(
                success=True,
                output=json.dumps({
                    "total": result.get("total", len(items)),
                    "has_more": result.get("has_more", False),
                    "records": items,
                }, ensure_ascii=False, indent=2),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"查询飞书记录失败: {str(e)}")


class FeishuWriteRecordsTool(Tool):
    """创建/更新/删除记录（写入，action 区分）"""

    def __init__(self):
        super().__init__(
            name="feishu_write_records",
            description=(
                "向飞书多维表格写入数据（创建/更新/删除记录）。"
                "action 区分操作类型："
                "create=新增记录（需 fields）；update=更新记录（需 records，含 record_id+fields）；"
                "delete=删除记录（需 record_ids）。"
                "需要 base_token 和 table_id。"
                "此操作会修改云端数据，执行前请与用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "base_token": {
                        "type": "string",
                        "description": "飞书多维表格的 token（app_token）",
                    },
                    "table_id": {
                        "type": "string",
                        "description": "数据表 ID（tbl 开头）",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["create", "update", "delete"],
                        "description": "create=新增记录；update=更新记录；delete=删除记录",
                    },
                    "records": {
                        "type": "array",
                        "description": "待写入的记录列表。create 时每项为 {fields:{...}}；"
                                        "update 时每项为 {record_id, fields:{...}}；delete 时忽略此参数",
                        "items": {"type": "object"},
                    },
                    "record_ids": {
                        "type": "array",
                        "description": "delete 时必填：要删除的 record_id 列表",
                        "items": {"type": "string"},
                    },
                },
                "required": ["base_token", "table_id", "action"],
            },
        )

    async def execute(self, base_token: str = "", table_id: str = "", action: str = "",
                      records: Optional[List[Dict]] = None, record_ids: Optional[List] = None,
                      **kwargs) -> ToolResult:
        try:
            if not base_token or not table_id:
                return ToolResult(success=False, output="", error="base_token 和 table_id 不能为空")
            action = (action or "").strip().lower()
            if action not in ("create", "update", "delete"):
                return ToolResult(success=False, output="", error=f"未知 action: {action}")

            service = _build_service()

            if action == "create":
                records = records or []
                if not records:
                    return ToolResult(success=False, output="", error="create 操作需要提供 records（要新增的记录）")
                # records 项转换为 fields（支持 {fields:{...}} 或直接的 {...}）
                fields_list = []
                for r in records:
                    if isinstance(r, dict):
                        if "fields" in r and isinstance(r.get("fields"), dict):
                            fields_list.append(r["fields"])
                        else:
                            fields_list.append(r)
                created = await service.create_records(base_token, table_id, fields_list)
                return ToolResult(success=True, output=json.dumps(
                    {"action": "create", "created": len(created), "records": created},
                    ensure_ascii=False, indent=2))

            elif action == "update":
                records = records or []
                if not records:
                    return ToolResult(success=False, output="", error="update 操作需要提供 records（含 record_id 和 fields）")
                updates = []
                for r in records:
                    if isinstance(r, dict) and "record_id" in r and "fields" in r:
                        updates.append({"record_id": r["record_id"], "fields": r["fields"]})
                if not updates:
                    return ToolResult(success=False, output="", error="update 记录格式错误：每项需含 record_id 和 fields")
                updated = await service.update_records(base_token, table_id, updates)
                return ToolResult(success=True, output=json.dumps(
                    {"action": "update", "updated": len(updated), "records": updated},
                    ensure_ascii=False, indent=2))

            else:  # delete
                record_ids = record_ids or []
                if not record_ids:
                    return ToolResult(success=False, output="", error="delete 操作需要提供 record_ids（要删除的记录ID）")
                ids = [str(x) for x in record_ids if x]
                if not ids:
                    return ToolResult(success=False, output="", error="record_ids 为空")
                result = await service.delete_records(base_token, table_id, ids)
                return ToolResult(success=True, output=json.dumps(
                    {"action": "delete", **result}, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"飞书写入失败: {str(e)}")


class FeishuCreateBaseTool(Tool):
    """创建多维表格（写入）"""

    def __init__(self):
        super().__init__(
            name="feishu_create_base",
            description=(
                "创建新的飞书多维表格（Base），可同时指定名称。"
                "创建成功后返回新表格的 token 和链接。"
                "默认创建一个空表格（默认 schema）。"
                "此操作会创建云上资源，执行前请与用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "多维表格名称",
                    },
                },
                "required": ["name"],
            },
        )

    async def execute(self, name: str = "", **kwargs) -> ToolResult:
        try:
            if not name or not name.strip():
                return ToolResult(success=False, output="", error="name 不能为空")
            service = _build_service()
            base = await service.create_base(name=name.strip())
            if not base:
                return ToolResult(success=False, output="", error="创建失败，未返回表格信息")
            return ToolResult(success=True, output=json.dumps(base, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"创建多维表格失败: {str(e)}")


# ──── IM 消息工具（P1：发文本 / 图片 / 文件 到群或用户）────

def _resolve_media_bytes(source: str) -> bytes:
    """解析图片/文件来源为字节流。

    支持：
      - 本地绝对路径（直接读取）
      - http(s) URL（下载）
      - /api/chat/... 站内代理路径（拼本机 API Base 下载）
    """
    import httpx
    s = (source or "").strip()
    if not s:
        raise RuntimeError("media 参数为空")
    if s.startswith(("/api/", "api/")):
        base = os.environ.get("API_BASE", "http://127.0.0.1:8001").rstrip("/")
        path = s if s.startswith("/") else f"/{s}"
        resp = httpx.get(f"{base}{path}", timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    if s.startswith(("http://", "https://")):
        resp = httpx.get(s, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    p = os.path.abspath(os.path.expanduser(s))
    if not os.path.isfile(p):
        raise RuntimeError(f"文件不存在: {s}")
    with open(p, "rb") as f:
        return f.read()


class FeishuSendMessageTool(Tool):
    """发送文本消息到飞书群/用户（P1）"""

    def __init__(self):
        super().__init__(
            name="feishu_send_message",
            description=(
                "向飞书群聊或用户发送一条文本消息。"
                "receive_id 为目标群或用户的 ID（优先从 feishu_list_chats 获取群 chat_id）；"
                "receive_id_type 默认 chat_id。发送前请与用户确认内容与目标。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "receive_id": {
                        "type": "string",
                        "description": "接收方 ID（群 chat_id / 用户 open_id 等）",
                    },
                    "text": {
                        "type": "string",
                        "description": "要发送的文本内容",
                    },
                    "receive_id_type": {
                        "type": "string",
                        "enum": ["chat_id", "open_id", "user_id", "email"],
                        "description": "receive_id 的类型，默认 chat_id",
                    },
                },
                "required": ["receive_id", "text"],
            },
        )

    async def execute(self, receive_id: str, text: str = "", receive_id_type: str = "chat_id", **kwargs) -> ToolResult:
        try:
            if not receive_id or not receive_id.strip():
                return ToolResult(success=False, output="", error="receive_id 不能为空")
            if not text or not text.strip():
                return ToolResult(success=False, output="", error="text 不能为空")
            service = _build_service()
            result = await service.send_text(receive_id.strip(), text.strip(), receive_id_type=receive_id_type or "chat_id")
            msg_id = (result or {}).get("message_id", "")
            return ToolResult(success=True, output=json.dumps({
                "success": True,
                "message_id": msg_id,
                "receive_id": receive_id.strip(),
                "receive_id_type": receive_id_type or "chat_id",
                "text": text.strip()[:120],
            }, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"飞书发送消息失败: {str(e)}")


class FeishuSendImageTool(Tool):
    """发送图片到飞书群/用户（P1，可复用文生图产物）"""

    def __init__(self):
        super().__init__(
            name="feishu_send_image",
            description=(
                "向飞书群聊或用户发送一张图片消息。"
                "image 可以是本地绝对路径、http(s) URL、或 /api/chat/... 站内图片地址；"
                "配合 generate_image 生成的图片使用效果最佳。发送前请与用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "receive_id": {
                        "type": "string",
                        "description": "接收方 ID（群 chat_id / 用户 open_id 等）",
                    },
                    "image": {
                        "type": "string",
                        "description": "图片来源：本地路径 / URL / /api/chat/... 站内图片地址",
                    },
                    "receive_id_type": {
                        "type": "string",
                        "enum": ["chat_id", "open_id", "user_id", "email"],
                        "description": "receive_id 的类型，默认 chat_id",
                    },
                },
                "required": ["receive_id", "image"],
            },
        )

    async def execute(self, receive_id: str, image: str = "", receive_id_type: str = "chat_id", **kwargs) -> ToolResult:
        try:
            if not receive_id or not receive_id.strip():
                return ToolResult(success=False, output="", error="receive_id 不能为空")
            data = _resolve_media_bytes(image)
            filename = os.path.basename(image.split("?")[0]) if image else "image.png"
            service = _build_service()
            result = await service.send_image(receive_id.strip(), data, filename=filename or "image.png",
                                              receive_id_type=receive_id_type or "chat_id")
            msg_id = (result or {}).get("message_id", "")
            return ToolResult(success=True, output=json.dumps({
                "success": True,
                "message_id": msg_id,
                "receive_id": receive_id.strip(),
                "receive_id_type": receive_id_type or "chat_id",
                "image": str(image)[:160],
                "bytes": len(data),
            }, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"飞书发送图片失败: {str(e)}")


class FeishuSendFileTool(Tool):
    """发送文件到飞书群/用户（P1）"""

    def __init__(self):
        super().__init__(
            name="feishu_send_file",
            description=(
                "向飞书群聊或用户发送一个文件消息。"
                "file_path 为本地文件绝对路径（需在项目沙箱内）或 URL。发送前请与用户确认。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "receive_id": {
                        "type": "string",
                        "description": "接收方 ID（群 chat_id / 用户 open_id 等）",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "文件来源：本地绝对路径或 URL",
                    },
                    "receive_id_type": {
                        "type": "string",
                        "enum": ["chat_id", "open_id", "user_id", "email"],
                        "description": "receive_id 的类型，默认 chat_id",
                    },
                },
                "required": ["receive_id", "file_path"],
            },
        )

    async def execute(self, receive_id: str, file_path: str = "", receive_id_type: str = "chat_id", **kwargs) -> ToolResult:
        try:
            if not receive_id or not receive_id.strip():
                return ToolResult(success=False, output="", error="receive_id 不能为空")
            data = _resolve_media_bytes(file_path)
            filename = os.path.basename(file_path.split("?")[0]) if file_path else "file.bin"
            service = _build_service()
            result = await service.send_file(receive_id.strip(), data, filename=filename or "file.bin",
                                             receive_id_type=receive_id_type or "chat_id")
            msg_id = (result or {}).get("message_id", "")
            return ToolResult(success=True, output=json.dumps({
                "success": True,
                "message_id": msg_id,
                "receive_id": receive_id.strip(),
                "receive_id_type": receive_id_type or "chat_id",
                "file": str(file_path)[:160],
                "bytes": len(data),
            }, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"飞书发送文件失败: {str(e)}")


class FeishuListChatsTool(Tool):
    """列出机器人所在群聊（只读，供发送消息时确定 receive_id）"""

    def __init__(self):
        super().__init__(
            name="feishu_list_chats",
            description=(
                "列出当前飞书机器人所在的所有群聊，返回每个群的 chat_id 和名称。"
                "当用户要求向飞书群发送消息但未指明群 ID 时，先调用本工具找到目标群。"
            ),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        try:
            service = _build_service()
            result = await service.list_chats(page_size=50)
            items = result.get("items", [])
            slim = [
                {"chat_id": it.get("chat_id", ""), "name": it.get("name", ""),
                 "description": it.get("description", "") or ""}
                for it in items
            ]
            if not slim:
                return ToolResult(success=False, output="", error="机器人未加入任何群聊，请先在飞书中将机器人拉入群")
            return ToolResult(success=True, output=json.dumps(slim, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"列出飞书群聊失败: {str(e)}")