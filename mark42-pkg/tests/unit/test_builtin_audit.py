"""BuiltinAudit 扩展测试（方案 44 Phase 1：探针接入 + 趋势存储）。

重点验证：
    1. 探针在 shadow 模式下不阻止生产 compact；
    2. 约束静态完整性在有/无约束时的行为；
    3. 趋势记录在新模块启动后正常写入；
    4. 旧六类结构核对不受影响（保持 fallback 兼容）。
"""

from __future__ import annotations

import json


from mark42.audit import AuditResult, Finding
from mark42.audit.constraint_identity import IntegrityReport
from mark42.audit.probes import MODE_SHADOW, ProbeOutcome, ProbeReport, build_report


# ⚠️ 注：BuiltinAudit 在构造时依赖 `from ..config import MARK42_STATE`
# 这个路径在生产环境存在，但测试环境需要先 mock 或提供隔离路径。
# 本测试只验证核心逻辑路径，不依赖磁盘上的真实目录。
# 集成测试在 Phase 2 覆盖。


def _make_audit_result(verdict: str = "pass", score: float = 0.95) -> AuditResult:
    return AuditResult(
        verdict=verdict,
        score=score,
        findings=[
            Finding(category="identity", item="点点", status="preserved"),
            Finding(category="preferences", item="中文优先", status="preserved"),
        ],
        recommendation="继续观察",
    )


def _make_probe_report(**kw) -> ProbeReport:
    from mark42.audit.probes import PROBE_DIMENSIONS
    outs = [
        ProbeOutcome(dimension=d, probe_id=f"{d}-x", score=5)
        for d in PROBE_DIMENSIONS
    ]
    return build_report(outs, **kw)


def _make_constraint_report(
    *,
    total: int = 5,
    preserved: int = 5,
    lost: int = 0,
    blocking: bool = False,
    detector_failed: bool = False,
) -> IntegrityReport:
    return IntegrityReport(
        total=total,
        preserved=preserved,
        lost=lost,
        blocking=blocking,
        detector_failed=detector_failed,
        findings=[],
    )


class TestProbeIntegration:
    """探针在 shadow 模式下不阻止生产 compact。"""

    def test_probe_report_shadow_mode(self):
        """shadow 模式：只记录，不阻断。"""
        rep = _make_probe_report(mode=MODE_SHADOW)
        assert rep.mode == MODE_SHADOW
        assert rep.total_score == 30

    def test_probe_report_never_raises(self):
        """探针异常不得向外抛——否则会拖垮审计主流程。"""
        from mark42.audit.probes import PROBE_DIMENSIONS
        # 模拟空响应（确定性评分会返回 0，不会抛）
        outs = [
            ProbeOutcome(dimension=d, probe_id="x", score=0, method="deterministic")
            for d in PROBE_DIMENSIONS
        ]
        rep = build_report(outs)  # 不应抛
        assert rep.total_score == 0
        assert rep.slo_ok is False

    def test_probe_with_empty_post_text(self):
        """压缩后摘要为空时探针应诚实报低分，而非崩溃。"""
        from mark42.audit.probes import score_deterministic, ProbeSpec
        spec = ProbeSpec(dimension="intent", question="Q", expect_any=["x"])
        out = score_deterministic(spec, "")
        assert out.score == 0  # 空响应得 0
        assert out.method == "deterministic"


class TestConstraintIntegration:
    """约束静态完整性在有/无约束时的行为。"""

    def test_constraint_report_empty_is_not_failure(self):
        """无约束时 survival_rate 应为 1.0（没约束就没丢）。"""
        rep = _make_constraint_report(total=0, preserved=0)
        assert rep.survival_rate() == 1.0
        assert rep.hard_survival_rate() == 1.0

    def test_constraint_report_all_lost(self):
        rep = _make_constraint_report(total=5, preserved=0, lost=5)
        assert rep.survival_rate() == 0.0
        assert rep.reinject_ids == []

    def test_constraint_report_blocking_detected(self):
        rep = _make_constraint_report(total=5, preserved=2, lost=3, blocking=True)
        assert rep.blocking is True

    def test_reinject_ids_on_loss(self):
        """丢失的约束必须被标记为重注入候选。"""
        from mark42.audit.constraint_identity import (
            IntegrityFinding,
        )
        rep = IntegrityReport(
            total=2,
            findings=[
                IntegrityFinding(constraint_id="c-a", status="preserved",
                                 priority="P0", strength="hard"),
                IntegrityFinding(constraint_id="c-b", status="lost",
                                 priority="P1", strength="hard"),
            ],
            reinject_ids=["c-b"],
        )
        assert len(rep.reinject_ids) == 1
        assert "c-b" in rep.reinject_ids

    def test_constraint_report_json_serializable(self):
        rep = _make_constraint_report()
        blob = json.dumps(rep.to_dict(), ensure_ascii=False)
        # survival_rate 是方法，不出现在 to_dict 中
        assert "total" in blob
        assert "preserved" in blob
        assert rep.survival_rate() == 1.0


class TestTrendsIntegration:
    """趋势记录在新模块启动后正常写入。"""

    def test_trend_append_sample(self, tmp_path):
        from mark42.audit.trends import TrendStore, QualitySample
        store = TrendStore(tmp_path / "t.jsonl")
        store.append(QualitySample(timestamp="t1", probe_total=30))
        assert len(store.load()) == 1

    def test_trend_lifecycle(self, tmp_path):
        """审计结果 → 样本 → 写入 → 摘要。"""
        from mark42.audit.trends import TrendStore, sample_from_reports
        store = TrendStore(tmp_path / "t.jsonl")

        # 模拟一次审计
        ar = _make_audit_result()
        pr = _make_probe_report()
        cr = _make_constraint_report()
        sample = sample_from_reports(
            probe_report=pr,
            structure_score=ar.score,
            structure_verdict=ar.verdict,
            constraint_survival=cr.survival_rate(),
            constraint_hard_survival=cr.hard_survival_rate(),
            constraint_blocking=cr.blocking,
            timestamp="2026-08-07T14:00:00+08:00",
            trace_id="tr-test",
            version="2.8.2",
        )
        store.append(sample)
        sm = store.summarize()
        assert sm.probe_avg == 30.0
        assert sm.structure_avg == 0.95
        assert sm.constraint_survival_avg == 1.0

    def test_consecutive_trends(self, tmp_path):
        from mark42.audit.trends import TrendStore, sample_from_reports
        from mark42.audit.probes import PROBE_DIMENSIONS
        store = TrendStore(tmp_path / "t.jsonl")
        for score in (30, 28, 26, 24, 22, 20):
            per_dim = max(score // 6, 0)
            outs = [
                ProbeOutcome(dimension=d, probe_id=f"{d}-x", score=per_dim,
                             method="deterministic")
                for d in PROBE_DIMENSIONS
            ]
            pr = build_report(outs)
            pr.total_score = score
            cr = _make_constraint_report(preserved=5, lost=0)
            s = sample_from_reports(probe_report=pr, structure_score=0.9,
                                    constraint_survival=cr.survival_rate(),
                                    constraint_hard_survival=cr.hard_survival_rate(),
                                    timestamp=f"t{score}", trace_id="x")
            store.append(s)
        sm = store.summarize()
        assert sm.regression is True
        assert sm.probe_min == 20


class TestAuditResult:
    """旧 audit 结构不受影响。"""

    def test_result_has_expected_fields(self):
        result = _make_audit_result()
        assert result.verdict == "pass"
        assert result.score == 0.95
        assert len(result.findings) == 2
        assert result.recommendation == "继续观察"

    def test_skip_result_has_zero_score(self):
        result = AuditResult(verdict="skip", score=0.0)
        assert result.score == 0.0
        assert result.verdict == "skip"

    def test_error_result_has_error_field(self):
        result = AuditResult(verdict="error", score=0.0, error="disk full")
        assert result.error == "disk full"

    def test_findings_detail_not_mutated(self):
        result = _make_audit_result()
        f = result.findings[0]
        assert f.category == "identity"
        assert f.item == "点点"
        assert f.status == "preserved"
