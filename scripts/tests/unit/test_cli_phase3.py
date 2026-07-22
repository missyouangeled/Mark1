"""
cli.py 补充测试 - Phase 3 候选模块

覆盖未测的 CLI 子命令分发：
  - archive (list/show/approve/reject/stats)
  - consciousness (check/eval/handle/advisor/revalidate)
  - cores (list/probe/quarantine/restore)
  - chaos (list/run/history)
  - module (check/summary)
  - cluster (list/status/replace)
  - breaker (list/status/reset/reset-all)
  - context-safety (apply/verify/status)
  - _find_mark42_processes / _pid_alive / _stop_assemble
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import cli


# ── 辅助 ──

def _set_argv(*args):
    """设置 sys.argv。"""
    sys.argv = ["mark42"] + list(args)


# ── _pid_alive / _find_mark42_processes ──


class TestPidAlive:
    def test_alive_pid(self):
        """当前进程的 PID 肯定 alive。"""
        import os
        assert cli._pid_alive(os.getpid()) is True

    def test_dead_pid(self):
        """不存在的 PID 返回 False。"""
        assert cli._pid_alive(999999) is False


class TestFindMark42Processes:
    def test_returns_dict_structure(self):
        """返回正确结构。"""
        result = cli._find_mark42_processes()
        assert "parent" in result
        assert "children" in result
        assert isinstance(result["children"], list)

    def test_no_crash_on_ps_failure(self, mocker):
        """ps 命令失败时不崩。"""
        mocker.patch("subprocess.check_output", side_effect=Exception("fail"))
        result = cli._find_mark42_processes()
        assert result["parent"] is None
        assert result["children"] == []


# ── archive 子命令 ──


class TestArchiveCli:
    def test_archive_list(self, mocker, capsys):
        """archive list 正常分发。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_instance.list_entries.return_value = []
        mock_instance.stats.return_value = {"total": 0}
        _set_argv("archive", "list")
        cli.main()
        mock_instance.list_entries.assert_called_once()

    def test_archive_show_not_found(self, mocker, capsys):
        """archive show 找不到条目。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_instance.get.return_value = None
        _set_argv("archive", "show", "ERR-999")
        result = cli.main()
        assert result == 1

    def test_archive_show_found(self, mocker, capsys):
        """archive show 找到条目。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_entry = MagicMock()
        mock_entry.to_dict.return_value = {"id": "ERR-001"}
        mock_instance.get.return_value = mock_entry
        _set_argv("archive", "show", "ERR-001")
        cli.main()
        mock_instance.get.assert_called_once_with("ERR-001")

    def test_archive_approve(self, mocker):
        """archive approve 分发。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_instance.approve_for_auto.return_value = {"ok": True, "reason": "OK"}
        _set_argv("archive", "approve", "ERR-001")
        result = cli.main()
        mock_instance.approve_for_auto.assert_called_once()

    def test_archive_reject(self, mocker):
        """archive reject 分发。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_instance.reject.return_value = {"ok": True, "reason": "rejected"}
        _set_argv("archive", "reject", "ERR-001", "--notes", "test")
        result = cli.main()
        mock_instance.reject.assert_called_once()

    def test_archive_stats(self, mocker, capsys):
        """archive stats 分发。"""
        mock_arc = mocker.patch("mark42_modules.error_archive.ErrorArchive")
        mock_instance = mock_arc.return_value
        mock_instance.stats.return_value = {
            "total": 5, "by_status": {"pending": 3, "approved": 2},
            "auto_approved_count": 1
        }
        _set_argv("archive", "stats")
        cli.main()
        mock_instance.stats.assert_called_once()


# ── consciousness 子命令 ──


class TestConsciousnessCli:
    def test_consciousness_check(self, mocker, capsys):
        """consciousness check 分发。"""
        mock_cs = mocker.patch("mark42_modules.consciousness.Consciousness")
        mock_instance = mock_cs.return_value
        mock_result = MagicMock()
        mock_result.healthy = True
        mock_result.checked_at = "2026-07-22"
        mock_result.issues = []
        mock_result.to_dict.return_value = {"healthy": True}
        mock_instance.self_check.return_value = mock_result
        _set_argv("consciousness", "check")
        cli.main()
        mock_instance.self_check.assert_called_once()

    def test_consciousness_check_json(self, mocker, capsys):
        """consciousness check --json 输出 JSON。"""
        mock_cs = mocker.patch("mark42_modules.consciousness.Consciousness")
        mock_instance = mock_cs.return_value
        mock_result = MagicMock()
        mock_result.healthy = True
        mock_result.checked_at = "2026-07-22"
        mock_result.issues = []
        mock_result.to_dict.return_value = {"healthy": True, "issues": []}
        mock_instance.self_check.return_value = mock_result
        _set_argv("consciousness", "check", "--json")
        cli.main()
        mock_instance.self_check.assert_called_once()

    def test_consciousness_eval_missing_args(self, mocker, capsys):
        """consciousness eval 缺少必填参数。"""
        mocker.patch("mark42_modules.consciousness.Consciousness")
        _set_argv("consciousness", "eval")
        result = cli.main()
        assert result == 1

    def test_consciousness_handle_missing_args(self, mocker, capsys):
        """consciousness handle 缺少必填参数。"""
        mocker.patch("mark42_modules.consciousness.Consciousness")
        _set_argv("consciousness", "handle")
        result = cli.main()
        assert result == 1

    def test_consciousness_handle_with_args(self, mocker):
        """consciousness handle 正常分发。"""
        mock_cs = mocker.patch("mark42_modules.consciousness.Consciousness")
        mock_instance = mock_cs.return_value
        mock_instance.handle_issue.return_value = {"path": "C4_dialog"}
        _set_argv("consciousness", "handle", "--source", "test", "--category", "unknown")
        cli.main()
        mock_instance.handle_issue.assert_called_once()

    def test_consciousness_revalidate(self, mocker):
        """consciousness revalidate 分发。"""
        mock_cs = mocker.patch("mark42_modules.consciousness.Consciousness")
        mock_instance = mock_cs.return_value
        mock_instance.verify_read_protocol.return_value = {
            "passed": True, "score": 6, "total": 10, "min_correct": 2
        }
        _set_argv("consciousness", "revalidate")
        cli.main()
        mock_instance.verify_read_protocol.assert_called_once_with(force=True)


# ── cores 子命令 ──


class TestCoresCli:
    def test_cores_list(self, mocker, capsys):
        """cores list 正常分发。"""
        mock_list = mocker.patch("mark42_modules.core_registry.cli_cores_list")
        mock_list.return_value = {
            "cores": [{"core_id": "core_1", "model_name": "test", "status": "healthy"}],
            "summary": {"total": 1, "statuses": {"healthy": 1}, "critical_down": []}
        }
        _set_argv("cores", "list")
        cli.main()
        mock_list.assert_called_once()

    def test_cores_probe(self, mocker, capsys):
        """cores probe 正常分发。"""
        mock_probe = mocker.patch("mark42_modules.core_registry.cli_cores_probe")
        mock_probe.return_value = {"core_1": {"status": "healthy", "reason": ""}}
        _set_argv("cores", "probe")
        cli.main()
        mock_probe.assert_called_once()

    def test_cores_quarantine_missing_id(self, mocker, capsys):
        """cores quarantine 缺少 --core-id。"""
        _set_argv("cores", "quarantine")
        result = cli.main()
        assert result == 1

    def test_cores_quarantine(self, mocker):
        """cores quarantine 正常分发。"""
        mock_q = mocker.patch("mark42_modules.core_registry.cli_cores_quarantine")
        mock_q.return_value = {"ok": True}
        _set_argv("cores", "quarantine", "--core-id", "core_1", "--reason", "test")
        cli.main()
        mock_q.assert_called_once_with("core_1", "test")

    def test_cores_restore_missing_id(self, mocker, capsys):
        """cores restore 缺少 --core-id。"""
        _set_argv("cores", "restore")
        result = cli.main()
        assert result == 1

    def test_cores_restore(self, mocker):
        """cores restore 正常分发。"""
        mock_r = mocker.patch("mark42_modules.core_registry.cli_cores_restore")
        mock_r.return_value = {"ok": True}
        _set_argv("cores", "restore", "--core-id", "core_1")
        cli.main()
        mock_r.assert_called_once_with("core_1")


# ── breaker 子命令 ──


class TestBreakerCli:
    def test_breaker_list_empty(self, mocker, capsys):
        """breaker list 全部 closed。"""
        mock_cb = mocker.patch("mark42_modules.circuit_breaker.CircuitBreaker")
        mock_instance = mock_cb.return_value
        mock_instance.list_all.return_value = []
        _set_argv("breaker", "list")
        cli.main()
        mock_instance.list_all.assert_called_once()

    def test_breaker_list_with_open(self, mocker, capsys):
        """breaker list 有 open 状态。"""
        mock_cb = mocker.patch("mark42_modules.circuit_breaker.CircuitBreaker")
        mock_instance = mock_cb.return_value
        mock_instance.list_all.return_value = [
            {"core_id": "core_1", "status": "open", "consecutive_failures": 5}
        ]
        _set_argv("breaker", "list")
        cli.main()
        mock_instance.list_all.assert_called_once()

    def test_breaker_status_by_core(self, mocker, capsys):
        """breaker status --core-id。"""
        mock_cb = mocker.patch("mark42_modules.circuit_breaker.CircuitBreaker")
        mock_instance = mock_cb.return_value
        mock_instance.get_state.return_value = {"status": "closed", "consecutive_failures": 0}
        _set_argv("breaker", "status", "--core-id", "core_1")
        cli.main()
        mock_instance.get_state.assert_called_once_with("core_1")

    def test_breaker_reset_missing_id(self, mocker, capsys):
        """breaker reset 缺少 --core-id。"""
        _set_argv("breaker", "reset")
        result = cli.main()
        assert result == 1

    def test_breaker_reset(self, mocker):
        """breaker reset 正常分发。"""
        mock_cb = mocker.patch("mark42_modules.circuit_breaker.CircuitBreaker")
        mock_instance = mock_cb.return_value
        _set_argv("breaker", "reset", "--core-id", "core_1")
        cli.main()
        mock_instance.reset.assert_called_once_with("core_1")

    def test_breaker_reset_all(self, mocker):
        """breaker reset-all 正常分发。"""
        mock_cb = mocker.patch("mark42_modules.circuit_breaker.CircuitBreaker")
        mock_instance = mock_cb.return_value
        _set_argv("breaker", "reset-all")
        cli.main()
        mock_instance.reset_all.assert_called_once()


# ── context-safety 子命令 ──


class TestContextSafetyCli:
    def test_context_safety_status(self, mocker):
        """context-safety status 分发。"""
        mock_status = mocker.patch("mark42_modules.context_safety.context_safety_status")
        _set_argv("context-safety", "status")
        cli.main()
        mock_status.assert_called_once()

    def test_context_safety_apply(self, mocker):
        """context-safety apply 分发。"""
        mock_apply = mocker.patch("mark42_modules.context_safety.context_safety_apply")
        mock_apply.return_value = {"validateOk": True}
        _set_argv("context-safety", "apply")
        cli.main()
        mock_apply.assert_called_once()

    def test_context_safety_apply_validation_fail(self, mocker):
        """context-safety apply 验证失败时 exit(1)。"""
        mock_apply = mocker.patch("mark42_modules.context_safety.context_safety_apply")
        mock_apply.return_value = {"validateOk": False}
        _set_argv("context-safety", "apply")
        with pytest.raises(SystemExit) as exc_info:
            cli.main()
        assert exc_info.value.code == 1

    def test_context_safety_verify(self, mocker):
        """context-safety verify 分发。"""
        mock_verify = mocker.patch("mark42_modules.context_safety.context_safety_verify")
        mock_verify.return_value = 0
        _set_argv("context-safety", "verify")
        with pytest.raises(SystemExit):
            cli.main()
        mock_verify.assert_called_once()


# ── logs 子命令补充 ──


class TestLogsCliExtra:
    def test_logs_rotate(self, mocker):
        """logs --rotate 分发。"""
        mock_rotate = mocker.patch("mark42_modules.logs.log_rotate")
        mock_rotate.return_value = {}
        _set_argv("logs", "--rotate")
        cli.main()
        mock_rotate.assert_called_once_with("all")

    def test_logs_status(self, mocker):
        """logs --status 分发。"""
        mock_status = mocker.patch("mark42_modules.logs.log_rotate_status")
        _set_argv("logs", "--status")
        cli.main()
        mock_status.assert_called_once()


# ── cost 子命令 ──


class TestCostCli:
    def test_cost_today(self, mocker, capsys):
        """cost today 分发。"""
        mock_today = mocker.patch("mark42_modules.cost_tracker.cli_cost_today")
        mock_today.return_value = {"total_calls": 0, "total_cost": 0.0}
        _set_argv("cost", "today")
        cli.main()
        mock_today.assert_called_once()

    def test_cost_default_is_today(self, mocker):
        """cost 不带 action 默认走 today。"""
        mock_today = mocker.patch("mark42_modules.cost_tracker.cli_cost_today")
        mock_today.return_value = {}
        _set_argv("cost")
        cli.main()
        mock_today.assert_called_once()

    def test_cost_month(self, mocker):
        """cost month 分发。"""
        mock_month = mocker.patch("mark42_modules.cost_tracker.cli_cost_month")
        mock_month.return_value = {}
        _set_argv("cost", "month")
        cli.main()
        mock_month.assert_called_once()

    def test_cost_top(self, mocker):
        """cost top 分发。"""
        mock_top = mocker.patch("mark42_modules.cost_tracker.cli_cost_top")
        mock_top.return_value = []
        _set_argv("cost", "top", "--top-n", "5")
        cli.main()
        mock_top.assert_called_once_with(n=5, days=None)


# ── chaos 子命令 ──


class TestChaosCli:
    def test_chaos_list(self, mocker, capsys):
        """chaos list 分发。"""
        mock_engine = mocker.patch("mark42_modules.chaos_engine.ChaosEngine")
        mock_instance = mock_engine.return_value
        mock_instance.list_experiments.return_value = [
            {"name": "kill_engine", "description": "模拟 engine 崩溃"}
        ]
        _set_argv("chaos", "list")
        cli.main()
        mock_instance.list_experiments.assert_called_once()

    def test_chaos_run_missing_scenario(self, mocker, capsys):
        """chaos run 缺少 --scenario。"""
        mock_engine = mocker.patch("mark42_modules.chaos_engine.ChaosEngine")
        mock_instance = mock_engine.return_value
        mock_instance.list_experiments.return_value = []
        _set_argv("chaos", "run")
        result = cli.main()
        assert result == 1

    def test_chaos_run_dry_run(self, mocker):
        """chaos run 默认 dry_run。"""
        mock_engine = mocker.patch("mark42_modules.chaos_engine.ChaosEngine")
        mock_instance = mock_engine.return_value
        mock_result = MagicMock()
        mock_result.status = "passed"
        mock_result.experiment = "kill_engine"
        mock_result.duration_ms = 10
        mock_result.setup_ok = True
        mock_result.execute_ok = True
        mock_result.verify_ok = True
        mock_result.cleanup_ok = True
        mock_result.details = "[DRY-RUN] ok"
        mock_instance.run_experiment.return_value = mock_result
        _set_argv("chaos", "run", "--scenario", "kill_engine")
        cli.main()
        mock_instance.run_experiment.assert_called_once_with("kill_engine", dry_run=True)

    def test_chaos_run_execute(self, mocker):
        """chaos run --execute-now 真实执行。"""
        mock_engine = mocker.patch("mark42_modules.chaos_engine.ChaosEngine")
        mock_instance = mock_engine.return_value
        mock_result = MagicMock()
        mock_result.status = "passed"
        mock_result.experiment = "fill_disk"
        mock_result.duration_ms = 500
        mock_result.setup_ok = True
        mock_result.execute_ok = True
        mock_result.verify_ok = True
        mock_result.cleanup_ok = True
        mock_result.details = "ok"
        mock_instance.run_experiment.return_value = mock_result
        _set_argv("chaos", "run", "--scenario", "fill_disk", "--execute-now")
        cli.main()
        mock_instance.run_experiment.assert_called_once_with("fill_disk", dry_run=False)

    def test_chaos_history(self, mocker, capsys):
        """chaos history 分发。"""
        mock_engine = mocker.patch("mark42_modules.chaos_engine.ChaosEngine")
        mock_instance = mock_engine.return_value
        mock_instance.get_results.return_value = [
            {"experiment": "kill_engine", "status": "passed", "started_at": "2026-07-22T00:00:00Z", "duration_ms": 100}
        ]
        _set_argv("chaos", "history")
        cli.main()
        mock_instance.get_results.assert_called_once()
