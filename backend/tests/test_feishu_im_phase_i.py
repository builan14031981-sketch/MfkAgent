"""飞书 IM 消息闭环（P1）测试：工具注册 / 风险策略 / 工具执行 / REST 端点 / 图片路径解析。

不依赖真实飞书 API（mock FeishuService），仅验证本项目侧逻辑。
"""
import json
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.tools import tool_registry  # noqa: E402
from app.core.tool_runtime.risk_engine import TOOL_RISK_POLICY, READ_ONLY_TOOLS, Verdict, RiskLevel  # noqa: E402
from app.core.tool_runtime.permission import PermissionFilter  # noqa: E402

IM_TOOLS = ["feishu_send_message", "feishu_send_image", "feishu_send_file", "feishu_list_chats"]


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """禁止测试期间访问真实飞书（保险丝）。"""
    monkeypatch.setattr("httpx.AsyncClient.request", AsyncMock(side_effect=RuntimeError("network disabled in test")))


@pytest.mark.asyncio
async def test_tools_registered():
    names = {t.name for t in tool_registry.get_all()}
    for n in IM_TOOLS:
        assert n in names, f"工具 {n} 未注册"


def test_tools_in_base_and_policy():
    base = set(PermissionFilter.BASE_TOOLS)
    for n in ["feishu_send_message", "feishu_send_image", "feishu_send_file"]:
        assert n in base, f"{n} 不在 BASE_TOOLS"
        pol = TOOL_RISK_POLICY.get(n)
        assert pol is not None and pol[0] == Verdict.REQUIRE_APPROVAL and pol[1] is RiskLevel.WRITE, f"{n} 风险策略错误"
        assert n not in READ_ONLY_TOOLS
    assert "feishu_list_chats" in base
    assert "feishu_list_chats" in READ_ONLY_TOOLS


@pytest.mark.asyncio
async def test_send_message_tool_execute():
    from app.services import feishu_tools
    svc = AsyncMock()
    svc.send_text = AsyncMock(return_value={"message_id": "om_123"})
    with patch.object(feishu_tools, "_build_service", return_value=svc):
        tool = feishu_tools.FeishuSendMessageTool()
        res = await tool.execute(receive_id="oc_test", text="你好")
    assert res.success is True
    assert json.loads(res.output)["message_id"] == "om_123"
    svc.send_text.assert_awaited_once_with("oc_test", "你好", receive_id_type="chat_id")


@pytest.mark.asyncio
async def test_send_message_tool_requires_fields():
    from app.services import feishu_tools
    tool = feishu_tools.FeishuSendMessageTool()
    res = await tool.execute(receive_id="", text="")
    assert res.success is False and "不能为空" in res.error


@pytest.mark.asyncio
async def test_send_image_tool_upload_and_send(monkeypatch):
    from app.services import feishu_tools
    import httpx
    class FakeResp:
        content = b"\x89PNGfake"
        def raise_for_status(self):
            pass
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())
    svc = AsyncMock()
    svc.send_image = AsyncMock(return_value={"message_id": "om_img"})
    with patch.object(feishu_tools, "_build_service", return_value=svc):
        tool = feishu_tools.FeishuSendImageTool()
        res = await tool.execute(receive_id="oc_t", image="http://example.com/x.png")
    assert res.success is True
    assert json.loads(res.output)["bytes"] > 0


@pytest.mark.asyncio
async def test_send_image_local_path(tmp_path):
    from app.services import feishu_tools
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG\x0d\x0a\x1a\x0a" + b"x" * 100)
    data = feishu_tools._resolve_media_bytes(str(img))
    assert data[:8] == b"\x89PNG\x0d\x0a\x1a\x0a"


@pytest.mark.asyncio
async def test_send_image_missing_file():
    from app.services import feishu_tools
    with pytest.raises(RuntimeError):
        feishu_tools._resolve_media_bytes("Z:/no_such_file_xyz.png")


@pytest.mark.asyncio
async def test_send_file_tool_execute(tmp_path):
    from app.services import feishu_tools
    f = tmp_path / "r.txt"
    f.write_text("hello", encoding="utf-8")
    svc = AsyncMock()
    svc.send_file = AsyncMock(return_value={"message_id": "om_file"})
    with patch.object(feishu_tools, "_build_service", return_value=svc):
        tool = feishu_tools.FeishuSendFileTool()
        res = await tool.execute(receive_id="oc_t", file_path=str(f))
    assert res.success is True


@pytest.mark.asyncio
async def test_list_chats_tool_no_chats():
    from app.services import feishu_tools
    svc = AsyncMock()
    svc.list_chats = AsyncMock(return_value={"items": []})
    with patch.object(feishu_tools, "_build_service", return_value=svc):
        tool = feishu_tools.FeishuListChatsTool()
        res = await tool.execute()
    assert res.success is False and "未加入" in res.error


@pytest.mark.asyncio
async def test_list_chats_tool_slim():
    from app.services import feishu_tools
    svc = AsyncMock()
    svc.list_chats = AsyncMock(return_value={"items": [{"chat_id": "oc_1", "name": "测试群"}]})
    with patch.object(feishu_tools, "_build_service", return_value=svc):
        tool = feishu_tools.FeishuListChatsTool()
        res = await tool.execute()
    assert res.success is True
    out = json.loads(res.output)
    assert out[0]["chat_id"] == "oc_1"


def test_schemas_valid():
    from app.services import feishu_tools
    for cls in (feishu_tools.FeishuSendMessageTool, feishu_tools.FeishuSendImageTool,
                feishu_tools.FeishuSendFileTool, feishu_tools.FeishuListChatsTool):
        d = cls().get_definition()
        assert d["type"] == "function"
        assert d["function"]["name"].startswith("feishu_")
        assert "parameters" in d["function"]


def test_tool_definitions_exposed_to_llm():
    """LLM 可见工具定义应包含新飞书工具（注册即暴露）。"""
    from app.services.tools import tool_registry as reg
    defs = reg.get_all()
    names = {t.name for t in defs}
    assert "feishu_send_message" in names


@pytest.mark.asyncio
async def test_api_endpoints_exist():
    """REST 路由已挂载（存在性校验，不实际调飞书）。"""
    import app.api.feishu as api
    paths = {getattr(r, "path", None) for r in api.router.routes}
    assert "/chats" in paths
    assert "/message" in paths
    assert "/image" in paths
    assert "/file" in paths


def test_media_resolve_proxy_path(monkeypatch):
    """代理路径 /api/chat/... 应拼 API_BASE 下载。"""
    from app.services import feishu_tools
    import httpx
    class FakeResp:
        content = b"\x89PNGfake"
        def raise_for_status(self):
            pass
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResp())
    data = feishu_tools._resolve_media_bytes("/api/chat/9/generated_image?path=output/x.png")
    assert data == b"\x89PNGfake"
