"""Test output_guard.py 输出截断。"""

from mark42.output_guard import (
    _normalize_text,
    _trim,
    compact_preview,
    should_spill_to_file,
    trim_detail,
    trim_json_short,
    trim_summary,
)


class TestNormalizeText:
    """测试 _normalize_text 文本规范化"""

    def test_none_returns_empty_string(self):
        """None 返回空字符串"""
        result = _normalize_text(None)
        assert result == ""

    def test_removes_extra_spaces(self):
        """移除多余空格"""
        result = _normalize_text("  hello   world  ")
        assert result == "hello world"

    def test_normalize_windows_newlines(self):
        """规范化 Windows 换行 (\\r\\n)"""
        result = _normalize_text("line1\r\nline2")
        assert result == "line1 line2"

    def test_normalize_old_mac_newlines(self):
        """规范化旧 Mac 换行 (\\r)"""
        result = _normalize_text("line1\rline2")
        assert result == "line1 line2"

    def test_strips_each_line(self):
        """每行都去首尾空格，然后合并"""
        text = "  line1  \n  line2  \n  line3  "
        result = _normalize_text(text)
        assert result == "line1 line2 line3"

    def test_empty_lines_removed(self):
        """空行被移除"""
        text = "line1\n\n\nline2"
        result = _normalize_text(text)
        assert result == "line1 line2"

    def test_non_string_input(self):
        """非字符串输入（数字等）"""
        result = _normalize_text(12345)
        assert result == "12345"

    def test_whitespace_only(self):
        """仅空白字符"""
        result = _normalize_text("   \n  \t  \n   ")
        assert result == ""


class TestTrim:
    """测试 _trim 基础截断函数"""

    def test_within_limit_no_truncation(self):
        """内容在限制内不截断"""
        text = "hello"
        result = _trim(text, 10)
        assert result == "hello"
        assert "…" not in result

    def test_exceeds_limit_with_ellipsis(self):
        """超过限制时加省略号"""
        text = "hello world this is long"
        result = _trim(text, 10)
        assert len(result) <= 10
        assert result.endswith("…")

    def test_limit_one(self):
        """limit = 1 的边界情况"""
        text = "hello"
        result = _trim(text, 1)
        assert result == "h"
        assert "…" not in result  # limit <= 1 不加省略号

    def test_limit_zero(self):
        """limit = 0"""
        text = "hello"
        result = _trim(text, 0)
        assert result == ""

    def test_exact_limit(self):
        """刚好等于限制"""
        text = "hello"  # 5 chars
        result = _trim(text, 5)
        assert result == "hello"
        assert "…" not in result

    def test_preserves_normalization(self):
        """截断前先做规范化"""
        text = "  hello   world  this   is   long  "
        result = _trim(text, 15)
        assert "  " not in result  # 没有双空格
        assert result.endswith("…")

    def test_non_string_input(self):
        """非字符串输入"""
        result = _trim(1234567890, 5)
        assert result == "1234…"


class TestTrimSummary:
    """测试 trim_summary 摘要截断"""

    def test_default_limit_120(self):
        """默认限制 120 字符"""
        text = "a" * 200
        result = trim_summary(text)
        assert len(result) <= 120
        assert result.endswith("…")

    def test_custom_limit(self):
        """自定义限制"""
        text = "hello world this is a test"
        result = trim_summary(text, 10)
        assert len(result) <= 10

    def test_short_text_no_truncation(self):
        """短文本不截断"""
        text = "short"
        result = trim_summary(text)
        assert result == "short"

    def test_none_input(self):
        """None 输入"""
        result = trim_summary(None)
        assert result == ""

    def test_with_newlines(self):
        """包含换行的文本"""
        text = "line1\nline2\nline3\nline4\nline5"
        result = trim_summary(text, 15)
        assert "\n" not in result  # 规范化后无换行
        assert result.endswith("…")


class TestTrimDetail:
    """测试 trim_detail 详情截断"""

    def test_default_limit_280(self):
        """默认限制 280 字符"""
        text = "a" * 500
        result = trim_detail(text)
        assert len(result) <= 280
        assert result.endswith("…")

    def test_custom_limit(self):
        """自定义限制"""
        text = "hello world this is a detail"
        result = trim_detail(text, 15)
        assert len(result) <= 15

    def test_short_text_no_truncation(self):
        """短文本不截断"""
        text = "short detail"
        result = trim_detail(text)
        assert result == "short detail"

    def test_none_input(self):
        """None 输入"""
        result = trim_detail(None)
        assert result == ""

    def test_mixed_content(self):
        """混合中英文内容"""
        text = "你好世界 " * 50  # 250 chars
        result = trim_detail(text)
        assert len(result) <= 280


class TestCompactPreview:
    """测试 compact_preview 预览压缩"""

    def test_default_limit_160(self):
        """默认限制 160 字符"""
        text = "a" * 300
        result = compact_preview(text)
        assert len(result) <= 160
        assert result.endswith("…")

    def test_custom_limit(self):
        """自定义限制"""
        result = compact_preview("hello world", 5)
        assert len(result) <= 5

    def test_none_input(self):
        """None 输入"""
        result = compact_preview(None)
        assert result == ""


class TestShouldSpillToFile:
    """测试 should_spill_to_file 判断是否溢出"""

    def test_below_limit_returns_false(self):
        """低于限制返回 False"""
        text = "short text"
        result = should_spill_to_file(text, 100)
        assert result is False

    def test_above_limit_returns_true(self):
        """高于限制返回 True"""
        text = "a" * 500
        result = should_spill_to_file(text, 100)
        assert result is True

    def test_default_limit_300(self):
        """默认限制 300"""
        text = "a" * 400
        result = should_spill_to_file(text)
        assert result is True

    def test_exact_limit_returns_false(self):
        """刚好等于限制返回 False（不溢出）"""
        text = "a" * 300
        result = should_spill_to_file(text, 300)
        assert result is False

    def test_normalized_length_used(self):
        """使用规范化后的长度判断"""
        text = "  a  " * 100  # 原始长度 400，规范化后 199 ("a a a ...")
        result = should_spill_to_file(text, 200)
        assert result is False  # 规范化后 199 < 200

    def test_none_input_returns_false(self):
        """None 输入返回 False"""
        result = should_spill_to_file(None, 100)
        assert result is False


class TestTrimJsonShort:
    """测试 trim_json_short JSON 短截断"""

    def test_truncate_string_value(self):
        """截断字符串值"""
        data = {"key": "a" * 300}
        result = trim_json_short(data, limit=100)
        assert len(result["key"]) <= 100
        assert result["key"].endswith("…")

    def test_recursive_dict(self):
        """递归处理 dict"""
        data = {"outer": {"inner": {"deep": "a" * 300}}}
        result = trim_json_short(data, limit=100)
        assert len(result["outer"]["inner"]["deep"]) <= 100

    def test_recursive_list(self):
        """递归处理 list"""
        data = {"items": ["a" * 300, "b" * 300, "c" * 300]}
        result = trim_json_short(data, limit=100)
        for item in result["items"]:
            assert len(item) <= 100

    def test_numeric_values_unchanged(self):
        """数值类型不变"""
        data = {"int": 42, "float": 3.14, "bool": True}
        result = trim_json_short(data, limit=100)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["bool"] is True

    def test_none_value_unchanged(self):
        """None 值不变"""
        data = {"null": None}
        result = trim_json_short(data, limit=100)
        assert result["null"] is None

    def test_mixed_structure(self):
        """混合复杂结构"""
        data = {
            "name": "a" * 300,
            "count": 100,
            "items": [{"id": 1, "desc": "b" * 300}, {"id": 2, "desc": "c" * 300}],
            "meta": {"tags": ["tag1", "tag2", "tag3"], "info": "d" * 300},
        }
        result = trim_json_short(data, limit=50)

        assert len(result["name"]) <= 50
        assert result["count"] == 100
        assert len(result["items"][0]["desc"]) <= 50
        assert len(result["meta"]["info"]) <= 50

    def test_empty_structures(self):
        """空结构"""
        data = {"empty_dict": {}, "empty_list": [], "empty_str": ""}
        result = trim_json_short(data, limit=100)
        assert result["empty_dict"] == {}
        assert result["empty_list"] == []
        assert result["empty_str"] == ""

    def test_tuple_input(self):
        """元组输入"""
        data = (1, "a" * 300, {"key": "b" * 300})
        result = trim_json_short(data, limit=50)
        assert isinstance(result, tuple)
        assert result[0] == 1
        assert len(result[1]) <= 50
        assert len(result[2]["key"]) <= 50

    def test_default_limit_160(self):
        """默认限制 160"""
        data = {"key": "a" * 300}
        result = trim_json_short(data)  # no limit arg
        assert len(result["key"]) <= 160
