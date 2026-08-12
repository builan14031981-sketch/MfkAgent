"""测试包管理意图识别

验证新增的 package_management 意图类型是否正确工作，
同时确保现有意图识别不受影响。
"""

import pytest
from app.core.tool_runtime.intent import IntentAnalyzer


@pytest.fixture
def analyzer():
    """创建 IntentAnalyzer 实例"""
    return IntentAnalyzer()


class TestPackageManagerIntent:
    """包管理意图测试类"""

    def test_factual_query_installed_packages(self, analyzer):
        """测试：查看已安装的 Python 包 → package_management"""
        message = "帮我看看装了哪些 Python 包"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True
        assert result["layer"] == "factual_need"
        assert result["confidence"] == 0.9

    def test_action_upgrade_dependency(self, analyzer):
        """测试：如何升级这个依赖 → package_management"""
        message = "如何升级这个依赖"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True
        assert result["layer"] == "action_intent"
        assert result["confidence"] == 0.85

    def test_existing_file_operation_unchanged(self, analyzer):
        """测试：查看文件内容 → file_operation（不能破坏现有识别）"""
        message = "查看文件内容"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "file_operation"
        assert result["suggest_tools"] is True
        assert result["layer"] == "factual_need"
        assert result["confidence"] == 0.9

    def test_general_chat_unaffected(self, analyzer):
        """测试：今天天气怎么样 → general_chat（无工具建议）"""
        message = "今天天气怎么样"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "general_chat"
        assert result["suggest_tools"] is False
        assert result["layer"] == "self_check"
        assert result["confidence"] == 0.5


class TestPackageManagerAdditionalScenarios:
    """额外的包管理场景测试"""

    def test_requirements_check(self, analyzer):
        """测试：检查 requirements.txt"""
        message = "查看 requirements.txt 里的依赖"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True

    def test_pip_install(self, analyzer):
        """测试：pip install 命令"""
        message = "帮我安装 requests 包"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True

    def test_npm_update(self, analyzer):
        """测试：npm update"""
        message = "更新所有 npm 依赖"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True

    def test_package_version_check(self, analyzer):
        """测试：查看包版本"""
        message = "flask 是什么版本"
        result = analyzer.analyze(message)
        
        assert result["intent"] == "package_management"
        assert result["suggest_tools"] is True
