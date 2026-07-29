"""Mark42 SmartCrusher 独立模块。

设计文档:
- docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
- docs/design/mark42-Phase2路线-20260625.md (P1-4 拆分)

职责:
- JSON / 混合工具输出压缩
- 提供单例与兼容公开 API: SmartCrusher / get_smartcrusher / smartcrush
"""

import json
from typing import Any

# 【2026-07-13】不能用相对路径, 因为 algo_scheduler 从外部 `from smart_crusher import smartcrush`
from mark42_modules.utils import safe_call


class SmartCrusher:
    """借鉴 Headroom JSON compressor：JSON 工具输出压缩"""

    def __init__(self,
                 max_array_len: int = 5,
                 max_string_len: int = 200,
                 max_depth: int = 3,
                 max_numeric_array_len: int = 50):
        self.max_array_len = max_array_len
        self.max_string_len = max_string_len
        self.max_depth = max_depth
        self.max_numeric_array_len = max_numeric_array_len

    def crush(self, content: str) -> tuple[str, dict]:
        stats = {
            "algorithm": "smartcrush",
            "original_bytes": len(content.encode('utf-8')),
            "crushed_bytes": 0,
            "arrays_truncated": 0,
            "strings_truncated": 0,
            "depth_truncated": 0,
            "numeric_arrays_compressed": 0,
            "is_pure_json": False,
            "ratio": 0.0,
        }

        if not content or not content.strip():
            stats["ratio"] = 0.0
            return content, stats

        try:
            obj = json.loads(content)
            stats["is_pure_json"] = True
        except (json.JSONDecodeError, ValueError):
            return self._crush_mixed(content, stats)

        crushed = self._crush_value(obj, depth=0, stats=stats)

        try:
            result = json.dumps(crushed, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            stats["ratio"] = 0.0
            stats["error"] = f"serialization failed: {e}"
            return content, stats

        stats["crushed_bytes"] = len(result.encode('utf-8'))
        stats["ratio"] = 1.0 - (stats["crushed_bytes"] / max(1, stats["original_bytes"]))
        return result, stats

    def _crush_value(self, value: Any, depth: int, stats: dict) -> Any:
        if depth > self.max_depth:
            stats["depth_truncated"] += 1
            return f"... (depth > {self.max_depth} truncated)"

        if isinstance(value, dict):
            return {k: self._crush_value(v, depth + 1, stats) for k, v in value.items()}

        if isinstance(value, list):
            if self._is_numeric_array(value) and len(value) > self.max_numeric_array_len:
                stats["numeric_arrays_compressed"] += 1
                return self._compress_numeric_array(value)

            if len(value) > self.max_array_len:
                stats["arrays_truncated"] += 1
                head = [self._crush_value(v, depth + 1, stats) for v in value[:self.max_array_len]]
                summary = f"... (total {len(value)} items, head {self.max_array_len} shown)"
                return head + [summary]

            return [self._crush_value(v, depth + 1, stats) for v in value]

        if isinstance(value, str):
            if len(value) > self.max_string_len:
                stats["strings_truncated"] += 1
                return (value[:self.max_string_len] +
                        f"... ({len(value) - self.max_string_len} chars truncated)")
            return value

        return value

    def _is_numeric_array(self, arr: list) -> bool:
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in arr)

    def _compress_numeric_array(self, arr: list) -> str:
        if not arr:
            return "[]"
        return (f"[numeric array: length={len(arr)}, "
                f"min={min(arr)}, max={max(arr)}, "
                f"mean={sum(arr)/len(arr):.2f}, "
                f"sum={sum(arr)}]")

    def _crush_mixed(self, content: str, stats: dict) -> tuple[str, dict]:
        lines = content.splitlines()
        max_lines = 50

        if len(lines) > max_lines:
            head = "\n".join(lines[:max_lines])
            tail_marker = f"\n... ({len(lines) - max_lines} more lines, {len(content.encode('utf-8'))} bytes total)"
            result = head + tail_marker
        else:
            result = content

        stats["crushed_bytes"] = len(result.encode('utf-8'))
        stats["ratio"] = 1.0 - (stats["crushed_bytes"] / max(1, stats["original_bytes"]))
        stats["mode"] = "mixed_lines"
        return result, stats


_smartcrusher_singleton: SmartCrusher | None = None


def get_smartcrusher() -> SmartCrusher:
    global _smartcrusher_singleton
    if _smartcrusher_singleton is None:
        _smartcrusher_singleton = SmartCrusher()
    return _smartcrusher_singleton


@safe_call(default=("", {"error": "smartcrush failed"}), label="smartcrush")
def smartcrush(content: str) -> tuple[str, dict]:
    return get_smartcrusher().crush(content)


def _run_tests():
    print("=" * 60)
    print("SmartCrusher 单元测试")
    print("=" * 60)

    crusher = SmartCrusher(max_array_len=5, max_string_len=200, max_depth=3)

    test1_input = json.dumps({
        "users": [
            {"id": i, "name": f"user_{i}", "bio": "x" * 500}
            for i in range(100)
        ]
    }, ensure_ascii=False)
    test1_output, test1_stats = crusher.crush(test1_input)
    print(f"\n[测试 1] 100 个用户对象数组 (每条 500 字符 bio)")
    print(f"  原始: {test1_stats['original_bytes']} bytes")
    print(f"  压缩: {test1_stats['crushed_bytes']} bytes")
    print(f"  压缩率: {test1_stats['ratio'] * 100:.1f}%")
    print(f"  数组截断: {test1_stats['arrays_truncated']}")
    print(f"  字符串截断: {test1_stats['strings_truncated']}")
    assert test1_stats['arrays_truncated'] >= 1
    assert test1_stats['strings_truncated'] >= 1
    assert test1_stats['ratio'] > 0.7
    print("  ✓ 通过 (数组先被截断, 只前 5 个 bio 被截断)")

    nested = {"a": {"b": {"c": {"d": {"e": {"f": "deep value"}}}}}}
    test2_output, test2_stats = crusher.crush(json.dumps(nested))
    print(f"\n[测试 2] 深度嵌套对象 (depth 6)")
    print(f"  深度截断: {test2_stats['depth_truncated']}")
    assert test2_stats['depth_truncated'] >= 1
    assert "truncated" in test2_output
    print("  ✓ 通过")

    test3_input = json.dumps({"timestamps": list(range(1000)), "values": [i * 1.5 for i in range(1000)]})
    test3_output, test3_stats = crusher.crush(test3_input)
    print(f"\n[测试 3] 1000 元素数值数组")
    print(f"  数值数组压缩: {test3_stats['numeric_arrays_compressed']}")
    assert test3_stats['numeric_arrays_compressed'] == 2
    assert "numeric array" in test3_output
    print("  ✓ 通过")

    test4_output, test4_stats = crusher.crush("\n".join(f"line {i}" for i in range(100)))
    print(f"\n[测试 4] 100 行纯文本")
    print(f"  mode: {test4_stats.get('mode')}")
    assert test4_stats.get('mode') == 'mixed_lines'
    assert "more lines" in test4_output
    print("  ✓ 通过")

    test5_output, test5_stats = crusher.crush("")
    print(f"\n[测试 5] 空内容")
    assert test5_output == ""
    assert test5_stats['ratio'] == 0.0
    print("  ✓ 通过")

    test6_output, test6_stats = crusher.crush('{"a": 1, "b": 2}')
    print(f"\n[测试 6] 小 JSON (无压缩需求)")
    print(f"  压缩率: {test6_stats['ratio'] * 100:.1f}% (可能为 0 或负)")
    print("  ✓ 通过 (小内容不需压缩)")

    print("\n" + "=" * 60)
    print("所有测试通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    _run_tests()
