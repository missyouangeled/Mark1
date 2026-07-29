"""output_guard.py 测试 — token 优化/截断策略。"""

import pytest

from mark42_modules.output_guard import (
    _normalize_text,
    _trim,
    trim_summary,
    trim_detail,
    compact_preview,
    should_spill_to_file,
    trim_json_short,
)


class TestNormalizeText:
    """_normalize_text() 文本规范化。"""

    def test_none_returns_empty(self):
        assert _normalize_text(None) == ""

    def test_empty_string_returns_empty(self):
        assert _normalize_text("") == ""

    def test_windows_line_endings_normalized(self):
        result = _normalize_text("line1\r\nline2\rline3")
        assert result == "line1 line2 line3"

    def test_leading_trailing_whitespace_removed(self):
        result = _normalize_text("   hello   world   ")
        assert result == "hello world"

    def test_multiple_spaces_collapsed(self):
        result = _normalize_text("hello     world   how  are you")
        assert result == "hello world how are you"

    def test_empty_lines_removed(self):
        result = _normalize_text("line1\n\n\nline2\n\nline3")
        assert result == "line1 line2 line3"

    def test_line_whitespace_stripped(self):
        result = _normalize_text("  line1  \n  line2  \n  line3  ")
        assert result == "line1 line2 line3"

    def test_non_string_input(self):
        assert _normalize_text(123) == "123"
        assert _normalize_text(3.14) == "3.14"
        assert _normalize_text(True) == "True"


class TestTrim:
    """_trim() 文本截断。"""

    def test_text_shorter_than_limit_no_ellipsis(self):
        result = _trim("short text", 100)
        assert result == "short text"
        assert "…" not in result

    def test_text_exactly_limit_no_ellipsis(self):
        result = _trim("12345", 5)
        assert result == "12345"

    def test_text_longer_than_limit_adds_ellipsis(self):
        result = _trim("this is a long text", 10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_limit_1_truncates_without_ellipsis(self):
        result = _trim("hello", 1)
        assert result == "h"
        assert "…" not in result

    def test_limit_0(self):
        result = _trim("hello", 0)
        assert result == ""

    def test_negative_limit_behaves_as_end_slice(self):
        # 负数 limit 被当作 Python 切片，从末尾截取
        # normalized[:-1] 会去掉最后一个字符
        result = _trim("hello", -1)
        assert result == "hell"  # 去掉了 'o'

    def test_whitespace_before_ellipsis_trimmed(self):
        # "hello world" 截断到 7 应该是 "hello …" 而不是 "hello  …"
        # 但实际上是先截断再 rstrip()，所以末尾空格会被去掉
        result = _trim("hello world", 7)
        # 截断到 7 字符：前 6 个字符 + ellipsis
        # "hello " (6 chars) rstrip() -> "hello" + "…" = 6 chars
        # 让我验证实际行为
        assert "…" in result
        assert not result.endswith(" …")  # 不应该有空格在省略号前


class TestPublicTrimFunctions:
    """公共截断函数的默认参数测试。"""

    def test_trim_summary_default_limit(self):
        long_text = "a" * 200
        result = trim_summary(long_text)
        # 默认 limit=120，应该有省略号
        assert len(result) == 120
        assert result.endswith("…")

    def test_trim_summary_custom_limit(self):
        result = trim_summary("hello world", limit=5)
        assert len(result) == 5

    def test_trim_detail_default_limit(self):
        long_text = "a" * 400
        result = trim_detail(long_text)
        # 默认 limit=280
        assert len(result) == 280
        assert result.endswith("…")

    def test_compact_preview_default_limit(self):
        long_text = "a" * 300
        result = compact_preview(long_text)
        # 默认 limit=160
        assert len(result) == 160
        assert result.endswith("…")


class TestShouldSpillToFile:
    """should_spill_to_file() 判断是否需要输出到文件。"""

    def test_short_text_returns_false(self):
        assert should_spill_to_file("short text", limit=100) is False

    def test_long_text_returns_true(self):
        long_text = "a" * 500
        assert should_spill_to_file(long_text, limit=300) is True

    def test_exactly_limit_returns_false(self):
        text = "a" * 300
        assert should_spill_to_file(text, limit=300) is False

    def test_default_limit_300(self):
        text = "a" * 350
        assert should_spill_to_file(text) is True


class TestTrimJsonShort:
    """trim_json_short() JSON 结构递归截断。"""

    def test_string_value_truncated(self):
        result = trim_json_short("very long string value", limit=10)
        assert len(result) == 10
        assert result.endswith("…")

    def test_dict_values_truncated(self):
        data = {
            "name": "John",
            "bio": "This is a very long biography that should be truncated",
        }
        result = trim_json_short(data, limit=20)
        assert result["name"] == "John"  # 短字符串不截断
        assert len(result["bio"]) == 20  # 长字符串被截断

    def test_list_values_truncated(self):
        data = ["short", "this is a very long list item that needs truncation"]
        result = trim_json_short(data, limit=15)
        assert result[0] == "short"
        assert len(result[1]) == 15

    def test_tuple_values_truncated(self):
        data = ("a", "very long tuple element here")
        result = trim_json_short(data, limit=10)
        assert result[0] == "a"
        assert len(result[1]) == 10
        assert isinstance(result, tuple)

    def test_nested_structure_truncated(self):
        data = {
            "user": {
                "name": "Alice",
                "profile": {"bio": "Long biography text that should be truncated"},
            },
            "posts": [
                {"title": "Short"},
                {"title": "Very long post title that needs truncation"},
            ],
        }
        result = trim_json_short(data, limit=15)
        assert result["user"]["name"] == "Alice"
        assert len(result["user"]["profile"]["bio"]) == 15
        assert result["posts"][0]["title"] == "Short"
        assert len(result["posts"][1]["title"]) == 15

    def test_non_string_values_preserved(self):
        data = {"count": 42, "active": True, "price": 3.14, "none": None}
        result = trim_json_short(data, limit=10)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["price"] == 3.14
        assert result["none"] is None

    def test_empty_structures(self):
        assert trim_json_short({}, limit=10) == {}
        assert trim_json_short([], limit=10) == []
        assert trim_json_short((), limit=10) == ()
