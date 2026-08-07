"""约束身份与静态完整性测试（方案 44 Phase 1）。

重点钉住三条容易做成假绿灯的地方：
    1. `constraint_id` 必须**稳定**——改排版不得变成"新约束"；
    2. 检测器异常时必须**全量重注入**（失败安全，宁可多注不可漏注）；
    3. P0 丢失必须阻断，P2 丢失只记趋势。
"""

from __future__ import annotations

import pytest

from mark42.audit.constraint_identity import (
    PRIORITY_ACTIONS,
    PRIORITY_P0,
    PRIORITY_P1,
    PRIORITY_P2,
    STRENGTH_HARD,
    STRENGTH_SOFT,
    ConstraintRecord,
    IntegrityReport,
    build_constraint_record,
    check_static_integrity,
    classify_priority,
    classify_strength,
    dedupe_records,
    detect_conflicts,
    make_constraint_id,
    normalize_constraint_text,
    select_reinject_records,
    text_hash,
)
from mark42.context_state import validate_context_state, new_empty_state

# ── 归一化与 ID 稳定性 ────────────────────────────────


class TestNormalization:
    def test_strips_markdown_and_punctuation(self):
        a = normalize_constraint_text("**只用中文回复，禁止英文。**")
        b = normalize_constraint_text("- 只用中文回复 禁止英文")
        assert a == b

    def test_case_insensitive(self):
        assert normalize_constraint_text("No English") == \
               normalize_constraint_text("NO ENGLISH")

    def test_handles_empty(self):
        assert normalize_constraint_text("") == ""
        assert normalize_constraint_text("   ") == ""
        assert normalize_constraint_text(None) == ""  # type: ignore[arg-type]

    def test_fullwidth_and_halfwidth_punctuation_equal(self):
        assert normalize_constraint_text("发送前，先问") == \
               normalize_constraint_text("发送前, 先问")


class TestConstraintIdStability:
    def test_same_text_same_id(self):
        assert make_constraint_id("只用中文") == make_constraint_id("只用中文")

    def test_reformatting_does_not_change_id(self):
        """核心不变量：改排版不能变成"新约束"。"""
        base = make_constraint_id("只用中文回复，禁止英文")
        assert make_constraint_id("**只用中文回复，禁止英文**") == base
        assert make_constraint_id("- 只用中文回复 禁止英文 ") == base
        assert make_constraint_id("## 只用中文回复；禁止英文。") == base

    def test_different_text_different_id(self):
        assert make_constraint_id("只用中文") != make_constraint_id("只用英文")

    def test_line_number_not_in_id(self):
        """行号会随编辑漂移，不能算进 ID。"""
        a = build_constraint_record("只用中文", source_file="SOUL.md", line_no=6)
        b = build_constraint_record("只用中文", source_file="SOUL.md", line_no=99)
        assert a.constraint_id == b.constraint_id

    def test_id_has_stable_prefix(self):
        assert make_constraint_id("x").startswith("c-")

    def test_text_hash_detects_rewrite(self):
        """ID 稳定，但 text_hash 要能看出原文被改过。"""
        a = build_constraint_record("只用中文回复，禁止英文")
        b = build_constraint_record("只用中文回复；禁止英文")
        assert a.constraint_id == b.constraint_id
        assert a.text_hash != b.text_hash

    def test_text_hash_deterministic(self):
        assert text_hash("abc") == text_hash("abc")
        assert text_hash("abc") != text_hash("abd")


# ── 分级 ──────────────────────────────────────────────


class TestPriorityClassification:
    @pytest.mark.parametrize("text", [
        "只用中文回复，禁止英文",
        "No English. Chinese ONLY.",
        "发送邮件/推文/公开内容前先问",
        "公开发送前必须确认",
        "主会话内禁止 restart/stop gateway",
        "私密的东西不外传，凭据不入日志",
        "召回只返回证据，不得把推断伪装成事实",
        "高风险系统操作前必读崩坏案例",
    ])
    def test_p0_patterns(self, text):
        assert classify_priority(text) == PRIORITY_P0

    @pytest.mark.parametrize("text", [
        "高风险脚本默认 dry-run",
        "新增能力默认关闭",
        "交付前必须自检",
        "先查现有能力再动手",
        "改完必须留痕，写入变更流水",
        "问题追根因，禁止躲避式修复",
        "改配置先备份，准备好回滚路径",
    ])
    def test_p1_patterns(self, text):
        assert classify_priority(text) == PRIORITY_P1

    @pytest.mark.parametrize("text", [
        "日常聊天不要清单式收尾",
        "喜欢被叫点点",
        "语速放慢 20%",
    ])
    def test_p2_default(self, text):
        assert classify_priority(text) == PRIORITY_P2

    def test_unknown_falls_to_p2_not_p0(self):
        """保守策略：拿不准落 P2，避免误阻断。"""
        assert classify_priority("随便写点什么不相干的话") == PRIORITY_P2

    def test_p0_wins_over_p1_when_both_match(self):
        """同时命中时 P0 优先。"""
        text = "改配置先备份；公开发送前必须确认"
        assert classify_priority(text) == PRIORITY_P0

    def test_empty_text_is_p2(self):
        assert classify_priority("") == PRIORITY_P2


class TestStrength:
    def test_p0_p1_are_hard(self):
        assert classify_strength("只用中文", PRIORITY_P0) == STRENGTH_HARD
        assert classify_strength("默认 dry-run", PRIORITY_P1) == STRENGTH_HARD

    def test_p2_is_soft(self):
        assert classify_strength("不要清单式收尾", PRIORITY_P2) == STRENGTH_SOFT

    def test_priority_actions_complete(self):
        assert PRIORITY_ACTIONS[PRIORITY_P0] == "block"
        assert PRIORITY_ACTIONS[PRIORITY_P1] == "warn_and_reinject"
        assert PRIORITY_ACTIONS[PRIORITY_P2] == "trend_only"

    def test_record_action_on_failure(self):
        r = build_constraint_record("只用中文")
        assert r.action_on_failure() == "block"


# ── 记录构造与去重 ────────────────────────────────────


class TestRecordBuilding:
    def test_full_record(self):
        r = build_constraint_record("  只用中文回复，禁止英文  ",
                                    source_file="SOUL.md", line_no=6)
        assert r.text == "只用中文回复，禁止英文"
        assert r.source_file == "SOUL.md"
        assert r.line_no == 6
        assert r.priority == PRIORITY_P0
        assert r.strength == STRENGTH_HARD
        assert r.summary
        assert r.text_hash

    def test_summary_truncated(self):
        long = "只用中文" * 40
        r = build_constraint_record(long)
        assert len(r.summary) <= 60

    def test_dedupe_keeps_first(self):
        recs = [
            build_constraint_record("只用中文", source_file="SOUL.md", line_no=6),
            build_constraint_record("**只用中文**", source_file="AGENTS.md", line_no=99),
        ]
        out = dedupe_records(recs)
        assert len(out) == 1
        assert out[0].source_file == "SOUL.md"
        assert out[0].line_no == 6

    def test_dedupe_preserves_distinct(self):
        recs = [
            build_constraint_record("只用中文"),
            build_constraint_record("默认 dry-run"),
        ]
        assert len(dedupe_records(recs)) == 2

    def test_dedupe_empty(self):
        assert dedupe_records([]) == []


class TestContextStateInterop:
    def test_record_converts_to_valid_state_item(self):
        """转出来的形状必须能通过 ContextState 校验（含 evidence 强制）。"""
        recs = [
            build_constraint_record("只用中文回复", source_file="SOUL.md", line_no=6),
            build_constraint_record("默认 dry-run", source_file="ACTIVE_RULES.md", line_no=20),
        ]
        st = new_empty_state()
        st.constraints = [r.to_context_state_item() for r in recs]
        rep = validate_context_state(st)
        assert rep.ok, rep.summary()

    def test_evidence_field_populated(self):
        r = build_constraint_record("只用中文", source_file="SOUL.md", line_no=6)
        assert r.to_context_state_item()["evidence"] == "SOUL.md:6"

    def test_no_source_still_valid_shape(self):
        """无来源文件时 evidence 为空——校验会拒，这是预期行为。"""
        r = build_constraint_record("只用中文")
        item = r.to_context_state_item()
        assert item["evidence"] == ""
        st = new_empty_state()
        st.constraints = [item]
        assert "missing_evidence" in validate_context_state(st).codes()


# ── 静态完整性检测 ────────────────────────────────────


class TestStaticIntegrity:
    def _recs(self):
        return [
            build_constraint_record("只用中文回复，禁止英文", source_file="SOUL.md", line_no=6),
            build_constraint_record("高风险脚本默认 dry-run", source_file="ACTIVE_RULES.md", line_no=20),
            build_constraint_record("日常聊天不要清单式收尾", source_file="rules/chat.md", line_no=12),
        ]

    def test_all_preserved(self):
        recs = self._recs()
        post = "\n".join(r.text for r in recs)
        rep = check_static_integrity(recs, post)
        assert rep.total == 3
        assert rep.preserved == 3
        assert rep.lost == 0
        assert rep.survival_rate() == 1.0
        assert rep.hard_survival_rate() == 1.0
        assert rep.reinject_ids == []
        assert rep.blocking is False

    def test_preserved_despite_reformatting(self):
        """换排版不算丢——归一化匹配要生效。"""
        recs = self._recs()
        post = "**只用中文回复；禁止英文。** 高风险脚本默认 dry-run。日常聊天不要清单式收尾"
        rep = check_static_integrity(recs, post)
        assert rep.lost == 0

    def test_all_lost(self):
        recs = self._recs()
        rep = check_static_integrity(recs, "完全不相干的摘要内容")
        assert rep.lost == 3
        assert rep.survival_rate() == 0.0
        assert len(rep.reinject_ids) == 3

    def test_p0_loss_blocks(self):
        """P0 丢失必须阻断（方案 §6.3）。"""
        recs = self._recs()
        post = "高风险脚本默认 dry-run。日常聊天不要清单式收尾"
        rep = check_static_integrity(recs, post)
        assert rep.blocking is True

    def test_p2_loss_does_not_block(self):
        """P2 丢失只记趋势，不阻断。"""
        recs = self._recs()
        post = "只用中文回复，禁止英文。高风险脚本默认 dry-run"
        rep = check_static_integrity(recs, post)
        assert rep.lost == 1
        assert rep.blocking is False

    def test_degraded_on_partial_fragments(self):
        recs = [build_constraint_record(
            "改配置先备份 准备好回滚路径 记录变更流水",
            source_file="ACTIVE_RULES.md", line_no=8)]
        post = "改配置先备份，准备好回滚路径"
        rep = check_static_integrity(recs, post)
        f = rep.findings[0]
        assert f.status in ("degraded", "preserved")
        if f.status == "degraded":
            assert "命中" in f.detail

    def test_empty_records(self):
        rep = check_static_integrity([], "任何文本")
        assert rep.total == 0
        assert rep.survival_rate() == 1.0
        assert rep.hard_survival_rate() == 1.0
        assert rep.blocking is False

    def test_empty_post_text_all_lost(self):
        recs = self._recs()
        rep = check_static_integrity(recs, "")
        assert rep.lost == 3

    def test_hard_survival_excludes_soft(self):
        """hard 存活率只看 hard——soft 丢了不该拉低它。"""
        recs = self._recs()
        post = "只用中文回复，禁止英文。高风险脚本默认 dry-run"
        rep = check_static_integrity(recs, post)
        assert rep.hard_survival_rate() == 1.0
        assert rep.survival_rate() < 1.0

    def test_report_json_serializable(self):
        rep = check_static_integrity(self._recs(), "只用中文回复，禁止英文")
        assert "findings" in rep.to_json()

    def test_trace_id_propagated(self):
        rep = check_static_integrity([], "", trace_id="tr-1", timestamp="2026-08-07T14:00:00+08:00")
        assert rep.trace_id == "tr-1"
        assert rep.timestamp == "2026-08-07T14:00:00+08:00"


# ── 失败安全降级（方案 §6.2 核心要求）────────────────


class TestFailSafeDegradation:
    def test_detector_exception_marks_failed_and_reinjects_all(self):
        """检测器坏了必须全量重注入——宁可多注入，不可漏注入。"""
        class Boom:
            """伪造一个会在 normalize 时炸掉的记录。"""
            constraint_id = "c-boom"
            priority = PRIORITY_P0
            strength = STRENGTH_HARD
            summary = "x"

            @property
            def text(self):
                raise RuntimeError("模拟检测器内部异常")

        rep = check_static_integrity([Boom()], "任何文本")  # type: ignore[list-item]
        assert rep.detector_failed is True
        assert "RuntimeError" in rep.detector_error
        assert rep.reinject_ids == ["c-boom"]

    def test_check_never_raises(self):
        """本函数是失败安全的——绝不向上抛异常。"""
        class Boom:
            constraint_id = "c-x"
            priority = PRIORITY_P0
            strength = STRENGTH_HARD
            summary = "x"

            @property
            def text(self):
                raise ValueError("boom")

        rep = check_static_integrity([Boom()], "x")  # type: ignore[list-item]
        assert isinstance(rep, IntegrityReport)

    def test_select_reinject_returns_all_on_detector_failure(self):
        recs = [build_constraint_record("只用中文"), build_constraint_record("dry-run")]
        rep = IntegrityReport(detector_failed=True, reinject_ids=[])
        assert len(select_reinject_records(recs, rep)) == 2

    def test_select_reinject_filters_normally(self):
        recs = [
            build_constraint_record("只用中文回复，禁止英文", source_file="SOUL.md", line_no=6),
            build_constraint_record("高风险脚本默认 dry-run", source_file="A.md", line_no=1),
        ]
        post = "只用中文回复，禁止英文"
        rep = check_static_integrity(recs, post)
        picked = select_reinject_records(recs, rep)
        assert len(picked) == 1
        assert "dry-run" in picked[0].text

    def test_select_reinject_empty_when_all_preserved(self):
        recs = [build_constraint_record("只用中文回复", source_file="SOUL.md", line_no=6)]
        rep = check_static_integrity(recs, "只用中文回复")
        assert select_reinject_records(recs, rep) == []


# ── 冲突检测 ──────────────────────────────────────────


class TestConflictDetection:
    def test_no_conflict_for_distinct(self):
        recs = [build_constraint_record("只用中文"), build_constraint_record("dry-run")]
        assert detect_conflicts(recs) == []

    def test_same_id_different_hash_is_conflict(self):
        """同一条约束被改写过。"""
        a = build_constraint_record("只用中文回复，禁止英文")
        b = ConstraintRecord(
            constraint_id=a.constraint_id,
            text="只用中文回复，禁止英文（新版）",
            text_hash="different-hash",
            priority=a.priority,
            strength=a.strength,
        )
        conflicts = detect_conflicts([a, b])
        assert len(conflicts) == 1
        assert "改写" in conflicts[0][2]

    def test_same_id_same_hash_different_priority(self):
        a = build_constraint_record("只用中文")
        b = ConstraintRecord(
            constraint_id=a.constraint_id,
            text=a.text,
            text_hash=a.text_hash,
            priority=PRIORITY_P2,
            strength=STRENGTH_SOFT,
        )
        conflicts = detect_conflicts([a, b])
        assert len(conflicts) == 1
        assert "优先级" in conflicts[0][2]

    def test_identical_records_no_conflict(self):
        a = build_constraint_record("只用中文")
        b = build_constraint_record("只用中文")
        assert detect_conflicts([a, b]) == []

    def test_empty_input(self):
        assert detect_conflicts([]) == []
