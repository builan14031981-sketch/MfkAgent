"""意图识别单元测试。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.intent import IntentAnalyzer


def test_file_factual():
    r = IntentAnalyzer().analyze("帮我看看这个文件的内容")
    assert r["intent"] == "file_operation"
    assert r["suggest_tools"] is True
    assert r["layer"] == "factual_need"


def test_debug_factual():
    r = IntentAnalyzer().analyze("为什么测试失败了")
    assert r["intent"] == "project_debug"


def test_memory_factual():
    r = IntentAnalyzer().analyze("你记住我讨厌香菜")
    assert r["intent"] in ("memory", "memory_operation")


def test_action_file():
    r = IntentAnalyzer().analyze("帮我创建一个文件")
    assert r["intent"] == "file_operation"


def test_general_chat():
    r = IntentAnalyzer().analyze("今天天气怎么样")
    assert r["suggest_tools"] is False
    assert r["intent"] == "general_chat"


def test_empty_message():
    r = IntentAnalyzer().analyze("")
    assert r["intent"] == "general_chat"