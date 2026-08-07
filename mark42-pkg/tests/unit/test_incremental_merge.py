"""增量合并测试（方案 44 Phase 2）。

重点钉住四条「不可退让」的合并规则（方案 §4.3）：
    1. hard 约束不可被删除；
    2. 已完成任务不得静默重新激活；
    3. 无来源的新增事实拒绝入库；
    4. patch 非法时**零污染** —— 绝不返回部分合并的状态。
"""

from __future__ import annotations

import pytest

from mark42.audit.incremental_merge import (
    DEFAULT_MAX_PATCH_ITEMS,
    OP_ADD,
    OP_COMPLETE,
    OP_REVOKE,
    OP_SUPERSEDE,
    OP_UPDATE,
    PROTECTED_FIELDS,
    RejectReason,
    merge_active_task,
    merge_list_field,
    merge_patch,
    validate_patch,
)
from mark42.context_state import new_empty_state


def _state(**kw):
    st = new_empty_state(session_intent=kw.pop("session_intent", "初始目标"))
    for k, v in kw.items():
        setattr(st, k, v)
    return st


def _ev(**kw):
    base = {"summary": "x", "evidence": "m-1"}
    base.update(kw)
    return base


# ── patch 形状校验 ────────────────────────────────────


class TestValidatePatch:
    def test_empty_patch_ok(self):
        assert validate_patch({}) == []

    def test_non_dict_rejected(self):
        issues = validate_patch(["not a dict"])
        assert issues[0].code == RejectReason.NOT_A_DICT

    @pytest.mark.parametrize("field", PROTECTED_FIELDS)
    def test_protected_fields_rejected(self, field):
        """模型不得伪造游标 / schema 版本 / 时间戳。"""
        issues = validate_patch({field: "whatever"})
        assert any(i.code == RejectReason.PROTECTED_FIELD for i in issues)

    def test_unknown_field_rejected(self):
        issues = validate_patch({"secret_backdoor": []})
        assert any(i.code == RejectReason.UNKNOWN_FIELD for i in issues)

    def test_bad_op_rejected(self):
        issues = validate_patch({"decisions": [{"op": "nuke"}]})
        assert any(i.code == RejectReason.BAD_OP for i in issues)

    def test_list_field_must_be_list(self):
        issues = validate_patch({"decisions": {"op": "add"}})
        assert any(i.code == RejectReason.BAD_ITEM_TYPE for i in issues)

    def test_session_intent_must_be_str(self):
        issues = validate_patch({"session_intent": 123})
        assert any(i.code == RejectReason.BAD_ITEM_TYPE for i in issues)

    def test_active_task_must_be_dict(self):
        issues = validate_patch({"active_task": ["x"]})
        assert any(i.code == RejectReason.BAD_ITEM_TYPE for i in issues)

    def test_too_many_items_rejected(self):
        patch = {"next_steps": [{"op": OP_ADD, "summary": f"s{i}"}
                                for i in range(DEFAULT_MAX_PATCH_ITEMS + 1)]}
        issues = validate_patch(patch)
        assert any(i.code == RejectReason.TOO_MANY_ITEMS for i in issues)

    def test_valid_patch_passes(self):
        patch = {
            "session_intent": "新目标",
            "decisions": [{"op": OP_ADD, "summary": "决定", "evidence": "m-1"}],
            "active_task": {"op": OP_UPDATE, "title": "T", "status": "in_progress"},
        }
        assert validate_patch(patch) == []


# ── 零污染 ────────────────────────────────────────────


class TestZeroPollution:
    def test_illegal_patch_returns_no_state(self):
        """核心保证：非法 patch 绝不返回部分合并的状态。"""
        old = _state(decisions=[_ev(decision_id="d1")])
        res = merge_patch(old, {"source_cursor": {"byte_offset": 999}})
        assert res.ok is False
        assert res.state is None

    def test_old_state_never_mutated(self):
        old = _state(decisions=[_ev(decision_id="d1")])
        before = old.to_json()
        merge_patch(old, {"decisions": [{"op": OP_ADD, "summary": "新",
                                         "evidence": "m-2"}]})
        assert old.to_json() == before

    def test_partial_failure_rejects_whole_patch(self):
        """一条非法就整份拒绝，不能挑合法的先合进去。"""
        old = _state()
        patch = {
            "decisions": [
                {"op": OP_ADD, "summary": "合法", "evidence": "m-1"},
                {"op": OP_ADD, "summary": "无源"},  # 缺 evidence
            ],
        }
        res = merge_patch(old, patch)
        assert res.ok is False
        assert res.state is None
        assert RejectReason.MISSING_EVIDENCE in res.codes()


# ── hard 约束不可删（方案 §4.3）───────────────────────


class TestHardConstraintProtection:
    def _old(self):
        return _state(constraints=[
            {"constraint_id": "c-hard", "text": "只用中文",
             "strength": "hard", "priority": "P0", "evidence": "SOUL.md:6"},
            {"constraint_id": "c-soft", "text": "少用列表",
             "strength": "soft", "priority": "P2", "evidence": "chat.md:1"},
        ])

    def test_revoking_hard_constraint_rejected(self):
        res = merge_patch(self._old(),
                          {"constraints": [{"op": OP_REVOKE,
                                            "constraint_id": "c-hard"}]})
        assert res.ok is False
        assert RejectReason.HARD_CONSTRAINT_DELETION in res.codes()

    def test_revoking_soft_constraint_allowed(self):
        res = merge_patch(self._old(),
                          {"constraints": [{"op": OP_REVOKE,
                                            "constraint_id": "c-soft",
                                            "reason": "用户改了偏好"}]})
        assert res.ok, res.summary()
        soft = [c for c in res.state.constraints if c["constraint_id"] == "c-soft"][0]
        assert soft["revoked"] is True
        assert soft["revoked_reason"] == "用户改了偏好"

    def test_hard_constraint_can_be_updated(self):
        """只能更新，不能删除。"""
        res = merge_patch(self._old(),
                          {"constraints": [{"op": OP_UPDATE,
                                            "constraint_id": "c-hard",
                                            "text": "只用中文（含代码注释）",
                                            "strength": "hard",
                                            "priority": "P0",
                                            "evidence": "SOUL.md:6"}]})
        assert res.ok, res.summary()
        hard = [c for c in res.state.constraints
                if c["constraint_id"] == "c-hard"][0]
        assert "含代码注释" in hard["text"]

    def test_hard_constraint_survives_unrelated_patch(self):
        res = merge_patch(self._old(),
                          {"next_steps": [{"op": OP_ADD, "summary": "下一步"}]})
        assert res.ok, res.summary()
        assert len(res.state.hard_constraints()) == 1


# ── 已完成任务不得静默重开（方案 §4.3）────────────────


class TestTaskLifecycle:
    def test_complete_moves_to_completed_work(self):
        old = _state(active_task={"title": "Phase 2", "status": "in_progress"})
        res = merge_patch(old, {"active_task": {"op": OP_COMPLETE}})
        assert res.ok, res.summary()
        assert res.state.active_task == {}
        assert len(res.state.completed_work) == 1
        assert res.state.completed_work[0]["status"] == "done"

    def test_done_task_cannot_silently_reactivate(self):
        old = _state(
            active_task={},
            completed_work=[{"title": "Phase 1", "status": "done"}],
        )
        res = merge_patch(old, {"active_task": {"op": OP_UPDATE,
                                                "title": "Phase 1",
                                                "status": "in_progress"}})
        assert res.ok is False
        assert RejectReason.DONE_TASK_REACTIVATED in res.codes()

    def test_explicit_reopen_allowed(self):
        """新消息明确重开时可以 —— 但必须显式。"""
        old = _state(
            active_task={},
            completed_work=[{"title": "Phase 1", "status": "done"}],
        )
        res = merge_patch(old, {"active_task": {"op": OP_UPDATE,
                                                "title": "Phase 1",
                                                "status": "in_progress",
                                                "reopen": True}})
        assert res.ok, res.summary()
        assert res.state.active_task["title"] == "Phase 1"
        # reopen 标记不落库
        assert "reopen" not in res.state.active_task

    def test_switching_task_parks_the_old_one(self):
        """换任务时旧的未完成任务不能凭空消失。"""
        old = _state(active_task={"title": "旧任务", "status": "in_progress"})
        res = merge_patch(old, {"active_task": {"op": OP_UPDATE,
                                                "title": "新任务",
                                                "status": "in_progress"}})
        assert res.ok, res.summary()
        assert res.state.active_task["title"] == "新任务"
        parked = [w for w in res.state.completed_work if w["title"] == "旧任务"]
        assert len(parked) == 1
        assert parked[0]["parked_reason"] == "superseded_by_new_active_task"

    def test_updating_same_task_does_not_park(self):
        old = _state(active_task={"title": "T", "status": "pending"})
        res = merge_patch(old, {"active_task": {"op": OP_UPDATE, "title": "T",
                                                "status": "in_progress"}})
        assert res.ok, res.summary()
        assert res.state.completed_work == []
        assert res.state.active_task["status"] == "in_progress"

    def test_merge_active_task_unit(self):
        task, completed, issues, n = merge_active_task(
            {"title": "A", "status": "in_progress"},
            {"op": OP_COMPLETE},
            [],
        )
        assert task == {}
        assert completed[0]["status"] == "done"
        assert issues == []
        assert n == 1


# ── 来源强制 ──────────────────────────────────────────


class TestEvidenceEnforcement:
    @pytest.mark.parametrize("field", ["decisions", "constraints", "artifacts"])
    def test_add_without_evidence_rejected(self, field):
        item = {"op": OP_ADD, "summary": "无源"}
        if field == "constraints":
            item["text"] = "无源约束"
        if field == "artifacts":
            item["path"] = "x.py"
        res = merge_patch(_state(), {field: [item]})
        assert res.ok is False
        assert RejectReason.MISSING_EVIDENCE in res.codes()

    def test_add_with_evidence_ok(self):
        res = merge_patch(_state(), {"decisions": [
            {"op": OP_ADD, "decision_id": "d1", "summary": "有源",
             "evidence": "m-3"}]})
        assert res.ok, res.summary()
        assert len(res.state.decisions) == 1

    def test_evidence_not_required_for_next_steps(self):
        res = merge_patch(_state(), {"next_steps": [
            {"op": OP_ADD, "summary": "下一步"}]})
        assert res.ok, res.summary()

    def test_require_evidence_can_be_disabled(self):
        res = merge_patch(_state(),
                          {"decisions": [{"op": OP_ADD, "summary": "无源"}]},
                          require_evidence=False)
        assert res.ok, res.summary()

    def test_falsy_line_zero_is_not_evidence(self):
        """回归：line: 0 不算来源（与 context_state 同口径）。"""
        res = merge_patch(_state(), {"decisions": [
            {"op": OP_ADD, "summary": "假装有源", "line": 0}]})
        assert res.ok is False
        assert RejectReason.MISSING_EVIDENCE in res.codes()


# ── 推断隔离 ──────────────────────────────────────────


class TestInferenceIsolation:
    def test_inference_claiming_fact_rejected(self):
        res = merge_patch(_state(), {"inferences": [
            {"op": OP_ADD, "summary": "他肯定累了", "is_fact": True}]})
        assert res.ok is False
        assert RejectReason.INFERENCE_AS_FACT in res.codes()

    def test_normal_inference_accepted(self):
        res = merge_patch(_state(), {"inferences": [
            {"op": OP_ADD, "summary": "他可能累了", "confidence": 0.4}]})
        assert res.ok, res.summary()
        assert len(res.state.inferences) == 1

    def test_inference_needs_no_evidence(self):
        """推断本来就没有硬证据 —— 不该按事实标准要求它。"""
        res = merge_patch(_state(), {"inferences": [
            {"op": OP_ADD, "summary": "猜测"}]})
        assert res.ok, res.summary()


# ── supersedes 链（方案 §4.3：保留链，不删旧决定）──────


class TestSupersedeChain:
    def _old(self):
        return _state(decisions=[
            {"decision_id": "d1", "summary": "用 glm-5.2 做 compaction",
             "evidence": "m-1"},
        ])

    def test_supersede_keeps_old_decision(self):
        """新决定覆盖旧决定，但旧的必须留着（链要可追溯）。"""
        res = merge_patch(self._old(), {"decisions": [
            {"op": OP_SUPERSEDE, "decision_id": "d2",
             "summary": "换 doubao-seed-2.0-pro", "supersedes": "d1",
             "evidence": "m-5"}]})
        assert res.ok, res.summary()
        ids = [d["decision_id"] for d in res.state.decisions]
        assert ids == ["d1", "d2"]

    def test_old_decision_marked_superseded_by(self):
        res = merge_patch(self._old(), {"decisions": [
            {"op": OP_SUPERSEDE, "decision_id": "d2", "summary": "新",
             "supersedes": "d1", "evidence": "m-5"}]})
        old = [d for d in res.state.decisions if d["decision_id"] == "d1"][0]
        assert old["superseded_by"] == "d2"

    def test_dangling_supersedes_rejected(self):
        res = merge_patch(self._old(), {"decisions": [
            {"op": OP_SUPERSEDE, "decision_id": "d2", "summary": "新",
             "supersedes": "d-ghost", "evidence": "m-5"}]})
        assert res.ok is False
        assert RejectReason.DANGLING_SUPERSEDES in res.codes()

    def test_supersede_multiple(self):
        old = _state(decisions=[
            {"decision_id": "d1", "summary": "A", "evidence": "m-1"},
            {"decision_id": "d2", "summary": "B", "evidence": "m-2"},
        ])
        res = merge_patch(old, {"decisions": [
            {"op": OP_SUPERSEDE, "decision_id": "d3", "summary": "C",
             "supersedes": ["d1", "d2"], "evidence": "m-3"}]})
        assert res.ok, res.summary()
        for did in ("d1", "d2"):
            item = [d for d in res.state.decisions if d["decision_id"] == did][0]
            assert item["superseded_by"] == "d3"


# ── artifacts 以路径为键（方案 §4.3）──────────────────


class TestArtifactMerge:
    def test_same_path_merges_not_duplicates(self):
        old = _state(artifacts=[
            {"path": "mark42/armor.py", "status": "modified", "evidence": "m-1"}])
        res = merge_patch(old, {"artifacts": [
            {"op": OP_UPDATE, "path": "mark42/armor.py", "status": "tested",
             "evidence": "m-9"}]})
        assert res.ok, res.summary()
        assert len(res.state.artifacts) == 1
        assert res.state.artifacts[0]["status"] == "tested"

    def test_different_paths_coexist(self):
        old = _state(artifacts=[
            {"path": "a.py", "status": "modified", "evidence": "m-1"}])
        res = merge_patch(old, {"artifacts": [
            {"op": OP_ADD, "path": "b.py", "status": "created",
             "evidence": "m-2"}]})
        assert res.ok, res.summary()
        assert len(res.state.artifacts) == 2

    def test_repeated_add_same_path_is_idempotent(self):
        old = _state(artifacts=[
            {"path": "a.py", "status": "modified", "evidence": "m-1"}])
        patch = {"artifacts": [
            {"op": OP_ADD, "path": "a.py", "status": "modified",
             "evidence": "m-1"}]}
        res = merge_patch(old, patch)
        assert res.ok, res.summary()
        assert len(res.state.artifacts) == 1


# ── 幂等与确定性（方案 §4.6：同输入同结果）───────────


class TestIdempotence:
    def test_same_patch_twice_same_fingerprint(self):
        old = _state()
        patch = {"decisions": [{"op": OP_ADD, "decision_id": "d1",
                                "summary": "决定", "evidence": "m-1"}]}
        a = merge_patch(old, patch)
        b = merge_patch(a.state, patch)
        assert a.ok and b.ok
        assert a.state.fingerprint() == b.state.fingerprint()

    def test_no_duplicate_items_after_repeat(self):
        old = _state()
        patch = {"constraints": [{"op": OP_ADD, "constraint_id": "c1",
                                  "text": "只用中文", "strength": "hard",
                                  "evidence": "SOUL.md:6"}]}
        st = old
        for _ in range(5):
            res = merge_patch(st, patch)
            assert res.ok, res.summary()
            st = res.state
        assert len(st.constraints) == 1

    def test_empty_patch_only_bumps_timestamp(self):
        old = _state(decisions=[_ev(decision_id="d1")])
        res = merge_patch(old, {})
        assert res.ok, res.summary()
        assert res.state.fingerprint() == old.fingerprint()

    def test_ten_rounds_preserve_intent_and_constraints(self):
        """方案 §4.6 验收：连续 10 次增量后目标/约束仍在。"""
        st = _state(
            session_intent="按方案 44 补全 Mark42",
            constraints=[{"constraint_id": "c-zh", "text": "只用中文",
                          "strength": "hard", "priority": "P0",
                          "evidence": "SOUL.md:6"}],
            active_task={"title": "Phase 2", "status": "in_progress"},
        )
        for i in range(10):
            res = merge_patch(st, {"next_steps": [
                {"op": OP_ADD, "summary": f"步骤{i}"}]})
            assert res.ok, f"第 {i} 轮失败: {res.summary()}"
            st = res.state
        assert st.session_intent == "按方案 44 补全 Mark42"
        assert len(st.hard_constraints()) == 1
        assert st.active_task["title"] == "Phase 2"
        assert len(st.next_steps) == 10


# ── merge_list_field 单元 ─────────────────────────────


class TestMergeListFieldUnit:
    def test_add_appends(self):
        out, issues, n = merge_list_field(
            [], [{"op": OP_ADD, "summary": "x", "evidence": "m"}], "decisions")
        assert len(out) == 1 and issues == [] and n == 1

    def test_op_field_stripped_from_stored_item(self):
        out, _, _ = merge_list_field(
            [], [{"op": OP_ADD, "summary": "x", "evidence": "m"}], "decisions")
        assert "op" not in out[0]

    def test_revoke_missing_key_is_idempotent(self):
        out, issues, n = merge_list_field(
            [], [{"op": OP_REVOKE, "constraint_id": "ghost"}], "constraints")
        assert issues == [] and n == 1

    def test_complete_marks_done(self):
        out, issues, n = merge_list_field(
            [{"id": "t1", "status": "pending"}],
            [{"op": OP_COMPLETE, "id": "t1"}], "next_steps")
        assert out[0]["status"] == "done"
        assert issues == []

    def test_order_is_preserved(self):
        old = [{"id": "a"}, {"id": "b"}]
        out, _, _ = merge_list_field(
            old, [{"op": OP_ADD, "id": "c"}], "next_steps")
        assert [i["id"] for i in out] == ["a", "b", "c"]
