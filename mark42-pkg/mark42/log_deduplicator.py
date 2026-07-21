"""Mark42 日志去重压缩器（方向 A 算法 2）

设计文档:
- 整体设计: docs/design/mark42-压缩方案借鉴Headroom-20260624.md
- 实施计划: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (4.3 节)

借鉴 Headroom log dedup 思路, 纯 Python 实现:
1. 检测 log 风格 (时间戳 / DEBUG|INFO|WARN|ERROR|FATAL 前缀)
2. 行级 dedup: 相同行合并为 "重复 N 次"
3. 保留最后 N 行原文 (失败时 debug 用)
4. 提取关键事件 (ERROR/FATAL/Exception) 原样保留

接口风格: 与 compression_algorithms.py 的 SmartCrusher 对齐
  class Xxx + get_xxx() 单例 + xxx(content) -> tuple[str, dict]

创建日期: 2026-06-24 17:20
作者: 贾维斯 (响应点点 "按你的建议走 全力提速")
"""

import re
from collections import Counter, OrderedDict

from .log_setup import get_logger

logger = get_logger(__name__)


# ============================================================================
# LogDeduplicator - 借鉴 Headroom log dedup
# 设计: 行级 dedup + tail 保留 + critical event 提取
# 预期压缩率: 80-95%
# ============================================================================


class LogDeduplicator:
    """日志去重压缩器"""

    # 日志特征行: 时间戳或级别前缀 (位置不固定, 容错宽松)
    LOG_PATTERN = re.compile(
        r"(?:"
        r"\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?|"  # 时间戳 2026-06-24 12:34:56 / 2026-06-24T12:34:56.789+08:00
        r"\[\s*(?:DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE)\s*\]|"  # [INFO] [ERROR]
        r"(?:DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE)\s*[:|-]|"  # INFO: / ERROR-
        r"\bI\d{4}|\bW\d{4}|\bE\d{4}|"  # I1234/W1234/E1234 (Android logcat)
        r"\d{1,3}(?:\.\d{1,3}){3}\s+-\s+-|"  # 192.168.1.1 - - (apache)
        r"\[pid\s+\d+\]|"  # [pid 12345]
        r"\d+\s+user\s+-\s+|"  # user - (sudo)
        r"Traceback \(most recent call last\):"  # Python 异常
        r")"
    )

    # 关键事件关键词 (大小写不敏感)
    CRITICAL_KEYWORDS = re.compile(
        r"\b(ERROR|FATAL|CRITICAL|Exception|Traceback|PANIC|OOM|SEGFAULT|"
        r"StackOverflow|OutOfMemory|AssertionError|KeyError|ValueError|"
        r"AttributeError|TypeError|RuntimeError|ImportError|SyntaxError)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        keep_tail_lines: int = 50,  # 保留最后 N 行原文 (debug 用)
        dedup_min_repeat: int = 3,  # 重复 >= N 次才合并
        max_unique_lines: int = 200,  # 最多保留 N 个唯一行
        min_log_score: float = 0.3,
    ):  # 判定为 log 的最低特征行占比
        self.keep_tail_lines = keep_tail_lines
        self.dedup_min_repeat = dedup_min_repeat
        self.max_unique_lines = max_unique_lines
        self.min_log_score = min_log_score

    def is_log(self, content: str) -> bool:
        """检测内容是否像日志"""
        if not content or not content.strip():
            return False
        lines = content.splitlines()
        if len(lines) < 5:
            return False
        # 抽样前 50 行, 计算 LOG_PATTERN 命中比例 (用 search 任意位置)
        sample = lines[: min(50, len(lines))]
        hits = sum(1 for ln in sample if self.LOG_PATTERN.search(ln))
        score = hits / len(sample)
        return score >= self.min_log_score

    def dedup(self, content: str) -> tuple[str, dict]:
        """压缩日志内容

        Args:
            content: 原始日志文本

        Returns:
            (压缩后文本, 统计信息)
        """
        stats = {
            "algorithm": "log_dedup",
            "original_bytes": len(content.encode("utf-8")),
            "original_lines": 0,
            "unique_lines": 0,
            "merged_groups": 0,
            "repeated_lines_total": 0,
            "kept_tail_lines": 0,
            "critical_events": [],
            "is_log": False,
            "crushed_bytes": 0,
            "ratio": 0.0,
            "mode": "none",
        }

        if not content or not content.strip():
            stats["ratio"] = 0.0
            return content, stats

        lines = content.splitlines()
        stats["original_lines"] = len(lines)

        # 非日志内容: 原样返回
        if not self.is_log(content):
            stats["crushed_bytes"] = stats["original_bytes"]
            stats["ratio"] = 0.0
            stats["mode"] = "passthrough"
            return content, stats

        stats["is_log"] = True

        # 1. 分离 tail lines
        # 注意: keep_tail_lines=0 时, lines[-0:] 会返回整份列表, 不是空列表。
        # 这里显式处理 <=0, 避免“整份日志都被当成 tail”这种边界 bug。
        if self.keep_tail_lines <= 0:
            tail = []
            head = lines
        else:
            tail = lines[-self.keep_tail_lines :] if len(lines) > self.keep_tail_lines else lines
            head = lines[: -self.keep_tail_lines] if len(lines) > self.keep_tail_lines else []
        stats["kept_tail_lines"] = len(tail)

        # 2. 提取 critical events (从全量内容中)
        critical = self._extract_critical_events(lines)
        stats["critical_events"] = critical

        # 3. 对 head 做 dedup
        if head:
            counter = Counter(head)
            # 按首次出现顺序保留 (OrderedDict 保序)
            seen = OrderedDict()
            for line in head:
                if line not in seen:
                    seen[line] = counter[line]
            # 截断到 max_unique_lines
            unique_kept = list(seen.items())[: self.max_unique_lines]
        else:
            unique_kept = []

        # 4. 组装输出
        out_lines = []
        out_lines.append(
            f"=== [Mark42 LogDeduplicator] 原始 {stats['original_lines']} 行, 去重后 {len(unique_kept)} 个唯一行 + tail {len(tail)} 行 ==="
        )
        out_lines.append("")

        # 4a. critical events 置顶
        if critical:
            out_lines.append(f"--- 关键事件 ({len(critical)} 条) ---")
            for evt in critical[:20]:  # 最多 20 条
                out_lines.append(evt)
            out_lines.append("")

        # 4b. 去重后的 head
        if unique_kept:
            out_lines.append("--- 去重后的日志 (head) ---")
            merged_count = 0
            for line, count in unique_kept:
                if count >= self.dedup_min_repeat:
                    out_lines.append(f"  [×{count}] {line}")
                    merged_count += 1
                    stats["repeated_lines_total"] += count
                else:
                    out_lines.append(f"  {line}")
            stats["merged_groups"] = merged_count
            stats["unique_lines"] = len(unique_kept)
            out_lines.append("")

        # 4c. tail 原文
        if tail:
            out_lines.append(f"--- 最后 {len(tail)} 行原文 (debug 用) ---")
            out_lines.extend(tail)

        result = "\n".join(out_lines)
        stats["crushed_bytes"] = len(result.encode("utf-8"))
        stats["ratio"] = 1.0 - (stats["crushed_bytes"] / max(1, stats["original_bytes"]))
        stats["mode"] = "dedup"

        return result, stats

    def _extract_critical_events(self, lines: list[str]) -> list[str]:
        """提取关键事件行 (ERROR/FATAL/Exception 等)"""
        critical = []
        for line in lines:
            if self.CRITICAL_KEYWORDS.search(line):
                critical.append(line.strip())
        # 去重但保序
        seen = set()
        unique_critical = []
        for evt in critical:
            if evt not in seen:
                seen.add(evt)
                unique_critical.append(evt)
        return unique_critical


# ============================================================================
# 单例 + 公开 API
# ============================================================================

_log_dedup_singleton: LogDeduplicator | None = None


def get_log_deduplicator() -> LogDeduplicator:
    """获取 LogDeduplicator 单例 (按需创建)"""
    global _log_dedup_singleton
    if _log_dedup_singleton is None:
        _log_dedup_singleton = LogDeduplicator()
    return _log_dedup_singleton


def logdedup(content: str) -> tuple[str, dict]:
    """公开 API: 日志去重压缩

    Args:
        content: 原始日志内容

    Returns:
        (压缩后文本, 统计信息字典)
    """
    return get_log_deduplicator().dedup(content)


# ============================================================================
# 单元测试 (直接运行: python3 log_deduplicator.py)
# ============================================================================


def _run_tests():
    """运行测试（已提取到 tests/test_log_deduplicator.py）。"""
    from tests.test_log_deduplicator import run_tests

    return run_tests()


if __name__ == "__main__":
    import sys

    success = _run_tests()
    sys.exit(0 if success else 1)
