"""错误档案反馈闭环（方案 44 建设项 F / Phase 5 / §9.6）。

当前不足（方案 §9.6）
--------------------
`auto_remediate` 可以执行修复，但**执行结果没有回写档案**。
档案只知道"批准过"，不知道"修复是否真的成功"。

本模块补：
    - `record_outcome()`：统一回写执行结果
    - `effectiveness` 字段：成功率追踪
    - L3 -> L2 自动降级：连续失败 -> 撤销 auto_approved
    - 禁止自动升回 L3：降级后必须人工重新批准

设计原则
--------
    - 成功一次不自动证明方案长期有效
    - 连续 2 次失败立即降级
    - 环境或版本变化后旧方案降为"需复核"
    - 不做梯度训练，不改模型权重，只做可审计的状态更新
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: 连续失败几次后自动降级
L3_DOWNGRADE_THRESHOLD = 2

#: 最近 N 次成功率低于此阈值时降级
L3_SUCCESS_RATE_WINDOW = 5
L3_SUCCESS_RATE_THRESHOLD = 0.4

#: outcome 结果枚举
OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
OUTCOME_PARTIAL = "partial"
OUTCOME_ROLLED_BACK = "rolled_back"

OUTCOMES = (OUTCOME_SUCCESS, OUTCOME_FAILED, OUTCOME_PARTIAL, OUTCOME_ROLLED_BACK)


@dataclass
class ExecutionOutcome:
    """一次 auto_remediate 执行的结果记录。"""

    execution_id: str
    entry_id: str
    result: str  # success / failed / partial / rolled_back
    verification: str = ""
    side_effects: list[str] = field(default_factory=list)
    effectiveness_score: float = 0.0
    last_validated_at: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "entry_id": self.entry_id,
            "result": self.result,
            "verification": self.verification,
            "side_effects": list(self.side_effects),
            "effectiveness_score": self.effectiveness_score,
            "last_validated_at": self.last_validated_at,
            "timestamp": self.timestamp,
        }


@dataclass
class DowngradeDecision:
    """L3 -> L2 降级决策。"""

    should_downgrade: bool = False
    reason: str = ""
    new_status: str = ""
    new_auto_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_downgrade": self.should_downgrade,
            "reason": self.reason,
            "new_status": self.new_status,
            "new_auto_approved": self.new_auto_approved,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── 降级判定 ──────────────────────────────────────────


def check_downgrade(
    consecutive_failures: int,
    recent_outcomes: list[str],
    *,
    threshold: int = L3_DOWNGRADE_THRESHOLD,
    window: int = L3_SUCCESS_RATE_WINDOW,
    rate_threshold: float = L3_SUCCESS_RATE_THRESHOLD,
) -> DowngradeDecision:
    """判定是否应该 L3 -> L2 降级。

    规则（方案 §9.6）：
        1. 连续 `threshold` 次失败 -> 立即降级
        2. 最近 `window` 次成功率低于 `rate_threshold` -> 降级
        3. partial 不清零 consecutive_failures，但按配置计入失败窗口

    Returns:
        DowngradeDecision
    """
    # 规则 1：连续失败
    if consecutive_failures >= threshold:
        return DowngradeDecision(
            should_downgrade=True,
            reason=f"consecutive_failures={consecutive_failures} >= {threshold}",
            new_status="RESOLVED",  # 降为非自动批准
            new_auto_approved=False,
        )

    # 规则 2：成功率窗口
    if len(recent_outcomes) >= window:
        recent = recent_outcomes[-window:]
        # success 算成功，partial 不算成功也不算失败
        successes = sum(1 for o in recent if o == OUTCOME_SUCCESS)
        rate = successes / len(recent)
        if rate < rate_threshold:
            return DowngradeDecision(
                should_downgrade=True,
                reason=f"success_rate={rate:.0%} < {rate_threshold:.0%} in last {window}",
                new_status="RESOLVED",
                new_auto_approved=False,
            )

    return DowngradeDecision()


# ── outcome 记录 ─────────────────────────────────────

#: outcome 历史文件名
OUTCOMES_FILENAME = "remediation_outcomes.jsonl"


def record_outcome(
    outcomes_path: Path | str,
    outcome: ExecutionOutcome,
) -> None:
    """把执行结果追加到 outcomes 文件（JSONL）。

    方案 §9.6：auto_remediate 无论成功、失败、部分成功或回滚，
    都必须调用统一 record_outcome()。
    """
    path = Path(outcomes_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not outcome.timestamp:
        outcome.timestamp = now_iso()
    line = json.dumps(outcome.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_outcomes(
    outcomes_path: Path | str,
    *,
    entry_id: str | None = None,
    limit: int | None = None,
) -> list[ExecutionOutcome]:
    """读取 outcomes 历史。"""
    path = Path(outcomes_path)
    if not path.exists():
        return []
    results: list[ExecutionOutcome] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if entry_id and data.get("entry_id") != entry_id:
                    continue
                results.append(ExecutionOutcome(**{
                    k: v for k, v in data.items()
                    if k in ExecutionOutcome.__dataclass_fields__
                }))
    except OSError:
        return results
    if limit and limit > 0:
        return results[-limit:]
    return results


def compute_effectiveness(
    outcomes: list[ExecutionOutcome],
) -> dict[str, Any]:
    """计算某个 entry 的修复方案有效性统计。"""
    if not outcomes:
        return {
            "total": 0,
            "successes": 0,
            "failures": 0,
            "partials": 0,
            "rolled_back": 0,
            "success_rate": None,
            "consecutive_failures": 0,
            "last_result": None,
            "last_validated_at": "",
        }
    successes = sum(1 for o in outcomes if o.result == OUTCOME_SUCCESS)
    failures = sum(1 for o in outcomes if o.result == OUTCOME_FAILED)
    partials = sum(1 for o in outcomes if o.result == OUTCOME_PARTIAL)
    rolled = sum(1 for o in outcomes if o.result == OUTCOME_ROLLED_BACK)

    # 连续失败计数（从最近的往前数）
    consecutive = 0
    for o in reversed(outcomes):
        if o.result in (OUTCOME_FAILED, OUTCOME_ROLLED_BACK):
            consecutive += 1
        elif o.result == OUTCOME_SUCCESS:
            break  # 成功清零
        # partial 不清零也不累加

    rate = successes / len(outcomes) if outcomes else 0.0
    last = outcomes[-1]

    return {
        "total": len(outcomes),
        "successes": successes,
        "failures": failures,
        "partials": partials,
        "rolled_back": rolled,
        "success_rate": rate,
        "consecutive_failures": consecutive,
        "last_result": last.result,
        "last_validated_at": last.last_validated_at or last.timestamp,
        "failure_count": failures + rolled,  # 失败 + 回滚都算不成功
    }


def should_invalidate_on_version_change(
    outcomes: list[ExecutionOutcome],
    current_version: str,
) -> bool:
    """环境或版本变化后旧方案是否需要复核（方案 §9.6）。

    首版简化：如果 outcomes 里有 last_validated_at 且与当前版本不同，
    标记为需复核。实际的版本对比由调用方完成。
    """
    if not outcomes:
        return False
    # 如果有 side_effects 记录了版本信息，检查是否变化
    for o in reversed(outcomes):
        if o.side_effects and current_version in o.side_effects:
            return False
    return True  # 没找到当前版本的记录 -> 需复核
