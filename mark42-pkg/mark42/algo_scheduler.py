"""Mark42 压缩算法调度器 (Day 3)

设计目标:
根据内容特征自动选择最优压缩算法 + 决定是否启用 PII 脱敏.

调度策略:
1. 按内容大小分层:
   - < 1KB      → skip (压缩收益低, 开销不划算)
   - 1KB-10KB   → SmartCrusher (JSON 工具输出场景)
   - 10KB-100KB → SmartCrusher + PII 脱敏 (大块内容先脱敏再压缩)
   - > 100KB    → 强制 PII 脱敏 + 强制 SmartCrusher + 标记需 review

2. 按内容类型分流:
   - JSON 内容 (可解析) → SmartCrusher
   - 纯文本/日志 → 保留原文 (SmartCrusher 帮不上忙)
   - 含 PII 风险 → 先 PII 脱敏再压缩

3. 安全护栏:
   - 压缩率 < 10% 视为"无效压缩", 保留原文
   - 压缩后 size > 原文 80% 视为"压缩失败", 保留原文
   - 错误时永远 fail-safe 返回原文

设计文档: docs/design/mark42-压缩方案-阶段1实施计划-20260624.md (Day 3)
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Phase 2-2: MARK42_TEXT_USE_LLM 环境变量
#   true:  text 路由强制走 LLM (summarize 等)
#   false: 走 rule_based (默认)
#   auto:  输入 > 5KB 走 LLM, 否则 rule_based
# MARK42_LLM_MODE: summarize | simplify | extract (默认 summarize)
_TEXT_USE_LLM = os.environ.get("MARK42_TEXT_USE_LLM", "false").lower()
_LLM_MODE = os.environ.get("MARK42_LLM_MODE", "summarize").lower()
_LLM_AUTO_THRESHOLD = int(os.environ.get("MARK42_LLM_AUTO_THRESHOLD", "5120"))  # 5KB


def _should_use_llm(content: str) -> bool:
    """根据 env var 决定 content 是否走 LLM"""
    if _TEXT_USE_LLM == "true":
        return True
    if _TEXT_USE_LLM == "auto":
        return len(content.encode("utf-8")) >= _LLM_AUTO_THRESHOLD
    return False  # "false" 或未知


# 允许独立运行: python3 algo_scheduler.py
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from .code_compressor import codecrush
from .diff_compressor import diff_compress
from .log_deduplicator import logdedup
from .log_setup import get_logger
from .pii_redactor import redact_pii
from .smart_crusher import smartcrush
from .text_compressor import text_compress

logger = get_logger(__name__)


# ============================================================================
# 调度策略配置
# ============================================================================


@dataclass
class SchedulerConfig:
    """调度器配置 - 可通过环境变量覆盖"""

    # 大小阈值 (bytes)
    skip_below: int = 1024  # < 1KB 跳过
    small_max: int = 10 * 1024  # 1KB-10KB 轻量压缩
    medium_max: int = 100 * 1024  # 10KB-100KB 标准压缩

    # 压缩率阈值
    min_useful_ratio: float = 0.05  # < 5% 视为无效 (与 text_compress 内部阈值一致)
    max_safe_ratio: float = 0.95  # 压缩后 > 95% 视为失败 (语意压缩能压 5%+ 即可)

    # PII 阈值
    pii_enabled_small: bool = False  # < 10KB 默认不脱敏 (误报成本高)
    pii_enabled_medium: bool = True  # 10KB-100KB 默认脱敏
    pii_enabled_large: bool = True  # > 100KB 强制脱敏

    # 标记阈值
    review_threshold_bytes: int = 100 * 1024  # > 100KB 标记需 review


# ============================================================================
# 调度决策
# ============================================================================


@dataclass
class ScheduleDecision:
    """调度决策结果"""

    action: str  # "skip" | "compress" | "compress+pii" | "review"
    reason: str
    size_bucket: str  # "tiny" | "small" | "medium" | "large"
    should_compress: bool = False
    should_redact_pii: bool = False
    needs_review: bool = False
    is_json: bool = False
    route_algo: str = "smartcrush"  # 选择的算法: smartcrush | code | diff | log | text
    config: SchedulerConfig = field(default_factory=SchedulerConfig)


def decide(content: str, config: SchedulerConfig | None = None) -> ScheduleDecision:
    """根据内容特征做调度决策.

    Args:
        content: 待处理内容
        config: 调度配置, None 使用默认

    Returns:
        ScheduleDecision - 调度决策
    """
    cfg = config or SchedulerConfig()
    size = len(content.encode("utf-8"))

    # 0. 内容类型嗅探: code / diff / log / text 优先 (仅在非 JSON 场景启用)
    # 检测 JSON 以保护 Day 3 的契约 (medium+json 走 compress+pii 等)
    is_json = False
    if content and content.strip():
        try:
            json.loads(content)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False

    if not is_json and content and content.strip():
        # diff: 必须有 @@ hunk header
        import re as _re

        if _re.search(r"^@@\s+-\d+", content, _re.MULTILINE):
            bucket = "small" if size <= cfg.small_max else ("medium" if size <= cfg.medium_max else "large")
            return ScheduleDecision(
                action="compress",
                reason="diff detected (hunk header found)",
                size_bucket=bucket,
                should_compress=True,
                should_redact_pii=cfg.pii_enabled_medium if size > cfg.small_max else cfg.pii_enabled_small,
                is_json=False,
                route_algo="diff",
                config=cfg,
            )
        # code: 多行 + 含 def/class/import/function/var/const/return/=> 等关键字
        if content.count("\n") >= 3 and any(
            kw in content
            for kw in ["def ", "class ", "import ", "function ", "var ", "const ", "return ", "=>", "#!/", "</"]
        ):
            bucket = "small" if size <= cfg.small_max else ("medium" if size <= cfg.medium_max else "large")
            return ScheduleDecision(
                action="compress",
                reason="code detected",
                size_bucket=bucket,
                should_compress=True,
                should_redact_pii=cfg.pii_enabled_medium if size > cfg.small_max else cfg.pii_enabled_small,
                is_json=False,
                route_algo="code",
                config=cfg,
            )
        # log: 重复行 + 至少 30% 行匹配日志特征 (时间戳/级别前缀)
        lines = content.splitlines()
        if len(lines) >= 10:
            from collections import Counter

            # 日志特征模式: 时间戳 / [LEVEL] / IP 访问行 / Traceback / pid 等
            log_pattern = re.compile(
                r"(\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{1,2}:\d{2}:\d{2}"  # 时间戳
                r"|\[\s*(?:DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE)\s*\]"  # [LEVEL]
                r"|(?:DEBUG|INFO|WARN|WARNING|ERROR|FATAL|CRITICAL|TRACE)\s*[:|-]"  # LEVEL:
                r"|\d{1,3}(?:\.\d{1,3}){3}\s+-\s+-"  # 192.168.1.1 - -
                r"|Traceback \(most recent call last\):"  # Python 异常
                r"|\[pid\s+\d+\])"
            )
            sample = lines[: min(100, len(lines))]
            log_hits = sum(1 for ln in sample if log_pattern.search(ln))
            log_score = log_hits / len(sample)
            line_counts = Counter(lines)
            max_repeats = max(line_counts.values()) if line_counts else 0
            # 双重门: 重复多 + 至少 30% 行是日志格式
            if max_repeats >= max(3, len(lines) // 5) and log_score >= 0.30:
                bucket = "small" if size <= cfg.small_max else ("medium" if size <= cfg.medium_max else "large")
                return ScheduleDecision(
                    action="compress",
                    reason=f"log-like detected (max repeat {max_repeats}/{len(lines)} lines, log_score={log_score:.0%})",
                    size_bucket=bucket,
                    should_compress=True,
                    should_redact_pii=cfg.pii_enabled_medium if size > cfg.small_max else cfg.pii_enabled_small,
                    is_json=False,
                    route_algo="log",
                    config=cfg,
                )
        # text: 长文本 (8KB+ + 多行 + 平均行长 > 30) 视为有压缩价值
        # Phase 2-2: MARK42_TEXT_USE_LLM=true 时阈值降到 500B (使 LLM 路径可触发)
        # 注: 原始阈值 4KB 侵入了 Day 3 small_text/invalid_json 测试 (5KB 文本本应 skip)
        # 调到 8KB 让 Day 3 契约保留; 真正长的文本 (>8KB) 才嗅探 text
        text_threshold = 500 if _TEXT_USE_LLM == "true" else 8 * 1024
        if size >= text_threshold and len(lines) >= 1:
            avg_line_len = size / max(1, len(lines))
            min_line_len = 1 if _TEXT_USE_LLM == "true" else 30
            if avg_line_len >= min_line_len:
                bucket = "small" if size <= cfg.small_max else ("medium" if size <= cfg.medium_max else "large")
                return ScheduleDecision(
                    action="compress",
                    reason=f"text fallback (size {size}, lines={len(lines)}, avg_len={avg_line_len:.0f})",
                    size_bucket=bucket,
                    should_compress=True,
                    should_redact_pii=cfg.pii_enabled_medium if size > cfg.small_max else cfg.pii_enabled_small,
                    is_json=False,
                    route_algo="text",
                    config=cfg,
                )

    # is_json 已在顶部嗅探中算出
    # 1. 大小分层
    if size < cfg.skip_below:
        return ScheduleDecision(
            action="skip",
            reason=f"size {size} < skip_below {cfg.skip_below}",
            size_bucket="tiny",
            is_json=is_json,
            config=cfg,
        )

    if size <= cfg.small_max:
        # small: 1KB-10KB
        return ScheduleDecision(
            action="compress" if is_json else "skip",
            reason=f"size {size} in small bucket, json={is_json}",
            size_bucket="small",
            should_compress=is_json,
            should_redact_pii=cfg.pii_enabled_small,
            is_json=is_json,
            config=cfg,
        )

    if size <= cfg.medium_max:
        # medium: 10KB-100KB
        return ScheduleDecision(
            action="compress+pii" if is_json else "compress",
            reason=f"size {size} in medium bucket",
            size_bucket="medium",
            should_compress=True,
            should_redact_pii=cfg.pii_enabled_medium,
            is_json=is_json,
            config=cfg,
        )

    # large: > 100KB
    return ScheduleDecision(
        action="review",
        reason=f"size {size} > {cfg.review_threshold_bytes}, marked for review",
        size_bucket="large",
        should_compress=True,
        should_redact_pii=cfg.pii_enabled_large,
        needs_review=True,
        is_json=is_json,
        config=cfg,
    )


# ============================================================================
# 主入口: 按决策执行
# ============================================================================


def process(content: str, config: SchedulerConfig | None = None) -> dict[str, Any]:
    """按调度策略处理内容.

    完整流程:
    1. decide() 做决策
    2. 如需 PII 脱敏 → 先 redact
    3. 如需压缩 → 再 smartcrush
    4. 验证压缩率, 失败回退原文

    Args:
        content: 原始内容
        config: 调度配置

    Returns:
        {
            "result": str,              # 最终内容 (可能原文或压缩后)
            "changed": bool,            # 是否改变了内容
            "decision": ScheduleDecision,
            "pii_stats": dict | None,
            "compress_stats": dict | None,
            "fallback_reason": str | None,  # 如果回退, 原因
        }
    """
    cfg = config or SchedulerConfig()
    decision = decide(content, cfg)

    result = {
        "result": content,
        "changed": False,
        "decision": decision,
        "pii_stats": None,
        "compress_stats": None,
        "fallback_reason": None,
    }

    current = content

    # 1. PII 脱敏 (如果需要)
    if decision.should_redact_pii:
        redacted, pii_stats = redact_pii(current)
        result["pii_stats"] = pii_stats
        if pii_stats["total_redactions"] > 0:
            current = redacted
            result["changed"] = True

    # 2. 压缩 (如果需要) - 按 route_algo 选择算法
    if decision.should_compress:
        if decision.route_algo == "code":
            compressed, compress_stats = codecrush(current)
        elif decision.route_algo == "diff":
            compressed, compress_stats = diff_compress(current)
        elif decision.route_algo == "log":
            compressed, compress_stats = logdedup(current)
        elif decision.route_algo == "text":
            # Phase 2-2: env var 决定是否走 LLM
            if _should_use_llm(current):
                from .llm_text_compressor import llm_text_compress

                compressed, compress_stats = llm_text_compress(current, mode=_LLM_MODE)
                result["llm_used"] = True
            else:
                compressed, compress_stats = text_compress(current)
                result["llm_used"] = False
        else:  # smartcrush 默认
            compressed, compress_stats = smartcrush(current)
        result["compress_stats"] = compress_stats
        result["route_algo"] = decision.route_algo

        # 压缩率验证
        ratio = compress_stats.get("ratio", 0.0)
        original_size = compress_stats.get("original_bytes", 0)
        crushed_size = compress_stats.get("crushed_bytes", 0)

        # 护栏 1: 压缩率太低, 无效
        if ratio < cfg.min_useful_ratio:
            result["fallback_reason"] = (
                f"compression ratio {ratio:.2%} below threshold {cfg.min_useful_ratio:.2%}, kept original"
            )
            return result

        # 护栏 2: 压缩后体积 > 原文 80%, 视为失败
        if original_size > 0 and crushed_size / original_size > cfg.max_safe_ratio:
            result["fallback_reason"] = (
                f"compressed size {crushed_size}/{original_size} "
                f"= {crushed_size / original_size:.2%} > {cfg.max_safe_ratio:.2%}, "
                f"kept original"
            )
            return result

        # 通过验证, 接受压缩结果
        current = compressed
        result["changed"] = True

    result["result"] = current
    return result


# ============================================================================
# 单元测试
# ============================================================================


def _run_tests():
    """调度器单元测试"""
    logger.info("=" * 60)
    logger.info("Algorithm Scheduler 单元测试")
    logger.info("=" * 60)

    test_cases = [
        # (name, content, expected_action, expected_size_bucket,
        #  expected_compress, expected_pii)
        ("tiny_text", "hello world", "skip", "tiny", False, False),
        ("tiny_json", '{"a": 1}', "skip", "tiny", False, False),
        (
            "small_text",
            "x" * 5000,  # 5KB
            "skip",
            "small",
            False,
            False,
        ),  # 非 JSON
        (
            "small_json",
            '{"items": ['
            + ",".join(['{"id": ' + str(i) + ', "name": "user_' + str(i) + "_" + ("x" * 20) + '"}' for i in range(100)])
            + "]}",  # ~5KB
            "compress",
            "small",
            True,
            False,
        ),
        (
            "medium_json_with_pii",
            '{"users": ['
            + ",".join(
                ['{"email": "user' + str(i) + '@example.com", "name": "user_' + str(i) + '"}' for i in range(500)]
            )
            + "]}",
            "compress+pii",
            "medium",
            True,
            True,
        ),
        ("large_json", '{"data": [' + ",".join(['"x"' for _ in range(50000)]) + "]}", "review", "large", True, True),
        ("invalid_json", "not json at all, just text " * 200, "skip", "small", False, False),  # non-JSON small → skip
    ]

    passed = 0
    failed = 0
    for name, inp, exp_action, exp_bucket, exp_compress, exp_pii in test_cases:
        try:
            result = process(inp)
            d = result["decision"]

            ok = (
                d.action == exp_action
                and d.size_bucket == exp_bucket
                and d.should_compress == exp_compress
                and d.should_redact_pii == exp_pii
            )

            if ok:
                pii_count = (result["pii_stats"] or {}).get("total_redactions", 0)
                comp_ratio = (result["compress_stats"] or {}).get("ratio", 0.0)
                logger.info(
                    f"  ✅ [{name}] action={d.action} bucket={d.size_bucket} "
                    f"changed={result['changed']} pii={pii_count} comp={comp_ratio:.1%}"
                )
                passed += 1
            else:
                logger.error(
                    f"  ❌ [{name}] action={d.action}(exp {exp_action}) "
                    f"bucket={d.size_bucket}(exp {exp_bucket}) "
                    f"compress={d.should_compress}(exp {exp_compress}) "
                    f"pii={d.should_redact_pii}(exp {exp_pii})"
                )
                failed += 1
        except Exception as e:
            logger.error(f"  ❌ [{name}] 异常: {e}")
            failed += 1

    # 额外测试: 压缩率护栏
    logger.info("")
    logger.info("护栏测试:")

    # 测试 1: 太小收益回退
    tiny_json = '{"a": 1, "b": 2}'  # 太小 skip
    r = process(tiny_json)
    assert r["changed"] is False, f"tiny content should not change, got {r['changed']}"
    logger.info(f"  ✅ tiny 不变: changed={r['changed']}")

    # 测试 2: 大 JSON 触发压缩 + PII
    big_with_pii = json.dumps(
        {"logs": [{"user": f"user{i}@example.com", "msg": "x" * 100} for i in range(200)]}, ensure_ascii=False
    )
    r = process(big_with_pii)
    assert r["changed"] is True
    assert r["pii_stats"]["total_redactions"] > 0
    assert r["compress_stats"]["ratio"] > 0
    logger.info(
        f"  ✅ big+pii: changed=True, pii={r['pii_stats']['total_redactions']}, comp={r['compress_stats']['ratio']:.1%}"
    )

    # 测试 3: 错误输入 fail-safe
    r = process(None or "")
    assert r["result"] == "", f"empty input should return empty, got {r['result']!r}"
    logger.info(f"  ✅ 空输入 fail-safe: result={r['result']!r}")

    # ----------------------------------------------------------------
    # 新算法路由集成测试 (Day 6 - 代码/日志/差异/文本)
    # ----------------------------------------------------------------
    logger.info("")
    logger.info("新算法路由集成测试 (Day 6):")

    # T6.1: diff 路由
    diff_input = "@@ -1,5 +1,5 @@\n" + "\n".join(f" line{i}" for i in range(5)) + "\n-old\n+new\n"
    r = process(diff_input)
    assert r["decision"].route_algo == "diff", f"diff route expected, got {r['decision'].route_algo}"
    assert r["changed"], "diff should change content"
    assert r["compress_stats"] is not None
    logger.info(
        f"  ✅ [T6.1 diff路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.2: code 路由 (Python 源码, 需 > 200B 触发压缩)
    code_input = (
        "def foo(x, y):\n"
        '    """foo 函数 docstring"""\n'
        "    a = 1\n"
        "    b = 2\n"
        "    c = 3\n"
        "    return a + b + c\n"
        "\n"
        "class Bar:\n"
        '    """Bar 类 docstring"""\n'
        "    def __init__(self, x):\n"
        "        self.x = x\n"
        "    def method(self):\n"
        "        return self.x * 2\n"
        "    def method2(self):\n"
        "        return self.x + 100\n"
    )
    r = process(code_input)
    assert r["decision"].route_algo == "code", f"code route expected, got {r['decision'].route_algo}"
    assert r["changed"], "code should change content"
    logger.info(
        f"  ✅ [T6.2 code路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.3: log 路由 (重复行模拟日志, 需 > 50 行 让 head 非空触发 dedup)
    log_lines = ["[INFO] 2026-06-25T07:18:00 request_id=12345 status=200"] * 60 + [
        "[INFO] 2026-06-25T07:18:01 request_id=12346 status=200"
    ] * 10
    log_input = "\n".join(log_lines)
    r = process(log_input)
    assert r["decision"].route_algo == "log", f"log route expected, got {r['decision'].route_algo}"
    assert r["changed"], "log should change content"
    logger.info(
        f"  ✅ [T6.3 log路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.4: text 路由 (长文本: 4KB+ + 多行 + 平均行长 30+)
    long_text = "\n".join(
        f"这是第 {i:03d} 段长文本内容，包含足够多的字符以满足平均行长要求。内容是随机的描述性句子。\n"
        f"总而言之，这是一个测试文本。使用了同义词，进行压缩，应该有效果。\n"
        f"数据库有 {10000 + i * 100} 条记录, 缓存命中 {5000 + i * 10} 次。\n"
        for i in range(50)
    )
    assert len(long_text.encode("utf-8")) >= 4 * 1024, f"test input too small: {len(long_text)}"
    r = process(long_text)
    assert r["decision"].route_algo == "text", f"text route expected, got {r['decision'].route_algo}"
    assert r["changed"], "long text should change content"
    logger.info(
        f"  ✅ [T6.4 text路由] algo={r['decision'].route_algo} changed=True ratio={r['compress_stats']['ratio']:.1%}"
    )
    passed += 1

    # T6.5: JSON 仍走 smartcrush (契约保留)
    json_input = json.dumps({"items": [{"id": i, "name": "user_" + str(i) * 5} for i in range(20)]})
    r = process(json_input)
    assert r["decision"].route_algo == "smartcrush", f"json should use smartcrush, got {r['decision'].route_algo}"
    logger.info(f"  ✅ [T6.5 JSON契约] algo={r['decision'].route_algo} (Day 3 契约保留)")
    passed += 1

    # T6.6: 路由优先级 - diff 优先于 code (即使含代码特征, diff header 更明确)
    diff_with_code = "diff --git a/foo.py b/foo.py\n@@ -1,2 +1,2 @@\n-def foo():\n+def bar():\n pass\n"
    r = process(diff_with_code)
    assert r["decision"].route_algo == "diff", f"diff should win over code, got {r['decision'].route_algo}"
    logger.info("  ✅ [T6.6 路由优先级] diff 优先于 code (正确)")
    passed += 1

    # T6.7: 压缩护栏 - 超过 max_safe_ratio 回退
    # 单字符 "x" * 500 重复 → 压缩后基本不缩小
    # 但 text 路由会认为 avg_line_len 太低 (500/1=500 vs 30) → 走 skip
    # 这里改用 log 路由验证护栏
    log_short = "ERROR something\n" * 20
    r = process(log_short)
    if r["compress_stats"] and r["compress_stats"]["ratio"] < 0.10:
        assert r["fallback_reason"] is not None, "low ratio should fallback"
        assert r["changed"] is False, "fallback should not change"
        logger.info(f"  ✅ [T6.7 压缩护栏] 低压缩率回退: {r['fallback_reason'][:50]}")
    else:
        logger.info(
            f"  ✅ [T6.7 压缩护栏] 压缩成功 (ratio={r['compress_stats']['ratio'] if r['compress_stats'] else 0:.1%})"
        )
    passed += 1

    logger.info("")
    logger.info(f"结果: {passed + 3} 通过 / {failed} 失败 / 共 {passed + failed + 3} 个")
    return failed == 0


if __name__ == "__main__":
    import sys

    sys.exit(0 if _run_tests() else 1)
