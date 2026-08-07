"""Shadow 对比 + 回滚演练测试（方案 44 Phase 6）。"""

from __future__ import annotations

import json


from mark42.audit.shadow_report import (
    ShadowReportStore,
    compare_shadow,
)
from mark42.audit.rollback_drill import run_rollback_drill


# ── Shadow 对比 ───────────────────────────────────────


class TestShadowComparison:
    def _legacy(self):
        return {
            "strategyUsed": "llm-analyze",
            "preserved": {
                "userIdentity": "点点（袁文涛）",
                "preferences": ["中文优先"],
                "activeProjects": ["Mark42"],
            },
            "analyzedMessages": 10,
        }

    def _structured(self):
        return {
            "strategyUsed": "structured-shadow",
            "itemCount": 5,
            "stateFingerprint": "abc123",
            "preserved": {
                "sessionIntent": "按方案 44 干活",
                "decisions": ["先冻结 schema"],
                "constraints": ["只用中文", "默认 dry-run"],
            },
        }

    def test_comparison_basic(self):
        comp = compare_shadow(self._legacy(), self._structured(),
                              trace_id="tr1")
        assert comp.legacy_strategy == "llm-analyze"
        assert comp.structured_strategy == "structured-shadow"
        assert comp.structured_item_count == 5
        assert comp.constraints_total == 2
        assert comp.constraints_survived == 2
        assert comp.trace_id == "tr1"

    def test_intent_comparison(self):
        legacy = {"preserved": {"userIdentity": "按方案 44 干活"}}
        structured = {"preserved": {"sessionIntent": "按方案 44 干活"}}
        comp = compare_shadow(legacy, structured)
        assert comp.intent_captured_by_structured is True

    def test_intent_mismatch(self):
        legacy = {"preserved": {"userIdentity": "完全不同的目标"}}
        structured = {"preserved": {"sessionIntent": "另一个目标"}}
        comp = compare_shadow(legacy, structured)
        assert comp.intent_captured_by_structured is False

    def test_probe_scores_with_post_text(self):
        comp = compare_shadow(self._legacy(), self._structured(),
                              post_text="按方案 44 干活")
        assert comp.legacy_probe_total is not None
        assert comp.structured_probe_total is not None

    def test_json_serializable(self):
        comp = compare_shadow(self._legacy(), self._structured())
        json.loads(comp.to_json())


class TestShadowReportStore:
    def test_append_and_load(self, tmp_path):
        store = ShadowReportStore(tmp_path / "shadow.jsonl")
        comp = compare_shadow({"preserved": {}}, {"preserved": {}})
        store.append(comp)
        loaded = store.load()
        assert len(loaded) == 1
        assert loaded[0].legacy_strategy == ""

    def test_summarize_empty(self, tmp_path):
        store = ShadowReportStore(tmp_path / "shadow.jsonl")
        assert store.summarize() == {"count": 0}

    def test_summarize_with_data(self, tmp_path):
        store = ShadowReportStore(tmp_path / "shadow.jsonl")
        for i in range(3):
            comp = compare_shadow(
                {"preserved": {"userIdentity": "x"}},
                {"preserved": {"sessionIntent": "x",
                                 "constraints": ["只用中文", "dry-run"]}},
            )
            store.append(comp)
        sm = store.summarize()
        assert sm["count"] == 3
        assert sm["intent_capture_rate"] == 1.0
        assert sm["constraint_survival_avg"] == 1.0

    def test_bad_lines_skipped(self, tmp_path):
        store = ShadowReportStore(tmp_path / "shadow.jsonl")
        store.append(compare_shadow({}, {}))
        store.path.open("a").write("broken\n")
        store.append(compare_shadow({}, {}))
        assert len(store.load()) == 2


# ── 回滚演练 ──────────────────────────────────────────


class TestRollbackDrill:
    def test_all_flags_default_off(self):
        """所有 flag 默认关闭。"""
        report = run_rollback_drill()
        assert report.all_passed, [
            (s.flag, s.detail) for s in report.steps if not s.passed
        ]

    def test_six_checks_run(self):
        report = run_rollback_drill()
        assert len(report.steps) == 6

    def test_report_serializable(self):
        import json
        report = run_rollback_drill()
        json.dumps(report.to_dict(), ensure_ascii=False)
