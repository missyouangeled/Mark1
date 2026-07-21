"""Mark42 压缩子系统性能基准脚本。

P2-6 目标：
- 测 5 个本地压缩算法的延迟 / 内存 / 压缩率
- 单独测 algo_scheduler 端到端开销
- 单独测 compress_queue 常驻队列开销，以及 llm_text_compress_async 单次封装入口总成本
- 默认不触发真实 LLM 外部调用，确保本地可稳定复现

运行：
    python3 scripts/mark42_modules/perf_bench.py
"""

from __future__ import annotations

from .log_setup import get_logger

logger = get_logger(__name__)

import json
import sys
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median, quantiles
from typing import Any


def _flush():
    """确保 stdout 立即刷出（尤其在被 pipe/tail 时）。"""
    sys.stdout.flush()


_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from .algo_scheduler import process as scheduler_process
from .code_compressor import codecrush
from .compress_queue import CompressQueue, CompressRequest
from .diff_compressor import diff_compress
from .llm_text_compressor import llm_text_compress_async
from .log_deduplicator import logdedup
from .smart_crusher import smartcrush
from .text_compressor import text_compress


@dataclass
class BenchResult:
    runs: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    peak_mem_kb_p50: float
    ratio_p50: float | None = None
    ratio_p95: float | None = None
    changed_rate: float | None = None
    notes: str = ""


def _truncate_utf8(text: str, target_bytes: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= target_bytes:
        return text
    return data[:target_bytes].decode("utf-8", errors="ignore")


def _measure_peak_kb(run_once: Callable[[], Any]) -> float:
    tracemalloc.start()
    run_once()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024


def _warmup(run_once: Callable[[], Any], sample: str, warmup_runs: int = 1) -> None:
    for _ in range(warmup_runs):
        run_once(sample)


def _safe_quantile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    n = 100 if percentile == 99 else 20 if percentile == 95 else None
    if n is None:
        raise ValueError(percentile)
    try:
        idx = 98 if percentile == 99 else 18
        return quantiles(values, n=n)[idx]
    except Exception:
        return max(values)


def _estimate_ratio(stats: dict[str, Any] | None) -> float | None:
    if not isinstance(stats, dict):
        return None
    ratio = stats.get("ratio")
    if isinstance(ratio, (int, float)):
        return float(ratio)
    return None


def _estimate_changed(stats: dict[str, Any] | None, out: Any, src: str) -> bool | None:
    if not isinstance(stats, dict):
        return None
    if "changed" in stats and isinstance(stats["changed"], bool):
        return stats["changed"]
    if isinstance(out, str):
        return out != src
    return None


def bench_sync_algo(algo_fn: Callable[[str], tuple[Any, dict]], samples: list[str]) -> BenchResult:
    latencies: list[float] = []
    peak_mems: list[float] = []
    ratios: list[float] = []
    changed_hits = 0
    changed_seen = 0

    for sample in samples:
        _warmup(algo_fn, sample)
        t0 = time.perf_counter()
        out, stats = algo_fn(sample)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        peak = _measure_peak_kb(lambda s=sample: algo_fn(s))

        latencies.append(elapsed_ms)
        peak_mems.append(peak)

        ratio = _estimate_ratio(stats)
        if ratio is not None:
            ratios.append(ratio)

        changed = _estimate_changed(stats, out, sample)
        if changed is not None:
            changed_seen += 1
            if changed:
                changed_hits += 1

    return BenchResult(
        runs=len(samples),
        p50_ms=median(latencies),
        p95_ms=_safe_quantile(latencies, 95),
        p99_ms=_safe_quantile(latencies, 99),
        peak_mem_kb_p50=median(peak_mems),
        ratio_p50=median(ratios) if ratios else None,
        ratio_p95=_safe_quantile(ratios, 95) if len(ratios) >= 2 else (ratios[0] if ratios else None),
        changed_rate=(changed_hits / changed_seen) if changed_seen else None,
    )


def bench_scheduler(samples: list[str]) -> BenchResult:
    latencies: list[float] = []
    peak_mems: list[float] = []
    ratios: list[float] = []
    changed_hits = 0

    for sample in samples:
        _warmup(scheduler_process, sample)
        t0 = time.perf_counter()
        result = scheduler_process(sample)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        peak = _measure_peak_kb(lambda s=sample: scheduler_process(s))

        latencies.append(elapsed_ms)
        peak_mems.append(peak)
        ratio = result.get("ratio")
        if isinstance(ratio, (int, float)):
            ratios.append(float(ratio))
        if result.get("changed") is True:
            changed_hits += 1

    return BenchResult(
        runs=len(samples),
        p50_ms=median(latencies),
        p95_ms=_safe_quantile(latencies, 95),
        p99_ms=_safe_quantile(latencies, 99),
        peak_mem_kb_p50=median(peak_mems),
        ratio_p50=median(ratios) if ratios else None,
        ratio_p95=_safe_quantile(ratios, 95) if len(ratios) >= 2 else (ratios[0] if ratios else None),
        changed_rate=(changed_hits / len(samples)) if samples else None,
        notes="algo_scheduler.process end-to-end",
    )


def bench_async_queue(samples: list[str]) -> BenchResult:
    latencies: list[float] = []
    peak_mems: list[float] = []
    ratios: list[float] = []
    changed_hits = 0
    q = CompressQueue(max_workers=2, max_queue_size=max(20, len(samples) * 2))
    q.start()

    try:
        for idx, sample in enumerate(samples):
            req = CompressRequest(content=sample, session_id=f"bench-{idx}-warmup")
            if not q.enqueue(req):
                raise RuntimeError("queue warmup enqueue failed")
            if not req.wait(timeout=30.0):
                raise TimeoutError("queue warmup timed out")

            req = CompressRequest(content=sample, session_id=f"bench-{idx}")
            t0 = time.perf_counter()
            accepted = q.enqueue(req)
            if not accepted:
                raise RuntimeError("queue enqueue failed during benchmark")
            _flush()
            logger.info(f"  [{idx + 1}/{len(samples)}] queued")
            done = req.wait(timeout=30.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _flush()
            if done:
                logger.info(f"  [{idx + 1}/{len(samples)}] done ({elapsed_ms:.0f}ms)")
            else:
                logger.error(f"  [{idx + 1}/{len(samples)}] TIMEOUT")
            peak = _measure_peak_kb(lambda s=sample, i=idx: _queue_roundtrip(q, s, f"bench-mem-{i}"))

            if not done:
                raise TimeoutError("queue wait timed out")
            if req.error:
                raise RuntimeError(req.error)
            if not req.result:
                raise RuntimeError("queue result missing")

            latencies.append(elapsed_ms)
            peak_mems.append(peak)
            ratio = req.result.get("ratio")
            if isinstance(ratio, (int, float)):
                ratios.append(float(ratio))
            if req.result.get("changed") is True:
                changed_hits += 1
    finally:
        # shutdown 带超时，避免 worker 线程永久阻塞主线程
        q.shutdown(timeout=15.0)
    _flush()

    return BenchResult(
        runs=len(samples),
        p50_ms=median(latencies),
        p95_ms=_safe_quantile(latencies, 95),
        p99_ms=_safe_quantile(latencies, 99),
        peak_mem_kb_p50=median(peak_mems),
        ratio_p50=median(ratios) if ratios else None,
        ratio_p95=_safe_quantile(ratios, 95) if len(ratios) >= 2 else (ratios[0] if ratios else None),
        changed_rate=(changed_hits / len(samples)) if samples else None,
        notes="CompressQueue enqueue + wait end-to-end",
    )


def bench_async_entry(samples: list[str]) -> BenchResult:
    latencies: list[float] = []
    peak_mems: list[float] = []
    ratios: list[float] = []
    changed_hits = 0

    for idx, sample in enumerate(samples):
        _warmup(lambda s: llm_text_compress_async(s, timeout=30.0), sample)
        t0 = time.perf_counter()
        result = llm_text_compress_async(sample, timeout=30.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        _flush()
        logger.info(f"  [{idx + 1}/{len(samples)}] async_entry done ({elapsed_ms:.0f}ms)")
        peak = _measure_peak_kb(lambda s=sample: llm_text_compress_async(s, timeout=30.0))

        latencies.append(elapsed_ms)
        peak_mems.append(peak)
        stats = result.get("stats") if isinstance(result, dict) else None
        out = result.get("result", "") if isinstance(result, dict) else ""
        ratio = _estimate_ratio(stats)
        if ratio is not None:
            ratios.append(ratio)
        changed = _estimate_changed(stats, out, sample)
        if changed is not None and changed:
            changed_hits += 1

    return BenchResult(
        runs=len(samples),
        p50_ms=median(latencies),
        p95_ms=_safe_quantile(latencies, 95),
        p99_ms=_safe_quantile(latencies, 99),
        peak_mem_kb_p50=median(peak_mems),
        ratio_p50=median(ratios) if ratios else None,
        ratio_p95=_safe_quantile(ratios, 95) if len(ratios) >= 2 else (ratios[0] if ratios else None),
        changed_rate=(changed_hits / len(samples)) if samples else None,
        notes="llm_text_compress_async 单次调用总成本（含内部建队列/等待/关闭；可能走 rule_based fallback）",
    )


def _queue_roundtrip(queue: CompressQueue, sample: str, session_id: str) -> dict[str, Any]:
    req = CompressRequest(content=sample, session_id=session_id)
    accepted = queue.enqueue(req)
    if not accepted:
        raise RuntimeError("queue enqueue failed during memory probe")
    done = req.wait(timeout=30.0)
    if not done:
        raise TimeoutError("queue wait timed out during memory probe")
    if req.error:
        raise RuntimeError(req.error)
    return req.result or {}


def gen_text_sample(size_kb: int) -> str:
    paragraph = (
        "总而言之，这是一段用于性能基准的中文技术文本。"
        "需要说明的是，系统会记录日志、返回结果、更新配置，并在必要时进行错误处理。"
        "The service returns response metadata and application configuration for validation.\n"
    )
    target = size_kb * 1024
    text = paragraph * (target // max(1, len(paragraph.encode("utf-8"))) + 5)
    return _truncate_utf8(text, target)


def gen_code_sample(size_kb: int) -> str:
    chunk = (
        "def handle_request(user_id, payload):\n"
        "    config = load_config()\n"
        "    if not payload:\n"
        "        return {'ok': False, 'error': 'empty'}\n"
        "    return process_payload(user_id, payload, config)\n\n"
    )
    target = size_kb * 1024
    text = chunk * (target // len(chunk.encode("utf-8")) + 5)
    return _truncate_utf8(text, target)


def gen_log_sample(size_kb: int) -> str:
    line = "2026-06-26 08:00:00 INFO worker[pid 1234] request finished status=200 path=/api/test\n"
    target = size_kb * 1024
    text = line * (target // len(line.encode("utf-8")) + 10)
    return _truncate_utf8(text, target)


def gen_diff_sample(size_kb: int) -> str:
    header = "@@ -1,50 +1,50 @@\n"
    body = "- old line content for benchmark\n+ new line content for benchmark\n"
    target = size_kb * 1024
    text = header + body * (target // len(body.encode("utf-8")) + 10)
    return _truncate_utf8(text, target)


def gen_json_sample(size_kb: int) -> str:
    target = size_kb * 1024
    items = []
    i = 0
    while True:
        items.append(
            {
                "id": i,
                "name": f"user_{i}",
                "bio": "x" * 180,
                "tags": ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"],
                "values": list(range(60)),
            }
        )
        text = json.dumps({"items": items}, ensure_ascii=False)
        if len(text.encode("utf-8")) >= target:
            return _truncate_utf8(text, target)
        i += 1


def gen_mixed_scheduler_sample(size_kb: int) -> str:
    target = size_kb * 1024
    text_budget = max(256, target // 2)
    code_budget = max(128, target // 4)
    log_budget = max(128, target - text_budget - code_budget)
    text = _truncate_utf8(
        gen_text_sample(max(1, text_budget // 1024 + (1 if text_budget % 1024 else 0))),
        text_budget,
    )
    code = _truncate_utf8(
        gen_code_sample(max(1, code_budget // 1024 + (1 if code_budget % 1024 else 0))),
        code_budget,
    )
    log = _truncate_utf8(
        gen_log_sample(max(1, log_budget // 1024 + (1 if log_budget % 1024 else 0))),
        log_budget,
    )
    return _truncate_utf8(text + "\n" + code + "\n" + log, target)


def make_samples(kind: str, size_kb: int, n: int) -> list[str]:
    generators = {
        "json": gen_json_sample,
        "text": gen_text_sample,
        "code": gen_code_sample,
        "log": gen_log_sample,
        "diff": gen_diff_sample,
        "mixed": gen_mixed_scheduler_sample,
    }
    gen = generators[kind]
    return [gen(size_kb) for _ in range(n)]


def report_line(label: str, result: BenchResult) -> str:
    ratio = f"{result.ratio_p50:.1%}" if result.ratio_p50 is not None else "-"
    changed = f"{result.changed_rate:.0%}" if result.changed_rate is not None else "-"
    return (
        f"| {label} | {result.runs} | {result.p50_ms:.2f} | {result.p95_ms:.2f} | "
        f"{result.p99_ms:.2f} | {result.peak_mem_kb_p50:.0f} | {ratio} | {changed} |"
    )


def format_report(
    sync_results: dict[str, dict[int, BenchResult]],
    scheduler_results: dict[int, BenchResult],
    async_results: dict[str, dict[int, BenchResult]],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# Mark42 压缩子系统性能基准 ({datetime.now().strftime('%Y-%m-%d')})",
        "",
        "## 测试环境",
        f"- 生成时间: {now}",
        f"- Python: {sys.version.split()[0]}",
        f"- 平台: {sys.platform}",
        f"- 工作目录: {Path.cwd()}",
        "- 说明: 默认不触发真实 LLM 外部调用；异步项仅测本地队列/回退路径开销。",
        "- 注意: `async_entry` 表示 `llm_text_compress_async()` 单次封装入口总成本，包含内部建队列/等待/关闭，不等同于常驻队列吞吐。",
        "",
        "## 一、本地算法层（裸算法）",
        "",
        "| 算法 | 样本数 | P50(ms) | P95(ms) | P99(ms) | P50峰值内存(KB) | P50压缩率 | Changed率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for algo_name, size_map in sync_results.items():
        for size_kb, result in size_map.items():
            lines.append(report_line(f"{algo_name}-{size_kb}KB", result))

    lines += [
        "",
        "## 二、调度层（algo_scheduler.process）",
        "",
        "| 路由样本 | 样本数 | P50(ms) | P95(ms) | P99(ms) | P50峰值内存(KB) | P50压缩率 | Changed率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for size_kb, result in scheduler_results.items():
        lines.append(report_line(f"scheduler-mixed-{size_kb}KB", result))

    lines += [
        "",
        "## 三、异步层（常驻队列 / 单次封装入口）",
        "",
        "| 路径 | 样本数 | P50(ms) | P95(ms) | P99(ms) | P50峰值内存(KB) | P50压缩率 | Changed率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for path_name, size_map in async_results.items():
        for size_kb, result in size_map.items():
            lines.append(report_line(f"{path_name}-{size_kb}KB", result))

    lines += [
        "",
        "## 结论摘要",
        "",
        "- 本报告把裸算法、调度层、异步层分开测，避免把路由/排队开销混进算法本体。",
        "- `queue-*` 代表常驻 `CompressQueue` 的入队+等待成本；`async_entry-*` 代表 `llm_text_compress_async()` 单次封装入口总成本，适合看封装开销，不适合当作常驻吞吐基线。",
        "- LLM 真实联网耗时不计入本报告主表；如需补测，应单独记录网络与 provider 波动。",
        "- 若后续进入 P2-7 Heavy 层，可直接拿本报告作为前置基线。",
        "",
    ]
    return "\n".join(lines)


def _progress(label: str, done: int, total: int):
    """进度提示。"""
    logger.info(f"[{label}] {done}/{total}")
    _flush()


def main() -> None:
    sizes = [1, 10, 100, 1024]
    sync_runs = {1: 12, 10: 12, 100: 8, 1024: 4}
    async_runs = {1: 6, 10: 6, 100: 4, 1024: 2}

    sync_algos: dict[str, tuple[Callable[[str], tuple[Any, dict]], str]] = {
        "smartcrush": (smartcrush, "json"),
        "text": (text_compress, "text"),
        "code": (codecrush, "code"),
        "log": (logdedup, "log"),
        "diff": (diff_compress, "diff"),
    }

    sync_results: dict[str, dict[int, BenchResult]] = {}
    logger.info("=== 本地算法层基准 ===")
    _flush()
    for algo_name, (fn, kind) in sync_algos.items():
        sync_results[algo_name] = {}
        for size_kb in sizes:
            samples = make_samples(kind, size_kb, sync_runs[size_kb])
            result = bench_sync_algo(fn, samples)
            sync_results[algo_name][size_kb] = result
            logger.info(
                f"{algo_name:12s} {size_kb:4d}KB  P50={result.p50_ms:8.2f}ms  P95={result.p95_ms:8.2f}ms  Mem={result.peak_mem_kb_p50:8.0f}KB"
            )

    scheduler_results: dict[int, BenchResult] = {}
    logger.info("\n=== 调度层基准 ===")
    _flush()
    for size_kb in sizes:
        samples = make_samples("mixed", size_kb, async_runs[size_kb])
        result = bench_scheduler(samples)
        scheduler_results[size_kb] = result
        logger.info(
            f"scheduler     {size_kb:4d}KB  P50={result.p50_ms:8.2f}ms  P95={result.p95_ms:8.2f}ms  Mem={result.peak_mem_kb_p50:8.0f}KB"
        )

    async_results: dict[str, dict[int, BenchResult]] = {"queue": {}, "async_entry": {}}
    logger.info("\n=== 异步层基准 ===")
    _flush()
    for size_kb in sizes:
        samples = make_samples("text", size_kb, async_runs[size_kb])
        queue_result = bench_async_queue(samples)
        async_results["queue"][size_kb] = queue_result
        logger.info(
            f"queue         {size_kb:4d}KB  P50={queue_result.p50_ms:8.2f}ms  P95={queue_result.p95_ms:8.2f}ms  Mem={queue_result.peak_mem_kb_p50:8.0f}KB"
        )

        entry_result = bench_async_entry(samples)
        async_results["async_entry"][size_kb] = entry_result
        logger.info(
            f"async_entry   {size_kb:4d}KB  P50={entry_result.p50_ms:8.2f}ms  P95={entry_result.p95_ms:8.2f}ms  Mem={entry_result.peak_mem_kb_p50:8.0f}KB"
        )
        _flush()

    report = format_report(sync_results, scheduler_results, async_results)
    out_path = Path("docs/design/mark42-压缩方案-性能基准-20260626.md")
    out_path.write_text(report)
    logger.info(f"\n报告已写入: {out_path}")


if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            from .compress_queue import shutdown_compress_queue
        except ImportError:
            from .compress_queue import shutdown_compress_queue
        shutdown_compress_queue()
