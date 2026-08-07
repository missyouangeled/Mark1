"""能力探针 schema 与确定性评分测试（方案 44 Phase 0）。

重点覆盖三类容易做成"假绿灯"的地方：
    1. 探针维度与现有 AUDIT_CATEGORIES **不得混为一谈**（方案 §5.2）；
    2. gate 模式**不承诺**自动撤销 compact（方案 §5.4）；
    3. `evidence_absent` 的维度不得被算成模型缺陷（比较两端必须同源）。
"""

from __future__ import annotations

import json

import pytest

from mark42.audit import AUDIT_CATEGORIES
from mark42.audit.probes import (
    GATE_CANNOT_AUTO_REVERT,
    MODE_GATE,
    MODE_SHADOW,
    PROBE_DIMENSIONS,
    PROBE_EVIDENCE,
    PROBE_INSTRUCTION,
    PROBE_MODES,
    PROBE_QUESTIONS,
    PROBE_TO_AUDIT_CATEGORY,
    PROBE_TOTAL_MAX,
    SCORE_RUBRIC,
    SLO_MIN_TOTAL,
    SLO_STRICT_MIN,
    ProbeOutcome,
    ProbeReport,
    ProbeSpec,
    build_report,
    default_probe_specs,
    detect_hallucination,
    detect_regression,
    evaluate_slo,
    score_deterministic,
)

# ── 辅助 ──────────────────────────────────────────────


def _full_marks(**override) -> list[ProbeOutcome]:
    """六维全 5 分。"""
    outs = []
    for d in PROBE_DIMENSIONS:
        outs.append(ProbeOutcome(dimension=d, probe_id=f"{d}-x",
                                 score=override.get(d, 5)))
    return outs


# ── schema 冻结 ───────────────────────────────────────


class TestSchemaFrozen:
    def test_six_dimensions(self):
        assert len(PROBE_DIMENSIONS) == 6
        assert PROBE_TOTAL_MAX == 30

    def test_every_dimension_has_question(self):
        for d in PROBE_DIMENSIONS:
            assert PROBE_QUESTIONS[d]

    def test_every_dimension_mapped_to_audit_category(self):
        """映射只用于报告关联（方案 §5.2）。"""
        for d in PROBE_DIMENSIONS:
            cats = PROBE_TO_AUDIT_CATEGORY[d]
            assert cats, f"{d} 缺少映射"
            for c in cats:
                assert c in AUDIT_CATEGORIES, f"{c} 不是合法的结构审计类别"

    def test_probe_dimensions_are_not_audit_categories(self):
        """铁律：新探针不是旧审计类别的改名。两套必须可区分。"""
        assert set(PROBE_DIMENSIONS).isdisjoint(set(AUDIT_CATEGORIES))

    def test_rubric_covers_zero_to_five(self):
        assert set(SCORE_RUBRIC) == {0, 1, 2, 3, 4, 5}
        assert "违反约束" in SCORE_RUBRIC[0]

    def test_default_specs_cover_all_dimensions(self):
        specs = default_probe_specs()
        assert {s.dimension for s in specs} == set(PROBE_DIMENSIONS)

    def test_strict_dimensions_marked_in_specs(self):
        by_dim = {s.dimension: s for s in default_probe_specs()}
        assert by_dim[PROBE_INSTRUCTION].strict is True
        assert by_dim[PROBE_EVIDENCE].strict is True

    def test_probe_id_is_stable_and_distinct(self):
        a = ProbeSpec(dimension="intent", question="Q", expect_any=["x", "y"])
        b = ProbeSpec(dimension="intent", question="Q", expect_any=["y", "x"])
        c = ProbeSpec(dimension="intent", question="Q2", expect_any=["x", "y"])
        assert a.probe_id() == b.probe_id(), "关键词顺序不应改变 ID"
        assert a.probe_id() != c.probe_id(), "问题变了 ID 必须变"

    def test_gate_does_not_promise_auto_revert(self):
        """方案 §5.4 修订要点：compact 返回后不可自动撤销。"""
        assert GATE_CANNOT_AUTO_REVERT is True
        assert MODE_GATE in PROBE_MODES


# ── 确定性评分 ────────────────────────────────────────


class TestDeterministicScoring:
    def test_all_matched_full_score(self):
        spec = ProbeSpec(dimension="intent", question="Q",
                         expect_all=["Mark42"], expect_any=["压缩"])
        out = score_deterministic(spec, "我们在做 Mark42 的压缩改造")
        assert out.score == 5
        assert out.method == "deterministic"
        assert not out.missing

    def test_forbid_wins_over_everything(self):
        """禁止项优先级最高——哪怕其他断言全中也判 0。"""
        spec = ProbeSpec(dimension="instruction", question="Q",
                         expect_all=["中文"], forbid=["Sure, I"])
        out = score_deterministic(spec, "中文 Sure, I can help")
        assert out.score == 0
        assert out.is_violation()
        assert out.violated == ["Sure, I"]

    def test_empty_response_zero(self):
        spec = ProbeSpec(dimension="intent", question="Q", expect_any=["x"])
        assert score_deterministic(spec, "").score == 0
        assert score_deterministic(spec, "   ").score == 0

    def test_all_required_missing_zero(self):
        spec = ProbeSpec(dimension="decision", question="Q",
                         expect_all=["豆包", "compaction"])
        out = score_deterministic(spec, "完全不相干的回答")
        assert out.score == 0
        assert set(out.missing) == {"豆包", "compaction"}

    def test_more_than_half_missing_scores_one(self):
        spec = ProbeSpec(dimension="decision", question="Q",
                         expect_all=["a", "b", "c"])
        out = score_deterministic(spec, "只提到 a")
        assert out.score == 1

    def test_partial_missing_scores_three(self):
        spec = ProbeSpec(dimension="decision", question="Q",
                         expect_all=["a", "b", "c", "d"])
        out = score_deterministic(spec, "提到 a b c")
        assert out.score == 3

    def test_expect_any_all_missed_caps_at_two(self):
        spec = ProbeSpec(dimension="artifact", question="Q",
                         expect_any=["armor.py", "config.py"])
        out = score_deterministic(spec, "改了一些文件")
        assert out.score == 2

    def test_no_assertions_defers_to_judge(self):
        """没有断言时不能假装打分——必须标 skipped 交给 judge。"""
        spec = ProbeSpec(dimension="intent", question="Q")
        out = score_deterministic(spec, "有内容")
        assert out.method == "skipped"
        assert "judge" in out.reason

    def test_raw_response_is_preserved(self):
        """方案 §5.3：禁止只存最终分数。"""
        spec = ProbeSpec(dimension="intent", question="Q", expect_any=["x"])
        out = score_deterministic(spec, "这里有 x 出现")
        assert "这里有 x" in out.raw_response

    def test_evidence_absent_propagates(self):
        spec = ProbeSpec(dimension="artifact", question="Q", expect_any=["a.py"])
        out = score_deterministic(spec, "不知道", evidence_absent=True)
        assert out.evidence_absent is True


# ── SLO 判定 ──────────────────────────────────────────


class TestSLO:
    def test_full_marks_pass(self):
        rep = build_report(_full_marks())
        assert rep.slo_ok, rep.slo_failures
        assert rep.total_score == 30

    def test_total_below_threshold_fails(self):
        rep = build_report([
            ProbeOutcome(dimension=d, probe_id="x", score=3)
            for d in PROBE_DIMENSIONS
        ])
        assert rep.total_score == 18 < SLO_MIN_TOTAL
        assert not rep.slo_ok
        assert any("total_below_slo" in f for f in rep.slo_failures)

    def test_strict_dimension_below_min_fails_even_if_total_ok(self):
        """Instruction=3 但总分够——仍必须失败。"""
        outs = _full_marks()
        for o in outs:
            if o.dimension == PROBE_INSTRUCTION:
                o.score = 3
        rep = build_report(outs)
        assert rep.total_score == 28 >= SLO_MIN_TOTAL
        assert not rep.slo_ok
        assert any("strict_dimension_below_min" in f for f in rep.slo_failures)

    def test_evidence_absent_exempts_strict_check(self):
        """上游没证据时低分不算模型缺陷（比较两端必须同源）。"""
        outs = _full_marks()
        for o in outs:
            if o.dimension == PROBE_EVIDENCE:
                o.score = 1
                o.evidence_absent = True
        rep = build_report(outs)
        assert not any("strict_dimension_below_min" in f for f in rep.slo_failures)

    def test_evidence_absent_still_counts_toward_total(self):
        """豁免只针对严格单项，总分仍如实反映。"""
        outs = _full_marks()
        for o in outs:
            if o.dimension == PROBE_EVIDENCE:
                o.score = 1
                o.evidence_absent = True
        rep = build_report(outs)
        assert rep.total_score == 26

    def test_violation_always_fails(self):
        outs = _full_marks()
        outs[0].violated = ["English reply"]
        rep = build_report(outs)
        assert not rep.slo_ok
        assert any("constraint_violation" in f for f in rep.slo_failures)

    def test_hallucination_always_fails(self):
        rep = build_report(_full_marks(), hallucination=True)
        assert not rep.slo_ok
        assert "hallucination_detected" in rep.slo_failures

    def test_missing_strict_dimension_detected(self):
        outs = [o for o in _full_marks() if o.dimension != PROBE_INSTRUCTION]
        rep = build_report(outs)
        assert any("missing_strict_dimension" in f for f in rep.slo_failures)

    def test_strict_min_boundary_is_inclusive(self):
        outs = _full_marks()
        for o in outs:
            if o.dimension in (PROBE_INSTRUCTION, PROBE_EVIDENCE):
                o.score = SLO_STRICT_MIN
        rep = build_report(outs)
        assert not any("strict_dimension" in f for f in rep.slo_failures)

    def test_evaluate_slo_recomputes_total(self):
        rep = ProbeReport(outcomes=_full_marks(), total_score=999)
        evaluate_slo(rep)
        assert rep.total_score == 30

    def test_bad_mode_rejected(self):
        with pytest.raises(ValueError, match="未知探针模式"):
            build_report(_full_marks(), mode="turbo")

    def test_judge_fallback_counted(self):
        outs = _full_marks()
        outs[0].method = "judge"
        outs[1].method = "judge"
        rep = build_report(outs)
        assert rep.judge_fallback_count == 2


# ── hallucination 检测 ────────────────────────────────


class TestHallucination:
    def test_marked_inference_is_not_hallucination(self):
        """明确标注推断 = 遵守了召回/推断分离，不该被罚。"""
        assert detect_hallucination("我猜他肯定是累了", ["无关证据"]) is False
        assert detect_hallucination("这是我的判断，肯定是配置问题", []) is False

    def test_unsupported_assertion_is_hallucination(self):
        assert detect_hallucination("肯定是磁盘满了导致的", ["CPU 负载偏高"]) is True

    def test_supported_assertion_is_not_hallucination(self):
        assert detect_hallucination("肯定是磁盘满了", ["磁盘满了，根盘 100%"]) is False

    def test_empty_response(self):
        assert detect_hallucination("", ["x"]) is False

    def test_plain_statement_without_assertion_words(self):
        assert detect_hallucination("根盘用了 76%", []) is False


# ── 回归检测 ──────────────────────────────────────────


class TestRegression:
    def test_insufficient_history(self):
        assert detect_regression([30, 29, 28]) is False

    def test_stable_history_no_regression(self):
        assert detect_regression([28, 29, 28, 29, 28, 29]) is False

    def test_clear_drop_triggers(self):
        assert detect_regression([30, 30, 30, 20, 20, 20]) is True

    def test_small_drop_below_threshold(self):
        """29→28 只掉 3.4%，不到 10% 阈值。"""
        assert detect_regression([29, 29, 29, 28, 28, 28]) is False

    def test_improvement_never_regression(self):
        assert detect_regression([20, 20, 20, 30, 30, 30]) is False

    def test_zero_prior_avg_guarded(self):
        assert detect_regression([0, 0, 0, 0, 0, 0]) is False


# ── 报告序列化 ────────────────────────────────────────


class TestReportSerialization:
    def test_json_serializable(self):
        rep = build_report(_full_marks(), mode=MODE_SHADOW, timestamp="2026-08-07T13:00:00+08:00")
        blob = rep.to_json()
        back = json.loads(blob)
        assert back["total_score"] == 30
        assert back["mode"] == MODE_SHADOW

    def test_disclaimer_always_present(self):
        """方案 §6.2 强制要求：报告必须声明不等价于生产 Agent 行为。"""
        rep = build_report(_full_marks())
        assert "不能等价证明真实 Agent 行为" in rep.disclaimer or \
               "不能等价证明真实 Agent 会话行为" in rep.disclaimer

    def test_by_dimension_lookup(self):
        rep = build_report(_full_marks())
        assert set(rep.by_dimension()) == set(PROBE_DIMENSIONS)
