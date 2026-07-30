"""
code_analyzer.py 单元测试
测试所有公开函数和类：
- CodeBug 数据类
- AnalysisResult 数据类
- CodeAnalyzer
- CLI 函数
"""

import json
from unittest.mock import MagicMock, patch

from mark42.code_analyzer import (
    AnalysisResult,
    CodeAnalyzer,
    CodeBug,
    cli_analyze_code,
    cli_analyze_file,
)


class TestCodeBug:
    """测试 CodeBug 数据类。"""

    def test_code_bug_creation_default(self):
        """测试使用默认值创建 CodeBug。"""
        bug = CodeBug()
        assert bug.line == 0
        assert bug.severity == "info"
        assert bug.desc == ""

    def test_code_bug_creation_custom(self):
        """测试自定义 CodeBug。"""
        bug = CodeBug(line=42, severity="critical", desc="空指针异常")
        assert bug.line == 42
        assert bug.severity == "critical"
        assert bug.desc == "空指针异常"


class TestAnalysisResult:
    """测试 AnalysisResult 数据类。"""

    def test_analysis_result_default(self):
        """测试默认值创建。"""
        result = AnalysisResult()
        assert result.bugs == []
        assert result.quality_score == 0
        assert result.summary == ""
        assert result.suggestions == []
        assert result.elapsed_ms == 0
        assert result.error is None

    def test_analysis_result_with_bugs(self):
        """测试带 bugs 的结果。"""
        bugs = [CodeBug(line=10, severity="warning", desc="未使用变量")]
        result = AnalysisResult(
            bugs=bugs,
            quality_score=8,
            summary="简单的数学计算",
            suggestions=["添加类型注解"],
            elapsed_ms=150,
        )
        assert len(result.bugs) == 1
        assert result.quality_score == 8
        assert result.summary == "简单的数学计算"
        assert result.elapsed_ms == 150

    def test_has_critical_bug_true(self):
        """测试存在 critical bug。"""
        bugs = [
            CodeBug(line=10, severity="warning", desc="警告"),
            CodeBug(line=20, severity="critical", desc="严重错误"),
        ]
        result = AnalysisResult(bugs=bugs)
        assert result.has_critical_bug is True

    def test_has_critical_bug_false(self):
        """测试不存在 critical bug。"""
        bugs = [CodeBug(line=10, severity="warning", desc="警告")]
        result = AnalysisResult(bugs=bugs)
        assert result.has_critical_bug is False

    def test_has_critical_bug_no_bugs(self):
        """测试没有 bugs 时返回 False。"""
        result = AnalysisResult()
        assert result.has_critical_bug is False

    def test_to_dict(self):
        """测试 to_dict 方法。"""
        result = AnalysisResult(
            bugs=[CodeBug(line=5, severity="info", desc="测试")],
            quality_score=7,
            summary="测试代码",
            suggestions=["改进1"],
            elapsed_ms=100,
            error=None,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["quality_score"] == 7
        assert d["summary"] == "测试代码"
        assert len(d["bugs"]) == 1
        assert d["elapsed_ms"] == 100
        assert d["error"] is None


class TestCodeAnalyzer:
    """测试 CodeAnalyzer 主类。"""

    def test_code_analyzer_init_default(self):
        """测试默认初始化。"""
        with patch('mark42.code_analyzer.load_config') as mock_load:
            with patch('mark42.code_analyzer.build_consciousness') as mock_build:
                mock_load.return_value = {"model": "test"}
                mock_build.return_value = MagicMock()
                analyzer = CodeAnalyzer()
                assert analyzer.config is not None
                assert analyzer.llm is not None

    def test_code_analyzer_with_custom_config(self):
        """测试自定义配置。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_build.return_value = MagicMock()
            analyzer = CodeAnalyzer(config={"custom": "config"})
            assert analyzer.config == {"custom": "config"}

    def test_code_analyzer_no_llm(self):
        """测试 LLM provider 不可用时。"""
        with patch('mark42.code_analyzer.load_config') as mock_load:
            with patch('mark42.code_analyzer.build_consciousness') as mock_build:
                mock_load.return_value = {}
                mock_build.return_value = None
                analyzer = CodeAnalyzer()
                result = analyzer.analyze("print('hello')")
                assert result.error == "LLM provider 不可用"

    def test_analyze_empty_code(self):
        """测试分析空代码。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_build.return_value = MagicMock()
            analyzer = CodeAnalyzer()
            result = analyzer.analyze("   ")
            assert result.error == "代码为空"

    def test_analyze_llm_exception(self):
        """测试 LLM 调用异常。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_llm.chat.side_effect = Exception("API 调用失败")
            mock_build.return_value = mock_llm
            analyzer = CodeAnalyzer()
            result = analyzer.analyze("print('hello')")
            assert "LLM 调用失败" in result.error

    def test_analyze_success_with_content_attribute(self):
        """测试成功分析（响应有 content 属性）。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({
                "bugs": [{"line": 1, "severity": "info", "desc": "test"}],
                "quality_score": 8,
                "summary": "测试代码",
                "suggestions": ["改进建议"]
            })
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1 + 1")

            assert result.error is None
            assert result.quality_score == 8
            assert result.summary == "测试代码"
            assert len(result.bugs) == 1

    def test_analyze_success_with_dict_response(self):
        """测试成功分析（响应是字典格式）。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "bugs": [],
                            "quality_score": 10,
                            "summary": "完美代码",
                            "suggestions": []
                        })
                    }
                }]
            }
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1 + 1")

            assert result.error is None
            assert result.quality_score == 10

    def test_analyze_empty_response_content(self):
        """测试 LLM 返回空内容。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = ""
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1")

            assert result.error == "LLM 返回空"

    def test_analyze_markdown_wrapped_response(self):
        """测试响应被 markdown ``` 包裹。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = "```json\n" + json.dumps({
                "bugs": [],
                "quality_score": 9,
                "summary": "markdown 包裹",
                "suggestions": []
            }) + "\n```"
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1")

            assert result.error is None
            assert result.quality_score == 9

    def test_analyze_invalid_json(self):
        """测试 JSON 解析失败。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = "这不是 JSON"
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1")

            assert "JSON 解析失败" in result.error

    def test_analyze_missing_fields(self):
        """测试 JSON 缺少字段时使用默认值。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = "{}"  # 空 JSON
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze("x = 1")

            assert result.error is None
            assert result.quality_score == 0
            assert result.bugs == []
            assert result.suggestions == []

    @patch('mark42.code_analyzer.Path.exists')
    def test_analyze_file_not_exists(self, mock_exists):
        """测试分析不存在的文件。"""
        mock_exists.return_value = False
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_build.return_value = MagicMock()
            analyzer = CodeAnalyzer()
            result = analyzer.analyze_file("/nonexistent/file.py")
            assert "文件不存在" in result.error

    @patch('mark42.code_analyzer.Path.exists')
    @patch('mark42.code_analyzer.Path.read_text')
    def test_analyze_file_success(self, mock_read, mock_exists):
        """测试成功分析文件。"""
        mock_exists.return_value = True
        mock_read.return_value = "x = 1 + 1"

        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({
                "bugs": [],
                "quality_score": 10,
                "summary": "简单计算",
                "suggestions": []
            })
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze_file("/path/test.py")

            assert result.error is None
            assert result.quality_score == 10

    @patch('mark42.code_analyzer.Path.exists')
    @patch('mark42.code_analyzer.Path.read_text')
    def test_analyze_file_language_detection(self, mock_read, mock_exists):
        """测试根据文件扩展名检测语言。"""
        mock_exists.return_value = True
        mock_read.return_value = "console.log('hello')"

        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({
                "bugs": [], "quality_score": 10, "summary": "", "suggestions": []
            })
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            # 不指定语言，应该根据 .js 后缀推断
            result = analyzer.analyze_file("/path/test.js")
            assert result.error is None

    @patch('mark42.code_analyzer.Path.exists')
    @patch('mark42.code_analyzer.Path.read_text')
    def test_analyze_file_unknown_extension(self, mock_read, mock_exists):
        """测试未知文件扩展名使用 text。"""
        mock_exists.return_value = True
        mock_read.return_value = "some content"

        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({
                "bugs": [], "quality_score": 10, "summary": "", "suggestions": []
            })
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            result = analyzer.analyze_file("/path/test.unknown")
            assert result.error is None

    def test_health_check_success(self):
        """测试健康检查成功。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.content = json.dumps({
                "bugs": [], "quality_score": 10, "summary": "", "suggestions": []
            })
            mock_llm.chat.return_value = mock_resp
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            assert analyzer.health_check() is True

    def test_health_check_failure(self):
        """测试健康检查失败。"""
        with patch('mark42.code_analyzer.build_consciousness') as mock_build:
            mock_llm = MagicMock()
            mock_llm.chat.side_effect = Exception("error")
            mock_build.return_value = mock_llm

            analyzer = CodeAnalyzer()
            assert analyzer.health_check() is False


class TestCLI:
    """测试 CLI 接口函数。"""

    @patch('mark42.code_analyzer.build_consciousness')
    def test_cli_analyze_code(self, mock_build):
        """测试 CLI 分析代码。"""
        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps({
            "bugs": [], "quality_score": 8, "summary": "CLI 测试", "suggestions": []
        })
        mock_llm.chat.return_value = mock_resp
        mock_build.return_value = mock_llm

        result = cli_analyze_code("x = 1 + 1", "python")

        assert isinstance(result, dict)
        assert result["quality_score"] == 8
        assert result["summary"] == "CLI 测试"

    @patch('mark42.code_analyzer.Path.exists')
    @patch('mark42.code_analyzer.Path.read_text')
    @patch('mark42.code_analyzer.build_consciousness')
    def test_cli_analyze_file(self, mock_build, mock_read, mock_exists):
        """测试 CLI 分析文件。"""
        mock_exists.return_value = True
        mock_read.return_value = "x = 1"

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = json.dumps({
            "bugs": [], "quality_score": 9, "summary": "CLI 文件测试", "suggestions": []
        })
        mock_llm.chat.return_value = mock_resp
        mock_build.return_value = mock_llm

        result = cli_analyze_file("/path/test.py")

        assert isinstance(result, dict)
        assert result["quality_score"] == 9
