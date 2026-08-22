"""飞书集成 API 接口。

提供飞书配置管理、连接测试、多维表格操作等 RESTful 接口。
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import os

from app.core.config import settings
from app.services.feishu import get_feishu_service, reset_feishu_service, FeishuError

logger = logging.getLogger(__name__)

router = APIRouter()


# ──── 请求/响应模型 ────

class FeishuConfigInput(BaseModel):
    app_id: str
    app_secret: str


class FeishuConfigResponse(BaseModel):
    app_id: str
    has_secret: bool  # 不返回完整 secret，只返回是否已配置


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    token_valid: bool
    has_bases: bool = False


class BaseInfo(BaseModel):
    app_token: str
    name: str
    url: str
    revision: int = -1


class BasesListResponse(BaseModel):
    items: List[BaseInfo]
    has_more: bool
    page_token: str = ""
    total: int


class RecordItem(BaseModel):
    record_id: str
    fields: Dict[str, Any]


class RecordsListResponse(BaseModel):
    items: List[RecordItem]
    has_more: bool
    page_token: str = ""
    total: int


class CreateRecordsInput(BaseModel):
    records: List[Dict[str, Any]]


class UpdateRecordsInput(BaseModel):
    records: List[Dict[str, Any]]


class DeleteRecordsInput(BaseModel):
    record_ids: List[str]


class CreateBaseInput(BaseModel):
    name: str
    folder_token: str = ""


# ──── IM 消息请求模型（P1）────

class SendMessageInput(BaseModel):
    receive_id: str
    text: str
    receive_id_type: str = "chat_id"


class SendImageInput(BaseModel):
    receive_id: str
    image: str
    receive_id_type: str = "chat_id"


class SendFileInput(BaseModel):
    receive_id: str
    file_path: str
    receive_id_type: str = "chat_id"


# ──── 辅助函数 ────

def _get_feishu_service_with_config():
    """获取飞书服务实例（优先使用 settings 中的配置）"""
    app_id = settings.FEISHU_APP_ID
    app_secret = settings.FEISHU_APP_SECRET
    
    if not app_id or not app_secret:
        raise HTTPException(
            status_code=400,
            detail="未配置飞书 App ID 或 App Secret，请先在设置中配置"
        )
    
    return get_feishu_service(app_id=app_id, app_secret=app_secret)


# ──── 配置管理接口 ────

@router.get("/config", response_model=FeishuConfigResponse)
async def get_config():
    """获取当前飞书配置（不返回完整 secret）"""
    return FeishuConfigResponse(
        app_id=settings.FEISHU_APP_ID,
        has_secret=bool(settings.FEISHU_APP_SECRET),
    )


@router.post("/config")
async def save_config(config: FeishuConfigInput):
    """保存飞书配置（写入 .env 文件）。

    健壮性约定：
      - App ID 留空则忽略，不清空（前端"只改一个"时不影响另一个）。
      - App Secret 留空则保留旧值（避免用户只改 App ID 时把 Secret 清掉）。
      - .env 路径统一锚定 BACKEND_DIR，与 config.py 读取位置一致。
    """
    from app.core.config import BACKEND_DIR

    # 确定有效配置：留空的字段回退到当前内存值（不覆盖已配置项）
    new_app_id = (config.app_id or "").strip()
    new_secret = (config.app_secret or "").strip()

    old_app_id = (settings.FEISHU_APP_ID or "").strip()
    old_secret = (settings.FEISHU_APP_SECRET or "").strip()

    eff_app_id = new_app_id or old_app_id
    eff_secret = new_secret or old_secret

    # 更新内存（仅当有有效值时）
    if eff_app_id:
        settings.FEISHU_APP_ID = eff_app_id
    if eff_secret:
        settings.FEISHU_APP_SECRET = eff_secret

    # 写入 .env 文件（持久化）
    env_path = BACKEND_DIR / ".env"
    env_lines = []
    if env_path.exists():
        env_lines = env_path.read_text(encoding="utf-8").splitlines()

    # 更新或添加配置项（保留已存在但本次未提交的一定要写回旧值，绝不写空）
    remaining = {"FEISHU_APP_ID": eff_app_id, "FEISHU_APP_SECRET": eff_secret}
    new_lines = []
    for line in env_lines:
        if line.startswith("FEISHU_APP_ID="):
            new_lines.append(f"FEISHU_APP_ID={remaining['FEISHU_APP_ID']}")
            remaining.pop("FEISHU_APP_ID", None)
        elif line.startswith("FEISHU_APP_SECRET="):
            new_lines.append(f"FEISHU_APP_SECRET={remaining['FEISHU_APP_SECRET']}")
            remaining.pop("FEISHU_APP_SECRET", None)
        else:
            new_lines.append(line)

    # 文件里原本不存在的项，追加（仅在有效值非空时追加）
    for key, value in remaining.items():
        if value:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # 重置飞书服务实例（下次调用时使用新配置）
    reset_feishu_service()

    logger.info("飞书配置已更新")
    return {"message": "配置已保存", "app_id": eff_app_id}


@router.post("/test", response_model=TestConnectionResponse)
async def test_connection():
    """测试飞书连接"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.test_connection()
        return TestConnectionResponse(**result)
    except HTTPException:
        raise
    except FeishuError as e:
        return TestConnectionResponse(
            success=False,
            message=f"连接失败: {str(e)}",
            token_valid=False,
        )
    except Exception as e:
        logger.exception("测试连接失败")
        return TestConnectionResponse(
            success=False,
            message=f"未知错误: {str(e)}",
            token_valid=False,
        )


# ──── 多维表格操作接口 ────

@router.get("/bases", response_model=BasesListResponse)
async def list_bases(page_size: int = 20, page_token: str = ""):
    """列出用户有权限的多维表格"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.list_bases(page_size=page_size, page_token=page_token)
        
        items = []
        for item in result.get("items", []):
            items.append(BaseInfo(
                app_token=item.get("app_token", ""),
                name=item.get("name", ""),
                url=item.get("url", ""),
                revision=item.get("revision", -1),
            ))
        
        return BasesListResponse(
            items=items,
            has_more=result.get("has_more", False),
            page_token=result.get("page_token", ""),
            total=result.get("total", 0),
        )
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("列出多维表格失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/bases/{base_token}")
async def get_base(base_token: str):
    """获取多维表格详情"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.get_base(base_token)
        return result
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("获取多维表格详情失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/bases")
async def create_base(input: CreateBaseInput):
    """创建新的多维表格"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.create_base(name=input.name, folder_token=input.folder_token)
        return result
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("创建多维表格失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/bases/{base_token}/tables")
async def list_tables(base_token: str):
    """列出多维表格内的所有数据表"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.list_tables(base_token)
        return {"items": result}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("列出数据表失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/bases/{base_token}/tables/{table_id}/fields")
async def list_fields(base_token: str, table_id: str):
    """列出数据表的所有字段"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.list_fields(base_token, table_id)
        return {"items": result}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("列出字段失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.get("/bases/{base_token}/tables/{table_id}/records", response_model=RecordsListResponse)
async def list_records(
    base_token: str,
    table_id: str,
    page_size: int = 20,
    page_token: str = "",
    filter: str = "",
    sort: str = "",
):
    """列出数据表的记录"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.list_records(
            base_token,
            table_id,
            page_size=page_size,
            page_token=page_token,
            filter_expr=filter,
            sort_expr=sort,
        )
        
        items = []
        for item in result.get("items", []):
            items.append(RecordItem(
                record_id=item.get("record_id", ""),
                fields=item.get("fields", {}),
            ))
        
        return RecordsListResponse(
            items=items,
            has_more=result.get("has_more", False),
            page_token=result.get("page_token", ""),
            total=result.get("total", 0),
        )
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("列出记录失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/bases/{base_token}/tables/{table_id}/records")
async def create_records(base_token: str, table_id: str, input: CreateRecordsInput):
    """批量创建记录"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.create_records(base_token, table_id, input.records)
        return {"records": result, "created": len(result)}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("创建记录失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.put("/bases/{base_token}/tables/{table_id}/records")
async def update_records(base_token: str, table_id: str, input: UpdateRecordsInput):
    """批量更新记录"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.update_records(base_token, table_id, input.records)
        return {"records": result, "updated": len(result)}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("更新记录失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.delete("/bases/{base_token}/tables/{table_id}/records")
async def delete_records(base_token: str, table_id: str, input: DeleteRecordsInput):
    """批量删除记录"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.delete_records(base_token, table_id, input.record_ids)
        return result
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("删除记录失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


# ──── IM 消息接口（P1：发文本 / 图片 / 文件；列群）────

async def _resolve_media(source: str) -> bytes:
    """读取图片/文件字节（本地路径 / URL / /api/... 站内路径）。

    注意：必须异步下载（async 请求内若用同步 httpx.get 请求本服务自己，
    会占用 uvicorn event loop，造成自环死锁超时）。
    """
    import httpx
    s = (source or "").strip()
    if not s:
        raise HTTPException(status_code=422, detail="资源路径不能为空")
    if s.startswith(("/api/", "api/")):
        base = os.environ.get("API_BASE", "http://127.0.0.1:8001").rstrip("/")
        path = s if s.startswith("/") else f"/{s}"
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as ac:
            resp = await ac.get(f"{base}{path}")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"获取站内资源失败（HTTP {resp.status_code}）")
        return resp.content
    if s.startswith(("http://", "https://")):
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as ac:
            resp = await ac.get(s)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"下载资源失败（HTTP {resp.status_code}）")
        return resp.content
    p = os.path.abspath(os.path.expanduser(s))
    if not os.path.isfile(p):
        raise HTTPException(status_code=404, detail=f"文件不存在: {s}")
    with open(p, "rb") as f:
        return f.read()


@router.get("/chats")
async def list_chats(page_size: int = 20, page_token: str = ""):
    """列出机器人所在群聊（供选择发送目标）"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.list_chats(page_size=page_size, page_token=page_token)
        return result
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("列出飞书群聊失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/message")
async def send_message(input: SendMessageInput):
    """发送文本消息到飞书群/用户"""
    try:
        service = _get_feishu_service_with_config()
        result = await service.send_text(
            input.receive_id.strip(), input.text, receive_id_type=input.receive_id_type or "chat_id"
        )
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("发送飞书消息失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/image")
async def send_image(input: SendImageInput):
    """上传并发送图片到飞书群/用户"""
    try:
        data = await _resolve_media(input.image)
        filename = os.path.basename(input.image.split("?")[0]) or "image.png"
        service = _get_feishu_service_with_config()
        result = await service.send_image(
            input.receive_id.strip(), data, filename=filename, receive_id_type=input.receive_id_type or "chat_id"
        )
        return {"success": True, "data": result, "bytes": len(data)}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("发送飞书图片失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@router.post("/file")
async def send_file(input: SendFileInput):
    """上传并发送文件到飞书群/用户"""
    try:
        data = await _resolve_media(input.file_path)
        filename = os.path.basename(input.file_path.split("?")[0]) or "file.bin"
        service = _get_feishu_service_with_config()
        result = await service.send_file(
            input.receive_id.strip(), data, filename=filename, receive_id_type=input.receive_id_type or "chat_id"
        )
        return {"success": True, "data": result, "bytes": len(data)}
    except HTTPException:
        raise
    except FeishuError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("发送飞书文件失败")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")
