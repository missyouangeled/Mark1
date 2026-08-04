"""pytest tests for mark42/watchdog.py"""

import json
import os
from unittest.mock import Mock, patch

from mark42.watchdog import (
    _check_heartbeat,
    _check_process,
    _get_env,
    _log,
    _restart_service,
    watchdog_check,
)

# ── _get_env tests ──


def test_get_env_existing():
    """Test _get_env returns existing env var."""
    os.environ["TEST_WATCHDOG_VAR"] = "test_value"
    assert _get_env("TEST_WATCHDOG_VAR") == "test_value"
    del os.environ["TEST_WATCHDOG_VAR"]


def test_get_env_default():
    """Test _get_env returns default when env var not set."""
    assert _get_env("NONEXISTENT_VAR_12345", "default_val") == "default_val"
    assert _get_env("NONEXISTENT_VAR_12345") == ""


# ── _log tests ──


def test_log_creates_file(tmp_path):
    """Test _log creates log file and writes message."""
    log_file = tmp_path / "watchdog.log"
    _log("Test message", log_file)

    assert log_file.exists()
    content = log_file.read_text()
    assert "Test message" in content
    assert "[" in content  # timestamp


def test_log_creates_parent_dirs(tmp_path):
    """Test _log creates parent directories if needed."""
    log_file = tmp_path / "nested" / "deep" / "watchdog.log"
    _log("Nested test", log_file)

    assert log_file.exists()
    assert "Nested test" in log_file.read_text()


def test_log_ignores_errors():
    """Test _log silently ignores errors (e.g. invalid path)."""
    # Should not raise
    _log("Test", "/invalid/path/that/cannot/be/created.log")


# ── _check_heartbeat tests ──


def test_check_heartbeat_file_missing(tmp_path):
    """Test _check_heartbeat when file doesn't exist."""
    heartbeat = tmp_path / "nonexistent.json"
    ok, reason = _check_heartbeat(heartbeat)
    assert ok is False
    assert "不存在" in reason


def test_check_heartbeat_valid(tmp_path):
    """Test _check_heartbeat with valid recent heartbeat."""
    heartbeat = tmp_path / "heartbeat.json"

    # Use real recent time
    from datetime import datetime, timezone

    recent_time = datetime.now(timezone.utc).isoformat()
    heartbeat.write_text(json.dumps({"lastTick": recent_time}))

    ok, reason = _check_heartbeat(heartbeat, warn_threshold=300)
    assert ok is True
    assert reason == ""


def test_check_heartbeat_timeout(tmp_path):
    """Test _check_heartbeat when heartbeat is timed out."""
    heartbeat = tmp_path / "heartbeat.json"
    data = {"lastTick": "2026-01-01T12:00:00+00:00"}
    heartbeat.write_text(json.dumps(data))

    ok, reason = _check_heartbeat(heartbeat, warn_threshold=60)
    assert ok is False
    assert "超时" in reason


def test_check_heartbeat_missing_lasttick(tmp_path):
    """Test _check_heartbeat when lastTick field is missing."""
    heartbeat = tmp_path / "heartbeat.json"
    heartbeat.write_text(json.dumps({"otherField": "value"}))

    ok, reason = _check_heartbeat(heartbeat)
    assert ok is False
    assert "lastTick" in reason


def test_check_heartbeat_corrupted_json(tmp_path):
    """Test _check_heartbeat with corrupted JSON."""
    heartbeat = tmp_path / "heartbeat.json"
    heartbeat.write_text("not valid json {{{")

    ok, reason = _check_heartbeat(heartbeat)
    assert ok is False
    assert "不可解析" in reason


# ── _check_process tests ──


def test_check_process_exists():
    """Test _check_process returns True when process exists."""
    with patch("mark42.watchdog.subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout.strip.return_value = "1234"
        mock_run.return_value = mock_result

        result = _check_process("some-process-pattern")
        assert result is True
        mock_run.assert_called_once()


def test_check_process_not_exists():
    """Test _check_process returns False when process doesn't exist."""
    with patch("mark42.watchdog.subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 1  # pgrep returns 1 when no match
        mock_result.stdout.strip.return_value = ""
        mock_run.return_value = mock_result

        result = _check_process("nonexistent-process")
        assert result is False


def test_check_process_exception():
    """Test _check_process handles subprocess exception gracefully."""
    with patch("mark42.watchdog.subprocess.run") as mock_run:
        mock_run.side_effect = Exception("subprocess error")

        result = _check_process("pattern")
        assert result is False


# ── _restart_service tests ──


def test_restart_service_calls_systemctl(tmp_path):
    """Test _restart_service calls systemctl restart."""
    log_file = tmp_path / "watchdog.log"

    with patch("mark42.watchdog.subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        _restart_service("test.service", log_file)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "systemctl" in args
        assert "--user" in args
        assert "restart" in args
        assert "test.service" in args


def test_restart_service_failure_logs_error(tmp_path):
    """Test _restart_service logs error when restart fails."""
    log_file = tmp_path / "watchdog.log"

    with patch("mark42.watchdog.subprocess.run") as mock_run:
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr.strip.return_value = "Failed to restart"
        mock_run.return_value = mock_result

        _restart_service("test.service", log_file)

        log_content = log_file.read_text()
        assert "重启失败" in log_content or "Failed" in log_content


# ── watchdog_check tests ──


def test_watchdog_check_all_normal(tmp_path):
    """Test watchdog_check when everything is normal (no restart needed)."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Create valid heartbeat
    heartbeat_file = state_dir / "engine" / "daemon-heartbeat.json"
    heartbeat_file.parent.mkdir(parents=True)

    from datetime import datetime, timezone

    recent_time = datetime.now(timezone.utc).isoformat()
    heartbeat_file.write_text(json.dumps({"lastTick": recent_time}))

    env_vars = {
        "XDG_STATE_HOME": str(tmp_path / "state"),
        "MARK42_STATE_DIR": str(tmp_path / "state" / "openclaw" / "mark42"),
        "MARK42_LOG_DIR": str(tmp_path / "logs"),
        "HEARTBEAT": str(heartbeat_file),
    }

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process") as mock_check_proc,
        patch("mark42.watchdog._restart_service") as mock_restart,
        patch("mark42.watchdog.time.sleep"),
    ):
        mock_check_proc.return_value = True  # Both processes alive

        watchdog_check()

        # No restart should be called
        mock_restart.assert_not_called()


def test_watchdog_check_heartbeat_timeout(tmp_path):
    """Test watchdog_check triggers restart when heartbeat times out."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = state_dir / "daemon-heartbeat.json"
    # Old timestamp (timed out)
    heartbeat_file.write_text(json.dumps({"lastTick": "2020-01-01T00:00:00+00:00"}))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)

    env_vars = {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(heartbeat_file),
    }

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process") as mock_check_proc,
        patch("mark42.watchdog._restart_service") as mock_restart,
        patch("mark42.watchdog.time.sleep"),
    ):
        mock_check_proc.return_value = False  # Processes dead

        watchdog_check()

        # Should have called restart
        assert mock_restart.call_count >= 1


def test_watchdog_check_engine_dead(tmp_path):
    """Test watchdog_check triggers restart when engine is dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = state_dir / "daemon-heartbeat.json"
    from datetime import datetime, timezone

    recent_time = datetime.now(timezone.utc).isoformat()
    heartbeat_file.write_text(json.dumps({"lastTick": recent_time}))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)

    env_vars = {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(heartbeat_file),
    }

    def mock_check_process(pattern):
        if "engine" in pattern:
            return False  # Engine dead
        if "armor" in pattern:
            return True  # Armor alive
        return False

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process", side_effect=mock_check_process),
        patch("mark42.watchdog._restart_service") as mock_restart,
        patch("mark42.watchdog.time.sleep"),
    ):
        watchdog_check()

        # Should restart engine
        mock_restart.assert_called_once()
        assert "engine" in mock_restart.call_args[0][0]


def test_watchdog_check_armor_dead(tmp_path):
    """Test watchdog_check triggers restart when armor is dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = state_dir / "daemon-heartbeat.json"
    from datetime import datetime, timezone

    recent_time = datetime.now(timezone.utc).isoformat()
    heartbeat_file.write_text(json.dumps({"lastTick": recent_time}))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)

    env_vars = {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(heartbeat_file),
    }

    def mock_check_process(pattern):
        if "engine" in pattern:
            return True  # Engine alive
        if "armor" in pattern:
            return False  # Armor dead
        return False

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process", side_effect=mock_check_process),
        patch("mark42.watchdog._restart_service") as mock_restart,
        patch("mark42.watchdog.time.sleep"),
    ):
        watchdog_check()

        # Should restart armor
        mock_restart.assert_called_once()
        assert "armor" in mock_restart.call_args[0][0]


def test_watchdog_check_both_dead(tmp_path):
    """Test watchdog_check restarts both when both processes are dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = state_dir / "daemon-heartbeat.json"
    from datetime import datetime, timezone

    recent_time = datetime.now(timezone.utc).isoformat()
    heartbeat_file.write_text(json.dumps({"lastTick": recent_time}))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)

    env_vars = {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(heartbeat_file),
    }

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process") as mock_check_proc,
        patch("mark42.watchdog._restart_service") as mock_restart,
        patch("mark42.watchdog.time.sleep"),
    ):
        mock_check_proc.return_value = False  # Both dead

        watchdog_check()

        # Should restart both
        assert mock_restart.call_count == 2
        calls = mock_restart.call_args_list
        service_names = [call[0][0] for call in calls]
        assert any("engine" in name for name in service_names)
        assert any("armor" in name for name in service_names)


def test_watchdog_check_logs_restart(tmp_path):
    """Test watchdog_check logs restart events."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    heartbeat_file = state_dir / "daemon-heartbeat.json"
    heartbeat_file.write_text(json.dumps({"lastTick": "2020-01-01T00:00:00+00:00"}))

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)

    env_vars = {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(heartbeat_file),
    }

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)),
        patch("mark42.watchdog._check_process") as mock_check_proc,
        patch("mark42.watchdog._restart_service"),
        patch("mark42.watchdog.time.sleep"),
    ):
        mock_check_proc.return_value = False

        watchdog_check()

        # Check log file was created
        log_file = log_dir / "watchdog.log"
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "检测到异常" in log_content or "重启" in log_content


# ── 回归测试：watchdog 健康判定与退出码真实性 ─────────────


def _wd_env(tmp_path, hb_content=None):
    """构造隔离的 watchdog 环境变量。"""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    hb = state_dir / "daemon-heartbeat.json"
    if hb_content is not None:
        hb.write_text(json.dumps(hb_content))
    return {
        "XDG_STATE_HOME": str(state_dir),
        "MARK42_STATE_DIR": str(state_dir / "mark42"),
        "MARK42_LOG_DIR": str(log_dir),
        "HEARTBEAT": str(hb),
    }


def test_stale_heartbeat_with_live_pids_still_restarts(tmp_path):
    """回归测试：心跳超时但进程仍存活时必须重启，且不得谎报成功。

    历史 bug：need_restart 由心跳决定，但实际重启条件只看进程是否存在。
    两个进程都活着时一个 service 都不会重启，随后只复查 PID，
    于是记录 "✅ 重启成功" —— daemon 已卡死却被判为健康。
    """
    from mark42.watchdog import watchdog_check

    env = _wd_env(tmp_path, {"lastTick": "2020-01-01T00:00:00+00:00"})
    logged = []

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
        patch("mark42.watchdog._check_process", return_value=True),
        patch("mark42.watchdog._restart_service", return_value=True) as mock_restart,
        patch("mark42.watchdog._log", side_effect=lambda m, lf: logged.append(m)),
        patch("mark42.watchdog.time.sleep"),
    ):
        rc = watchdog_check()

    assert mock_restart.call_count >= 1, "心跳超时必须触发重启"
    assert rc != 0, "心跳未恢复必须以非零退出"
    assert not any("重启成功" in m for m in logged), "心跳仍异常时不得记录重启成功"


def test_restart_success_requires_heartbeat_recovery(tmp_path):
    """重启后心跳恢复才算成功。"""
    from mark42.watchdog import watchdog_check

    env = _wd_env(tmp_path)
    logged = []
    calls = {"n": 0}

    def hb_side_effect(path, threshold=300):
        calls["n"] += 1
        return (False, "心跳超时") if calls["n"] == 1 else (True, "")

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
        patch("mark42.watchdog._check_heartbeat", side_effect=hb_side_effect),
        patch("mark42.watchdog._check_process", return_value=True),
        patch("mark42.watchdog._restart_service", return_value=True),
        patch("mark42.watchdog._log", side_effect=lambda m, lf: logged.append(m)),
        patch("mark42.watchdog.time.sleep"),
    ):
        rc = watchdog_check()

    assert rc == 0
    assert any("重启成功" in m for m in logged)


def test_systemctl_restart_failure_returns_nonzero(tmp_path):
    """回归测试：systemctl 重启失败必须以非零退出。

    历史 bug：_restart_service() 不返回结果，watchdog_check() 恒返回 None，
    模块入口也没有 sys.exit，因此恢复失败仍被 systemd 记作成功。
    """
    from mark42.watchdog import watchdog_check

    env = _wd_env(tmp_path)

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
        patch("mark42.watchdog._check_heartbeat", return_value=(True, "")),
        patch("mark42.watchdog._check_process", return_value=False),
        patch("mark42.watchdog._restart_service", return_value=False),
        patch("mark42.watchdog.time.sleep"),
    ):
        rc = watchdog_check()

    assert rc != 0


def test_restart_service_reports_failure_status(tmp_path):
    """_restart_service 必须把 systemctl 返回码转成布尔结果。"""
    from mark42.watchdog import _restart_service

    logfile = tmp_path / "wd.log"

    ok_result = Mock(returncode=0, stdout="", stderr="")
    with patch("mark42.watchdog.subprocess.run", return_value=ok_result):
        assert _restart_service("svc", logfile) is True

    bad_result = Mock(returncode=1, stdout="", stderr="unit not found")
    with patch("mark42.watchdog.subprocess.run", return_value=bad_result):
        assert _restart_service("svc", logfile) is False


def test_all_healthy_returns_zero_and_stays_silent(tmp_path):
    """一切正常时静默且返回 0。"""
    from mark42.watchdog import watchdog_check

    env = _wd_env(tmp_path)
    logged = []

    with (
        patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env.get(k, d)),
        patch("mark42.watchdog._check_heartbeat", return_value=(True, "")),
        patch("mark42.watchdog._check_process", return_value=True),
        patch("mark42.watchdog._log", side_effect=lambda m, lf: logged.append(m)),
    ):
        rc = watchdog_check()

    assert rc == 0
    assert logged == []
