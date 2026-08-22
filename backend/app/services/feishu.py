"""飞书多维表格服务层 — 封装飞书 Open API 调用。

职责：
- 认证管理（tenant_access_token 获取、缓存、自动刷新）
- 多维表格 CRUD 操作（表、字段、记录）
- 统一错误处理和日志

飞书 API 文档：https://open.feishu.cn/document/server-docs/docs/bitable-v1/bitable-overview
"""
import time
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class FeishuError(Exception):
    """飞书 API 错误"""
    def __init__(self, message: str, code: int = 0, details: str = ""):
        super().__init__(message)
        self.code = code
        self.details = details


class FeishuService:
    """飞书服务层 — 封装多维表格 API 调用"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self, app_id: str = "", app_secret: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str = ""
        self._token_expires: float = 0  # token 过期时间戳
    
    async def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token（带缓存）"""
        # 如果 token 还有效（提前 5 分钟刷新），直接返回
        if self._token and time.time() < self._token_expires - 300:
            return self._token
        
        if not self.app_id or not self.app_secret:
            raise FeishuError("未配置飞书 App ID 或 App Secret")
        
        import httpx
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code != 200:
                    raise FeishuError(f"获取 token 失败（HTTP {response.status_code}）")
                
                data = response.json()
                if data.get("code") != 0:
                    raise FeishuError(
                        f"获取 token 失败: {data.get('msg', '未知错误')}",
                        code=data.get("code", 0)
                    )
                
                self._token = data["tenant_access_token"]
                # token 有效期 2 小时，这里记录过期时间
                self._token_expires = time.time() + data.get("expire", 7200)
                logger.info("飞书 tenant_access_token 获取成功，有效期 %d 秒", data.get("expire", 7200))
                return self._token
                
        except httpx.TimeoutException:
            raise FeishuError("获取 token 超时")
        except Exception as e:
            raise FeishuError(f"获取 token 失败: {str(e)}")
    
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """统一的 HTTP 请求方法（自动带 token）"""
        token = await self._get_tenant_access_token()
        url = f"{self.BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )
                
                if response.status_code != 200:
                    raise FeishuError(f"请求失败（HTTP {response.status_code}）")
                
                data = response.json()
                if data.get("code") != 0:
                    raise FeishuError(
                        f"API 错误: {data.get('msg', '未知错误')}",
                        code=data.get("code", 0),
                        details=str(data)
                    )
                
                return data.get("data", {})
                
        except httpx.TimeoutException:
            raise FeishuError("请求超时")
        except FeishuError:
            raise
        except Exception as e:
            raise FeishuError(f"请求失败: {str(e)}")
    
    # ──── 认证测试 ────
    
    async def test_connection(self) -> Dict[str, Any]:
        """测试飞书连接（验证 App ID/Secret 能获取 tenant_access_token 即可）。

        注意：不用「列出多维表格」来验证——飞书的 /bitable/v1/apps 列表接口
        要求 user_access_token（用户身份授权）；应用身份调用会返回 404，
        凭据正确也会误报失败。因此这里仅以 token 获取成功作为连通性标准。
        """
        try:
            token = await self._get_tenant_access_token()
            return {
                "success": True,
                "message": "连接成功，凭证有效，Agent 可使用飞书工具",
                "token_valid": True,
                "has_bases": bool(token),
            }
        except FeishuError as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
                "token_valid": False,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接失败: {str(e)}",
                "token_valid": False,
            }
    
    # ──── 多维表格（Base）操作 ────
    
    async def list_bases(self, page_size: int = 20, page_token: str = "") -> Dict[str, Any]:
        """列出用户有权限的多维表格"""
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        
        result = await self._request("GET", "/bitable/v1/apps", params=params)
        return {
            "items": result.get("items", []),
            "has_more": result.get("has_more", False),
            "page_token": result.get("page_token", ""),
            "total": result.get("total", 0),
        }
    
    async def get_base(self, base_token: str) -> Dict[str, Any]:
        """获取多维表格详情"""
        result = await self._request("GET", f"/bitable/v1/apps/{base_token}")
        return result.get("app", {})
    
    async def create_base(
        self,
        name: str,
        folder_token: str = "",
    ) -> Dict[str, Any]:
        """创建新的多维表格"""
        payload = {"name": name}
        if folder_token:
            payload["folder_token"] = folder_token
        
        result = await self._request("POST", "/bitable/v1/apps", json_data=payload)
        return result.get("app", {})
    
    # ──── 数据表（Table）操作 ────
    
    async def list_tables(self, base_token: str) -> List[Dict[str, Any]]:
        """列出多维表格内的所有数据表"""
        result = await self._request("GET", f"/bitable/v1/apps/{base_token}/tables")
        return result.get("items", [])
    
    async def get_table(self, base_token: str, table_id: str) -> Dict[str, Any]:
        """获取数据表详情"""
        result = await self._request("GET", f"/bitable/v1/apps/{base_token}/tables/{table_id}")
        return result.get("table", {})
    
    # ──── 字段（Field）操作 ────
    
    async def list_fields(self, base_token: str, table_id: str) -> List[Dict[str, Any]]:
        """列出数据表的所有字段"""
        result = await self._request(
            "GET",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/fields"
        )
        return result.get("items", [])
    
    # ──── 记录（Record）操作 ────
    
    async def list_records(
        self,
        base_token: str,
        table_id: str,
        page_size: int = 20,
        page_token: str = "",
        filter_expr: str = "",
        sort_expr: str = "",
    ) -> Dict[str, Any]:
        """列出数据表的记录（支持筛选和排序）"""
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        if filter_expr:
            params["filter"] = filter_expr
        if sort_expr:
            params["sort"] = sort_expr
        
        result = await self._request(
            "GET",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/records",
            params=params
        )
        return {
            "items": result.get("items", []),
            "has_more": result.get("has_more", False),
            "page_token": result.get("page_token", ""),
            "total": result.get("total", 0),
        }
    
    async def get_record(self, base_token: str, table_id: str, record_id: str) -> Dict[str, Any]:
        """获取单条记录详情"""
        result = await self._request(
            "GET",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/records/{record_id}"
        )
        return result.get("record", {})
    
    async def create_records(
        self,
        base_token: str,
        table_id: str,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量创建记录（最多 500 条）"""
        if len(records) > 500:
            raise FeishuError("单次创建记录不能超过 500 条")
        
        payload = {"records": [{"fields": r} for r in records]}
        result = await self._request(
            "POST",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/records/batch_create",
            json_data=payload
        )
        return result.get("records", [])
    
    async def update_records(
        self,
        base_token: str,
        table_id: str,
        records: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """批量更新记录（最多 500 条）"""
        if len(records) > 500:
            raise FeishuError("单次更新记录不能超过 500 条")
        
        payload = {"records": records}
        result = await self._request(
            "POST",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/records/batch_update",
            json_data=payload
        )
        return result.get("records", [])
    
    async def delete_records(
        self,
        base_token: str,
        table_id: str,
        record_ids: List[str],
    ) -> Dict[str, Any]:
        """批量删除记录（最多 500 条）"""
        if len(record_ids) > 500:
            raise FeishuError("单次删除记录不能超过 500 条")
        
        payload = {"records": record_ids}
        result = await self._request(
            "POST",
            f"/bitable/v1/apps/{base_token}/tables/{table_id}/records/batch_delete",
            json_data=payload
        )
        return {"deleted": len(record_ids)}

    # ──── IM 消息能力（P1：发文本 / 图片 / 文件 到群或用户）────

    async def list_chats(self, page_size: int = 20, page_token: str = "") -> Dict[str, Any]:
        """列出机器人所在群（返回 chat_id 供发送消息使用）"""
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        result = await self._request("GET", "/im/v1/chats", params=params)
        return {
            "items": result.get("items", []),
            "has_more": result.get("has_more", False),
            "page_token": result.get("page_token", ""),
        }

    async def send_text(
        self,
        receive_id: str,
        text: str,
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """发送文本消息（receive_id_type: chat_id / open_id / user_id / email）"""
        content = json.dumps({"text": text}, ensure_ascii=False)
        result = await self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json_data={"receive_id": receive_id, "msg_type": "text", "content": content},
        )
        return result

    async def upload_image(self, data: bytes, filename: str) -> str:
        """上传图片（消息用途），返回 image_key"""
        token = await self._get_tenant_access_token()
        url = f"{self.BASE_URL}/im/v1/images"
        files = {"image": (filename or "image.png", data, "image/png")}
        data_payload = {"image_type": "message"}
        headers = {"Authorization": f"Bearer {token}"}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data_payload, files=files, headers=headers)
                if response.status_code != 200:
                    raise FeishuError(f"上传图片失败（HTTP {response.status_code}）")
                body = response.json()
                if body.get("code") != 0:
                    raise FeishuError(f"上传图片失败: {body.get('msg', '未知错误')}", code=body.get("code", 0))
                key = (body.get("data") or {}).get("image_key", "")
                if not key:
                    raise FeishuError("上传图片失败: 未返回 image_key")
                return key
        except httpx.TimeoutException:
            raise FeishuError("上传图片超时")
        except FeishuError:
            raise
        except Exception as e:
            raise FeishuError(f"上传图片失败: {str(e)}")

    async def upload_file(self, data: bytes, filename: str) -> str:
        """上传文件（消息用途），返回 file_key"""
        token = await self._get_tenant_access_token()
        url = f"{self.BASE_URL}/im/v1/files"
        files = {"file": (filename or "file.bin", data, "application/octet-stream")}
        data_payload = {"file_type": "stream"}
        headers = {"Authorization": f"Bearer {token}"}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=data_payload, files=files, headers=headers)
                if response.status_code != 200:
                    raise FeishuError(f"上传文件失败（HTTP {response.status_code}）")
                body = response.json()
                if body.get("code") != 0:
                    raise FeishuError(f"上传文件失败: {body.get('msg', '未知错误')}", code=body.get("code", 0))
                key = (body.get("data") or {}).get("file_key", "")
                if not key:
                    raise FeishuError("上传文件失败: 未返回 file_key")
                return key
        except httpx.TimeoutException:
            raise FeishuError("上传文件超时")
        except FeishuError:
            raise
        except Exception as e:
            raise FeishuError(f"上传文件失败: {str(e)}")

    async def send_media(
        self,
        receive_id: str,
        msg_type: str,
        key: str,
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """发送媒体消息（图片/文件，key 为 image_key/file_key）"""
        content = json.dumps({f"{msg_type}_key": key})
        result = await self._request(
            "POST",
            "/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            json_data={"receive_id": receive_id, "msg_type": msg_type, "content": content},
        )
        return result

    async def send_image(
        self,
        receive_id: str,
        data: bytes,
        filename: str = "image.png",
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """上传并发送图片消息"""
        image_key = await self.upload_image(data, filename)
        return await self.send_media(receive_id, "image", image_key, receive_id_type)

    async def send_file(
        self,
        receive_id: str,
        data: bytes,
        filename: str = "file.bin",
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """上传并发送文件消息"""
        file_key = await self.upload_file(data, filename)
        return await self.send_media(receive_id, "file", file_key, receive_id_type)


# ──── 全局实例管理 ────

_feishu_service: Optional[FeishuService] = None


def get_feishu_service(app_id: str = "", app_secret: str = "") -> FeishuService:
    """获取飞书服务实例（单例模式）"""
    global _feishu_service
    
    # 如果传入了新的凭证，或者实例不存在，创建新实例
    if (app_id and app_secret) or _feishu_service is None:
        _feishu_service = FeishuService(app_id=app_id, app_secret=app_secret)
    
    return _feishu_service


def reset_feishu_service():
    """重置飞书服务实例（配置变更时调用）"""
    global _feishu_service
    _feishu_service = None
