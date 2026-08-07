"""质量趋势存储测试（方案 44 Phase 1）。

重点钉住：
    1. structure_score 与 probe_total **永不合并**（方案 §5.2）；
    2. `degraded_run` 样本不污染能力趋势；
    3. 坏行不得导致整份历史丢失（静默丢数据是最贵的故障形态）；
    4. 轮替必须原子，且保留**最近**的样本。
"""

from __future__ import annotations

import json

import pytest

from mark42.audit.probes import (
    PROBE_DIMENSIONS,
    PROBE_EVIDENCE,
    ProbeOutcome,
    build_report,
)
from mark42.audit.trends import (
    MAX_HISTORY_LINES,
    QualitySample,
    TrendStore,
    sample_from_reports,
    slo_status,
)


@pytest.fixture
def store(tmp_path):
    return TrendStore(tmp_path / "trends" / "quality-trends.jsonl")


def _report(score: int = 5, *, evidence_absent: bool = False):
    outs = [
        ProbeOutcome(dimension=d, probe_id=f"{d}-x", score=score,
                     evidence_absent=evidence_absent)
        for d in PROBE_DIMENSIONS
    ]
    return build_report(outs)


# ── 基础读写 ──────────────────────────────────────────


class TestBasicIO:
    def test_empty_store_returns_empty(self, store):
        assert store.load() == []
        assert store.summarize().count == 0

    def test_append_and_load(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=28))
        store.append(QualitySample(timestamp="t2", probe_total=30))
        samples = store.load()
        assert [s.timestamp for s in samples] == ["t1", "t2"]
        assert [s.probe_total for s in samples] == [28, 30]

    def test_creates_parent_dirs(self, store):
        store.append(QualitySample(timestamp="t1"))
        assert store.path.exists()

    def test_load_limit_returns_latest(self, store):
        for i in range(5):
            store.append(QualitySample(timestamp=f"t{i}", probe_total=20 + i))
        got = store.load(limit=2)
        assert [s.timestamp for s in got] == ["t3", "t4"]

    def test_jsonl_one_line_per_sample(self, store):
        store.append(QualitySample(timestamp="t1"))
        store.append(QualitySample(timestamp="t2"))
        lines = store.path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            json.loads(line)

    def test_unknown_fields_ignored_on_load(self, store):
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text(
            json.dumps({"timestamp": "t1", "probe_total": 30,
                        "future_field": "x"}) + "\n",
            encoding="utf-8")
        assert store.load()[0].probe_total == 30

    def test_append_failure_does_not_raise(self, tmp_path):
        """趋势写失败不得拖垮审计主流程。

        ⚠️ 这里是测试构造的极端场景——父路径是文件，append 时的 mkdir 必然失败。
        真实场景中趋势路径由 config 配置，不会出现父路径是文件的情况。
        此测试只验证：失败时**不抛异常，且原文件不被破坏**。
        """
        fpath = tmp_path / "file_as_dir"
        fpath.write_text("i am a file", encoding="utf-8")

        # 构造一个父路径是文件的 TrendStore（子路径做 append 目标）
        sub = TrendStore(fpath / "sub" / "t.jsonl")
        try:
            sub.append(QualitySample(timestamp="t"))
            # 没抛就算通过
        except Exception:  # noqa: BLE001 — 对外层不抛
            pytest.fail("append 不应向外抛异常")

        # 原文件仍在
        assert fpath.read_text(encoding="utf-8") == "i am a file"


# ── 损坏容忍 ──────────────────────────────────────────


class TestCorruptionTolerance:
    def test_bad_line_skipped_not_fatal(self, store):
        """一行坏了不能丢整份历史。"""
        store.append(QualitySample(timestamp="t1", probe_total=28))
        with store.path.open("a", encoding="utf-8") as f:
            f.write("{ this is not json\n")
        store.append(QualitySample(timestamp="t3", probe_total=30))

        samples = store.load()
        assert [s.timestamp for s in samples] == ["t1", "t3"]

    def test_blank_lines_skipped(self, store):
        store.append(QualitySample(timestamp="t1"))
        with store.path.open("a", encoding="utf-8") as f:
            f.write("\n\n   \n")
        assert len(store.load()) == 1

    def test_non_dict_json_skipped(self, store):
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text('["a list"]\n{"timestamp":"ok"}\n', encoding="utf-8")
        samples = store.load()
        assert len(samples) == 1
        assert samples[0].timestamp == "ok"


# ── 轮替 ──────────────────────────────────────────────


class TestRotation:
    def test_rotation_keeps_most_recent(self, store):
        for i in range(MAX_HISTORY_LINES + 20):
            store.append(QualitySample(timestamp=f"t{i}", probe_total=i % 31))
        samples = store.load()
        assert len(samples) == MAX_HISTORY_LINES
        # 保留的必须是**最近**的
        assert samples[-1].timestamp == f"t{MAX_HISTORY_LINES + 19}"

    def test_no_rotation_below_limit(self, store):
        for i in range(10):
            store.append(QualitySample(timestamp=f"t{i}"))
        assert len(store.load()) == 10

    def test_no_temp_files_left_behind(self, store):
        for i in range(MAX_HISTORY_LINES + 5):
            store.append(QualitySample(timestamp=f"t{i}"))
        leftovers = list(store.path.parent.glob("*.tmp"))
        assert leftovers == []


# ── 两套分数不得合并（方案 §5.2 核心）─────────────────


class TestScoreSeparation:
    def test_structure_and_probe_stored_separately(self, store):
        store.append(QualitySample(
            timestamp="t1", structure_score=0.9, probe_total=27))
        s = store.load()[0]
        assert s.structure_score == 0.9
        assert s.probe_total == 27

    def test_summary_reports_them_independently(self, store):
        store.append(QualitySample(timestamp="t1", structure_score=1.0, probe_total=30))
        store.append(QualitySample(timestamp="t2", structure_score=0.5, probe_total=18))
        sm = store.summarize()
        assert sm.structure_avg == 0.75
        assert sm.probe_avg == 24.0
        # 绝不出现把两者相加/平均的字段
        assert not hasattr(sm, "combined_score")
        assert not hasattr(sm, "overall_score")

    def test_probe_only_sample_leaves_structure_none(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30))
        sm = store.summarize()
        assert sm.probe_avg == 30.0
        assert sm.structure_avg is None

    def test_structure_only_sample_leaves_probe_none(self, store):
        store.append(QualitySample(timestamp="t1", structure_score=0.8))
        sm = store.summarize()
        assert sm.structure_avg == 0.8
        assert sm.probe_avg is None


# ── degraded_run 不污染趋势 ───────────────────────────


class TestDegradedExclusion:
    def test_degraded_excluded_by_default(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30))
        store.append(QualitySample(timestamp="t2", probe_total=6, degraded_run=True))
        sm = store.summarize()
        assert sm.count == 1
        assert sm.probe_avg == 30.0
        assert sm.excluded_degraded == 1

    def test_degraded_included_when_requested(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30))
        store.append(QualitySample(timestamp="t2", probe_total=6, degraded_run=True))
        sm = store.summarize(exclude_degraded=False)
        assert sm.count == 2
        assert sm.probe_avg == 18.0
        assert sm.excluded_degraded == 0

    def test_probe_history_excludes_degraded(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30))
        store.append(QualitySample(timestamp="t2", probe_total=6, degraded_run=True))
        assert store.probe_history() == [30]

    def test_all_degraded_yields_empty_summary(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=6, degraded_run=True))
        sm = store.summarize()
        assert sm.count == 0
        assert sm.probe_avg is None
        assert sm.excluded_degraded == 1


# ── 维度均值与 SLO 达标率 ─────────────────────────────


class TestDimensionStats:
    def test_dimension_avg(self, store):
        store.append(QualitySample(
            timestamp="t1", probe_total=30,
            probe_by_dimension={d: 5 for d in PROBE_DIMENSIONS}))
        store.append(QualitySample(
            timestamp="t2", probe_total=24,
            probe_by_dimension={d: 4 for d in PROBE_DIMENSIONS}))
        sm = store.summarize()
        for d in PROBE_DIMENSIONS:
            assert sm.dimension_avg[d] == 4.5

    def test_partial_dimension_data(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=10,
                                   probe_by_dimension={"intent": 5}))
        sm = store.summarize()
        assert sm.dimension_avg == {"intent": 5.0}

    def test_slo_pass_rate(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30, slo_ok=True))
        store.append(QualitySample(timestamp="t2", probe_total=18, slo_ok=False))
        store.append(QualitySample(timestamp="t3", probe_total=28, slo_ok=True))
        assert store.summarize().slo_pass_rate == pytest.approx(2 / 3)

    def test_min_max_latest(self, store):
        for score in (30, 20, 26):
            store.append(QualitySample(timestamp=f"t{score}", probe_total=score))
        sm = store.summarize()
        assert sm.probe_min == 20
        assert sm.probe_max_seen == 30
        assert sm.probe_latest == 26


# ── 回归检测联动 ──────────────────────────────────────


class TestRegressionIntegration:
    def test_regression_flagged(self, store):
        for score in (30, 30, 30, 20, 20, 20):
            store.append(QualitySample(timestamp=f"x{score}", probe_total=score))
        assert store.summarize().regression is True

    def test_no_regression_when_stable(self, store):
        for score in (28, 29, 28, 29, 28, 29):
            store.append(QualitySample(timestamp="x", probe_total=score))
        assert store.summarize().regression is False

    def test_insufficient_history_no_regression(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=10))
        assert store.summarize().regression is False


# ── 约束存活统计 ──────────────────────────────────────


class TestConstraintStats:
    def test_survival_avg_and_hard_min(self, store):
        store.append(QualitySample(timestamp="t1", probe_total=30,
                                   constraint_survival=1.0,
                                   constraint_hard_survival=1.0))
        store.append(QualitySample(timestamp="t2", probe_total=30,
                                   constraint_survival=0.8,
                                   constraint_hard_survival=0.9))
        sm = store.summarize()
        assert sm.constraint_survival_avg == pytest.approx(0.9)
        assert sm.constraint_hard_survival_min == pytest.approx(0.9)


# ── 样本构造 ──────────────────────────────────────────


class TestSampleFromReports:
    def test_maps_probe_report(self):
        rep = _report(5)
        s = sample_from_reports(probe_report=rep, timestamp="t1", trace_id="tr1")
        assert s.probe_total == 30
        assert s.slo_ok is True
        assert s.probe_by_dimension == {d: 5 for d in PROBE_DIMENSIONS}
        assert s.trace_id == "tr1"
        assert s.degraded_run is False

    def test_degraded_run_detected_from_outcomes(self):
        outs = [ProbeOutcome(dimension=d, probe_id="x", score=5)
                for d in PROBE_DIMENSIONS]
        for o in outs:
            if o.dimension == PROBE_EVIDENCE:
                o.evidence_absent = True
        s = sample_from_reports(probe_report=build_report(outs))
        assert s.degraded_run is True

    def test_structure_kept_separate(self):
        s = sample_from_reports(probe_report=_report(5), structure_score=0.7,
                                structure_verdict="partial")
        assert s.probe_total == 30
        assert s.structure_score == 0.7
        assert s.structure_verdict == "partial"

    def test_without_probe_report(self):
        s = sample_from_reports(structure_score=0.9, structure_verdict="pass")
        assert s.probe_total is None
        assert s.structure_score == 0.9

    def test_constraint_fields_mapped(self):
        s = sample_from_reports(constraint_survival=0.8,
                                constraint_hard_survival=1.0,
                                constraint_blocking=False)
        assert s.constraint_survival == 0.8
        assert s.constraint_hard_survival == 1.0

    def test_slo_failures_copied_not_shared(self):
        rep = _report(1)
        s = sample_from_reports(probe_report=rep)
        s.slo_failures.append("injected")
        assert "injected" not in rep.slo_failures


# ── SLO 状态判定 ──────────────────────────────────────


class TestSloStatus:
    def test_healthy(self, store):
        for _ in range(3):
            store.append(QualitySample(timestamp="t", probe_total=30,
                                       constraint_hard_survival=1.0))
        st = slo_status(store.summarize())
        assert st["ok"] is True
        assert st["issues"] == []

    def test_low_average_flagged(self, store):
        for _ in range(3):
            store.append(QualitySample(timestamp="t", probe_total=18))
        st = slo_status(store.summarize())
        assert st["ok"] is False
        assert any("probe_avg_below_slo" in i for i in st["issues"])

    def test_hard_constraint_loss_flagged(self, store):
        store.append(QualitySample(timestamp="t", probe_total=30,
                                   constraint_hard_survival=0.8))
        st = slo_status(store.summarize())
        assert any("hard_constraint_loss" in i for i in st["issues"])

    def test_regression_flagged_in_status(self, store):
        for score in (30, 30, 30, 20, 20, 20):
            store.append(QualitySample(timestamp="t", probe_total=score))
        st = slo_status(store.summarize())
        assert any("regression_detected" in i for i in st["issues"])

    def test_empty_store_is_ok(self, store):
        st = slo_status(store.summarize())
        assert st["ok"] is True
        assert st["sampleCount"] == 0
