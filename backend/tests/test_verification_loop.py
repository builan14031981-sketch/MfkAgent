"""Verification Loop V1 测试

覆盖验证循环控制：
1. 验证失败计数跟踪
2. 达到重试上限后停止重试
3. 验证成功后重置计数
4. 新增验证策略（replace_in_file, apply_patch, git_commit）
"""

import pytest
from app.core.tool_runtime.strategy import (
    ToolExecutionStrategy,
    StrategyStatus,
    get_strategy_engine,
    remove_strategy_engine,
)
from app.core.verification.models import VerificationResult, PASSED, FAILED, NEED_RETRY
from app.core.verification.strategies import (
    verify_replace_in_file,
    verify_apply_patch,
    verify_git_commit,
)


class TestVerificationLoopTracking:
    """验证循环跟踪测试"""

    def test_verification_failure_increments_counter(self):
        """验证失败应增加重试计数"""
        strategy = ToolExecutionStrategy()
        
        assert strategy.get_verification_retry_count() == 0
        
        strategy.record_verification_failure()
        assert strategy.get_verification_retry_count() == 1
        
        strategy.record_verification_failure()
        assert strategy.get_verification_retry_count() == 2

    def test_verification_success_resets_counter(self):
        """验证成功应重置重试计数"""
        strategy = ToolExecutionStrategy()
        
        # 先失败 2 次
        strategy.record_verification_failure()
        strategy.record_verification_failure()
        assert strategy.get_verification_retry_count() == 2
        
        # 成功后重置
        strategy.record_verification_success()
        assert strategy.get_verification_retry_count() == 0

    def test_should_stop_after_max_retries(self):
        """达到最大重试次数后应停止"""
        strategy = ToolExecutionStrategy()
        
        # 未达到上限
        for i in range(2):
            strategy.record_verification_failure()
        assert not strategy.should_stop_verification_retry()
        
        # 达到上限（MAX_VERIFICATION_RETRIES = 3）
        strategy.record_verification_failure()
        assert strategy.should_stop_verification_retry()

    def test_reset_clears_verification_counter(self):
        """重置应清除验证重试计数"""
        strategy = ToolExecutionStrategy()
        
        strategy.record_verification_failure()
        strategy.record_verification_failure()
        assert strategy.get_verification_retry_count() == 2
        
        strategy.reset()
        assert strategy.get_verification_retry_count() == 0


class TestReplaceInFileVerification:
    """replace_in_file 验证策略测试"""

    def test_replace_success(self, tmp_path):
        """替换成功应返回 PASSED"""
        # 创建测试文件（模拟替换后的内容）
        test_file = tmp_path / "test.txt"
        test_file.write_text("hi world", encoding="utf-8")
        
        record = {
            "tool": "replace_in_file",
            "status": "success",
            "arguments": {
                "relative_path": "test.txt",
                "old_str": "hello",
                "new_str": "hi",
            },
            "result": "replaced",
        }
        
        result = verify_replace_in_file(record, str(tmp_path))
        assert result.status == PASSED
        assert "替换成功" in result.message

    def test_replace_old_str_still_exists(self, tmp_path):
        """old_str 仍存在说明替换失败"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")
        
        record = {
            "tool": "replace_in_file",
            "status": "success",
            "arguments": {
                "relative_path": "test.txt",
                "old_str": "hello",
                "new_str": "hi",
            },
            "result": "failed",
        }
        
        result = verify_replace_in_file(record, str(tmp_path))
        assert result.status == NEED_RETRY
        assert "替换内容未生效" in result.message

    def test_replace_file_not_found(self, tmp_path):
        """文件不存在应返回 FAILED"""
        record = {
            "tool": "replace_in_file",
            "status": "success",
            "arguments": {
                "relative_path": "nonexistent.txt",
                "old_str": "hello",
                "new_str": "hi",
            },
            "result": "error",
        }
        
        result = verify_replace_in_file(record, str(tmp_path))
        assert result.status == FAILED
        assert "文件不存在" in result.message


class TestApplyPatchVerification:
    """apply_patch 验证策略测试"""

    def test_apply_patch_success(self, tmp_path):
        """patch 应用成功应返回 PASSED"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("modified content", encoding="utf-8")
        
        record = {
            "tool": "apply_patch",
            "status": "success",
            "arguments": {
                "relative_path": "test.txt",
                "patch": "@@ -1 +1 @@\n-modified content\n+new content",
            },
            "result": "patch applied",
        }
        
        result = verify_apply_patch(record, str(tmp_path))
        assert result.status == PASSED
        assert "patch 应用成功" in result.message

    def test_apply_patch_with_error(self, tmp_path):
        """patch 应用失败应返回 NEED_RETRY"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content", encoding="utf-8")
        
        record = {
            "tool": "apply_patch",
            "status": "success",
            "arguments": {
                "relative_path": "test.txt",
                "patch": "invalid patch",
            },
            "result": "error: patch failed",
        }
        
        result = verify_apply_patch(record, str(tmp_path))
        assert result.status == NEED_RETRY
        assert "patch 应用可能失败" in result.message

    def test_apply_patch_file_not_found(self, tmp_path):
        """文件不存在应返回 FAILED"""
        record = {
            "tool": "apply_patch",
            "status": "success",
            "arguments": {
                "relative_path": "nonexistent.txt",
                "patch": "some patch",
            },
            "result": "error",
        }
        
        result = verify_apply_patch(record, str(tmp_path))
        assert result.status == FAILED
        assert "文件不存在" in result.message


class TestGitCommitVerification:
    """git_commit 验证策略测试"""

    def test_git_commit_success(self):
        """git commit 成功（包含 hash）应返回 PASSED"""
        record = {
            "tool": "git_commit",
            "status": "success",
            "arguments": {"message": "test commit"},
            "result": "[main abc1234] test commit\n1 file changed",
        }
        
        result = verify_git_commit(record, None)
        assert result.status == PASSED
        assert "git commit 成功" in result.message

    def test_git_commit_failed(self):
        """git commit 失败应返回 NEED_RETRY"""
        record = {
            "tool": "git_commit",
            "status": "success",
            "arguments": {"message": "test commit"},
            "result": "error: nothing to commit",
        }
        
        result = verify_git_commit(record, None)
        assert result.status == NEED_RETRY
        assert "git commit 失败" in result.message

    def test_git_commit_unclear_result(self):
        """无法确定结果应返回 NEED_RETRY"""
        record = {
            "tool": "git_commit",
            "status": "success",
            "arguments": {"message": "test commit"},
            "result": "some unclear output",
        }
        
        result = verify_git_commit(record, None)
        assert result.status == NEED_RETRY
        assert "无法确认" in result.message


class TestVerificationLoopIntegration:
    """验证循环集成测试"""

    def test_verification_loop_exhaustion_flow(self):
        """验证循环耗尽流程"""
        strategy = ToolExecutionStrategy()
        
        # 模拟 3 次验证失败
        for i in range(3):
            strategy.record_verification_failure()
            assert strategy.get_verification_retry_count() == i + 1
        
        # 第 3 次后应停止
        assert strategy.should_stop_verification_retry()
        
        # 重置后应继续
        strategy.record_verification_success()
        assert not strategy.should_stop_verification_retry()
        assert strategy.get_verification_retry_count() == 0

    def test_strategy_engine_singleton_with_verification(self):
        """策略引擎单例应共享验证循环状态"""
        engine1 = get_strategy_engine("test_session_verification")
        engine2 = get_strategy_engine("test_session_verification")
        
        # 同一实例
        assert engine1 is engine2
        
        # 共享状态
        engine1.record_verification_failure()
        assert engine2.get_verification_retry_count() == 1
        
        # 清理
        remove_strategy_engine("test_session_verification")
