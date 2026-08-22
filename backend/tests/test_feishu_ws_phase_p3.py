"""飞书反向通道（WebSocket 长连接）解析逻辑单测。"""
import pytest

from app.services.feishu_ws import _parse_receive, _strip_mention_keys


def _payload(chat_type="group", message_type="text", content="{\"text\":\"@_user_1 你好\"}",
             mention=True, chat_id="oc_x", message_id="om_x"):
    return {
        "event": {
            "sender": {"sender_id": {"open_id": "ou_user"}, "sender_type": "user"},
            "message": {
                "chat_id": chat_id,
                "chat_type": chat_type,
                "message_type": message_type,
                "content": content,
                "message_id": message_id,
                "mention": mention,
            },
        }
    }


class TestStripMentionKeys:
    def test_removes_mention_placeholders(self):
        assert _strip_mention_keys("@_user_1 你好") == "你好"

    def test_removes_multiple_placeholders(self):
        assert _strip_mention_keys("@_user_1 @_user_2 大家好") == "大家好"

    def test_no_placeholder_keeps_text(self):
        assert _strip_mention_keys("  你好  ") == "你好"


class TestParseReceive:
    def test_group_mention_message_parsed(self):
        info = _parse_receive(_payload())
        assert info["chat_id"] == "oc_x"
        assert info["text"] == "你好"
        assert info["open_id"] == "ou_user"

    def test_group_without_mention_ignored(self):
        assert _parse_receive(_payload(mention=False)) is None

    def test_p2p_message_parsed_without_mention(self):
        info = _parse_receive(_payload(chat_type="p2p", mention=False))
        assert info["text"] == "你好"
        assert info["chat_type"] == "p2p"

    def test_non_text_message_ignored(self):
        assert _parse_receive(_payload(message_type="image")) is None

    def test_missing_chat_id_ignored(self):
        assert _parse_receive(_payload(chat_id="")) is None

    def test_bad_content_json_ignored(self):
        assert _parse_receive(_payload(content="not-json")) is None

    def test_empty_text_ignored(self):
        assert _parse_receive(_payload(content="{\"text\":\"@_user_1\"}")) is None

    def test_empty_payload_ignored(self):
        assert _parse_receive({}) is None