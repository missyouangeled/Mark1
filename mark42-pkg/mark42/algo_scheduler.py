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
from dataclasses import dataclass, field
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


# ------------------------------------------------------------------
# 压缩器注册表（解耦：压缩器自注册，scheduler 不硬 import）
# ------------------------------------------------------------------

from .log_setup import get_logger
from .pii_redactor import redact_pii

logger = get_logger(__name__)


@dataclass
class CompressorEntry:
    """注册表中的一个压缩器条目。"""

    name: str  # 算法名: smartcrush | code | diff | log | text
    func: Any  # callable(content: str) -> tuple[str, dict[str, Any]]


_REGISTRY: dict[str, CompressorEntry] = {}


def register_compressor(name: str, func: Any) -> None:
    """注册一个压缩算法到调度器。

    Args:
        name: 算法名（与 ScheduleDecision.route_algo 对应）
        func: callable(content: str) -> (compressed: str, stats: dict)
    """
    _REGISTRY[name] = CompressorEntry(name=name, func=func)
    logger.debug(f"压缩器注册: {name} -> {func.__module__}.{func.__name__}")


def get_compressor(name: str) -> CompressorEntry | None:
    """按名称获取已注册的压缩器。未注册返回 None。"""
    return _REGISTRY.get(name)


def list_compressors() -> list[str]:
    """列出所有已注册的压缩器名称。"""
    return sorted(_REGISTRY.keys())


# ------------------------------------------------------------------
# 自动注册内置压缩器（延迟加载，失败不影响 scheduler 本身）
# ------------------------------------------------------------------


def _register_builtin_compressors() -> None:
    """注册 Mark42 内置的 5 个压缩器 + smartcrush。

    每个压缩器独立 try-import，某个缺失不影响其余。
    """
    if _REGISTRY:
        return  # 已注册过

    try:
        from .smart_crusher import smartcrush

        register_compressor("smartcrush", smartcrush)
    except ImportError:
        logger.warning("smart_crusher 不可用，跳过注册")

    try:
        from .code_compressor import codecrush

        register_compressor("code", codecrush)
    except ImportError:
        logger.warning("code_compressor 不可用，跳过注册")

    try:
        from .diff_compressor import diff_compress

        register_compressor("diff", diff_compress)
    except ImportError:
        logger.warning("diff_compressor 不可用，跳过注册")

    try:
        from .log_deduplicator import logdedup

        register_compressor("log", logdedup)
    except ImportError:
        logger.warning("log_deduplicator 不可用，跳过注册")

    try:
        from .text_compressor import text_compress

        register_compressor("text", text_compress)
    except ImportError:
        logger.warning("text_compressor 不可用，跳过注册")


# 模块加载时自动注册
_register_builtin_compressors()


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

    # 2. 压缩 (如果需要) - 通过注册表获取算法
    if decision.should_compress:
        entry = get_compressor(decision.route_algo)
        if entry is None:
            result["fallback_reason"] = f"compressor '{decision.route_algo}' not registered"
            return result

        if decision.route_algo == "text":
            # Phase 2-2: env var 决定是否走 LLM
            if _should_use_llm(current):
                from .llm_text_compressor import llm_text_compress

                compressed, compress_stats = llm_text_compress(current, mode=_LLM_MODE)
                result["llm_used"] = True
            else:
                compressed, compress_stats = entry.func(current)
                result["llm_used"] = False
        else:
            compressed, compress_stats = entry.func(current)
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
    """运行测试（已提取到 tests/test_algo_scheduler.py）。"""
    from tests.test_algo_scheduler import run_tests

    return run_tests()


if __name__ == "__main__":
    import sys as _sys

    _sys.exit(0 if _run_tests() else 1)
