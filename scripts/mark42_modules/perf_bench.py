#!/usr/bin/env python3
"""Mark42 压缩子系统性能基准 (P2-6)

目标:
- 测 5 算法 + scheduler + async queue 的延迟 / 内存 / 压缩率
- 可选测 LLM (仅在可用配置存在时)
- 自动生成 Markdown 报告到 docs/design/
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

BASE_DIR = Path(__file__).resolve().parents[2]
REPORT_PATH = BASE_DIR / "docs" / "design" / "mark42-压缩方案-性能基准-20260625.md"

# 允许脚本直接运行
sys.path.insert(0, str(BASE_DIR / "scripts"))

from mark42_modules.smart_crusher import smartcrush
from mark42_modules.code_compressor import codecrush
from mark42_modules.diff_compressor import diff_compress
from mark42_modules.log_deduplicator import logdedup
from mark42_modules.text_compressor import text_compress
from mark42_modules.algo_scheduler import process as scheduler_process
from mark42_modules.compress_queue import CompressRequest, get_compress_queue

try:
    from mark42_modules.llm_text_compressor import llm_text_compress
except Exception:
    llm_text_compress = None


@dataclass
class BenchCase:
    name: str
    category: str
    content: str


@dataclass
class BenchResult:
    name: str
    category: str
    size_bytes: int
    runs: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mem_kb_p50: float
    ratio_avg: float
    changed_rate: float
    errors: int
    notes: str = ""


@dataclass
class QueueResult:
    mode: str
    runs: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    errors: int
    notes: str = ""


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    values = sorted(values)
    idx = (len(values) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(values) - 1)
    frac = idx - lower
    return values[lower] * (1 - frac) + values[upper] * frac


def _repeat_lines(line: str, target_bytes: int) -> str:
    line = line.rstrip("\n") + "\n"
    repeat = max(1, target_bytes // max(1, len(line.encode("utf-8"))))
    text = line * repeat
    while len(text.encode("utf-8")) < target_bytes:
        text += line
    return text


def build_cases() -> list[BenchCase]:
    sizes = [1, 10, 100, 1024]  # KB
    cases: list[BenchCase] = []

    for kb in sizes:
        target = kb * 1024

        text = _repeat_lines(
            "总而言之，这是一个用于性能基准的技术说明段落，包含较长中文描述、重复结论、缓存命中率和数据库统计。",
            target,
        )
        cases.append(BenchCase(name=f"text_{kb}kb", category="text", content=text))

        log = _repeat_lines(
            "2026-06-25 12:00:00 INFO mark42 daemon loop ok request_id=abc123 latency=12ms",
            target,
        )
        cases.append(BenchCase(name=f"log_{kb}kb", category="log", content=log))

        code = _repeat_lines(
            "def process_item(item):\n    result = item.get('value', 0) * 2\n    return result\n",
            target,
        )
        cases.append(BenchCase(name=f"code_{kb}kb", category="code", content=code))

        diff = _repeat_lines(
            "@@ -1,5 +1,5 @@\n- old line\n+ new line\n context line\n",
            target,
        )
        cases.append(BenchCase(name=f"diff_{kb}kb", category="diff", content=diff))

        # SmartCrusher 优先吃 JSON
        items = []
        i = 0
        while len(json.dumps({"items": items}, ensure_ascii=False).encode("utf-8")) < target:
            items.append({
                "id": i,
                "title": f"item_{i}",
                "desc": "这是一个很长的 JSON 文本字段，用于测试 SmartCrusher 的字符串截断和数组截断能力。" * 3,
                "scores": list(range(200)),
            })
            i += 1
        payload = json.dumps({"items": items}, ensure_ascii=False)
        cases.append(BenchCase(name=f"json_{kb}kb", category="json", content=payload))

    return cases


def extract_ratio(result: Any) -> tuple[float, bool]:
    """返回 (ratio, changed)"""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        stats = result[1]
        ratio = float(stats.get("ratio", 0.0) or 0.0)
        changed = ratio > 0.0
        return ratio, changed

    if isinstance(result, dict):
        stats = result.get("compress_stats") or {}
        ratio = float(stats.get("ratio", 0.0) or 0.0)
        changed = bool(result.get("changed", False)) or ratio > 0.0
        return ratio, changed

    return 0.0, False


def bench_function(label: str, case: BenchCase, fn: Callable[[str], Any], runs: int) -> BenchResult:
    latencies: list[float] = []
    mem_peaks: list[float] = []
    ratios: list[float] = []
    changed_hits = 0
    errors = 0

    for _ in range(runs):
        tracemalloc.start()
        t0 = time.perf_counter()
        try:
            result = fn(case.content)
            elapsed = (time.perf_counter() - t0) * 1000
            ratio, changed = extract_ratio(result)
            ratios.append(ratio)
            if changed:
                changed_hits += 1
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            errors += 1
            ratios.append(0.0)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        latencies.append(elapsed)
        mem_peaks.append(peak / 1024)

    return BenchResult(
        name=label,
        category=case.name,
        size_bytes=len(case.content.encode("utf-8")),
        runs=runs,
        p50_ms=statistics.median(latencies),
        p95_ms=percentile(latencies, 0.95),
        p99_ms=percentile(latencies, 0.99),
        mem_kb_p50=statistics.median(mem_peaks),
        ratio_avg=sum(ratios) / len(ratios),
        changed_rate=changed_hits / max(1, runs),
        errors=errors,
    )


def bench_scheduler(case: BenchCase, runs: int) -> BenchResult:
    # 注意: scheduler 是“路由 + 压缩”总链路，不是纯算法耗时
    return bench_function("scheduler", case, scheduler_process, runs)


def bench_queue(content: str, runs: int, wait: bool) -> QueueResult:
    queue = get_compress_queue()
    queue.start()
    latencies: list[float] = []
    errors = 0

    for i in range(runs):
        req = CompressRequest(
            request_id=f"bench-{int(wait)}-{i}",
            session_id="perf-bench",
            content=content,
            content_type="text/plain",
            priority=0,
        )
        t0 = time.perf_counter()
        ok = queue.enqueue(req)
        if not ok:
            errors += 1
            latencies.append((time.perf_counter() - t0) * 1000)
            continue
        if wait:
            try:
                req.wait(timeout=30)
            except Exception:
                errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)

    return QueueResult(
        mode="enqueue+wait" if wait else "enqueue-only",
        runs=runs,
        p50_ms=statistics.median(latencies) if latencies else 0.0,
        p95_ms=percentile(latencies, 0.95),
        p99_ms=percentile(latencies, 0.99),
        errors=errors,
    )


def llm_available() -> bool:
    if llm_text_compress is None:
        return False
    return bool(os.environ.get("LLM_API_KEY") or os.environ.get("MINIMAX_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def bench_llm(case: BenchCase, runs: int = 3) -> BenchResult | None:
    if not llm_available() or llm_text_compress is None:
        return None
    return bench_function("llm", case, lambda s: llm_text_compress(s, mode="summarize"), runs)


def format_result_table(results: list[BenchResult]) -> str:
    lines = [
        "| 算法 | 样本 | 大小 | P50(ms) | P95(ms) | P99(ms) | 内存P50(KB) | 平均压缩率 | changed率 | 错误 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.name} | {r.category} | {r.size_bytes} | {r.p50_ms:.2f} | {r.p95_ms:.2f} | {r.p99_ms:.2f} | {r.mem_kb_p50:.1f} | {r.ratio_avg:.1%} | {r.changed_rate:.0%} | {r.errors} |"
        )
    return "\n".join(lines)


def format_queue_table(results: list[QueueResult]) -> str:
    lines = [
        "| 队列模式 | runs | P50(ms) | P95(ms) | P99(ms) | 错误 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r.mode} | {r.runs} | {r.p50_ms:.2f} | {r.p95_ms:.2f} | {r.p99_ms:.2f} | {r.errors} |"
        )
    return "\n".join(lines)


def summarize_bottlenecks(results: list[BenchResult], queue_results: list[QueueResult], llm_result: BenchResult | None) -> str:
    slowest = max(results, key=lambda r: r.p95_ms) if results else None
    highest_mem = max(results, key=lambda r: r.mem_kb_p50) if results else None
    lines: list[str] = []
    if slowest:
        lines.append(f"- 最慢的非 LLM 路径是 `{slowest.name}` / `{slowest.category}`，P95 = {slowest.p95_ms:.2f}ms。")
    if highest_mem:
        lines.append(f"- 内存占用最高的是 `{highest_mem.name}` / `{highest_mem.category}`，内存 P50 = {highest_mem.mem_kb_p50:.1f}KB。")
    if queue_results:
        enqueue_only = next((r for r in queue_results if r.mode == "enqueue-only"), None)
        if enqueue_only:
            lines.append(f"- 异步队列 `enqueue-only` P50 = {enqueue_only.p50_ms:.2f}ms，验证 daemon tick 可在毫秒级返回。")
    if llm_result:
        lines.append(f"- LLM 路径 P95 = {llm_result.p95_ms:.2f}ms，明显高于 rule-based，继续保持 opt-in 是合理的。")
    else:
        lines.append("- 本次未测 LLM 路径（未检测到可用 key），报告只覆盖 rule-based 和异步队列。")
    return "\n".join(lines)


def write_report(results: list[BenchResult], queue_results: list[QueueResult], llm_result: BenchResult | None, meta: dict[str, Any]) -> None:
    content = [
        "# Mark42 压缩子系统性能基准 (2026-06-25)",
        "",
        "## 测试环境",
        "",
        f"- 主机: `{meta['node']}`",
        f"- 系统: `{meta['os']}`",
        f"- Python: `{meta['python']}`",
        f"- 样本集: 1KB / 10KB / 100KB / 1MB 的 text / log / code / diff / json",
        f"- rule-based runs: {meta['runs_rule']} 次/样本",
        f"- queue runs: {meta['runs_queue']} 次/模式",
        "",
        "## 算法性能表",
        "",
        format_result_table(results),
        "",
        "## 异步队列性能",
        "",
        format_queue_table(queue_results),
        "",
    ]

    if llm_result:
        content += [
            "## LLM 路径（可选）",
            "",
            "| 算法 | 样本 | 大小 | P50(ms) | P95(ms) | P99(ms) | 内存P50(KB) | 平均压缩率 | changed率 | 错误 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            f"| {llm_result.name} | {llm_result.category} | {llm_result.size_bytes} | {llm_result.p50_ms:.2f} | {llm_result.p95_ms:.2f} | {llm_result.p99_ms:.2f} | {llm_result.mem_kb_p50:.1f} | {llm_result.ratio_avg:.1%} | {llm_result.changed_rate:.0%} | {llm_result.errors} |",
            "",
        ]
    else:
        content += [
            "## LLM 路径（可选）",
            "",
            "- 本次未测（未检测到可用 key）。",
            "",
        ]

    content += [
        "## 结论",
        "",
        summarize_bottlenecks(results, queue_results, llm_result),
        "",
        "## 建议",
        "",
        "- 继续保持 `MARK42_TEXT_USE_LLM=false` 默认值，避免把高延迟路径变成默认行为。",
        "- 如果后续要优化 rule-based，可优先看表中 P95 较高的算法和 1MB 样本。",
        "- 若要扩充基准，建议下次补真实生产样本而不只是合成样本。",
        "",
        "_本报告由 `scripts/mark42_modules/perf_bench.py` 自动生成。_",
    ]

    REPORT_PATH.write_text("\n".join(content))


def main() -> int:
    cases = build_cases()
    runs_rule = 8
    runs_queue = 20

    algo_map: dict[str, Callable[[str], Any]] = {
        "smartcrush": smartcrush,
        "code": codecrush,
        "diff": diff_compress,
        "log": logdedup,
        "text": text_compress,
    }

    results: list[BenchResult] = []
    for case in cases:
        if case.category == "json":
            results.append(bench_function("smartcrush", case, smartcrush, runs_rule))
            results.append(bench_scheduler(case, runs_rule))
            continue
        if case.category == "text":
            results.append(bench_function("text", case, text_compress, runs_rule))
            results.append(bench_scheduler(case, runs_rule))
            continue
        if case.category == "log":
            results.append(bench_function("log", case, logdedup, runs_rule))
            results.append(bench_scheduler(case, runs_rule))
            continue
        if case.category == "code":
            results.append(bench_function("code", case, codecrush, runs_rule))
            results.append(bench_scheduler(case, runs_rule))
            continue
        if case.category == "diff":
            results.append(bench_function("diff", case, diff_compress, runs_rule))
            results.append(bench_scheduler(case, runs_rule))
            continue

    queue_sample = next(c.content for c in cases if c.name == "text_100kb")
    queue_results = [
        bench_queue(queue_sample, runs_queue, wait=False),
        bench_queue(queue_sample, runs_queue, wait=True),
    ]

    llm_case = next(c for c in cases if c.name == "text_10kb")
    llm_result = bench_llm(llm_case, runs=3)

    meta = {
        "node": platform.node(),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "runs_rule": runs_rule,
        "runs_queue": runs_queue,
    }
    write_report(results, queue_results, llm_result, meta)

    print(f"性能报告已生成: {REPORT_PATH}")
    print(f"算法结果: {len(results)} 条, 队列结果: {len(queue_results)} 条, LLM: {'yes' if llm_result else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
