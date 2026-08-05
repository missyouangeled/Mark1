"""
FAILURE.md 降级契约落地测试 + 成本追踪测试

验证：
  1. core_registry 的 probe_all 在核心降级时生成 FAILURE.md
  2. core_registry 的 quarantine 生成 FAILURE.md
  3. core_registry 的 restore 清理 FAILURE.md
  4. 成本追踪的记录、查询、汇总、导出
"""

import json
from datetime import datetime, timezone
from unittest.mock import patch

from mark42.cost_tracker import (
    MODEL_PRICING,
    CostRecord,
    CostTracker,
    _local_date,
    record_cost,
)


def _make_core(core_id="core_1_main_consciousness", status="healthy", criticality="critical"):
    """构造测试用 CoreEntry。"""
    from mark42.core_registry import CoreEntry
    return CoreEntry(
        core_id=core_id,
        core_role="test",
        model_name="test-model",
        runtime="api",
        base_url="http://localhost",
        criticality=criticality,
        status=status,
    )


# ══════════════════════════════════════
# FAILURE.md 降级契约落地测试
# ══════════════════════════════════════


class TestFailureMdLanding:
    """R13-D: core_registry 与 failure_contract 的集成。"""

    def test_probe_all_generates_failure_md_on_degraded(self, mocker):
        """核心从 healthy -> degraded 时生成 FAILURE.md。"""
        import mark42.core_registry as cr_mod
        from mark42.core_registry import CoreRegistry

        mocker.patch.object(cr_mod, "probe_core", return_value={
            "status": "degraded", "reason": "模拟降级"
        })

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="healthy")}
        mocker.patch.object(reg, "_save")

        mock_create = mocker.patch("mark42.failure_contract.create_contract_for_core")
        mock_write = mocker.patch("mark42.failure_contract.write_failure_md")

        reg.probe_all()

        mock_create.assert_called_once()
        mock_write.assert_called_once()

    def test_probe_all_removes_failure_md_on_recover(self, mocker):
        """核心从 degraded -> healthy 时删除 FAILURE.md。"""
        import mark42.core_registry as cr_mod
        from mark42.core_registry import CoreRegistry

        mocker.patch.object(cr_mod, "probe_core", return_value={
            "status": "healthy", "reason": ""
        })

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="degraded")}
        mocker.patch.object(reg, "_save")

        mock_remove = mocker.patch("mark42.failure_contract.remove_failure_md")

        reg.probe_all()

        mock_remove.assert_called_once_with("core_1_main_consciousness")

    def test_quarantine_generates_failure_md(self, mocker):
        """quarantine 时生成 FAILURE.md。"""
        from mark42.core_registry import CoreRegistry

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="healthy")}
        mocker.patch.object(reg, "_save")

        mock_create = mocker.patch("mark42.failure_contract.create_contract_for_core")
        mock_write = mocker.patch("mark42.failure_contract.write_failure_md")

        result = reg.quarantine("core_1_main_consciousness", "测试隔离")

        assert result is True
        mock_create.assert_called_once()
        mock_write.assert_called_once()

    def test_quarantine_unknown_core(self, mocker):
        """quarantine 未知核心返回 False。"""
        from mark42.core_registry import CoreRegistry

        reg = CoreRegistry()
        reg.cores = {}
        mocker.patch.object(reg, "_save")

        result = reg.quarantine("nonexistent", "test")
        assert result is False

    def test_restore_removes_failure_md(self, mocker):
        """restore 恢复 healthy 时删除 FAILURE.md。"""
        import mark42.core_registry as cr_mod
        from mark42.core_registry import CoreRegistry

        mocker.patch.object(cr_mod, "probe_core", return_value={
            "status": "healthy", "reason": ""
        })

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="quarantined")}
        mocker.patch.object(reg, "_save")

        mock_remove = mocker.patch("mark42.failure_contract.remove_failure_md")

        result = reg.restore("core_1_main_consciousness")

        assert result is True
        mock_remove.assert_called_once_with("core_1_main_consciousness")

    def test_restore_unknown_core(self, mocker):
        """restore 未知核心返回 False。"""
        from mark42.core_registry import CoreRegistry

        reg = CoreRegistry()
        reg.cores = {}
        mocker.patch.object(reg, "_save")

        result = reg.restore("nonexistent")
        assert result is False

    def test_probe_all_no_change_no_action(self, mocker):
        """核心状态没变化时不触发 FAILURE.md 操作。"""
        import mark42.core_registry as cr_mod
        from mark42.core_registry import CoreRegistry

        mocker.patch.object(cr_mod, "probe_core", return_value={
            "status": "healthy", "reason": ""
        })

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="healthy")}
        mocker.patch.object(reg, "_save")

        mock_create = mocker.patch("mark42.failure_contract.create_contract_for_core")
        mock_remove = mocker.patch("mark42.failure_contract.remove_failure_md")

        reg.probe_all()

        mock_create.assert_not_called()
        mock_remove.assert_not_called()

    def test_probe_all_degraded_stays_degraded(self, mocker):
        """核心持续 degraded 不重复生成 FAILURE.md。"""
        import mark42.core_registry as cr_mod
        from mark42.core_registry import CoreRegistry

        mocker.patch.object(cr_mod, "probe_core", return_value={
            "status": "degraded", "reason": "still bad"
        })

        reg = CoreRegistry()
        reg.cores = {"core_1_main_consciousness": _make_core(status="degraded")}
        mocker.patch.object(reg, "_save")

        mock_create = mocker.patch("mark42.failure_contract.create_contract_for_core")
        mock_remove = mocker.patch("mark42.failure_contract.remove_failure_md")

        reg.probe_all()

        mock_create.assert_not_called()
        mock_remove.assert_not_called()


# ══════════════════════════════════════
# 成本追踪测试
# ══════════════════════════════════════


class TestCostRecord:
    def test_creation(self):
        r = CostRecord(
            timestamp="2026-07-22T00:00:00Z",
            model="doubao-seed-2.0-pro",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_cny=0.001,
            caller_module="test",
        )
        assert r.model == "doubao-seed-2.0-pro"
        assert r.total_tokens == 150

    def test_to_dict(self):
        r = CostRecord(
            timestamp="2026-07-22T00:00:00Z",
            model="glm-5.2",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost_cny=0.0001,
        )
        d = r.to_dict()
        assert d["model"] == "glm-5.2"
        assert "timestamp" in d


class TestCostTrackerRecord:
    def test_record_creates_file(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "test_module")
        assert costs_file.exists()

    def test_record_writes_jsonl(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "test")
        lines = costs_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["model"] == "doubao-seed-2.0-pro"
        assert entry["prompt_tokens"] == 100
        assert entry["completion_tokens"] == 50
        assert entry["total_tokens"] == 150
        assert entry["caller_module"] == "test"

    def test_record_calculates_cost_doubao(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        r = tracker.record("doubao-seed-2.0-pro", 1000, 500, "test")
        # 1000 * 0.004/1000 + 500 * 0.012/1000 = 0.004 + 0.006 = 0.01
        assert r.cost_cny == 0.01

    def test_record_calculates_cost_glm(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        r = tracker.record("glm-5.2", 1000, 500, "test")
        # 1000 * 0.002/1000 + 500 * 0.006/1000 = 0.002 + 0.003 = 0.005
        assert r.cost_cny == 0.005

    def test_record_calculates_cost_unknown_model(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        r = tracker.record("unknown-model", 1000, 500, "test")
        # 默认用 doubao 价格
        assert r.cost_cny == 0.01

    def test_record_multiple(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        for i in range(5):
            tracker.record("doubao-seed-2.0-pro", 100 * i, 50 * i, f"mod_{i}")
        lines = costs_file.read_text().strip().splitlines()
        assert len(lines) == 5

    def test_record_cost_function(self, tmp_path):
        """便捷函数 record_cost 正常工作。"""
        costs_file = tmp_path / "costs.jsonl"
        with patch("mark42.cost_tracker.COSTS_FILE", costs_file):
            r = record_cost("doubao-seed-2.0-pro", 100, 50, "test")
            assert r.total_tokens == 150
            assert costs_file.exists()


class TestCostTrackerSummary:
    def test_daily_summary_empty(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        summary = tracker.get_daily_summary("2026-07-22")
        assert summary["total_calls"] == 0
        assert summary["total_cost"] == 0.0

    def test_daily_summary_with_data(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")
        tracker.record("glm-5.2", 200, 100, "mod_b")

        summary = tracker.get_daily_summary()
        assert summary["total_calls"] == 2
        assert summary["total_tokens"] == 450  # 150 + 250
        assert "doubao-seed-2.0-pro" in summary["by_model"]
        assert "glm-5.2" in summary["by_model"]

    def test_monthly_summary(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")
        tracker.record("glm-5.2", 200, 100, "mod_b")

        summary = tracker.get_monthly_summary()
        assert summary["total_calls"] == 2
        assert "by_day" in summary
        assert len(summary["by_day"]) >= 1

    def test_top_callers(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")
        tracker.record("glm-5.2", 200, 100, "mod_b")

        top = tracker.get_top_callers()
        assert len(top) == 2
        assert top[0]["module"] == "mod_a"  # 调用更多
        assert top[0]["calls"] == 2

    def test_top_callers_limit(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        for i in range(10):
            tracker.record("doubao-seed-2.0-pro", 100, 50, f"mod_{i}")

        top = tracker.get_top_callers(n=3)
        assert len(top) == 3

    def test_export_csv(self, tmp_path):
        costs_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=costs_file)
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")
        tracker.record("glm-5.2", 200, 100, "mod_b")

        csv_path = tmp_path / "export.csv"
        count = tracker.export_csv("2026-01-01", "2026-12-31", str(csv_path))
        assert count == 2
        assert csv_path.exists()
        import csv as csv_mod
        with open(csv_path) as f:
            reader = csv_mod.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert "model" in rows[0]
            assert "cost_cny" in rows[0]


class TestDailySummaryTimezone:
    """防回归：汇总日期必须按**本地**时区归属，不能直接切 UTC 时间戳前缀。

    历史 bug：``record()`` 用 ``datetime.now(timezone.utc)`` 落盘，而
    ``get_daily_summary()`` 默认日期取本地今天，却用 ``timestamp[:10]``
    直接比对。UTC+8 下本地 00:00–08:00 写入的记录 UTC 日期仍为前一天，
    导致早班时段成本日报恒为 0。
    """

    def test_local_date_converts_utc_to_local(self):
        # UTC 23:30 在 UTC+8 已经是次日 07:30
        got = _local_date("2026-08-04T23:30:00+00:00")
        expected = (
            datetime(2026, 8, 4, 23, 30, tzinfo=timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d")
        )
        assert got == expected

    def test_local_date_accepts_z_suffix_and_naive(self):
        expected = (
            datetime(2026, 8, 4, 23, 30, tzinfo=timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d")
        )
        # Z 结尾与裸时间戳（按 UTC 解释）应与显式 +00:00 一致
        assert _local_date("2026-08-04T23:30:00Z") == expected
        assert _local_date("2026-08-04T23:30:00") == expected

    def test_local_date_tolerates_dirty_data(self):
        # 单条脏数据不能让整份汇总抛异常
        assert _local_date("not-a-date") == "not-a-date"[:10]
        assert _local_date("") == ""

    def test_daily_summary_counts_record_written_now(self, tmp_path):
        """当下写入的记录必须出现在「今日」汇总里——早班时段也不能丢。"""
        tracker = CostTracker(costs_file=tmp_path / "costs.jsonl")
        tracker.record("doubao-seed-2.0-pro", 100, 50, "mod_a")

        summary = tracker.get_daily_summary()
        assert summary["total_calls"] == 1

    def test_daily_summary_uses_local_day_boundary(self, tmp_path):
        """手写 UTC 跳日时间戳，应归入它对应的**本地**日期而非 UTC 日期。"""
        costs_file = tmp_path / "costs.jsonl"
        utc_dt = datetime(2026, 8, 4, 23, 30, tzinfo=timezone.utc)
        record = {
            "timestamp": utc_dt.isoformat(),
            "model": "glm-5.2",
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "cost_cny": 1.0,
            "caller_module": "mod_b",
        }
        costs_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        tracker = CostTracker(costs_file=costs_file)
        local_day = utc_dt.astimezone().strftime("%Y-%m-%d")
        utc_day = utc_dt.strftime("%Y-%m-%d")

        assert tracker.get_daily_summary(local_day)["total_calls"] == 1
        if local_day != utc_day:
            assert tracker.get_daily_summary(utc_day)["total_calls"] == 0

    def test_monthly_and_csv_share_local_date_semantics(self, tmp_path):
        """月报分组与 CSV 导出必须跟日报用同一套日期语义。"""
        costs_file = tmp_path / "costs.jsonl"
        utc_dt = datetime(2026, 8, 4, 23, 30, tzinfo=timezone.utc)
        record = {
            "timestamp": utc_dt.isoformat(),
            "model": "glm-5.2",
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "total_tokens": 300,
            "cost_cny": 1.0,
            "caller_module": "mod_b",
        }
        costs_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

        tracker = CostTracker(costs_file=costs_file)
        local_day = utc_dt.astimezone().strftime("%Y-%m-%d")

        monthly = tracker.get_monthly_summary(local_day[:7])
        assert monthly["total_calls"] == 1
        assert local_day in monthly["by_day"]

        csv_path = tmp_path / "export.csv"
        assert tracker.export_csv(local_day, local_day, str(csv_path)) == 1


class TestModelPricing:
    def test_doubao_pricing(self):
        assert MODEL_PRICING["doubao-seed-2.0-pro"]["input"] == 0.004
        assert MODEL_PRICING["doubao-seed-2.0-pro"]["output"] == 0.012

    def test_glm_pricing(self):
        assert MODEL_PRICING["glm-5.2"]["input"] == 0.002
        assert MODEL_PRICING["glm-5.2"]["output"] == 0.006

    def test_default_pricing(self):
        assert MODEL_PRICING["default"]["input"] == 0.004
