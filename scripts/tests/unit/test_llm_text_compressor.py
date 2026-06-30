"""llm_text_compressor.py 测试群。

覆盖:
  - get_llm_text_compressor(mode) 工厂 (按 mode 缓存)
  - _clean_llm_output(content) 顶层函数 (剥离 <think> / markdown)
  - llm_text_compress(content, mode) 包装函数

设计:
  - 不真调 LLM (测试用 mock 或短文本 passthrough)
  - 短文本 (< min_text_size=500) 直接 passthrough, 不调 LLM
  - 异步版本略过 (单测聚焦同步路径)
"""

import asyncio

import pytest

from mark42_modules import llm_text_compressor


class TestLLMTextCompressorFactory:
    """get_llm_text_compressor() 工厂测试群 (按 mode 缓存)。"""

    def test_factory_singleton_same_mode(self):
        c1 = llm_text_compressor.get_llm_text_compressor("summarize")
        c2 = llm_text_compressor.get_llm_text_compressor("summarize")
        assert c1 is c2

    def test_factory_different_mode_rebuilds(self):
        """不同 mode 调用应触发重建 (实际实现)。"""
        c1 = llm_text_compressor.get_llm_text_compressor("summarize")
        c2 = llm_text_compressor.get_llm_text_compressor("extract")
        # 不同 mode -> 不是同对象
        assert c1 is not c2

    def test_factory_returns_instance(self):
        c = llm_text_compressor.get_llm_text_compressor("summarize")
        assert c is not None
        assert hasattr(c, "compress")

    def test_factory_invalid_mode_raises(self):
        """未知 mode 应在 __init__ 抛 ValueError。"""
        with pytest.raises(ValueError, match="unknown mode"):
            llm_text_compressor.LLMTextCompressor(mode="bogus_mode")


class TestCleanLLMOutput:
    """_clean_llm_output() 文本清洗测试群。"""

    def test_strips_think_blocks(self):
        text = "<think>内部思考</think>最终答案"
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert "<think>" not in cleaned
        assert "最终答案" in cleaned

    def test_preserves_normal_text(self):
        text = "正常文本, 没有特殊块。"
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert cleaned == text.strip()

    def test_handles_empty(self):
        assert llm_text_compressor._clean_llm_output("") == ""
        assert llm_text_compressor._clean_llm_output(None) == ""  # type: ignore

    def test_strips_whitespace(self):
        text = "  \n  实际内容  \n  "
        cleaned = llm_text_compressor._clean_llm_output(text)
        assert cleaned == "实际内容"

    def test_strips_markdown_block(self):
        """markdown 代码块包裹的内容应被剥离。"""
        text = "```\n实际内容\n```"
        cleaned = llm_text_compressor._clean_llm_output(text)
        # markdown 包裹应被剥
        assert "实际内容" in cleaned
        assert "```" not in cleaned


class TestLLMTextCompress:
    """llm_text_compress() 包装函数测试群。"""

    def test_short_text_passthrough(self):
        """短文本 (< min_text_size=500) 直接 passthrough。"""
        text = "短"
        result, meta = llm_text_compressor.llm_text_compress(text)
        # 短文本不走 LLM, status='passthrough_small'
        assert result == text
        assert meta.get("status") == "passthrough_small"

    def test_returns_tuple(self):
        """返回值是 2-tuple。"""
        text = "短"
        result = llm_text_compressor.llm_text_compress(text)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_metadata_contains_algorithm(self, sample_long_text):
        """meta['algorithm'] = 'llm_text_compress'。"""
        # sample_long_text 是 5KB 中文, 会走 LLM 或 fallback
        # 这里只测 metadata 结构, 不要求真 LLM 调通
        result, meta = llm_text_compressor.llm_text_compress(sample_long_text)
        # algorithm 字段必有
        assert "algorithm" in meta
        assert meta["algorithm"] == "llm_text_compress"


class TestLLMTextCompressAsync:
    """异步版本测试群 (不入队, 只验证接口)。"""

    def test_async_function_exists(self):
        """异步入口应存在。"""
        assert hasattr(llm_text_compressor, "llm_text_compress_async")
        assert callable(llm_text_compressor.llm_text_compress_async)
