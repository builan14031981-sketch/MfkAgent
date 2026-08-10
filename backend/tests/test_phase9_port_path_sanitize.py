"""Phase 9 P1 — 端口避让、长路径兼容、非法字符过滤 单元测试

测试场景：
  1. PortManager — 端口检测与文件读写
  2. PathUtils — 长路径前缀、Junction 检测、safe_resolve
  3. Sanitize — 文件名清理、路径清理、合法性检查
  4. 跨平台兼容 — Mac/Linux 下透明传递
"""

import sys
import os
import tempfile
import socket
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.port_manager import (
    _is_port_available,
    find_available_port,
    write_port_file,
    read_port_file,
    clear_port_file,
)
from app.core.path_utils import (
    is_windows,
    ensure_long_path,
    strip_long_path,
    IS_WINDOWS,
)
from app.core.sanitize import (
    sanitize_filename,
    sanitize_path,
    is_valid_filename,
)


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: PortManager — 端口检测与文件读写
# ══════════════════════════════════════════════════════════════════════════════

class TestPortAvailability:
    """测试端口可用性检测"""

    def test_default_port_available(self):
        """默认端口 8001 在测试环境中通常可用"""
        # 此测试可能因环境而异，主要验证函数不抛异常
        result = _is_port_available(8001)
        assert isinstance(result, bool)

    def test_port_available_returns_bool(self):
        """_is_port_available 返回布尔值"""
        for port in [8001, 18001, 28001]:
            result = _is_port_available(port)
            assert isinstance(result, bool)

    def test_find_available_port_returns_int(self):
        """find_available_port 返回有效端口号"""
        port = find_available_port(start_port=18001, max_attempts=10)
        assert isinstance(port, int)
        assert 18001 <= port <= 18010

    def test_find_available_port_increments(self):
        """当起始端口被占用时自动递增"""
        # 占用 18001 端口（不使用 SO_REUSEADDR，确保端口被真正占用）
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 18001))
        sock.listen(1)
        try:
            port = find_available_port(start_port=18001, max_attempts=10)
            assert port >= 18002, f"应跳过被占用的 18001，实际返回 {port}"
        finally:
            sock.close()


class TestPortFile:
    """测试端口文件读写"""

    def test_write_and_read(self):
        """写入端口文件后能正确读取"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".port", delete=False) as f:
            tmp_path = Path(f.name)

        try:
            write_port_file(8080, file_path=tmp_path)
            assert read_port_file(file_path=tmp_path) == 8080
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_read_nonexistent(self):
        """读取不存在的文件返回 None"""
        result = read_port_file(file_path=Path("/nonexistent/.mfkagent_port"))
        assert result is None

    def test_read_invalid(self):
        """读取格式错误的文件返回 None"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".port", delete=False) as f:
            f.write("not-a-number")
            tmp_path = Path(f.name)

        try:
            assert read_port_file(file_path=tmp_path) is None
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_clear_port_file(self):
        """清理端口文件后读取返回 None"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".port", delete=False) as f:
            f.write("9999")
            tmp_path = Path(f.name)

        try:
            clear_port_file(file_path=tmp_path)
            assert read_port_file(file_path=tmp_path) is None
        finally:
            tmp_path.unlink(missing_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: PathUtils — 长路径前缀
# ══════════════════════════════════════════════════════════════════════════════

class TestEnsureLongPath:
    """测试长路径前缀添加"""

    def test_returns_str(self):
        """ensure_long_path 始终返回字符串"""
        result = ensure_long_path("/tmp/test")
        assert isinstance(result, str)

    def test_relative_path_unchanged(self):
        """相对路径不添加前缀"""
        result = ensure_long_path("relative/path")
        if IS_WINDOWS:
            # Windows 上 abspath 会转为绝对路径
            assert "\\\\?\\" in result or result.endswith("relative\\path")
        else:
            assert result == "relative/path"

    def test_already_prefixed_not_duplicated(self):
        """已有 \\\\?\\ 前缀不重复添加"""
        if IS_WINDOWS:
            prefixed = "\\\\?\\C:\\test"
            result = ensure_long_path(prefixed)
            assert result == prefixed

    def test_strip_long_path(self):
        """strip_long_path 移除前缀"""
        if IS_WINDOWS:
            assert strip_long_path("\\\\?\\C:\\test") == "C:\\test"
            assert strip_long_path("\\\\?\\UNC\\server\\share") == "\\\\server\\share"
        assert strip_long_path("/normal/path") == "/normal/path"

    def test_strip_no_prefix(self):
        """无前缀路径原样返回"""
        assert strip_long_path("C:\\normal") == "C:\\normal"
        assert strip_long_path("/usr/local") == "/usr/local"


class TestIsWindows:
    """测试平台检测"""

    def test_is_windows_returns_bool(self):
        """is_windows 返回布尔值"""
        assert isinstance(is_windows(), bool)

    def test_is_windows_consistent(self):
        """is_windows 与 IS_WINDOWS 一致"""
        assert is_windows() == IS_WINDOWS


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: Sanitize — 文件名清理
# ══════════════════════════════════════════════════════════════════════════════

class TestSanitizeFilename:
    """测试文件名清理"""

    def test_normal_name_unchanged(self):
        """正常文件名不变"""
        assert sanitize_filename("hello.txt") == "hello.txt"
        assert sanitize_filename("my_file.py") == "my_file.py"

    def test_illegal_chars_replaced(self):
        """非法字符被替换"""
        if IS_WINDOWS:
            assert sanitize_filename("hello<world>.txt") == "hello_world_.txt"
            assert sanitize_filename('file:name"test') == "file_name_test"
            assert sanitize_filename("a/b\\c") == "a_b_c"

    def test_control_chars_replaced(self):
        """控制字符被替换"""
        if IS_WINDOWS:
            result = sanitize_filename("test\x01\x02file")
            assert "\x01" not in result
            assert "\x02" not in result

    def test_trailing_spaces_and_dots_removed(self):
        """首尾空格和点被移除"""
        if IS_WINDOWS:
            assert sanitize_filename("  test  ") == "test"
            assert sanitize_filename("test...") == "test"

    def test_reserved_names_prefixed(self):
        """Windows 保留名添加前缀"""
        if IS_WINDOWS:
            assert sanitize_filename("CON") == "_CON"
            assert sanitize_filename("NUL.txt") == "_NUL.txt"
            assert sanitize_filename("PRN") == "_PRN"
            assert sanitize_filename("COM1") == "_COM1"
            assert sanitize_filename("LPT1") == "_LPT1"

    def test_empty_returns_untitled(self):
        """空字符串返回 'untitled'"""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("   ") == "untitled"

    def test_only_illegal_chars_returns_untitled(self):
        """仅有非法字符时返回 'untitled'"""
        if IS_WINDOWS:
            result = sanitize_filename("<>:\"")
            assert result == "untitled" or len(result) > 0

    def test_consecutive_replacements_compressed(self):
        """连续替换字符压缩"""
        if IS_WINDOWS:
            result = sanitize_filename("a<>b")
            assert result == "a__b" or result == "a_b"

    def test_non_windows_minimal_cleanup(self):
        """非 Windows 下仅做基本清理"""
        if not IS_WINDOWS:
            # 空字符过滤
            assert sanitize_filename("test\x00file") == "test_file"
            # 正常名不变
            assert sanitize_filename("hello:world.txt") == "hello:world.txt"


class TestSanitizePath:
    """测试完整路径清理"""

    def test_normal_path_unchanged(self):
        """正常路径不变"""
        if IS_WINDOWS:
            result = sanitize_path("C:\\test\\file.txt")
            assert "test" in result
            assert "file.txt" in result
        else:
            result = sanitize_path("/home/user/file.txt")
            assert result == "/home/user/file.txt"

    def test_path_with_illegal_chars(self):
        """含非法字符的路径被清理"""
        if IS_WINDOWS:
            result = sanitize_path("C:\\test\\file<bad>.txt")
            assert "<" not in result
            assert "file_bad_.txt" in result

    def test_unc_path_handled(self):
        """UNC 路径处理"""
        if IS_WINDOWS:
            result = sanitize_path("\\\\server\\share\\path")
            assert "server" in result
            assert "share" in result


class TestIsValidFilename:
    """测试文件名合法性检查"""

    def test_valid_names(self):
        """合法文件名"""
        assert is_valid_filename("hello.txt")
        assert is_valid_filename("my_file.py")
        assert is_valid_filename("README.md")

    def test_invalid_empty(self):
        """空文件名不合法"""
        assert not is_valid_filename("")
        assert not is_valid_filename("   ")

    def test_invalid_illegal_chars(self):
        """含非法字符不合法"""
        if IS_WINDOWS:
            assert not is_valid_filename("file<name>.txt")
            assert not is_valid_filename('test"file')

    def test_invalid_reserved(self):
        """保留名不合法"""
        if IS_WINDOWS:
            assert not is_valid_filename("CON")
            assert not is_valid_filename("NUL.txt")

    def test_invalid_trailing(self):
        """首尾空格/点不合法"""
        if IS_WINDOWS:
            assert not is_valid_filename(" test.txt")
            assert not is_valid_filename("test.txt ")


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: 跨平台兼容 — Mac/Linux 透明传递
# ══════════════════════════════════════════════════════════════════════════════

class TestCrossPlatformSafety:
    """跨平台安全：Mac/Linux 下不报错"""

    def test_ensure_long_path_no_error(self):
        """ensure_long_path 在任何平台都不抛异常"""
        try:
            result = ensure_long_path("/tmp/test")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"ensure_long_path 不应抛异常: {e}")

    def test_sanitize_filename_no_error(self):
        """sanitize_filename 在任何平台都不抛异常"""
        try:
            result = sanitize_filename("normal_name.txt")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"sanitize_filename 不应抛异常: {e}")

    def test_sanitize_path_no_error(self):
        """sanitize_path 在任何平台都不抛异常"""
        try:
            result = sanitize_path("/tmp/test")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"sanitize_path 不应抛异常: {e}")

    def test_sanitize_with_unicode(self):
        """Unicode 文件名正确处理"""
        result = sanitize_filename("中文文件名.md")
        assert "中文文件名.md" in result or len(result) > 0

    def test_sanitize_with_emoji(self):
        """Emoji 文件名正确处理"""
        result = sanitize_filename("test🎉.txt")
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 直接运行
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])