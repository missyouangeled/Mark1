"""ContextState 契约测试（方案 44 Phase 0：schema 冻结）。

覆盖：
    - 序列化往返 / 未知字段容忍
    - 校验器各条规则（含"必须失败"的负例）
    - source_cursor 全部失效原因
    - 幂等与指纹稳定性
    - memory-index 兼容视图

⚠️ 本文件遵循方案 §12「先让测试变红，再修到变绿」：
   每条负例都断言**具体 error code**，不只断言 ok=False，
   避免测试因为别的原因偶然通过。
"""

from __future__ import annotations

import json

import pytest

from mark42.context_state import (
    CONTEXT_STATE_SCHEMA_VERSION,
    ContextState,
    CursorInvalidReason,
    SourceCursor,
    compute_prefix_hash,
    new_empty_state,
    render_memory_index_view,
    validate_context_state,
)

# ── 辅助 ──────────────────────────────────────────────


def _ev(**extra):
    """带来源的最小条目。"""
    base = {"summary": "x", "evidence": "msg-1"}
    base.update(extra)
    return base


def _codes(state, **kw):
    return validate_context_state(state, **kw).codes()


# ── 基础 / 序列化 ─────────────────────────────────────


class TestSerialization:
    def test_empty_state_is_valid(self):
        st = new_empty_state(session_intent="做 Mark42")
        rep = validate_context_state(st)
        assert rep.ok, rep.summary()
        assert st.schema_version == CONTEXT_STATE_SCHEMA_VERSION
        assert st.generated_at

    def test_json_roundtrip(self):
        st = new_empty_state()
        st.decisions = [_ev(decision_id="d1")]
        st.constraints = [{"constraint_id": "c1", "text": "只用中文",
                           "strength": "hard", "priority": "P0", "source": "SOUL.md"}]
        back = ContextState.from_json(st.to_json())
        assert back.to_dict() == st.to_dict()

    def test_from_dict_ignores_unknown_fields(self):
        """新版本写的额外字段不能让旧代码炸掉（向后兼容）。"""
        raw = new_empty_state().to_dict()
        raw["some_future_field"] = {"a": 1}
        st = ContextState.from_dict(raw)
        assert st.schema_version == CONTEXT_STATE_SCHEMA_VERSION

    def test_from_dict_rejects_non_dict(self):
        with pytest.raises(TypeError):
            ContextState.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_fingerprint_ignores_timestamp(self):
        a = new_empty_state()
        b = ContextState.from_dict(a.to_dict())
        b.generated_at = "2099-01-01T00:00:00+08:00"
        assert a.fingerprint() == b.fingerprint()

    def test_fingerprint_changes_with_content(self):
        a = new_empty_state()
        b = ContextState.from_dict(a.to_dict())
        b.decisions = [_ev()]
        assert a.fingerprint() != b.fingerprint()

    def test_fingerprint_stable_across_key_order(self):
        """同内容不同插入顺序必须同指纹（幂等前提）。"""
        a = new_empty_state()
        a.artifacts = [{"path": "x.py", "evidence": "m1", "status": "modified"}]
        b = new_empty_state()
        b.generated_at = a.generated_at
        b.artifacts = [{"status": "modified", "evidence": "m1", "path": "x.py"}]
        assert a.fingerprint() == b.fingerprint()


# ── schema 版本 ───────────────────────────────────────


class TestSchemaVersion:
    def test_zero_version_rejected(self):
        st = new_empty_state()
        st.schema_version = 0
        assert "bad_schema_version" in _codes(st)

    def test_future_version_rejected(self):
        st = new_empty_state()
        st.schema_version = CONTEXT_STATE_SCHEMA_VERSION + 5
        assert "future_schema_version" in _codes(st)

    def test_bad_timestamp_rejected(self):
        st = new_empty_state()
        st.generated_at = "昨天下午"
        assert "bad_timestamp" in _codes(st)


# ── active_task 唯一性 ───────────────────────────────


class TestActiveTask:
    def test_done_task_must_move_to_completed(self):
        """方案 §4.3：已完成任务不得留在 active。"""
        st = new_empty_state()
        st.active_task = {"title": "改压缩", "status": "done"}
        assert "done_task_still_active" in _codes(st)

    def test_bad_status_rejected(self):
        st = new_empty_state()
        st.active_task = {"title": "x", "status": "flying"}
        assert "bad_status" in _codes(st)

    def test_empty_task_rejected(self):
        st = new_empty_state()
        st.active_task = {"status": "pending"}
        assert "empty_task" in _codes(st)

    def test_valid_task_accepted(self):
        st = new_empty_state()
        st.active_task = {"title": "改压缩", "status": "in_progress"}
        assert validate_context_state(st).ok


# ── 来源引用（require_evidence）────────────────────────


class TestEvidenceRequirement:
    @pytest.mark.parametrize("field", ["decisions", "constraints", "artifacts"])
    def test_missing_evidence_rejected(self, field):
        """无来源的新增事实必须被拒（方案 §4.3）。"""
        st = new_empty_state()
        item = {"summary": "无源之说"}
        if field == "constraints":
            item["text"] = "无源约束"
        setattr(st, field, [item])
        assert "missing_evidence" in _codes(st)

    @pytest.mark.parametrize("key", ["evidence", "message_id", "source", "source_path", "cursor", "line"])
    def test_any_source_key_satisfies(self, key):
        st = new_empty_state()
        st.decisions = [{"summary": "有源", key: "m-9"}]
        assert validate_context_state(st).ok

    def test_require_evidence_can_be_disabled(self):
        st = new_empty_state()
        st.decisions = [{"summary": "无源"}]
        assert validate_context_state(st, require_evidence=False).ok

    def test_empty_evidence_value_does_not_count(self):
        st = new_empty_state()
        st.decisions = [{"summary": "假装有源", "evidence": ""}]
        assert "missing_evidence" in _codes(st)

    @pytest.mark.parametrize("falsy", [0, "", None, [], {}, False])
    def test_falsy_source_values_do_not_count(self, falsy):
        """回归：`line: 0` 曾被当成有效来源放过去。

        旧实现用白名单 `val not in (None, "", [], {})` 判定，
        数字 0 / False 不在该元组里 → 静默绕过 require_evidence。
        行号是 1-indexed，0 本身就不是合法行号。
        """
        st = new_empty_state()
        st.decisions = [{"summary": "假装有源", "line": falsy}]
        assert "missing_evidence" in _codes(st)

    def test_line_number_one_counts_as_source(self):
        st = new_empty_state()
        st.decisions = [{"summary": "有源", "line": 1}]
        assert validate_context_state(st).ok

    def test_completed_work_does_not_require_evidence(self):
        """只有 decisions/constraints/artifacts 强制来源。"""
        st = new_empty_state()
        st.completed_work = [{"summary": "干完了"}]
        assert validate_context_state(st).ok


# ── 约束专项 ──────────────────────────────────────────


class TestConstraints:
    def test_duplicate_constraint_id_rejected(self):
        st = new_empty_state()
        st.constraints = [
            {"constraint_id": "c1", "text": "只用中文", "evidence": "SOUL.md:5"},
            {"constraint_id": "c1", "text": "另一条", "evidence": "SOUL.md:9"},
        ]
        assert "duplicate_constraint_id" in _codes(st)

    def test_bad_strength_rejected(self):
        st = new_empty_state()
        st.constraints = [{"text": "x", "strength": "very_hard", "evidence": "m1"}]
        assert "bad_strength" in _codes(st)

    def test_bad_priority_rejected(self):
        st = new_empty_state()
        st.constraints = [{"text": "x", "priority": "P9", "evidence": "m1"}]
        assert "bad_priority" in _codes(st)

    def test_empty_constraint_rejected(self):
        st = new_empty_state()
        st.constraints = [{"strength": "hard", "evidence": "m1"}]
        assert "empty_constraint" in _codes(st)

    def test_hard_constraints_filter(self):
        st = new_empty_state()
        st.constraints = [
            {"text": "只用中文", "strength": "hard", "evidence": "m1"},
            {"text": "少用列表", "strength": "soft", "evidence": "m2"},
        ]
        hard = st.hard_constraints()
        assert len(hard) == 1 and hard[0]["text"] == "只用中文"


# ── 推断隔离 ──────────────────────────────────────────


class TestInferenceSeparation:
    def test_inference_cannot_claim_fact(self):
        """召回与推断分离：inferences 不得自称事实。"""
        st = new_empty_state()
        st.inferences = [{"summary": "他可能累了", "is_fact": True}]
        assert "inference_marked_fact" in _codes(st)

    def test_inference_without_fact_flag_ok(self):
        st = new_empty_state()
        st.inferences = [{"summary": "他可能累了", "confidence": 0.4}]
        assert validate_context_state(st).ok


# ── confidence ────────────────────────────────────────


class TestConfidence:
    @pytest.mark.parametrize("bad", [-0.1, 1.5, 2])
    def test_out_of_range_rejected(self, bad):
        st = new_empty_state()
        st.decisions = [_ev(confidence=bad)]
        assert "confidence_out_of_range" in _codes(st)

    def test_non_numeric_rejected(self):
        st = new_empty_state()
        st.decisions = [_ev(confidence="high")]
        assert "bad_confidence" in _codes(st)

    def test_bool_is_not_valid_confidence(self):
        """bool 是 int 子类，必须显式排除。"""
        st = new_empty_state()
        st.decisions = [_ev(confidence=True)]
        assert "bad_confidence" in _codes(st)

    @pytest.mark.parametrize("good", [0, 0.5, 1, 1.0])
    def test_in_range_accepted(self, good):
        st = new_empty_state()
        st.decisions = [_ev(confidence=good)]
        assert validate_context_state(st).ok


# ── supersedes 链 ─────────────────────────────────────


class TestSupersedes:
    def test_dangling_supersedes_rejected(self):
        st = new_empty_state()
        st.decisions = [_ev(decision_id="d2", supersedes="d-ghost")]
        assert "dangling_supersedes" in _codes(st)

    def test_valid_chain_accepted(self):
        st = new_empty_state()
        st.decisions = [
            _ev(decision_id="d1"),
            _ev(decision_id="d2", supersedes="d1"),
        ]
        assert validate_context_state(st).ok

    def test_list_form_supersedes(self):
        st = new_empty_state()
        st.decisions = [
            _ev(decision_id="d1"),
            _ev(decision_id="d2"),
            _ev(decision_id="d3", supersedes=["d1", "d2"]),
        ]
        assert validate_context_state(st).ok


# ── 类型与体积 ────────────────────────────────────────


class TestTypesAndLimits:
    def test_list_field_must_be_list(self):
        st = new_empty_state()
        st.decisions = {"not": "a list"}  # type: ignore[assignment]
        assert "bad_type" in _codes(st)

    def test_item_must_be_dict(self):
        st = new_empty_state()
        st.decisions = ["纯字符串"]  # type: ignore[list-item]
        assert "bad_item_type" in _codes(st)

    def test_too_many_items_rejected(self):
        st = new_empty_state()
        st.next_steps = [{"summary": f"s{i}"} for i in range(11)]
        assert "too_many_items" in _codes(st, max_items=10)

    def test_item_count(self):
        st = new_empty_state()
        st.decisions = [_ev(), _ev()]
        st.next_steps = [{"summary": "a"}]
        assert st.item_count() == 3


# ── SourceCursor ──────────────────────────────────────


class TestSourceCursor:
    def _cursor(self):
        return SourceCursor(
            session_id="s1",
            source_path="/tmp/sess.jsonl",
            inode=1234,
            byte_offset=100,
            last_message_id="m-10",
            observed_size=500,
            prefix_hash="abc",
            message_count=10,
        )

    def _check(self, cur, **over):
        args = dict(session_id="s1", inode=1234, current_size=500, prefix_hash="abc")
        args.update(over)
        return cur.validate_against(**args)

    def test_ok(self):
        assert self._check(self._cursor()) == CursorInvalidReason.OK

    def test_empty_cursor_is_no_cursor(self):
        assert self._check(SourceCursor()) == CursorInvalidReason.NO_CURSOR

    def test_session_mismatch(self):
        assert self._check(self._cursor(), session_id="other") == \
            CursorInvalidReason.SESSION_MISMATCH

    def test_inode_changed(self):
        assert self._check(self._cursor(), inode=9999) == \
            CursorInvalidReason.INODE_CHANGED

    def test_file_truncated(self):
        assert self._check(self._cursor(), current_size=10) == \
            CursorInvalidReason.FILE_TRUNCATED

    def test_offset_out_of_range(self):
        cur = self._cursor()
        cur.byte_offset = 10_000
        cur.observed_size = 0
        assert self._check(cur, current_size=500) == \
            CursorInvalidReason.OFFSET_OUT_OF_RANGE

    def test_prefix_hash_mismatch(self):
        assert self._check(self._cursor(), prefix_hash="zzz") == \
            CursorInvalidReason.PREFIX_HASH_MISMATCH

    def test_message_id_gap_actually_fires(self):
        """回归测试：首版实现里该分支永远不可能触发（死探针）。

        原代码 `if first_message_id and ... and first_message_id == ""`
        自相矛盾，等于永远返回 OK。这里断言它真的会报错。
        """
        cur = self._cursor()
        got = cur.validate_against(
            session_id="s1", inode=1234, current_size=500, prefix_hash="abc",
            observed_last_message_id="m-999",
        )
        assert got == CursorInvalidReason.MESSAGE_ID_GAP

    def test_message_id_match_is_ok(self):
        cur = self._cursor()
        got = cur.validate_against(
            session_id="s1", inode=1234, current_size=500, prefix_hash="abc",
            observed_last_message_id="m-10",
        )
        assert got == CursorInvalidReason.OK

    def test_none_message_id_skips_check(self):
        """调用方不做该项校验时不能误报。"""
        cur = self._cursor()
        got = cur.validate_against(
            session_id="s1", inode=1234, current_size=500, prefix_hash="abc",
            observed_last_message_id=None,
        )
        assert got == CursorInvalidReason.OK

    def test_missing_inode_skips_check(self):
        """调用方取不到 inode（传 0）时不应误判为轮替。"""
        assert self._check(self._cursor(), inode=0) == CursorInvalidReason.OK

    def test_growing_file_is_ok(self):
        """文件正常追加变大 —— 这是最常见的正常场景。"""
        assert self._check(self._cursor(), current_size=99999) == \
            CursorInvalidReason.OK

    def test_cursor_roundtrip_through_state(self):
        st = new_empty_state()
        cur = self._cursor()
        st.set_cursor(cur)
        assert st.cursor() == cur
        assert validate_context_state(st).ok

    def test_prefix_hash_helper_is_deterministic(self):
        a = compute_prefix_hash(b"hello world")
        b = compute_prefix_hash(b"hello world")
        assert a == b and len(a) == 32
        assert a != compute_prefix_hash(b"hello worlds")


# ── memory-index 兼容视图 ─────────────────────────────


class TestMemoryIndexView:
    def test_view_shape(self):
        st = new_empty_state(session_intent="开发 Mark42")
        st.active_task = {"title": "Phase 0", "status": "in_progress"}
        st.decisions = [_ev(summary="先冻结 schema")]
        st.constraints = [{"text": "只用中文", "strength": "hard", "evidence": "SOUL.md"}]
        st.artifacts = [{"path": "mark42/context_state.py", "evidence": "m1"}]
        st.next_steps = [{"summary": "写探针"}]
        view = render_memory_index_view(st)

        assert view["strategyUsed"] == "structured-incremental"
        assert view["modelGenerated"] is True
        assert view["preserved"]["sessionIntent"] == "开发 Mark42"
        assert view["preserved"]["decisions"] == ["先冻结 schema"]
        assert view["preserved"]["artifacts"] == ["mark42/context_state.py"]
        assert view["stateFingerprint"] == st.fingerprint()
        assert view["itemCount"] == st.item_count()

    def test_view_is_json_serializable(self):
        st = new_empty_state()
        json.dumps(render_memory_index_view(st), ensure_ascii=False)

    def test_view_does_not_leak_inferences_into_preserved(self):
        """推断不得混进 preserved（召回与推断分离）。"""
        st = new_empty_state()
        st.inferences = [{"summary": "他大概想早点收工"}]
        view = render_memory_index_view(st)
        assert view["inferences"] == st.inferences
        assert "他大概想早点收工" not in json.dumps(
            view["preserved"], ensure_ascii=False)

    def test_artifacts_without_path_skipped(self):
        st = new_empty_state()
        st.artifacts = [{"evidence": "m1"}, {"path": "a.py", "evidence": "m2"}]
        view = render_memory_index_view(st)
        assert view["preserved"]["artifacts"] == ["a.py"]


# ── 报告对象 ──────────────────────────────────────────


class TestValidationReport:
    def test_summary_readable_on_failure(self):
        st = new_empty_state()
        st.schema_version = 0
        rep = validate_context_state(st)
        assert not rep.ok
        assert "bad_schema_version" in rep.summary()

    def test_summary_ok_on_success(self):
        assert validate_context_state(new_empty_state()).summary() == "ok"

    def test_multiple_issues_collected(self):
        st = new_empty_state()
        st.schema_version = 0
        st.generated_at = "昨天"
        st.decisions = [{"summary": "无源"}]
        codes = _codes(st)
        assert {"bad_schema_version", "bad_timestamp", "missing_evidence"} <= set(codes)
