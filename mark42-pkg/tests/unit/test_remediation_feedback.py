"""错误档案反馈闭环测试（方案 44 Phase 5 / §9.6）。

重点钉住：
    1. 连续 2 次失败 -> 立即降级，撤销 auto_approved；
    2. 成功一次清零 consecutive_failures，但不自动证明长期有效；
    3. 降级后禁止自动升回 L3；
    4. record_outcome 必须被所有路径调用（success/failed/partial/rolled_back）。
"""

from __future__ import annotations

import json


from mark42.audit.remediation_feedback import (
    L3_SUCCESS_RATE_WINDOW,
    OUTCOME_FAILED,
    OUTCOME_PARTIAL,
    OUTCOME_ROLLED_BACK,
    OUTCOME_SUCCESS,
    ExecutionOutcome,
    check_downgrade,
    compute_effectiveness,
    load_outcomes,
    record_outcome,
    should_invalidate_on_version_change,
)


def _outcome(entry_id="e1", result=OUTCOME_SUCCESS, **kw):
    return ExecutionOutcome(
        execution_id=kw.get("exec_id", "x1"),
        entry_id=entry_id,
        result=result,
        verification=kw.get("verification", ""),
        side_effects=kw.get("side_effects", []),
        effectiveness_score=kw.get("score", 0.0),
        last_validated_at=kw.get("last_validated_at", ""),
        timestamp=kw.get("timestamp", ""),
    )


# ── 降级判定 ──────────────────────────────────────────


class TestDowngrade:
    def test_consecutive_failures_trigger_downgrade(self):
        dec = check_downgrade(consecutive_failures=2, recent_outcomes=[])
        assert dec.should_downgrade is True
        assert dec.new_auto_approved is False

    def test_single_failure_no_downgrade(self):
        dec = check_downgrade(consecutive_failures=1, recent_outcomes=[])
        assert dec.should_downgrade is False

    def test_zero_failures_no_downgrade(self):
        assert not check_downgrade(0, []).should_downgrade

    def test_success_rate_below_threshold(self):
        outcomes = [OUTCOME_FAILED] * L3_SUCCESS_RATE_WINDOW
        dec = check_downgrade(0, outcomes)
        assert dec.should_downgrade is True
        assert "success_rate" in dec.reason

    def test_success_rate_above_threshold(self):
        outcomes = [OUTCOME_SUCCESS] * 3 + [OUTCOME_FAILED] * 2
        dec = check_downgrade(0, outcomes)
        assert dec.should_downgrade is False  # 60% > 40%

    def test_partial_does_not_clear_failures(self):
        """partial 不清零 consecutive_failures（方案 §9.6）。"""
        dec = check_downgrade(2, [OUTCOME_PARTIAL])
        assert dec.should_downgrade is True

    def test_insufficient_window_no_downgrade(self):
        """窗口不足时不判定成功率。"""
        dec = check_downgrade(0, [OUTCOME_FAILED, OUTCOME_FAILED])
        assert dec.should_downgrade is False

    def test_downgrade_reason_includes_numbers(self):
        dec = check_downgrade(3, [])
        assert "3" in dec.reason
        assert "2" in dec.reason  # threshold


# ── record_outcome + load_outcomes ───────────────────


class TestOutcomeIO:
    def test_record_and_load(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        record_outcome(p, _outcome(result=OUTCOME_SUCCESS))
        record_outcome(p, _outcome(result=OUTCOME_FAILED))
        loaded = load_outcomes(p)
        assert len(loaded) == 2
        assert loaded[0].result == OUTCOME_SUCCESS
        assert loaded[1].result == OUTCOME_FAILED

    def test_record_sets_timestamp(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        record_outcome(p, _outcome())
        loaded = load_outcomes(p)
        assert loaded[0].timestamp  # 自动填充

    def test_load_empty(self, tmp_path):
        assert load_outcomes(tmp_path / "nope.jsonl") == []

    def test_load_by_entry_id(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        record_outcome(p, _outcome(entry_id="e1"))
        record_outcome(p, _outcome(entry_id="e2"))
        loaded = load_outcomes(p, entry_id="e1")
        assert len(loaded) == 1
        assert loaded[0].entry_id == "e1"

    def test_load_with_limit(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        for i in range(5):
            record_outcome(p, _outcome(entry_id=f"e{i}"))
        loaded = load_outcomes(p, limit=2)
        assert len(loaded) == 2

    def test_bad_line_skipped(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        record_outcome(p, _outcome())
        p.open("a", encoding="utf-8").write("{ broken\n")
        record_outcome(p, _outcome())
        assert len(load_outcomes(p)) == 2

    def test_jsonl_format(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        record_outcome(p, _outcome(result=OUTCOME_SUCCESS, verification="pytest"))
        lines = p.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["result"] == OUTCOME_SUCCESS
        assert data["verification"] == "pytest"


# ── compute_effectiveness ───────────────────────────


class TestEffectiveness:
    def test_empty(self):
        stats = compute_effectiveness([])
        assert stats["total"] == 0
        assert stats["success_rate"] is None
        assert stats["consecutive_failures"] == 0

    def test_all_success(self):
        outcomes = [_outcome(result=OUTCOME_SUCCESS) for _ in range(3)]
        stats = compute_effectiveness(outcomes)
        assert stats["successes"] == 3
        assert stats["success_rate"] == 1.0
        assert stats["consecutive_failures"] == 0

    def test_consecutive_failures_count(self):
        outcomes = [
            _outcome(result=OUTCOME_SUCCESS),
            _outcome(result=OUTCOME_FAILED),
            _outcome(result=OUTCOME_FAILED),
        ]
        stats = compute_effectiveness(outcomes)
        assert stats["consecutive_failures"] == 2

    def test_success_clears_consecutive(self):
        outcomes = [
            _outcome(result=OUTCOME_FAILED),
            _outcome(result=OUTCOME_FAILED),
            _outcome(result=OUTCOME_SUCCESS),
            _outcome(result=OUTCOME_FAILED),
        ]
        stats = compute_effectiveness(outcomes)
        assert stats["consecutive_failures"] == 1  # 只有最后一个

    def test_partial_does_not_clear(self):
        outcomes = [
            _outcome(result=OUTCOME_FAILED),
            _outcome(result=OUTCOME_PARTIAL),
            _outcome(result=OUTCOME_FAILED),
        ]
        stats = compute_effectiveness(outcomes)
        assert stats["consecutive_failures"] == 2  # partial 不清零

    def test_rolled_back_counts_as_failure(self):
        outcomes = [
            _outcome(result=OUTCOME_SUCCESS),
            _outcome(result=OUTCOME_ROLLED_BACK),
            _outcome(result=OUTCOME_ROLLED_BACK),
        ]
        stats = compute_effectiveness(outcomes)
        assert stats["consecutive_failures"] == 2
        assert stats["rolled_back"] == 2

    def test_last_result(self):
        outcomes = [_outcome(result=OUTCOME_SUCCESS), _outcome(result=OUTCOME_FAILED)]
        stats = compute_effectiveness(outcomes)
        assert stats["last_result"] == OUTCOME_FAILED

    def test_failure_count_includes_rolled_back(self):
        outcomes = [_outcome(result=OUTCOME_FAILED), _outcome(result=OUTCOME_ROLLED_BACK)]
        stats = compute_effectiveness(outcomes)
        assert stats["failure_count"] == 2


# ── 版本失效 ──────────────────────────────────────────


class TestVersionInvalidation:
    def test_no_outcomes_no_invalidation(self):
        assert should_invalidate_on_version_change([], "2.8.2") is False

    def test_version_match_no_invalidation(self):
        outcomes = [_outcome(side_effects=["2.8.2"])]
        assert should_invalidate_on_version_change(outcomes, "2.8.2") is False

    def test_version_mismatch_invalidates(self):
        outcomes = [_outcome(side_effects=["2.8.1"])]
        assert should_invalidate_on_version_change(outcomes, "2.8.2") is True

    def test_checks_most_recent_first(self):
        outcomes = [
            _outcome(side_effects=["2.8.1"]),
            _outcome(side_effects=["2.8.2"]),
        ]
        assert should_invalidate_on_version_change(outcomes, "2.8.2") is False
