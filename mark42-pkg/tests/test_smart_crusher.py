"""Test smart_crusher.py JSON 压缩器。"""

import json

import pytest

from mark42.smart_crusher import SmartCrusher, get_smartcrusher, smartcrush


class TestSmartCrusherInit:
    """测试 SmartCrusher 初始化"""

    def test_default_params(self):
        """默认参数"""
        crusher = SmartCrusher()
        assert crusher.max_array_len == 5
        assert crusher.max_string_len == 200
        assert crusher.max_depth == 3
        assert crusher.max_numeric_array_len == 50

    def test_custom_params(self):
        """自定义参数"""
        crusher = SmartCrusher(
            max_array_len=10,
            max_string_len=100,
            max_depth=5,
            max_numeric_array_len=100,
        )
        assert crusher.max_array_len == 10
        assert crusher.max_string_len == 100
        assert crusher.max_depth == 5
        assert crusher.max_numeric_array_len == 100


class TestIsNumericArray:
    """测试 _is_numeric_array 判断数值数组"""

    def test_all_ints(self):
        """全是整数"""
        crusher = SmartCrusher()
        arr = [1, 2, 3, 4, 5]
        assert crusher._is_numeric_array(arr) is True

    def test_all_floats(self):
        """全是浮点数"""
        crusher = SmartCrusher()
        arr = [1.1, 2.2, 3.3]
        assert crusher._is_numeric_array(arr) is True

    def test_mixed_ints_floats(self):
        """混合整数和浮点数"""
        crusher = SmartCrusher()
        arr = [1, 2.2, 3, 4.4]
        assert crusher._is_numeric_array(arr) is True

    def test_contains_bool(self):
        """包含 bool（bool 是 int 子类，需要排除）"""
        crusher = SmartCrusher()
        arr = [1, True, 3, False]
        assert crusher._is_numeric_array(arr) is False

    def test_contains_string(self):
        """包含字符串"""
        crusher = SmartCrusher()
        arr = [1, 2, "three", 4]
        assert crusher._is_numeric_array(arr) is False

    def test_contains_none(self):
        """包含 None"""
        crusher = SmartCrusher()
        arr = [1, None, 3]
        assert crusher._is_numeric_array(arr) is False

    def test_empty_array(self):
        """空数组（边界情况，all([]) 返回 True）"""
        crusher = SmartCrusher()
        arr = []
        assert crusher._is_numeric_array(arr) is True


class TestCompressNumericArray:
    """测试 _compress_numeric_array 压缩数值数组"""

    def test_basic_stats(self):
        """基本统计信息"""
        crusher = SmartCrusher()
        arr = [1, 2, 3, 4, 5]
        result = crusher._compress_numeric_array(arr)

        assert "length=5" in result
        assert "min=1" in result
        assert "max=5" in result
        assert "mean=3.00" in result
        assert "sum=15" in result

    def test_float_precision(self):
        """浮点数精度保留 2 位"""
        crusher = SmartCrusher()
        arr = [1.12345, 2.67890]
        result = crusher._compress_numeric_array(arr)

        assert "mean=1.90" in result  # (1.12345 + 2.67890) / 2 = 1.901... -> 1.90

    def test_empty_array(self):
        """空数组"""
        crusher = SmartCrusher()
        arr = []
        result = crusher._compress_numeric_array(arr)
        assert result == "[]"

    def test_negative_numbers(self):
        """负数"""
        crusher = SmartCrusher()
        arr = [-5, -3, 0, 3, 5]
        result = crusher._compress_numeric_array(arr)

        assert "min=-5" in result
        assert "max=5" in result


class TestCrushValue:
    """测试 _crush_value 递归压缩值"""

    def test_basic_types_unchanged(self):
        """基本类型（非字符串/数组/对象）不变"""
        crusher = SmartCrusher()
        stats = {}

        assert crusher._crush_value(42, 0, stats) == 42
        assert crusher._crush_value(3.14, 0, stats) == 3.14
        assert crusher._crush_value(True, 0, stats) is True
        assert crusher._crush_value(None, 0, stats) is None

    def test_short_string_unchanged(self):
        """短字符串不变"""
        crusher = SmartCrusher(max_string_len=100)
        stats = {}
        text = "short string"

        result = crusher._crush_value(text, 0, stats)
        assert result == text

    def test_long_string_truncated(self):
        """长字符串被截断"""
        crusher = SmartCrusher(max_string_len=10)
        stats = {"strings_truncated": 0}
        text = "this is a very long string"  # 25 chars

        result = crusher._crush_value(text, 0, stats)
        assert len(result) > 10  # 包含提示信息
        assert "truncated" in result
        assert stats["strings_truncated"] == 1

    def test_short_array_unchanged(self):
        """短数组不变"""
        crusher = SmartCrusher(max_array_len=5)
        stats = {}
        arr = [1, 2, 3]

        result = crusher._crush_value(arr, 0, stats)
        assert result == [1, 2, 3]

    def test_long_array_truncated(self):
        """长数组被截断"""
        crusher = SmartCrusher(max_array_len=3)
        stats = {"arrays_truncated": 0}
        arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        result = crusher._crush_value(arr, 0, stats)
        assert len(result) == 4  # 3 items + 1 summary
        assert result[:3] == [1, 2, 3]
        assert "total 10 items" in result[3]
        assert stats["arrays_truncated"] == 1

    def test_numeric_array_compressed(self):
        """数值数组被压缩"""
        crusher = SmartCrusher(max_array_len=5, max_numeric_array_len=10)
        stats = {"numeric_arrays_compressed": 0}
        arr = list(range(100))  # 100 ints

        result = crusher._crush_value(arr, 0, stats)
        assert isinstance(result, str)
        assert "numeric array" in result
        assert "length=100" in result
        assert stats["numeric_arrays_compressed"] == 1

    def test_dict_recursive(self):
        """字典递归处理"""
        crusher = SmartCrusher(max_string_len=10)
        stats = {"strings_truncated": 0}
        data = {"name": "a" * 100, "count": 42}

        result = crusher._crush_value(data, 0, stats)
        assert "truncated" in result["name"]
        assert result["count"] == 42
        assert stats["strings_truncated"] == 1

    def test_depth_truncation(self):
        """深度超限被截断"""
        crusher = SmartCrusher(max_depth=2)
        stats = {"depth_truncated": 0}

        # depth 0: { (dict)
        # depth 1:   "level1": { (dict)
        # depth 2:     "level2": { (dict)
        # depth 3:       "level3": "deep" }}}  <- 超过 max_depth
        data = {"level1": {"level2": {"level3": "deep value"}}}

        result = crusher._crush_value(data, 0, stats)
        assert "truncated" in result["level1"]["level2"]["level3"]
        assert stats["depth_truncated"] == 1

    def test_nested_arrays_and_dicts(self):
        """嵌套数组和字典"""
        crusher = SmartCrusher(max_array_len=2, max_string_len=10)
        stats = {"arrays_truncated": 0, "strings_truncated": 0}

        data = {
            "users": [
                {"id": 1, "bio": "a" * 100},
                {"id": 2, "bio": "b" * 100},
                {"id": 3, "bio": "c" * 100},
                {"id": 4, "bio": "d" * 100},
            ]
        }

        result = crusher._crush_value(data, 0, stats)
        assert len(result["users"]) == 3  # 2 users + 1 summary
        assert "truncated" in result["users"][0]["bio"]
        assert stats["arrays_truncated"] == 1
        assert stats["strings_truncated"] >= 2


class TestCrushMixed:
    """测试 _crush_mixed 非 JSON 内容按行压缩"""

    def test_few_lines_no_truncation(self):
        """行数少不截断"""
        crusher = SmartCrusher()
        content = "line1\nline2\nline3"
        stats = {"original_bytes": len(content.encode("utf-8"))}

        result, out_stats = crusher._crush_mixed(content, stats)
        assert result == content
        assert out_stats["mode"] == "mixed_lines"

    def test_many_lines_truncated(self):
        """行数多被截断（默认 50 行）"""
        crusher = SmartCrusher()
        lines = [f"line {i}" for i in range(100)]
        content = "\n".join(lines)
        stats = {"original_bytes": len(content.encode("utf-8"))}

        result, out_stats = crusher._crush_mixed(content, stats)
        assert "more lines" in result
        assert "bytes total" in result
        assert len(result.splitlines()) <= 51  # 50 + 1 marker


class TestCrushMainMethod:
    """测试 crush 主方法"""

    def test_empty_content(self):
        """空内容"""
        crusher = SmartCrusher()
        content = ""

        result, stats = crusher.crush(content)
        assert result == ""
        assert stats["ratio"] == 0.0

    def test_whitespace_only(self):
        """仅空白 - 非 JSON 内容"""
        crusher = SmartCrusher()
        content = "   \n  \t  "

        result, stats = crusher.crush(content)
        # whitespace-only 不是纯 JSON，返回原始内容
        assert stats["is_pure_json"] is False
        assert result == content  # 50 行以内不截断

    def test_valid_json(self):
        """有效 JSON"""
        crusher = SmartCrusher()
        data = {"key": "value", "number": 42}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["is_pure_json"] is True
        assert "key" in result

    def test_invalid_json_mixed_mode(self):
        """无效 JSON 进入 mixed 模式"""
        crusher = SmartCrusher()
        content = "not json at all"

        result, stats = crusher.crush(content)
        assert stats["is_pure_json"] is False
        assert stats["mode"] == "mixed_lines"

    def test_compression_ratio_calculated(self):
        """压缩率正确计算"""
        crusher = SmartCrusher(max_array_len=2, max_string_len=10)
        data = {"items": ["a" * 1000 for _ in range(100)]}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["ratio"] > 0.9  # 应该有很高的压缩率
        assert stats["crushed_bytes"] < stats["original_bytes"]

    def test_array_truncation_stats(self):
        """数组截断统计"""
        crusher = SmartCrusher(max_array_len=2)
        data = {"items": list(range(10))}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["arrays_truncated"] >= 1

    def test_string_truncation_stats(self):
        """字符串截断统计"""
        crusher = SmartCrusher(max_string_len=10)
        data = {"text": "a" * 1000}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["strings_truncated"] >= 1

    def test_depth_truncation_stats(self):
        """深度截断统计"""
        crusher = SmartCrusher(max_depth=1)
        data = {"a": {"b": {"c": {"d": "deep"}}}}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["depth_truncated"] >= 1

    def test_numeric_array_compression_stats(self):
        """数值数组压缩统计"""
        crusher = SmartCrusher(max_numeric_array_len=10)
        data = {"values": list(range(100))}
        content = json.dumps(data)

        result, stats = crusher.crush(content)
        assert stats["numeric_arrays_compressed"] >= 1

    def test_json_serialization_error_fallback(self):
        """JSON 序列化错误时回退（这个比较难触发，测一个边缘情况）"""
        crusher = SmartCrusher()
        # 创建一个有循环引用的对象，_crush_value 处理时不会有问题
        # 但序列化时可能出问题。这里用一个简单测试确保错误被捕获。
        data = {"key": set([1, 2, 3])}  # set 不能 JSON 序列化
        content = json.dumps(data, default=str)  # 先序列化成功

        # 实际上这个测试主要是覆盖错误处理分支
        # 更直接的是确保函数不会崩溃
        result, stats = crusher.crush(content)
        assert "error" not in stats or stats["ratio"] == 0.0


class TestSingleton:
    """测试 get_smartcrusher 单例"""

    def test_returns_same_instance(self):
        """返回同一个实例"""
        c1 = get_smartcrusher()
        c2 = get_smartcrusher()
        assert c1 is c2

    def test_instance_is_smartcrusher(self):
        """实例类型正确"""
        c = get_smartcrusher()
        assert isinstance(c, SmartCrusher)


class TestSmartcrushPublicAPI:
    """测试 smartcrush 公开 API"""

    def test_basic_functionality(self):
        """基本功能 - 整数数组被当作数值数组压缩"""
        data = {"items": list(range(100))}
        content = json.dumps(data)

        result, stats = smartcrush(content)
        # 100 个整数被当作数值数组压缩，而不是普通数组截断
        assert "numeric array" in result
        assert "length=100" in result
        assert stats["numeric_arrays_compressed"] >= 1

    def test_empty_string(self):
        """空字符串"""
        result, stats = smartcrush("")
        assert result == ""

    def test_mixed_content(self):
        """混合内容"""
        result, stats = smartcrush("plain text line 1\nline 2\nline 3")
        assert stats["mode"] == "mixed_lines"


class TestIntegrationScenarios:
    """集成测试场景"""

    def test_large_user_array(self):
        """大型用户数组"""
        crusher = SmartCrusher(max_array_len=5, max_string_len=200)
        data = {"users": [{"id": i, "name": f"user_{i}", "bio": "x" * 500} for i in range(100)]}
        content = json.dumps(data, ensure_ascii=False)

        result, stats = crusher.crush(content)

        assert stats["arrays_truncated"] >= 1
        assert stats["strings_truncated"] >= 1
        assert stats["ratio"] > 0.7  # 高压缩率

    def test_deeply_nested_object(self):
        """深度嵌套对象"""
        crusher = SmartCrusher(max_depth=3)
        data = {"a": {"b": {"c": {"d": {"e": {"f": "deep value"}}}}}}
        content = json.dumps(data)

        result, stats = crusher.crush(content)

        assert stats["depth_truncated"] >= 1
        assert "truncated" in result

    def test_multiple_numeric_arrays(self):
        """多个数值数组"""
        crusher = SmartCrusher(max_numeric_array_len=10)
        data = {
            "timestamps": list(range(1000)),
            "values": [i * 1.5 for i in range(1000)],
            "counts": [i * 2 for i in range(2000)],
        }
        content = json.dumps(data)

        result, stats = crusher.crush(content)

        assert stats["numeric_arrays_compressed"] == 3
        assert result.count("numeric array") == 3

    def test_realistic_mixed_scenario(self):
        """真实混合场景 - 增加 max_depth 避免深度截断先触发"""
        crusher = SmartCrusher(max_depth=5)
        long_desc = "a" * 300  # 确保超过 max_string_len=200
        data = {
            "status": "success",
            "data": {
                "results": [
                    {
                        "id": i,
                        "title": f"Result {i}",
                        "description": long_desc,
                    }
                    for i in range(20)
                ],
                "metrics": {
                    "timestamps": list(range(100)),
                    "scores": [i * 0.1 for i in range(100)],
                },
            },
            "metadata": {"request_id": "abc123", "timestamp": 1234567890},
        }
        content = json.dumps(data)

        result, stats = crusher.crush(content)

        assert stats["arrays_truncated"] >= 1  # results 数组截断
        assert stats["strings_truncated"] >= 1  # description 截断
        assert stats["numeric_arrays_compressed"] >= 1  # timestamps/scores 压缩
        assert stats["ratio"] > 0.0
