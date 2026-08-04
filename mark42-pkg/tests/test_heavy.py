"""pytest tests for mark42/heavy.py"""

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from mark42.heavy import (
    heavy_cleanup,
    heavy_detect,
    heavy_detect_human,
    heavy_execute,
    heavy_finish,
    heavy_preflight,
    heavy_start,
)


@pytest.fixture(autouse=True)
def _set_caplog_level(caplog):
    """caplog 默认只捕获 WARNING+，设为 INFO 以匹配 heavy.py 的 logger.info 输出。"""
    caplog.set_level(logging.INFO, logger="mark42.heavy")

# ── heavy_preflight tests ──


def test_heavy_preflight_nonexistent_path(caplog):
    """Test heavy_preflight with non-existent path."""
    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        heavy_preflight("/nonexistent/path/that/does/not/exist")
        assert any("路径不存在" in record.message for record in caplog.records)


def test_heavy_preflight_with_valid_path(tmp_path, capsys):
    """Test heavy_preflight with valid path."""
    # Create some test files
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    with patch("mark42.heavy.armor_check") as mock_check, patch("mark42.heavy.os.popen") as mock_popen:
        mock_check.return_value = {"usagePercent": 50}

        mock_mem = Mock()
        mock_mem.read.return_value.strip.return_value = "16GB"

        mock_df = Mock()
        mock_df.read.return_value.strip.return_value = "100G/500G"

        # os.popen 被调用 3 次: free, df /, df /mnt/data
        mock_popen.side_effect = [mock_mem, mock_df, mock_df]

        heavy_preflight(str(tmp_path))

        output = capsys.readouterr().out
        assert (
            "文件数" in output
            or "总大小" in output
            or "上下文余量" in output
        )


# ── heavy_detect tests ──


def test_heavy_detect_nonexistent_path():
    """Test heavy_detect with non-existent path."""
    result = heavy_detect("/nonexistent/path")
    assert result["exists"] is False
    assert result["isHeavy"] is False
    assert "路径不存在" in result["advice"]


def test_heavy_detect_small_project(tmp_path):
    """Test heavy_detect with a small project (not heavy)."""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        result = heavy_detect(str(tmp_path))
        assert result["exists"] is True
        assert result["isHeavy"] is False
        assert "metrics" in result
        assert result["metrics"]["files"] == 1


def test_heavy_detect_many_files(tmp_path):
    """Test heavy_detect with many files (>=50 = heavy)."""
    for i in range(60):
        test_file = tmp_path / f"test_{i}.py"
        test_file.write_text(f"print('test {i}')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        result = heavy_detect(str(tmp_path))
        assert result["exists"] is True
        assert result["isHeavy"] is True
        assert "文件数" in str(result["reasons"])


def test_heavy_detect_high_context_usage(tmp_path):
    """Test heavy_detect with high context usage (>70% = heavy)."""
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 80}  # > 70%
        result = heavy_detect(str(tmp_path))
        assert result["exists"] is True
        assert result["isHeavy"] is True
        assert any("上下文已用" in r for r in result["reasons"])


def test_heavy_detect_deep_directory(tmp_path):
    """Test heavy_detect with deep directory structure (>=5 = heavy)."""
    deep_dir = tmp_path / "l1" / "l2" / "l3" / "l4" / "l5"
    deep_dir.mkdir(parents=True)
    test_file = deep_dir / "test.py"
    test_file.write_text("print('deep')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        result = heavy_detect(str(tmp_path))
        assert result["exists"] is True
        assert result["isHeavy"] is True
        assert any("目录深度" in r for r in result["reasons"])


# ── heavy_start tests ──


def test_heavy_start_nonexistent_path(tmp_path, monkeypatch, caplog):
    """Test heavy_start with non-existent path."""
    # Monkey patch state paths
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        heavy_start("/nonexistent/path", "test-task")
        assert any("路径不存在" in record.message for record in caplog.records)


def test_heavy_start_creates_state_files(tmp_path, monkeypatch):
    """Test heavy_start creates status.json and heavy state file."""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    test_project = tmp_path / "project"
    test_project.mkdir()
    for i in range(10):
        (test_project / f"file_{i}.py").write_text(f"content {i}")

    with patch("mark42.heavy.armor_check") as mock_check, patch("mark42.heavy._append_broker"):
        mock_check.return_value = {"usagePercent": 50}
        heavy_start(str(test_project), "test-task")

        # Check task dir created
        task_dir = fake_scratch / "test-task"
        assert task_dir.exists()

        # Check status.json
        status_file = task_dir / "status.json"
        assert status_file.exists()
        status = json.loads(status_file.read_text())
        assert status["taskName"] == "test-task"
        assert status["progress"] == "started"

        # Check heavy state file
        heavy_state_file = fake_heavy / "test-task.json"
        assert heavy_state_file.exists()
        heavy_state = json.loads(heavy_state_file.read_text())
        assert heavy_state["taskName"] == "test-task"
        assert heavy_state["status"] == "started"


# ── heavy_finish tests ──


def test_heavy_finish_nonexistent_task(tmp_path, monkeypatch, caplog):
    """Test heavy_finish with non-existent task."""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    heavy_finish("nonexistent-task")
    assert any("不存在" in record.message for record in caplog.records)


def test_heavy_finish_successful(tmp_path, monkeypatch):
    """Test heavy_finish successfully marks task as finished."""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    # Setup task state
    task_dir = fake_scratch / "test-task"
    task_dir.mkdir()

    # Create status.json with all subtasks done
    status = {
        "taskName": "test-task",
        "progress": "started",
        "subtasks": {
            "batch-001": {"status": "done"},
            "batch-002": {"status": "done"},
        },
    }
    (task_dir / "status.json").write_text(json.dumps(status))

    # Create heavy state file
    heavy_state = {
        "taskName": "test-task",
        "status": "started",
    }
    (fake_heavy / "test-task.json").write_text(json.dumps(heavy_state))

    with patch("mark42.heavy._append_broker"):
        heavy_finish("test-task")

        # Verify heavy state updated
        heavy_state = json.loads((fake_heavy / "test-task.json").read_text())
        assert heavy_state["status"] == "finished"
        assert "finishedAt" in heavy_state

        # Verify task status updated
        task_status = json.loads((task_dir / "status.json").read_text())
        assert task_status["progress"] == "finished"


# ── heavy_execute tests ──


def test_heavy_execute_nonexistent_task(tmp_path, monkeypatch, caplog):
    """Test heavy_execute with non-existent task."""
    fake_scratch = tmp_path / "scratch"
    fake_scratch.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)

    result = heavy_execute("nonexistent-task")
    assert any("未开工" in record.message for record in caplog.records)
    assert result is None


def test_heavy_execute_creates_script(tmp_path, monkeypatch):
    """Test heavy_execute creates execution script (dry run mode)."""
    fake_scratch = tmp_path / "scratch"
    fake_scratch.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)

    # Setup task state
    task_dir = fake_scratch / "test-task"
    task_dir.mkdir()

    # Create status.json with pending batch
    status = {
        "taskName": "test-task",
        "targetPath": str(tmp_path / "project"),
        "subtasks": {
            "batch-001": {"status": "pending", "files": ["file1.py", "file2.py"], "count": 2, "sizeMB": 0.01},
            "batch-002": {"status": "pending", "files": ["file3.py"], "count": 1, "sizeMB": 0.005},
        },
    }
    (task_dir / "status.json").write_text(json.dumps(status))

    with patch("mark42.heavy._append_broker"):
        result = heavy_execute("test-task")

        # Verify result
        assert result is not None
        assert result["queued"] is True
        assert result["dryRun"] is True

        # Verify script created
        script_path = Path(result["script"])
        assert script_path.exists()
        script_content = script_path.read_text()
        assert "#!/bin/bash" in script_content
        assert "processing" in script_content

        # Verify queue file created
        queue_file = task_dir / "execute-queue.jsonl"
        assert queue_file.exists()


def test_heavy_execute_with_command(tmp_path, monkeypatch):
    """Test heavy_execute with custom command."""
    fake_scratch = tmp_path / "scratch"
    fake_scratch.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)

    task_dir = fake_scratch / "test-task"
    task_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    status = {
        "taskName": "test-task",
        "targetPath": str(project_dir),
        "subtasks": {
            "batch-001": {"status": "pending", "files": ["file1.py"], "count": 1, "sizeMB": 0.01},
        },
    }
    (task_dir / "status.json").write_text(json.dumps(status))

    with patch("mark42.heavy._append_broker"):
        result = heavy_execute("test-task", command="cat {f}")

        script_content = Path(result["script"]).read_text()
        assert "cat " in script_content or "cat" in script_content


# ── heavy_cleanup tests ──


def test_heavy_cleanup_nonexistent_task(tmp_path, monkeypatch, caplog):
    """Test heavy_cleanup with non-existent task."""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    heavy_cleanup("nonexistent-task")
    assert any("不存在" in record.message for record in caplog.records)


def test_heavy_cleanup_removes_files(tmp_path, monkeypatch):
    """Test heavy_cleanup removes scratch dir and state file."""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir()
    fake_heavy.mkdir()

    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    # Create task files
    task_dir = fake_scratch / "test-task"
    task_dir.mkdir()
    (task_dir / "status.json").write_text("{}")
    (fake_heavy / "test-task.json").write_text("{}")

    heavy_cleanup("test-task")

    # Verify both removed
    assert not task_dir.exists()
    assert not (fake_heavy / "test-task.json").exists()


# ── heavy_detect_human tests ──


def test_heavy_detect_human_nonexistent(tmp_path, caplog):
    """Test heavy_detect_human with non-existent path."""
    heavy_detect_human("/nonexistent/path")
    assert any("路径不存在" in record.message for record in caplog.records)


def test_heavy_detect_human_small_project(tmp_path, capsys):
    """Test heavy_detect_human with small project (not heavy)."""
    (tmp_path / "test.py").write_text("print('hi')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        heavy_detect_human(str(tmp_path))
        output = capsys.readouterr().out
        assert "未達大工程标准" in output or "未达大工程标准" in output


# ── 回归测试：Heavy 状态机真实性 ──────────────────────────


def _setup_heavy_env(tmp_path, monkeypatch):
    """构造隔离的 heavy 环境，返回 (scratch, heavy_state, work_dir)。"""
    fake_scratch = tmp_path / "scratch"
    fake_heavy = tmp_path / "heavy"
    fake_scratch.mkdir(parents=True, exist_ok=True)
    fake_heavy.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mark42.heavy.SCRATCH", fake_scratch)
    monkeypatch.setattr("mark42.heavy.HEAVY_STATE", fake_heavy)

    work = tmp_path / "work"
    work.mkdir()
    for i in range(2):
        (work / f"f{i}.txt").write_text("x\n")
    return fake_scratch, fake_heavy, work


def _batch_statuses(scratch, task_name):
    st = json.loads((scratch / task_name / "status.json").read_text())
    return {k: v.get("status") for k, v in st["subtasks"].items()}


def test_dry_run_never_marks_batch_running(tmp_path, monkeypatch):
    """回归测试：dry-run 只入队未执行，不得把批次写成 running。

    历史 bug：execute_now=False 时仍先写 running，
    而 heavy_finish() 忽略 running，导致从未执行的任务被归档为 finished。
    """
    from mark42.heavy import heavy_execute, heavy_start

    scratch, _, work = _setup_heavy_env(tmp_path, monkeypatch)
    heavy_start(str(work), "t1")

    result = heavy_execute("t1")

    assert result["dryRun"] is True
    assert result["action"] == "queued"
    assert result["startedPid"] is None

    statuses = _batch_statuses(scratch, "t1")
    assert "running" not in statuses.values()
    assert "queued" in statuses.values()


def test_finish_rejects_unexecuted_dry_run_batches(tmp_path, monkeypatch, capsys):
    """回归测试：finish 必须拒绝仅入队(未真跑)的批次。"""
    from mark42.heavy import heavy_execute, heavy_finish, heavy_start

    _, fake_heavy, work = _setup_heavy_env(tmp_path, monkeypatch)
    heavy_start(str(work), "t1")
    heavy_execute("t1")

    heavy_finish("t1")
    captured = capsys.readouterr()

    assert "不建议收工" in captured.out
    heavy_status = json.loads((fake_heavy / "t1.json").read_text())
    assert heavy_status.get("status") != "finished"


def test_start_failure_persists_failed_not_running(tmp_path, monkeypatch):
    """回归测试：后台进程启动失败必须持久化为 failed。

    历史 bug：Popen 异常只改返回 dict 的 action，
    磁盘状态仍是 running；heavy_resume 只重试 failed/pending，
    heavy_finish 又忽略 running，该批次永远无法恢复。
    """
    import subprocess

    from mark42.heavy import heavy_execute, heavy_start

    scratch, _, work = _setup_heavy_env(tmp_path, monkeypatch)
    heavy_start(str(work), "t1")

    def boom(*args, **kwargs):
        raise OSError("cannot start")

    monkeypatch.setattr(subprocess, "Popen", boom)
    result = heavy_execute("t1", execute_now=True)

    assert result["action"] == "start_failed"
    statuses = _batch_statuses(scratch, "t1")
    assert "failed" in statuses.values()
    assert "running" not in statuses.values()


def test_resume_can_retry_failed_start(tmp_path, monkeypatch):
    """启动失败的批次必须能被 resume 重新处理。"""
    import subprocess

    from mark42.heavy import heavy_execute, heavy_resume, heavy_start

    _, _, work = _setup_heavy_env(tmp_path, monkeypatch)
    heavy_start(str(work), "t1")

    real_popen = subprocess.Popen

    def boom(*args, **kwargs):
        raise OSError("nope")

    # 只临时探针 Popen，不能用 monkeypatch.undo()（会连 SCRATCH 一起撤销）
    subprocess.Popen = boom
    try:
        heavy_execute("t1", execute_now=True)
    finally:
        subprocess.Popen = real_popen

    summary = heavy_resume("t1")
    assert summary["resumed"] >= 1
    assert "error" not in summary
