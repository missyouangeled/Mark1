"""text_compressor.py 测试群。

覆盖:
  - get_text_compressor() 工厂 (单例)
  - text_compress(content) 包装函数 (输入字符串 -> (压缩后, 元数据 dict))

设计:
  - 纯函数为主, 不需要 mock
  - 异常输入用 pytest.raises
  - meta 字段名按 text_compressor.py 实际: algorithm / original_bytes /
    crushed_bytes / ratio / mode / method
"""

import pytest

from mark42_modules import text_compressor


class TestTextCompressorFactory:
    """get_text_compressor() 工厂测试群。"""

    def test_factory_returns_instance(self):
        comp = text_compressor.get_text_compressor()
        assert comp is not None
        assert hasattr(comp, "compress")

    def test_factory_singleton(self):
        c1 = text_compressor.get_text_compressor()
        c2 = text_compressor.get_text_compressor()
        assert c1 is c2


class TestTextCompress:
    """text_compress() 包装函数测试群。"""

    def test_compress_normal_text(self, sample_long_text):
        """5KB 中文长文本应被压缩, ratio > 0。"""
        result, meta = text_compressor.text_compress(sample_long_text)
        assert isinstance(result, str)
        assert isinstance(meta, dict)
        assert "ratio" in meta
        assert 0.0 <= meta["ratio"] <= 1.0
        # 重复 "测试内容 " 4 字节, 长 5KB 应能压出一些
        assert meta["ratio"] > 0.0

    def test_compress_empty_text(self):
        """空字符串 -> 原文, 模式 'none'。"""
        result, meta = text_compressor.text_compress("")
        assert result == ""
        assert isinstance(meta, dict)
        assert meta.get("mode") == "none"

    def test_compress_repetitive_text(self, sample_repetitive_text):
        """重复段落应被去重, crushed_bytes < original_bytes。"""
        result, meta = text_compressor.text_compress(sample_repetitive_text)
        assert isinstance(result, str)
        assert meta["original_bytes"] > meta["crushed_bytes"]
        assert meta["ratio"] > 0.0

    def test_compress_chinese_text(self):
        """中文长文本 (50 行重复) 应能压出一些。

        注意: text_compressor 是行级算法, 重复内容必须换行才被识别。
        写在一行 50 次的字符串无法压出 — 那是 test_compress_repetitive_text 的领域。
        """
        line = "今天天气很好，适合出去走走。"
        text = "\n".join([line] * 50)
        result, meta = text_compressor.text_compress(text)
        # 中文不破坏 (短语应在)
        assert "今天天气" in result
        # 50 行重复, 应有压缩 (连续行去重至少 1 行)
        assert meta["original_bytes"] > meta["crushed_bytes"] or meta["dedup_repeat_lines"] > 0

    def test_metadata_contains_method(self, sample_long_text):
        """meta['method'] 来自构造参数。"""
        result, meta = text_compressor.text_compress(sample_long_text)
        assert "method" in meta
        assert meta["method"] in ("rule_based", "llm")

    def test_metadata_contains_mode(self, sample_long_text):
        """meta['mode'] 描述实际走的分支。"""
        result, meta = text_compressor.text_compress(sample_long_text)
        assert "mode" in meta
        # 合法 mode 集合 (从 _run_tests + compress 实现确认)
        valid_modes = {
            "none",                                    # 空文本
            "passthrough_small",                       # 短文本直通
            "rule_based_phrase_removal",               # 规则 - 水话删除
            "rule_based_synonym",                      # 规则 - 同义词
            "rule_based_number_unit",                  # 规则 - 数字单位
            "rule_based_repeat_dedup",                 # 规则 - 重复行去重
            "rule_based_combined",                     # 规则 - 组合
            "fallback_low_ratio",                      # 压缩率太低回退
            "error",                                   # 异常
            "llm_module_unavailable",                  # LLM 模式无模块
            "llm_ok", "llm_error", "llm_unknown",      # LLM 状态
        }
        assert meta["mode"] in valid_modes, f"unexpected mode: {meta['mode']}"

    def test_short_text_passthrough(self):
        """短文本 (< 200 字节) 直接 passthrough, 字节数不变。"""
        text = "短"
        result, meta = text_compressor.text_compress(text)
        assert result == text
        assert meta["mode"] == "passthrough_small"
        assert meta["original_bytes"] == meta["crushed_bytes"]

    def test_returns_tuple(self, sample_long_text):
        """返回值必须是 2-tuple。"""
        result = text_compressor.text_compress(sample_long_text)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)
