"""pytest tests for mark42/watchdog.py"""

import json
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

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
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process") as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
        mock_check_proc.return_value = True  # Both processes alive
        
        watchdog_check()
        
        # No restart should be called
        mock_restart.assert_not_called()


def test_watchdog_check_heartbeat_timeout(tmp_path):
    """Test watchdog_check triggers restart when heartbeat times out."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process") as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
        mock_check_proc.return_value = False  # Processes dead
        
        watchdog_check()
        
        # Should have called restart
        assert mock_restart.call_count >= 1


def test_watchdog_check_engine_dead(tmp_path):
    """Test watchdog_check triggers restart when engine is dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process", side_effect=mock_check_process) as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
        watchdog_check()
        
        # Should restart engine
        mock_restart.assert_called_once()
        assert "engine" in mock_restart.call_args[0][0]


def test_watchdog_check_armor_dead(tmp_path):
    """Test watchdog_check triggers restart when armor is dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process", side_effect=mock_check_process) as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
        watchdog_check()
        
        # Should restart armor
        mock_restart.assert_called_once()
        assert "armor" in mock_restart.call_args[0][0]


def test_watchdog_check_both_dead(tmp_path):
    """Test watchdog_check restarts both when both processes are dead."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process") as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
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
    state_dir.mkdir(parents=True)
    
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
    
    with patch("mark42.watchdog.os.environ.get", side_effect=lambda k, d="": env_vars.get(k, d)), \
         patch("mark42.watchdog._check_process") as mock_check_proc, \
         patch("mark42.watchdog._restart_service") as mock_restart, \
         patch("mark42.watchdog.time.sleep"):
        
        mock_check_proc.return_value = False
        
        watchdog_check()
        
        # Check log file was created
        log_file = log_dir / "watchdog.log"
        assert log_file.exists()
        log_content = log_file.read_text()
        assert "检测到异常" in log_content or "重启" in log_content
