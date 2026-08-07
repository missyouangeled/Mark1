"""fixture 场景集自检（方案 44 Phase 0）。

场景集是后续所有 Phase 的**尺子**。尺子本身必须先校准：
    - 每个场景的 expected_state 必须通过 schema 校验；
    - 每个场景声明的不变量必须真的成立（不能只写在注释里）；
    - 游标必须自洽（byte_offset / observed_size / message_count 对得上）；
    - 场景之间必须互不污染（load_all 每次返回新实例）。
"""

from __future__ import annotations

import pytest

from mark42.audit.probes import (
    PROBE_DIMENSIONS,
    ProbeSpec,
    build_report,
    score_deterministic,
)
from mark42.context_state import (
    CursorInvalidReason,
    validate_context_state,
)
from tests.fixtures.compaction_scenarios import (
    ALL_SCENARIOS,
    SCENARIO_SET_VERSION,
    load_all,
    load_by_name,
)

# ── 注册表 ────────────────────────────────────────────


class TestRegistry:
    def test_version_frozen(self):
        assert SCENARIO_SET_VERSION == 1

    def test_all_scenarios_loadable(self):
        scenarios = load_all()
        assert len(scenarios) == len(ALL_SCENARIOS) == 4

    def test_names_unique(self):
        names = [s.name for s in load_all()]
        assert len(names) == len(set(names))

    def test_load_by_name(self):
        assert load_by_name("work_continuity").name == "work_continuity"

    def test_unknown_name_raises_with_hints(self):
        with pytest.raises(KeyError) as ei:
            load_by_name("nope")
        assert "work_continuity" in str(ei.value)

    def test_load_all_returns_fresh_instances(self):
        """场景之间不得互相污染。"""
        a = load_by_name("work_continuity")
        b = load_by_name("work_continuity")
        a.expected_state.decisions.append({"summary": "污染", "evidence": "x"})
        assert len(b.expected_state.decisions) == 2


# ── 每个场景的通用契约 ────────────────────────────────


@pytest.mark.parametrize("scenario", load_all(), ids=lambda s: s.name)
class TestScenarioContract:
    def test_has_description_and_invariants(self, scenario):
        assert scenario.description
        assert scenario.invariants, f"{scenario.name} 未声明不变量"

    def test_expected_state_passes_validation(self, scenario):
        """尺子自身必须合法，否则后续对比全是噪音。"""
        rep = validate_context_state(scenario.expected_state)
        assert rep.ok, f"{scenario.name}: {rep.summary()}"

    def test_messages_well_formed(self, scenario):
        for m in scenario.messages:
            assert m["type"] == "message"
            assert m["id"]
            assert m["message"]["role"] in ("user", "assistant", "system")
            assert isinstance(m["message"]["content"], str)

    def test_message_ids_unique(self, scenario):
        ids = [m["id"] for m in scenario.messages]
        assert len(ids) == len(set(ids))

    def test_cursor_is_self_consistent(self, scenario):
        cur = scenario.expected_state.cursor()
        assert cur.is_populated()
        assert cur.message_count == len(scenario.messages)
        assert cur.last_message_id == scenario.messages[-1]["id"]
        assert cur.byte_offset <= cur.observed_size

    def test_cursor_validates_ok_against_own_snapshot(self, scenario):
        cur = scenario.expected_state.cursor()
        got = cur.validate_against(
            session_id=cur.session_id,
            inode=cur.inode,
            current_size=cur.observed_size,
            prefix_hash=cur.prefix_hash,
            observed_last_message_id=cur.last_message_id,
        )
        assert got == CursorInvalidReason.OK

    def test_probe_expectation_keys_are_valid_dimensions(self, scenario):
        for dim in scenario.probe_expectations:
            assert dim in PROBE_DIMENSIONS, f"{scenario.name} 用了非法维度 {dim}"

    def test_evidence_bearing_items_have_sources(self, scenario):
        """decisions/constraints/artifacts 必须可追溯。"""
        st = scenario.expected_state
        for fname in ("decisions", "constraints", "artifacts"):
            for item in getattr(st, fname):
                has = any(
                    item.get(k) for k in
                    ("evidence", "message_id", "source", "source_path", "cursor", "line")
                )
                assert has, f"{scenario.name}.{fname} 有条目缺来源: {item}"


# ── 场景特定不变量（真的去验，不只是写在注释里）──────


class TestWorkContinuityInvariants:
    def _sc(self):
        return load_by_name("work_continuity")

    def test_intent_present(self):
        assert "Mark42" in self._sc().expected_state.session_intent

    def test_active_task_not_done(self):
        assert self._sc().expected_state.active_task["status"] == "in_progress"

    def test_has_rejected_alternatives(self):
        """Decision 探针要能回答"哪些方案被否决了"。"""
        decisions = self._sc().expected_state.decisions
        rejected = [d for d in decisions if d.get("rejected")]
        assert rejected, "至少一个决策要记录被否决方案"

    def test_hard_constraint_count(self):
        assert len(self._sc().expected_state.hard_constraints()) == 3

    def test_artifacts_are_real_module_paths(self):
        paths = [a["path"] for a in self._sc().expected_state.artifacts]
        assert "mark42/context_state.py" in paths
        assert "mark42/audit/probes.py" in paths

    def test_probe_expectations_cover_all_six(self):
        """主场景必须能驱动全部六个维度。"""
        assert set(self._sc().probe_expectations) == set(PROBE_DIMENSIONS)

    def test_expectations_actually_derivable_from_state(self):
        """期望关键词必须真的能在状态里找到，否则断言无法通过。"""
        sc = self._sc()
        blob = sc.expected_state.to_json()
        for dim, kws in sc.probe_expectations.items():
            for kw in kws:
                assert kw in blob, f"{dim} 期望 {kw!r} 但状态里没有"


class TestConstraintHeavyInvariants:
    def _sc(self):
        return load_by_name("constraint_heavy")

    def test_five_hard_one_soft(self):
        st = self._sc().expected_state
        assert len(st.hard_constraints()) == 5
        assert len(st.constraints) == 6

    def test_all_constraints_have_stable_ids(self):
        for c in self._sc().expected_state.constraints:
            assert c.get("constraint_id"), f"缺 constraint_id: {c}"

    def test_p0_constraints_exist(self):
        p0 = [c for c in self._sc().expected_state.constraints
              if c.get("priority") == "P0"]
        assert len(p0) == 3

    def test_soft_constraint_is_p2(self):
        soft = [c for c in self._sc().expected_state.constraints
                if c.get("strength") == "soft"]
        assert len(soft) == 1
        assert soft[0]["priority"] == "P2"


class TestInferenceMixedInvariants:
    def _sc(self):
        return load_by_name("inference_mixed")

    def test_inference_is_separate_from_decisions(self):
        st = self._sc().expected_state
        assert st.inferences
        inf_text = st.inferences[0]["summary"]
        for d in st.decisions:
            assert inf_text not in str(d)

    def test_inference_carries_confidence(self):
        inf = self._sc().expected_state.inferences[0]
        assert 0.0 <= inf["confidence"] <= 1.0

    def test_inference_never_marked_fact(self):
        for inf in self._sc().expected_state.inferences:
            assert inf.get("is_fact") is not True

    def test_evidence_refs_exclude_inference(self):
        st = self._sc().expected_state
        inf_text = st.inferences[0]["summary"]
        for ref in st.evidence_refs:
            assert inf_text not in ref.get("excerpt", "")


class TestSparseInvariants:
    def _sc(self):
        return load_by_name("sparse")

    def test_empty_state_still_valid(self):
        assert validate_context_state(self._sc().expected_state).ok

    def test_no_probe_expectations(self):
        assert self._sc().probe_expectations == {}

    def test_sparse_low_score_is_exempted_from_strict_slo(self):
        """核心用途：上游没证据时低分不算模型缺陷。"""
        from mark42.audit.probes import ProbeOutcome

        outs = [
            ProbeOutcome(dimension=d, probe_id=f"{d}-x", score=1,
                         evidence_absent=True)
            for d in PROBE_DIMENSIONS
        ]
        rep = build_report(outs)
        # 总分确实低 -> 会因总分失败
        assert any("total_below_slo" in f for f in rep.slo_failures)
        # 但严格单项不得因此失败（那会误判为模型能力退化）
        assert not any("strict_dimension_below_min" in f for f in rep.slo_failures)


# ── 场景 + 确定性评分联动 ─────────────────────────────


class TestScenarioDrivenScoring:
    def test_perfect_answer_scores_full(self):
        """用场景期望构造探针，喂"完美答案"应拿满分。"""
        sc = load_by_name("work_continuity")
        answer = sc.expected_state.to_json()
        for dim, kws in sc.probe_expectations.items():
            spec = ProbeSpec(dimension=dim, question="Q", expect_all=kws)
            out = score_deterministic(spec, answer)
            assert out.score == 5, f"{dim} 应满分，实际 {out.score}: {out.reason}"

    def test_blank_answer_scores_zero(self):
        sc = load_by_name("work_continuity")
        for dim, kws in sc.probe_expectations.items():
            spec = ProbeSpec(dimension=dim, question="Q", expect_all=kws)
            assert score_deterministic(spec, "不记得了").score == 0

    def test_english_answer_violates_language_constraint(self):
        """约束场景：英文回答必须判违规（0 分）。"""
        spec = ProbeSpec(
            dimension="instruction",
            question="当前有哪些硬约束？",
            expect_all=["中文"],
            forbid=["Here are", "The constraints"],
        )
        out = score_deterministic(spec, "Here are the constraints: 中文 only")
        assert out.score == 0
        assert out.is_violation()

    def test_full_scenario_report_passes_slo(self):
        from mark42.audit.probes import ProbeOutcome

        sc = load_by_name("work_continuity")
        answer = sc.expected_state.to_json()
        outs: list[ProbeOutcome] = []
        for dim, kws in sc.probe_expectations.items():
            spec = ProbeSpec(dimension=dim, question="Q", expect_all=kws)
            outs.append(score_deterministic(spec, answer))
        rep = build_report(outs)
        assert rep.slo_ok, rep.slo_failures
        assert rep.total_score == 30
