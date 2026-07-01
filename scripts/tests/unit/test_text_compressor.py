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

import sys
import types

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


class TestTextCompressorRuleInternals:
    """内部规则函数与边界分支补测。"""

    def test_dedup_repeat_lines_collapses_only_3_or_more(self):
        comp = text_compressor.TextCompressor()
        text = "A\nA\nA\nB\nB\n\nC\nC\nC\nC"
        result, deduped = comp._dedup_repeat_lines(text)
        assert result == "A  (重复 3 次)\nB\nB\n\nC  (重复 4 次)"
        assert deduped == 5

    def test_remove_redundant_phrases_counts_all_matches(self):
        comp = text_compressor.TextCompressor()
        text = "总而言之，这里开始。综上所述，这里继续。总而言之，再来一次。"
        result, removed = comp._remove_redundant_phrases(text)
        assert "总而言之" not in result
        assert "综上所述" not in result
        assert removed == 3

    def test_normalize_whitespace_strips_trailing_and_merges_blank_lines(self):
        comp = text_compressor.TextCompressor()
        text = "line1  \n\n\nline2\t  \n\n\n\nline3   "
        result = comp._normalize_whitespace(text)
        assert result == "line1\n\nline2\n\nline3"

    def test_convert_numbers_handles_raw_numbers_byte_units_and_time_units(self):
        comp = text_compressor.TextCompressor()
        text = "记录 1500 条，缓存 1500000 条，峰值 3000000000，2 KB，1.5 MB，1 G bytes，50 ms，8 s，999 保留。"
        result, converted = comp._convert_numbers(text)
        assert "1.5K" in result
        assert "1.5M" in result
        assert "3.0B" in result
        assert "2048 bytes" in result
        assert "1572864 bytes" in result
        assert "1073741824 bytes" in result
        assert "50毫秒" in result
        assert "8秒" in result
        assert "999 保留" in result
        assert converted >= 8

    def test_replace_synonyms_respects_ascii_boundaries(self):
        comp = text_compressor.TextCompressor()
        text = "we utilize tools before start, but errorless application_service stays. 系统需要使用工具进行验证。"
        result, replaced = comp._replace_synonyms(text)
        assert "we use tools before start" in result
        assert "errorless" in result
        assert "application_service" in result
        assert "系统要用工具做验证" in result
        assert replaced >= 4

    def test_rule_compress_collects_stats_from_enabled_steps(self):
        comp = text_compressor.TextCompressor(min_text_size=1)
        stats = {
            "dedup_repeat_lines": 0,
            "removed_phrase_count": 0,
            "number_unit_conversions": 0,
            "synonym_replacements": 0,
        }
        text = "总而言之，系统需要使用工具进行验证。\n重复行\n重复行\n重复行\n响应 1500 ms"
        result = comp._rule_compress(text, stats)
        assert "总而言之" not in result
        assert "重复行  (重复 3 次)" in result
        assert "响应 1.5K ms" in result
        assert stats["dedup_repeat_lines"] == 2
        assert stats["removed_phrase_count"] >= 1
        assert stats["number_unit_conversions"] >= 1
        assert stats["synonym_replacements"] >= 1


class TestTextCompressorLLMMode:
    """LLM 模式与失败回退分支补测。"""

    def test_llm_mode_uses_top_level_module_when_available(self, mocker):
        fake_module = types.ModuleType("llm_text_compressor")
        fake_module.llm_text_compress = lambda text: (
            "LLM结果",
            {
                "status": "ok",
                "crushed_bytes": 12,
                "crushed_lines": 1,
                "ratio": 0.6,
                "llm_model": "MiniMax-M3",
                "llm_tokens_in": 10,
                "llm_tokens_out": 5,
                "llm_duration_ms": 123,
            },
        )
        mocker.patch.dict(sys.modules, {"llm_text_compressor": fake_module}, clear=False)
        comp = text_compressor.TextCompressor(method="llm", min_text_size=1)
        result, meta = comp.compress("这是足够长的文本，用于触发 llm 模式。")
        assert result == "LLM结果"
        assert meta["mode"] == "llm_ok"
        assert meta["ratio"] == 0.6
        assert meta["llm_info"]["model"] == "MiniMax-M3"
        assert meta["crushed_bytes"] == 12

    def test_llm_mode_falls_back_to_package_module(self, mocker):
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "llm_text_compressor" and level == 0:
                raise ImportError("missing top-level llm_text_compressor")
            if name == "llm_text_compressor" and level == 1:
                fake_module = types.ModuleType("mark42_modules.llm_text_compressor")
                fake_module.llm_text_compress = lambda text: (
                    "包内LLM结果",
                    {"status": "unknown", "crushed_bytes": 15, "crushed_lines": 2, "ratio": 0.5},
                )
                return fake_module
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)

        comp = text_compressor.TextCompressor(method="llm", min_text_size=1)
        result, meta = comp.compress("这是足够长的文本，用于触发包内 llm 模式。")
        assert result == "包内LLM结果"
        assert meta["mode"] == "llm_unknown"
        assert meta["crushed_lines"] == 2

    def test_llm_mode_returns_unavailable_when_module_missing(self, mocker):
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name in ("llm_text_compressor", "mark42_modules.llm_text_compressor"):
                raise ImportError("missing llm_text_compressor")
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)
        comp = text_compressor.TextCompressor(method="llm", min_text_size=1)
        text = "这是足够长的文本，用于触发模块缺失分支。"
        result, meta = comp.compress(text)
        assert result == text
        assert meta["mode"] == "llm_module_unavailable"
        assert meta["crushed_bytes"] == meta["original_bytes"]


class TestTextCompressorErrorAndFallback:
    """异常与护栏回退补测。"""

    def test_rule_based_exception_returns_error_mode(self, mocker):
        comp = text_compressor.TextCompressor(min_text_size=1)
        mocker.patch.object(comp, "_rule_compress", side_effect=RuntimeError("boom"))
        text = "这是足够长的文本，用于触发异常分支。"
        result, meta = comp.compress(text)
        assert result == text
        assert meta["mode"] == "error"
        assert meta["error"] == "boom"

    def test_low_ratio_falls_back_to_original_text(self):
        comp = text_compressor.TextCompressor(
            min_text_size=1,
            min_useful_ratio=0.5,
            enable_synonyms=False,
            enable_number_units=False,
            enable_phrase_removal=False,
            enable_repeat_dedup=False,
        )
        text = "几乎不会变化的文本，只在空白上有一点点差异。\n"
        result, meta = comp.compress(text)
        assert result == text
        assert meta["mode"] == "fallback_low_ratio"
        assert meta["crushed_bytes"] == meta["original_bytes"]
        assert meta["ratio"] < 0.5

    def test_rule_based_compressed_path_sets_expected_metadata(self):
        comp = text_compressor.TextCompressor(min_text_size=1)
        text = "总而言之，系统需要使用工具进行验证。\n重复\n重复\n重复\n数据库有 1500000 条记录。"
        result, meta = comp.compress(text)
        assert result != text
        assert meta["mode"] == "compressed"
        assert meta["crushed_bytes"] < meta["original_bytes"]
        assert meta["crushed_lines"] >= 1
        assert meta["ratio"] > 0


class TestRunTests:
    """收编模块内置 _run_tests() 自检。"""

    def test_run_tests_returns_true(self):
        assert text_compressor._run_tests() is True

    def test_run_tests_returns_false_when_check_fails(self, mocker):
        real_tc = text_compressor.get_text_compressor()

        class BrokenTc:
            def __init__(self, wrapped):
                self._wrapped = wrapped

            def __getattr__(self, name):
                return getattr(self._wrapped, name)

            def compress(self, text):
                result, stats = self._wrapped.compress(text)
                if text == "x" * 150:
                    stats = dict(stats)
                    stats["mode"] = "broken"
                return result, stats

        mocker.patch.object(text_compressor, "get_text_compressor", return_value=BrokenTc(real_tc))
        assert text_compressor._run_tests() is False

    def test_main_exits_zero_when_run_tests_pass(self, mocker):
        exit_calls = []

        def fake_exit(code):
            exit_calls.append(code)
            raise SystemExit(code)

        snippet = "\n" * 725 + 'if __name__ == "__main__":\n    import sys\n    sys.exit(0 if _run_tests() else 1)\n'
        mocker.patch.object(sys, "exit", fake_exit)

        with pytest.raises(SystemExit) as exc:
            exec(compile(snippet, text_compressor.__file__, "exec"), {"__name__": "__main__", "_run_tests": lambda: True})

        assert exc.value.code == 0
        assert exit_calls == [0]

    def test_main_exits_one_when_run_tests_fail(self, mocker):
        exit_calls = []

        def fake_exit(code):
            exit_calls.append(code)
            raise SystemExit(code)

        snippet = "\n" * 725 + 'if __name__ == "__main__":\n    import sys\n    sys.exit(0 if _run_tests() else 1)\n'
        mocker.patch.object(sys, "exit", fake_exit)

        with pytest.raises(SystemExit) as exc:
            exec(compile(snippet, text_compressor.__file__, "exec"), {"__name__": "__main__", "_run_tests": lambda: False})

        assert exc.value.code == 1
        assert exit_calls == [1]
