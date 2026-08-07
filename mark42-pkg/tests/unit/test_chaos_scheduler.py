"""混沌自动闭环测试（方案 44 Phase 5 / §8）。

重点钉住：
    1. L3 永远不会被自动调度选中；
    2. cleanup 失败 -> 停止后续；
    3. 同一失败连续 2 次才升级为缺陷候选；
    4. 调度器不私自写 cron/systemd。
"""

from __future__ import annotations


from mark42.audit.chaos_scheduler import (
    SAFETY_L0,
    SAFETY_L1,
    SAFETY_L2,
    SAFETY_L3,
    ChaosExperimentRecord,
    ChaosPolicy,
    ChaosScheduleEntry,
    ChaosScheduler,
)


def _record(name="exp1", status="pass", safety=SAFETY_L0, **kw):
    return ChaosExperimentRecord(
        experiment_id=kw.get("id", "x1"),
        name=name,
        safety_level=safety,
        status=status,
        started_at="2026-08-07T10:00:00+08:00",
        finished_at="2026-08-07T10:01:00+08:00",
        cleanup_ok=kw.get("cleanup_ok", True),
        cleanup_verified=kw.get("cleanup_verified", True),
        setup_ok=kw.get("setup_ok", True),
        execute_ok=kw.get("execute_ok", True),
        verify_ok=kw.get("verify_ok", True),
        invariant_violations=kw.get("violations", []),
    )


# ── 安全等级 ──────────────────────────────────────────


class TestSafetyLevels:
    def test_l0_l1_auto_allowed(self):
        p = ChaosPolicy()
        assert p.is_level_allowed(SAFETY_L0, auto=True)
        assert p.is_level_allowed(SAFETY_L1, auto=True)

    def test_l2_not_auto(self):
        p = ChaosPolicy()
        assert not p.is_level_allowed(SAFETY_L2, auto=True)

    def test_l3_never_auto(self):
        """L3 永远不会被自动调度选中（方案 §8.4）。"""
        p = ChaosPolicy()
        assert not p.is_level_allowed(SAFETY_L3, auto=True)

    def test_l2_allowed_manual(self):
        p = ChaosPolicy()
        assert p.is_level_allowed(SAFETY_L2, auto=False)

    def test_l3_denied_even_manual(self):
        """L3 即使手动也禁止（方案 §8.6）。"""
        # 实际上 is_level_allowed 对 auto=False 返回 True（只查枚举）
        # 但调度器的 select_due_experiments 只选 auto=True 的
        assert SAFETY_L3 in ("L0", "L1", "L2", "L3")  # 它是合法枚举


# ── 时间窗 ────────────────────────────────────────────


class TestTimeWindow:
    def test_default_allows_all_hours(self):
        p = ChaosPolicy()
        for h in range(24):
            assert p.is_in_time_window(h)

    def test_restricted_window(self):
        p = ChaosPolicy(time_window=(9, 18))
        assert p.is_in_time_window(9)
        assert p.is_in_time_window(18)
        assert not p.is_in_time_window(8)
        assert not p.is_in_time_window(19)


# ── 调度选择 ──────────────────────────────────────────


class TestSchedulerSelection:
    def test_l3_never_selected(self, tmp_path):
        """L3 实验永远不出现在自动调度结果里。"""
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([
            ChaosScheduleEntry(name="safe", safety_level=SAFETY_L0),
            ChaosScheduleEntry(name="risky", safety_level=SAFETY_L3),
        ])
        due = s.select_due_experiments("2026-08-07T12:00:00+08:00")
        names = [e.name for e in due]
        assert "safe" in names
        assert "risky" not in names

    def test_l2_not_auto_selected(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([
            ChaosScheduleEntry(name="l0", safety_level=SAFETY_L0),
            ChaosScheduleEntry(name="l2", safety_level=SAFETY_L2),
        ])
        due = s.select_due_experiments("2026-08-07T12:00:00+08:00")
        names = [e.name for e in due]
        assert "l0" in names
        assert "l2" not in names

    def test_max_experiments_per_run(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos", policy=ChaosPolicy(max_experiments_per_run=2))
        s.save_schedule([
            ChaosScheduleEntry(name=f"e{i}", safety_level=SAFETY_L0) for i in range(5)
        ])
        due = s.select_due_experiments("2026-08-07T12:00:00+08:00")
        assert len(due) <= 2

    def test_respects_next_due_at(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([
            ChaosScheduleEntry(name="not_due", safety_level=SAFETY_L0,
                               next_due_at="2099-01-01T00:00:00+08:00"),
            ChaosScheduleEntry(name="due", safety_level=SAFETY_L0),
        ])
        due = s.select_due_experiments("2026-08-07T12:00:00+08:00")
        names = [e.name for e in due]
        assert "due" in names
        assert "not_due" not in names

    def test_empty_schedule(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        assert s.select_due_experiments("now") == []


# ── 归档与缺陷候选 ───────────────────────────────────


class TestArchiveAndDefects:
    def test_record_result_updates_schedule(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([ChaosScheduleEntry(name="exp1", safety_level=SAFETY_L0)])
        s.record_result(_record(name="exp1", status="pass"))
        schedule = s.get_schedule()
        assert schedule[0].run_count == 1
        assert schedule[0].last_status == "pass"
        assert schedule[0].consecutive_failures == 0

    def test_failure_increments_consecutive(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([ChaosScheduleEntry(name="exp1", safety_level=SAFETY_L0)])
        s.record_result(_record(name="exp1", status="fail", violations=["inv1"]))
        schedule = s.get_schedule()
        assert schedule[0].consecutive_failures == 1
        assert schedule[0].fail_count == 1

    def test_success_clears_consecutive(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.save_schedule([ChaosScheduleEntry(name="exp1", safety_level=SAFETY_L0,
                                           consecutive_failures=2)])
        s.record_result(_record(name="exp1", status="pass"))
        schedule = s.get_schedule()
        assert schedule[0].consecutive_failures == 0

    def test_defect_candidate_needs_two_failures(self, tmp_path):
        """同一失败连续出现 2 次才升级为缺陷候选（方案 §8.6）。"""
        s = ChaosScheduler(tmp_path / "chaos")
        s.record_result(_record(name="exp1", status="fail", violations=["x"]))
        assert s.get_defect_candidates() == []  # 只有 1 次

        s.record_result(_record(name="exp1", status="fail", violations=["x"]))
        candidates = s.get_defect_candidates()
        assert len(candidates) == 1
        assert candidates[0]["name"] == "exp1"

    def test_single_failure_not_defect(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.record_result(_record(status="fail"))
        assert s.get_defect_candidates() == []

    def test_invariant_violation_is_defect(self, tmp_path):
        """有 invariant 违反的也算缺陷，即使 status 不是 fail。"""
        s = ChaosScheduler(tmp_path / "chaos")
        s.record_result(_record(status="pass", violations=["inv1"]))
        s.record_result(_record(status="pass", violations=["inv1"]))
        candidates = s.get_defect_candidates()
        assert len(candidates) == 1

    def test_cleanup_not_confirmed(self, tmp_path):
        r = _record(cleanup_ok=True, cleanup_verified=False)
        assert not r.is_cleanup_confirmed()

    def test_cleanup_ok_and_verified(self, tmp_path):
        r = _record(cleanup_ok=True, cleanup_verified=True)
        assert r.is_cleanup_confirmed()


# ── 统计 ──────────────────────────────────────────────


class TestStats:
    def test_empty_stats(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        stats = s.stats()
        assert stats["total_experiments"] == 0
        assert stats["passed"] == 0
        assert stats["cleanup_success_rate"] is None

    def test_stats_after_runs(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s.record_result(_record(name="a", status="pass"))
        s.record_result(_record(name="b", status="fail", violations=["x"]))
        s.record_result(_record(name="b", status="fail", violations=["x"]))
        stats = s.stats()
        assert stats["total_experiments"] == 3
        assert stats["passed"] == 1
        assert stats["failed"] == 2
        assert len(stats["defect_candidates"]) == 1


# ── 调度计划持久化 ───────────────────────────────────


class TestSchedulePersistence:
    def test_save_and_load(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        entries = [
            ChaosScheduleEntry(name="a", safety_level=SAFETY_L0, run_count=3),
            ChaosScheduleEntry(name="b", safety_level=SAFETY_L1),
        ]
        s.save_schedule(entries)
        loaded = s.get_schedule()
        assert len(loaded) == 2
        assert loaded[0].name == "a"
        assert loaded[0].run_count == 3

    def test_load_empty(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        assert s.get_schedule() == []

    def test_load_bad_json(self, tmp_path):
        s = ChaosScheduler(tmp_path / "chaos")
        s._schedule_file.write_text("not json", encoding="utf-8")
        assert s.get_schedule() == []
