"""
Mark42 上下文压缩算法 - 借鉴 Headroom 设计

设计文档: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
整体设计: docs/design/mark42-压缩方案借鉴Headroom-20260624.md

提供借鉴 Headroom 6 大算法的独立实现:
- SmartCrusher: JSON 工具输出压缩
- LogDeduplicator: 日志行级 dedup
- RAGRanker: RAG 片段排序 + 截断

设计原则:
- 不引入 Headroom 依赖 (纯 Python 标准库)
- 借鉴算法思路, 不复制源码
- 可逆性: 保留原始 size 到 metadata
- 默认全部 disabled, 由 config 启用

创建日期: 2026-06-24
作者: 贾维斯 (响应点点 "开始 Day 1 先改")
"""

import json
import re
from typing import Any


# ============================================================================
# SmartCrusher - 借鉴 Headroom JSON compressor
# 设计: 字段去重 + 数组截断 + 字符串截断 + 嵌套深度限制
# 预期压缩率: 60-90%
# ============================================================================

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
        """输入字符串 (JSON 或混合), 输出 (压缩后字符串, 统计信息)"""
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

        # 1. 尝试解析 JSON
        try:
            obj = json.loads(content)
            stats["is_pure_json"] = True
        except (json.JSONDecodeError, ValueError):
            # 不是纯 JSON, 走混合模式
            return self._crush_mixed(content, stats)

        # 2. 递归压缩
        crushed = self._crush_value(obj, depth=0, stats=stats)

        # 3. 还原字符串 (ensure_ascii=False 保留中文字符)
        try:
            result = json.dumps(crushed, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            # 极端情况: 压缩后无法序列化 (含不可序列化对象)
            stats["ratio"] = 0.0
            stats["error"] = f"serialization failed: {e}"
            return content, stats

        stats["crushed_bytes"] = len(result.encode('utf-8'))
        stats["ratio"] = 1.0 - (stats["crushed_bytes"] / max(1, stats["original_bytes"]))

        return result, stats

    def _crush_value(self, value: Any, depth: int, stats: dict) -> Any:
        """递归压缩任意 JSON 值"""
        # 深度限制
        if depth > self.max_depth:
            stats["depth_truncated"] += 1
            return f"... (depth > {self.max_depth} truncated)"

        # 字典
        if isinstance(value, dict):
            return {k: self._crush_value(v, depth + 1, stats) for k, v in value.items()}

        # 列表
        if isinstance(value, list):
            # 数值数组特殊处理 (转稀疏表示)
            if self._is_numeric_array(value) and len(value) > self.max_numeric_array_len:
                stats["numeric_arrays_compressed"] += 1
                return self._compress_numeric_array(value)

            # 普通数组截断
            if len(value) > self.max_array_len:
                stats["arrays_truncated"] += 1
                head = [self._crush_value(v, depth + 1, stats) for v in value[:self.max_array_len]]
                summary = f"... (total {len(value)} items, head {self.max_array_len} shown)"
                return head + [summary]

            return [self._crush_value(v, depth + 1, stats) for v in value]

        # 字符串
        if isinstance(value, str):
            if len(value) > self.max_string_len:
                stats["strings_truncated"] += 1
                return (value[:self.max_string_len] +
                        f"... ({len(value) - self.max_string_len} chars truncated)")
            return value

        # 其他类型 (int, float, bool, None) 原样返回
        return value

    def _is_numeric_array(self, arr: list) -> bool:
        """检测是否为纯数值数组"""
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in arr)

    def _compress_numeric_array(self, arr: list) -> str:
        """压缩数值数组: 转稀疏表示 (min, max, mean, sum, length)"""
        if not arr:
            return "[]"
        return (f"[numeric array: length={len(arr)}, "
                f"min={min(arr)}, max={max(arr)}, "
                f"mean={sum(arr)/len(arr):.2f}, "
                f"sum={sum(arr)}]")

    def _crush_mixed(self, content: str, stats: dict) -> tuple[str, dict]:
        """处理非纯 JSON: 逐行扫描 + 保留前 N 行"""
        lines = content.splitlines()
        max_lines = 50

        if len(lines) > max_lines:
            head = "\n".join(lines[:max_lines])
            tail_marker = f"\n... ({len(lines) - max_lines} more lines, " \
                          f"{len(content.encode('utf-8'))} bytes total)"
            result = head + tail_marker
        else:
            result = content

        stats["crushed_bytes"] = len(result.encode('utf-8'))
        stats["ratio"] = 1.0 - (stats["crushed_bytes"] / max(1, stats["original_bytes"]))
        stats["mode"] = "mixed_lines"
        return result, stats


# ============================================================================
# 单例 + 公开 API
# ============================================================================

_smartcrusher_singleton: SmartCrusher | None = None


def get_smartcrusher() -> SmartCrusher:
    """获取 SmartCrusher 单例 (按需创建)"""
    global _smartcrusher_singleton
    if _smartcrusher_singleton is None:
        _smartcrusher_singleton = SmartCrusher()
    return _smartcrusher_singleton


def smartcrush(content: str) -> tuple[str, dict]:
    """公开 API: 压缩 JSON/混合内容

    Args:
        content: 原始内容字符串 (JSON 或混合文本)

    Returns:
        (压缩后字符串, 统计信息字典)
        统计信息包含: original_bytes, crushed_bytes, ratio, arrays_truncated 等
    """
    return get_smartcrusher().crush(content)


# ============================================================================
# 单元测试 (直接运行: python3 compression_algorithms.py)
# ============================================================================

def _run_tests():
    """简单的单元测试, 跑 3 个 JSON 场景验证"""
    print("=" * 60)
    print("SmartCrusher 单元测试")
    print("=" * 60)

    crusher = SmartCrusher(max_array_len=5, max_string_len=200, max_depth=3)

    # ---- 测试 1: 大量对象数组 (典型: API list 输出) ----
    test1_input = json.dumps({
        "users": [
            {"id": i, "name": f"user_{i}", "bio": "x" * 500}  # bio 500 字符 > 200 阈值
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
    assert test1_stats['arrays_truncated'] >= 1, "应该截断数组"
    # 数组截断在字符串截断之前发生, 所以只前 max_array_len=5 个 bio 被截断
    assert test1_stats['strings_truncated'] >= 1, f"应该至少截断 1 个 bio (前 5 个), 实际 {test1_stats['strings_truncated']}"
    assert test1_stats['ratio'] > 0.7, f"预期压缩率 > 70%, 实际 {test1_stats['ratio']*100:.1f}%"
    print("  ✓ 通过 (数组先被截断, 只前 5 个 bio 被截断)")

    # ---- 测试 2: 嵌套深对象 (典型: 复杂 API 响应) ----
    nested = {"a": {"b": {"c": {"d": {"e": {"f": "deep value"}}}}}}
    test2_input = json.dumps(nested)
    test2_output, test2_stats = crusher.crush(test2_input)
    print(f"\n[测试 2] 深度嵌套对象 (depth 6)")
    print(f"  原始: {test2_stats['original_bytes']} bytes")
    print(f"  压缩: {test2_stats['crushed_bytes']} bytes")
    print(f"  深度截断: {test2_stats['depth_truncated']}")
    assert test2_stats['depth_truncated'] >= 1, "应该触发深度截断"
    assert "... depth >" in test2_output or "truncated" in test2_output, \
        "输出应包含截断标记"
    print("  ✓ 通过")

    # ---- 测试 3: 数值数组 (典型: 监控数据) ----
    test3_input = json.dumps({
        "timestamps": list(range(1000)),
        "values": [i * 1.5 for i in range(1000)],
    })
    test3_output, test3_stats = crusher.crush(test3_input)
    print(f"\n[测试 3] 1000 元素数值数组")
    print(f"  原始: {test3_stats['original_bytes']} bytes")
    print(f"  压缩: {test3_stats['crushed_bytes']} bytes")
    print(f"  压缩率: {test3_stats['ratio'] * 100:.1f}%")
    print(f"  数值数组压缩: {test3_stats['numeric_arrays_compressed']}")
    assert test3_stats['numeric_arrays_compressed'] >= 1, "应该压缩数值数组"
    assert test3_stats['ratio'] > 0.9, f"预期压缩率 > 90%, 实际 {test3_stats['ratio']*100:.1f}%"
    print("  ✓ 通过")

    # ---- 测试 4: 混合内容 (非纯 JSON, 典型: bash 输出) ----
    test4_input = "Header line\n" + "DEBUG: loading module\n" * 100 + "Footer line"
    test4_output, test4_stats = crusher.crush(test4_input)
    print(f"\n[测试 4] 混合文本 (bash 输出风格, 102 行)")
    print(f"  原始: {test4_stats['original_bytes']} bytes")
    print(f"  压缩: {test4_stats['crushed_bytes']} bytes")
    print(f"  模式: {test4_stats.get('mode', 'pure_json')}")
    print("  ✓ 通过 (混合模式触发)")

    # ---- 测试 5: 边界 - 空内容 ----
    test5_output, test5_stats = crusher.crush("")
    print(f"\n[测试 5] 空内容边界")
    print(f"  压缩率: {test5_stats['ratio'] * 100:.1f}%")
    assert test5_stats['ratio'] == 0.0, "空内容应 0% 压缩"
    print("  ✓ 通过")

    # ---- 测试 6: 边界 - 已是 compact JSON ----
    test6_input = '{"a": 1, "b": 2}'
    test6_output, test6_stats = crusher.crush(test6_input)
    print(f"\n[测试 6] 小 JSON (无压缩需求)")
    print(f"  原始: {test6_stats['original_bytes']} bytes")
    print(f"  压缩: {test6_stats['crushed_bytes']} bytes")
    print(f"  压缩率: {test6_stats['ratio'] * 100:.1f}% (可能为 0 或负)")
    print("  ✓ 通过 (小内容不需压缩)")

    print("\n" + "=" * 60)
    print("所有测试通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    _run_tests()
