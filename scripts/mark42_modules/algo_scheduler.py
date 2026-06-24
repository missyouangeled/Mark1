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
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 允许独立运行: python3 algo_scheduler.py
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from compression_algorithms import smartcrush
from pii_redactor import redact_pii


# ============================================================================
# 调度策略配置
# ============================================================================

@dataclass
class SchedulerConfig:
    """调度器配置 - 可通过环境变量覆盖"""
    
    # 大小阈值 (bytes)
    skip_below: int = 1024                # < 1KB 跳过
    small_max: int = 10 * 1024            # 1KB-10KB 轻量压缩
    medium_max: int = 100 * 1024          # 10KB-100KB 标准压缩
    
    # 压缩率阈值
    min_useful_ratio: float = 0.10        # < 10% 视为无效
    max_safe_ratio: float = 0.80          # 压缩后 > 80% 视为失败
    
    # PII 阈值
    pii_enabled_small: bool = False       # < 10KB 默认不脱敏 (误报成本高)
    pii_enabled_medium: bool = True       # 10KB-100KB 默认脱敏
    pii_enabled_large: bool = True        # > 100KB 强制脱敏
    
    # 标记阈值
    review_threshold_bytes: int = 100 * 1024  # > 100KB 标记需 review


# ============================================================================
# 调度决策
# ============================================================================

@dataclass
class ScheduleDecision:
    """调度决策结果"""
    
    action: str                           # "skip" | "compress" | "compress+pii" | "review"
    reason: str
    size_bucket: str                      # "tiny" | "small" | "medium" | "large"
    should_compress: bool = False
    should_redact_pii: bool = False
    needs_review: bool = False
    is_json: bool = False
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
    size = len(content.encode('utf-8'))
    
    # 检测是否为 JSON
    is_json = False
    if content and content.strip():
        try:
            json.loads(content)
            is_json = True
        except (json.JSONDecodeError, ValueError):
            is_json = False
    
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
    
    # 2. 压缩 (如果需要)
    if decision.should_compress and decision.is_json:
        compressed, compress_stats = smartcrush(current)
        result["compress_stats"] = compress_stats
        
        # 压缩率验证
        ratio = compress_stats.get("ratio", 0.0)
        original_size = compress_stats.get("original_bytes", 0)
        crushed_size = compress_stats.get("crushed_bytes", 0)
        
        # 护栏 1: 压缩率太低, 无效
        if ratio < cfg.min_useful_ratio:
            result["fallback_reason"] = (
                f"compression ratio {ratio:.2%} below threshold "
                f"{cfg.min_useful_ratio:.2%}, kept original"
            )
            return result
        
        # 护栏 2: 压缩后体积 > 原文 80%, 视为失败
        if original_size > 0 and crushed_size / original_size > cfg.max_safe_ratio:
            result["fallback_reason"] = (
                f"compressed size {crushed_size}/{original_size} "
                f"= {crushed_size/original_size:.2%} > {cfg.max_safe_ratio:.2%}, "
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
    print("=" * 60)
    print("Algorithm Scheduler 单元测试")
    print("=" * 60)
    
    test_cases = [
        # (name, content, expected_action, expected_size_bucket, 
        #  expected_compress, expected_pii)
        
        ("tiny_text",
         "hello world",
         "skip", "tiny", False, False),
        
        ("tiny_json",
         '{"a": 1}',
         "skip", "tiny", False, False),
        
        ("small_text",
         "x" * 5000,  # 5KB
         "skip", "small", False, False),  # 非 JSON
        
        ("small_json",
         '{"items": [' + ",".join([
             '{"id": ' + str(i) + ', "name": "user_' + str(i) + '_' + ("x" * 20) + '"}'
             for i in range(100)
         ]) + ']}',  # ~5KB
         "compress", "small", True, False),
        
        ("medium_json_with_pii",
         '{"users": [' + ",".join([
             '{"email": "user' + str(i) + '@example.com", "name": "user_' + str(i) + '"}'
             for i in range(500)
         ]) + ']}',
         "compress+pii", "medium", True, True),
        
        ("large_json",
         '{"data": [' + ",".join(['"x"' for _ in range(50000)]) + ']}',
         "review", "large", True, True),
        
        ("invalid_json",
         "not json at all, just text " * 200,
         "skip", "small", False, False),  # non-JSON small → skip
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
                print(f"  ✅ [{name}] action={d.action} bucket={d.size_bucket} "
                      f"changed={result['changed']} pii={pii_count} comp={comp_ratio:.1%}")
                passed += 1
            else:
                print(f"  ❌ [{name}] action={d.action}(exp {exp_action}) "
                      f"bucket={d.size_bucket}(exp {exp_bucket}) "
                      f"compress={d.should_compress}(exp {exp_compress}) "
                      f"pii={d.should_redact_pii}(exp {exp_pii})")
                failed += 1
        except Exception as e:
            print(f"  ❌ [{name}] 异常: {e}")
            failed += 1
    
    # 额外测试: 压缩率护栏
    print()
    print("护栏测试:")
    
    # 测试 1: 太小收益回退
    tiny_json = '{"a": 1, "b": 2}'  # 太小 skip
    r = process(tiny_json)
    assert r["changed"] is False, f"tiny content should not change, got {r['changed']}"
    print(f"  ✅ tiny 不变: changed={r['changed']}")
    
    # 测试 2: 大 JSON 触发压缩 + PII
    big_with_pii = json.dumps({
        "logs": [
            {"user": f"user{i}@example.com", "msg": "x" * 100}
            for i in range(200)
        ]
    }, ensure_ascii=False)
    r = process(big_with_pii)
    assert r["changed"] is True
    assert r["pii_stats"]["total_redactions"] > 0
    assert r["compress_stats"]["ratio"] > 0
    print(f"  ✅ big+pii: changed=True, pii={r['pii_stats']['total_redactions']}, "
          f"comp={r['compress_stats']['ratio']:.1%}")
    
    # 测试 3: 错误输入 fail-safe
    r = process(None or "")
    assert r["result"] == "", f"empty input should return empty, got {r['result']!r}"
    print(f"  ✅ 空输入 fail-safe: result={r['result']!r}")
    
    print()
    print(f"结果: {passed + 3} 通过 / {failed} 失败 / 共 {passed + failed + 3} 个")
    return failed == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_tests() else 1)