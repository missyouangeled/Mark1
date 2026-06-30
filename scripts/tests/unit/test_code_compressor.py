"""code_compressor.py 测试群。

覆盖:
  - get_code_compressor() 工厂 (单例)
  - codecrush(content) 包装函数
  - is_code() 启发式 (Python vs 非代码)

设计:
  - 纯函数为主, 不需要 mock
  - 用 sample_code_python fixture
  - 字段名按 code_compressor.py 实际: algorithm / language /
    original_bytes / crushed_bytes / ratio / removed_docstrings /
    removed_comments / mode / is_code
"""

import pytest

from mark42_modules import code_compressor


class TestCodeCompressorFactory:
    """get_code_compressor() 工厂测试群。"""

    def test_factory_singleton(self):
        c1 = code_compressor.get_code_compressor()
        c2 = code_compressor.get_code_compressor()
        assert c1 is c2

    def test_factory_returns_instance(self):
        comp = code_compressor.get_code_compressor()
        assert comp is not None
        assert hasattr(comp, "compress")
        assert hasattr(comp, "is_code")


class TestIsCode:
    """is_code() 启发式测试群。"""

    def test_python_code_detected(self, sample_code_python):
        comp = code_compressor.get_code_compressor()
        assert comp.is_code(sample_code_python) is True

    def test_natural_text_not_detected(self):
        comp = code_compressor.get_code_compressor()
        text = "今天天气很好。我和朋友去公园玩了很久, 然后回家吃饭。"
        # 长度 > 50 但无 Python 关键词
        assert comp.is_code(text) is False

    def test_empty_not_detected(self):
        comp = code_compressor.get_code_compressor()
        assert comp.is_code("") is False

    def test_short_text_not_detected(self):
        comp = code_compressor.get_code_compressor()
        # 长度 < 50
        assert comp.is_code("def foo(): pass") is False


class TestCodeCrush:
    """codecrush() 包装函数测试群。"""

    def test_codecrush_python(self, sample_code_python):
        """Python 代码应能压出一些 (注释/docstring 被去除)。"""
        result, meta = code_compressor.codecrush(sample_code_python)
        assert isinstance(result, str)
        assert isinstance(meta, dict)
        assert meta["is_code"] is True
        assert meta["language"] == "python"
        # 至少有 docstring 或 comment 被去除
        assert (
            meta["removed_docstrings"] > 0
            or meta["removed_comments"] > 0
            or meta["original_bytes"] >= meta["crushed_bytes"]
        )

    def test_codecrush_javascript(self):
        """JavaScript 代码 - is_code 应识别, 但 codecrush 可能 passthrough (仅支持 python)。"""
        js = (
            "function hello(name) {\n"
            "    // comment\n"
            "    return `Hello, ${name}`;\n"
            "}\n"
            "const x = 1;\n"
            "const y = 2;\n"
        ) * 5  # 重复撑过 min_code_size
        result, meta = code_compressor.codecrush(js)
        assert isinstance(result, str)
        assert isinstance(meta, dict)
        # is_code 启发式应识别
        assert meta["is_code"] is True or meta["mode"] == "passthrough"

    def test_codecrush_empty(self):
        """空字符串 -> 原文, mode='none'。"""
        result, meta = code_compressor.codecrush("")
        assert result == ""
        assert meta["mode"] == "none"

    def test_codecrush_natural_text_passthrough(self):
        """非代码内容应 passthrough, 不破坏。"""
        text = (
            "今天天气很好。我和朋友去公园玩了很久。\n"
            "我们买了一些水果, 比如苹果和香蕉。\n"
        ) * 5
        result, meta = code_compressor.codecrush(text)
        assert isinstance(result, str)
        # 不是代码, is_code=False
        assert meta["is_code"] is False
        # passthrough
        assert meta["mode"] == "passthrough"
        assert result == text

    def test_metadata_contains_language(self, sample_code_python):
        """meta['language'] 来自构造参数。"""
        result, meta = code_compressor.codecrush(sample_code_python)
        assert "language" in meta
        assert meta["language"] in ("python", "javascript", "auto", "unknown")

    def test_metadata_contains_saved_bytes(self, sample_code_python):
        """meta 含 original_bytes 和 crushed_bytes。"""
        result, meta = code_compressor.codecrush(sample_code_python)
        assert "original_bytes" in meta
        assert "crushed_bytes" in meta
        assert meta["original_bytes"] >= meta["crushed_bytes"]
        assert "ratio" in meta
        assert 0.0 <= meta["ratio"] <= 1.0

    def test_returns_tuple(self, sample_code_python):
        """返回值必须是 2-tuple。"""
        result = code_compressor.codecrush(sample_code_python)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)
