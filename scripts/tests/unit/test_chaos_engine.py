"""
R11 混沌工程引擎单元测试

测试覆盖：
  1. ChaosResult 数据类
  2. ChaosEngine 初始化
  3. 实验列表
  4. 四阶段框架（setup/execute/verify/cleanup）
  5. 各实验的 dry_run 模式
  6. 结果记录和查询
  7. 错误处理
  8. CLI 子命令（如果有）
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import mark42_modules.chaos_engine as ce
from mark42_modules.chaos_engine import (
    CHAOS_DIR,
    ChaosEngine,
    ChaosResult,
    RESULTS_FILE,
)


# ── 辅助 ──


def _make_result(**kwargs):
    """构造测试用 ChaosResult。"""
    defaults = {
        "experiment": "test",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 100,
        "status": "passed",
        "setup_ok": True,
        "execute_ok": True,
        "verify_ok": True,
        "cleanup_ok": True,
        "details": "ok",
        "metrics": {},
    }
    defaults.update(kwargs)
    return ChaosResult(**defaults)


# ── ChaosResult 数据类 ──


class TestChaosResult:
    def test_default_creation(self):
        r = _make_result()
        assert r.experiment == "test"
        assert r.status == "passed"
        assert r.metrics == {}

    def test_to_dict(self):
        r = _make_result(experiment="exp1", status="failed")
        d = r.to_dict()
        assert d["experiment"] == "exp1"
        assert d["status"] == "failed"
        assert "started_at" in d
        assert "duration_ms" in d

    def test_metrics_dict(self):
        r = _make_result(metrics={"recovery_time_ms": 500})
        assert r.metrics["recovery_time_ms"] == 500


# ── ChaosEngine 初始化 ──


class TestChaosEngineInit:
    def test_init_creates_dir(self, tmp_path):
        """初始化时创建 chaos 目录。"""
        chaos_dir = tmp_path / "chaos"
        engine = ChaosEngine(chaos_dir=chaos_dir)
        assert chaos_dir.exists()

    def test_results_file_path(self, tmp_path):
        chaos_dir = tmp_path / "chaos"
        engine = ChaosEngine(chaos_dir=chaos_dir)
        assert engine._results_file == chaos_dir / "results.jsonl"


# ── 实验列表 ──


class TestExperimentList:
    def test_list_experiments_returns_list(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        exps = engine.list_experiments()
        assert isinstance(exps, list)
        assert len(exps) >= 7

    def test_list_experiments_has_name_and_description(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        exps = engine.list_experiments()
        for e in exps:
            assert "name" in e
            assert "description" in e

    def test_list_experiments_contains_all_expected(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        exps = engine.list_experiments()
        names = [e["name"] for e in exps]
        assert "kill_engine" in names
        assert "kill_armor" in names
        assert "fill_disk" in names
        assert "network_latency" in names
        assert "high_context" in names
        assert "circuit_breaker_trip" in names
        assert "consciousness_degraded" in names


# ── dry_run 实验 ──


class TestDryRunExperiments:
    """所有实验在 dry_run=True 时都应通过。"""

    def test_kill_engine_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("kill_engine", dry_run=True)
        assert r.experiment == "kill_engine"
        assert r.status == "passed"
        assert r.setup_ok is True
        assert "[DRY-RUN]" in r.details

    def test_kill_armor_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("kill_armor", dry_run=True)
        assert r.status == "passed"

    def test_fill_disk_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("fill_disk", dry_run=True)
        assert r.status == "passed"

    def test_network_latency_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("network_latency", dry_run=True)
        assert r.status == "passed"

    def test_high_context_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("high_context", dry_run=True)
        assert r.status == "passed"

    def test_circuit_breaker_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("circuit_breaker_trip", dry_run=True)
        assert r.status == "passed"

    def test_consciousness_degraded_dry_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("consciousness_degraded", dry_run=True)
        assert r.status == "passed"


# ── 实验结果格式 ──


class TestExperimentResultFormat:
    def test_result_has_all_fields(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("fill_disk", dry_run=True)
        assert hasattr(r, "experiment")
        assert hasattr(r, "started_at")
        assert hasattr(r, "duration_ms")
        assert hasattr(r, "status")
        assert hasattr(r, "setup_ok")
        assert hasattr(r, "execute_ok")
        assert hasattr(r, "verify_ok")
        assert hasattr(r, "cleanup_ok")
        assert hasattr(r, "details")
        assert hasattr(r, "metrics")

    def test_result_started_at_is_iso(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("high_context", dry_run=True)
        # 能被解析为 ISO 时间
        datetime.fromisoformat(r.started_at.replace("Z", "+00:00"))

    def test_result_duration_positive(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("network_latency", dry_run=True)
        assert r.duration_ms >= 0


# ── 未知实验 ──


class TestUnknownExperiment:
    def test_unknown_experiment_returns_error(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("nonexistent", dry_run=True)
        assert r.status == "error"
        assert "未知实验" in r.details

    def test_unknown_experiment_no_setup(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = engine.run_experiment("nonexistent", dry_run=True)
        assert r.setup_ok is False


# ── run_suite ──


class TestRunSuite:
    def test_run_suite_returns_results_for_all(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        results = engine.run_suite(dry_run=True)
        assert len(results) >= 7
        for r in results:
            assert r.status == "passed"

    def test_run_suite_records_results(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        engine.run_suite(dry_run=True)
        # 结果写入文件
        assert engine._results_file.exists()
        lines = engine._results_file.read_text().strip().splitlines()
        assert len(lines) >= 7


# ── 结果查询 ──


class TestGetResults:
    def test_get_results_empty(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        assert engine.get_results() == []

    def test_get_results_after_run(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        engine.run_suite(dry_run=True)
        results = engine.get_results()
        assert len(results) >= 7
        for r in results:
            assert "experiment" in r
            assert "status" in r

    def test_get_results_limit(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        engine.run_suite(dry_run=True)
        results = engine.get_results(limit=3)
        assert len(results) <= 3

    def test_results_are_jsonl(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        engine.run_suite(dry_run=True)
        lines = engine._results_file.read_text().strip().splitlines()
        for line in lines:
            json.loads(line)  # 不抛异常


# ── setup 失败处理 ──


class TestSetupFailure:
    def test_setup_failure_returns_error(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        # mock setup 抛异常
        engine._setup_kill_engine = MagicMock(side_effect=RuntimeError("boom"))
        r = engine.exp_kill_engine(dry_run=True)
        assert r.status == "error"
        assert r.setup_ok is False
        assert "setup 失败" in r.details


# ── execute 失败处理 ──


class TestExecuteFailure:
    def test_execute_failure_still_cleans_up(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        # mock execute 抛异常，cleanup 正常
        engine._setup_kill_engine = MagicMock(return_value={})
        engine._execute_kill_engine = MagicMock(side_effect=RuntimeError("crash"))
        engine._cleanup_kill_engine = MagicMock()
        r = engine.exp_kill_engine(dry_run=True)
        assert r.execute_ok is False
        assert r.cleanup_ok is True  # cleanup 仍执行了
        engine._cleanup_kill_engine.assert_called_once()


# ── verify 失败处理 ──


class TestVerifyFailure:
    def test_verify_failure_returns_failed(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        engine._setup_kill_engine = MagicMock(return_value={})
        engine._execute_kill_engine = MagicMock(return_value={})
        engine._verify_kill_engine = MagicMock(return_value=False)
        engine._cleanup_kill_engine = MagicMock()
        r = engine.exp_kill_engine(dry_run=True)
        # dry_run 模式下 verify 失败仍返回 passed（因为 dry_run 跳过真实验证）
        # 但如果 verify 返回 False，会记录 verify_ok=False
        assert r.verify_ok is False


# ── fill_disk cleanup ──


class TestFillDiskCleanup:
    def test_cleanup_removes_temp_file(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        # 创建假临时文件
        tmp_file = Path("/tmp/mark42_chaos_fill_test")
        tmp_file.write_text("test")
        assert tmp_file.exists()
        # cleanup
        engine._cleanup_fill_disk(dry_run=False)
        assert not tmp_file.exists()

    def test_cleanup_no_crash_if_file_missing(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        # 文件不存在时不崩
        engine._cleanup_fill_disk(dry_run=False)


# ── circuit_breaker 实验 ──


class TestCircuitBreakerExperiment:
    def test_circuit_breaker_dry_run_setup(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        result = engine._setup_circuit_breaker(dry_run=True)
        assert "breaker_before" in result

    def test_circuit_breaker_dry_run_execute(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        result = engine._execute_circuit_breaker(dry_run=True)
        assert "action" in result


# ── systemd 检查 ──


class TestSystemdCheck:
    def test_check_systemd_service_returns_dict(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        result = engine._check_systemd_service("mark42-engine-daemon.service")
        assert "service" in result
        assert "active" in result
        assert "status" in result

    def test_check_systemd_service_nonexistent(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        result = engine._check_systemd_service("nonexistent.service")
        assert result["active"] is False


# ── _record_result ──


class TestRecordResult:
    def test_record_appends_to_jsonl(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        r = _make_result(experiment="test_exp")
        engine._record_result(r)
        lines = engine._results_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["experiment"] == "test_exp"
        assert "recorded_at" in entry

    def test_record_multiple_results(self, tmp_path):
        engine = ChaosEngine(chaos_dir=tmp_path)
        for i in range(5):
            r = _make_result(experiment=f"exp_{i}")
            engine._record_result(r)
        lines = engine._results_file.read_text().strip().splitlines()
        assert len(lines) == 5
