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

# 【2026-07-13】不能用相对路径, 因为 algo_scheduler 从外部 `from .smart_crusher import smartcrush`
from .log_setup import get_logger
from .utils import safe_call

logger = get_logger(__name__)


class SmartCrusher:
    """借鉴 Headroom JSON compressor：JSON 工具输出压缩"""

    def __init__(
        self, max_array_len: int = 5, max_string_len: int = 200, max_depth: int = 3, max_numeric_array_len: int = 50
    ):
        self.max_array_len = max_array_len
        self.max_string_len = max_string_len
        self.max_depth = max_depth
        self.max_numeric_array_len = max_numeric_array_len

    def crush(self, content: str) -> tuple[str, dict]:
        stats = {
            "algorithm": "smartcrush",
            "original_bytes": len(content.encode("utf-8")),
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

        stats["crushed_bytes"] = len(result.encode("utf-8"))
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
                head = [self._crush_value(v, depth + 1, stats) for v in value[: self.max_array_len]]
                summary = f"... (total {len(value)} items, head {self.max_array_len} shown)"
                return head + [summary]

            return [self._crush_value(v, depth + 1, stats) for v in value]

        if isinstance(value, str):
            if len(value) > self.max_string_len:
                stats["strings_truncated"] += 1
                return value[: self.max_string_len] + f"... ({len(value) - self.max_string_len} chars truncated)"
            return value

        return value

    def _is_numeric_array(self, arr: list) -> bool:
        return all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in arr)

    def _compress_numeric_array(self, arr: list) -> str:
        if not arr:
            return "[]"
        return (
            f"[numeric array: length={len(arr)}, "
            f"min={min(arr)}, max={max(arr)}, "
            f"mean={sum(arr) / len(arr):.2f}, "
            f"sum={sum(arr)}]"
        )

    def _crush_mixed(self, content: str, stats: dict) -> tuple[str, dict]:
        lines = content.splitlines()
        max_lines = 50

        if len(lines) > max_lines:
            head = "\n".join(lines[:max_lines])
            tail_marker = f"\n... ({len(lines) - max_lines} more lines, {len(content.encode('utf-8'))} bytes total)"
            result = head + tail_marker
        else:
            result = content

        stats["crushed_bytes"] = len(result.encode("utf-8"))
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
    """运行测试（已提取到 tests/test_smart_crusher.py）。"""
    from tests.test_smart_crusher import run_tests

    return run_tests()


if __name__ == "__main__":
    _run_tests()
