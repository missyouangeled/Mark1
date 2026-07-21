"""pytest tests for mark42/heavy.py"""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from mark42.heavy import (
    heavy_cleanup,
    heavy_detect,
    heavy_detect_human,
    heavy_execute,
    heavy_finish,
    heavy_preflight,
    heavy_start,
)

# ── heavy_preflight tests ──


def test_heavy_preflight_nonexistent_path(caplog):
    """Test heavy_preflight with non-existent path."""
    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        heavy_preflight("/nonexistent/path/that/does/not/exist")
        assert any("路径不存在" in record.message for record in caplog.records)


def test_heavy_preflight_with_valid_path(tmp_path, caplog):
    """Test heavy_preflight with valid path."""
    # Create some test files
    test_file = tmp_path / "test.py"
    test_file.write_text("print('hello')")

    with patch("mark42.heavy.armor_check") as mock_check, \
         patch("mark42.heavy.os.popen") as mock_popen:
        mock_check.return_value = {"usagePercent": 50}

        mock_mem = Mock()
        mock_mem.read.return_value.strip.return_value = "16GB"

        mock_df = Mock()
        mock_df.read.return_value.strip.return_value = "100G/500G"

        mock_popen.return_value = mock_mem
        mock_popen.side_effect = [mock_mem, mock_df]

        heavy_preflight(str(tmp_path))

        messages = [record.message for record in caplog.records]
        assert any("文件数" in msg for msg in messages) or any("总大小" in msg for msg in messages) or any("上下文余量" in msg for msg in messages)


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

    with patch("mark42.heavy.armor_check") as mock_check, \
         patch("mark42.heavy._append_broker"):
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
        }
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
        }
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
        }
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


def test_heavy_detect_human_small_project(tmp_path, caplog):
    """Test heavy_detect_human with small project (not heavy)."""
    (tmp_path / "test.py").write_text("print('hi')")

    with patch("mark42.heavy.armor_check") as mock_check:
        mock_check.return_value = {"usagePercent": 50}
        heavy_detect_human(str(tmp_path))
        messages = [record.message for record in caplog.records]
        assert any("未達大工程标准" in msg for msg in messages) or any("未达大工程标准" in msg for msg in messages)
