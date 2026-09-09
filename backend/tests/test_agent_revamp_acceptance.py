"""本次 Agent 核心硬伤修复与体验升级验收测试套件 (Revamp Acceptance Tests)

验证核心升级项：
1. 命令执行引擎对链式安全命令（如 &&）的多段顺序执行支持；
2. 智能首尾截断（保留 Traceback 与错误信息）；
3. edit_file 的换行符 (CRLF/LF) 与行级空白容错替换；
4. 顾念人格预设中的 "极客顾念 (geek)" 专业模式及切换触发；
5. 工具调用死循环熔断保护。
"""
import os
import tempfile
import pytest

from app.core import command_tools as CT
from app.core import tools
from app.core.character_presets import (
    CHARACTER_PRESETS,
    detect_preset_switch,
    get_preset,
)


def test_command_tools_smart_truncate():
    """验证 _truncate_output 智能保留头部与尾部，不丢弃尾部 Traceback"""
    text = "START_SETUP\n" + ("x" * 10000) + "\nTRACEBACK_ERROR_LINE"
    truncated = CT._truncate_output(text, max_chars=1000)
    assert "START_SETUP" in truncated
    assert "TRACEBACK_ERROR_LINE" in truncated
    assert "输出过长已折叠" in truncated


def test_command_tools_chain_pipeline_execution():
    """验证安全的 && 链式命令能够顺序执行并合并输出"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 在临时目录运行两次 python 输出
        cmd = 'python -c "print(\'PART_ONE\')" && python -c "print(\'PART_TWO\')"'
        out = CT.run_command(tmpdir, cmd)
        assert "PART_ONE" in out
        assert "PART_TWO" in out
        assert "[exit code 0]" in out


def test_edit_file_newline_and_indent_tolerance():
    """验证 edit_file 在换行符差异及缩进轻微变动时的容错替换"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.py")
        # 写入 CRLF 格式的文件
        with open(test_file, "wb") as f:
            f.write(b"def hello():\r\n    msg = 'old'\r\n    return msg\r\n")

        # 传入 LF 格式的待替换内容（模拟模型输出换行符漂移）
        old_text = "    msg = 'old'\n    return msg"
        new_text = "    msg = 'new'\n    return msg"

        res = tools.edit_file(tmpdir, "test.py", old_text, new_text)
        assert "替换 1 处" in res
        assert "写入回读校验通过" in res

        # 检查最终文件内容
        with open(test_file, "r", encoding="utf-8") as f:
            updated_content = f.read()
        assert "msg = 'new'" in updated_content


def test_character_presets_geek_mode():
    """验证极客顾念 (geek) 预设与切换指令"""
    assert "geek" in CHARACTER_PRESETS
    geek_preset = get_preset("geek")
    assert geek_preset.name == "极客顾念"
    assert "极客专注模式" in geek_preset.language_style
    assert geek_preset.emoji_max == 0

    # 验证触发词检测
    assert detect_preset_switch("我想切换到极客模式") == "geek"
    assert detect_preset_switch("进入专业模式帮我看下这段代码") == "geek"
    assert detect_preset_switch("极客顾念帮我排查一下") == "geek"
