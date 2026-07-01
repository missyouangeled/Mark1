"""smart_crusher.py 测试群。

覆盖:
  - get_smartcrusher() 工厂 (单例)
  - smartcrush(content) 包装函数

设计:
  - 实际: SmartCrusher 是 JSON 压缩器 (Headroom 风格)
    - 纯 JSON 路径: 截断数组/字符串/深度
    - 非 JSON 走 mixed 路径: 截断 50 行
  - meta 字段: algorithm / original_bytes / crushed_bytes /
    arrays_truncated / strings_truncated / depth_truncated /
    numeric_arrays_compressed / is_pure_json / ratio / mode
"""

import json as _json
import runpy
import warnings

import pytest

from mark42_modules import smart_crusher


class TestSmartCrusherFactory:
    """get_smartcrusher() 工厂测试群。"""

    def test_factory_singleton(self):
        c1 = smart_crusher.get_smartcrusher()
        c2 = smart_crusher.get_smartcrusher()
        assert c1 is c2

    def test_factory_returns_instance(self):
        comp = smart_crusher.get_smartcrusher()
        assert comp is not None
        assert hasattr(comp, "crush")


class TestSmartcrushJSON:
    """JSON 路径测试群。"""

    def test_pure_json(self):
        """合法 JSON 字符串 -> is_pure_json=True。"""
        obj = {"a": 1, "b": [1, 2, 3]}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert meta["is_pure_json"] is True
        assert isinstance(result, str)
        # 压缩后仍是合法 JSON
        parsed = _json.loads(result)
        assert parsed["a"] == 1

    def test_long_array_truncated(self):
        """长数组 (> max_array_len=5) -> 截断 + 标记。

        注意: 纯数字数组走 numeric_array 路径 (压缩为 summary),
        不会触发 arrays_truncated。要测 arrays_truncated 用字符串数组。
        """
        obj = {"items": ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert meta["is_pure_json"] is True
        # 数组被截断
        assert meta["arrays_truncated"] >= 1
        # 解析后, items 应是 head 5 + summary
        parsed = _json.loads(result)
        assert isinstance(parsed["items"], list)
        # head 5 + 1 summary 字符串
        assert len(parsed["items"]) == 6

    def test_long_string_truncated(self):
        """长字符串 (> max_string_len=200) -> 截断 + 标记。"""
        obj = {"text": "x" * 500}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert meta["strings_truncated"] >= 1
        parsed = _json.loads(result)
        # 字符串以 ... 结尾
        assert parsed["text"].endswith("truncated)")

    def test_numeric_array_compressed(self):
        """长数字数组 (> max_numeric_array_len=50) -> 压缩为 summary。"""
        obj = {"nums": list(range(100))}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert meta["is_pure_json"] is True
        # 数字数组被压缩
        assert meta["numeric_arrays_compressed"] >= 1
        parsed = _json.loads(result)
        # 数字数组被替换为字符串 summary
        assert "numeric array" in str(parsed["nums"])

    def test_nested_depth_truncated(self):
        """深度嵌套 (> max_depth=3) -> 截断。"""
        # 构造 5 层嵌套
        obj = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert meta["depth_truncated"] >= 1


class TestSmartcrushMixed:
    """非 JSON 路径 (mixed_lines) 测试群。"""

    def test_mixed_text_truncated_at_50_lines(self):
        """非 JSON 文本, 行数 > 50 -> 截断到 50 行 + summary。"""
        lines = "\n".join([f"line {i}" for i in range(100)])
        result, meta = smart_crusher.smartcrush(lines)
        assert meta["is_pure_json"] is False
        assert meta["mode"] == "mixed_lines"
        # 截断后应包含 "... (50 more lines..." 标记
        assert "more lines" in result

    def test_short_mixed_text_unchanged(self):
        """< 50 行的非 JSON 文本 -> 不变。"""
        lines = "\n".join([f"line {i}" for i in range(20)])
        result, meta = smart_crusher.smartcrush(lines)
        assert result == lines
        assert meta["mode"] == "mixed_lines"


class TestSmartcrushMetadata:
    """通用 meta 字段测试群。"""

    def test_metadata_contains_saved_bytes(self):
        """meta 含 original_bytes / crushed_bytes / ratio。

        注意: 压缩版用 indent=2, 小 JSON 反而比原始更大 (ratio < 0),
        测 actual ratio, 不强求 ratio >= 0。
        """
        obj = {"a": 1, "b": 2}
        result, meta = smart_crusher.smartcrush(_json.dumps(obj))
        assert "original_bytes" in meta
        assert "crushed_bytes" in meta
        assert "ratio" in meta
        # original/crushed 是正整数
        assert meta["original_bytes"] > 0
        assert meta["crushed_bytes"] > 0
        # 压缩后 (带 indent) 可能比原文大, ratio 可负
        # 限制在合理范围 (-1, 1) 即可
        assert -1.0 <= meta["ratio"] <= 1.0

    def test_empty_content(self):
        """空字符串 -> ratio=0, 不崩。"""
        result, meta = smart_crusher.smartcrush("")
        assert result == ""
        assert meta["ratio"] == 0.0

    def test_returns_tuple(self):
        """返回值必须是 2-tuple。"""
        obj = {"a": 1}
        result = smart_crusher.smartcrush(_json.dumps(obj))
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_serialization_failure_returns_original_and_error(self, mocker):
        """json.dumps 失败时应返回原文并写入 error 字段。"""
        crusher = smart_crusher.SmartCrusher()
        mocker.patch.object(smart_crusher.json, "loads", return_value={"ok": True})
        mocker.patch.object(smart_crusher.json, "dumps", side_effect=TypeError("bad dump"))

        out, meta = crusher.crush('{"ok": true}')

        assert out == '{"ok": true}'
        assert meta["ratio"] == 0.0
        assert meta["error"] == "serialization failed: bad dump"


class TestSmartCrusherHelpers:
    """补空数值数组与 _run_tests() 自检链路。"""

    def test_compress_numeric_array_empty_returns_brackets(self):
        crusher = smart_crusher.SmartCrusher()

        out = crusher._compress_numeric_array([])

        assert out == "[]"

    def test_run_tests_smoke(self, capsys):
        smart_crusher._run_tests()

        out = capsys.readouterr().out
        assert "SmartCrusher 单元测试" in out
        assert "[测试 1]" in out
        assert "[测试 6]" in out
        assert "所有测试通过 ✓" in out

    def test_module_main_runs_run_tests(self, capsys):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            runpy.run_module("mark42_modules.smart_crusher", run_name="__main__")

        out = capsys.readouterr().out
        assert "SmartCrusher 单元测试" in out
        assert "所有测试通过 ✓" in out
