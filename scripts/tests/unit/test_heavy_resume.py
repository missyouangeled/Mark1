"""Heavy 断点续传（retry/resume）单元测试。

测试范围：
  - heavy_execute(retry=True) 能重新执行 failed 批次
  - heavy_execute(retry=True) 不影响非 failed 批次
  - heavy_resume 自动找到所有 failed/pending 并重试
  - heavy_execute_all(retry=True) 包含 failed 批次
  - 批次状态记录 retryCount / lastRetryAt
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from mark42_modules import heavy


class TestHeavyRetry:
    """heavy_execute(retry=True) 断点续传测试。"""

    def _make_task(self, tmp_path, task_name="test-retry", batches=None):
        """创建一个有 failed 批次的任务。"""
        if batches is None:
            batches = {
                "batch-001": {
                    "status": "failed",
                    "files": ["a.py"],
                    "count": 1,
                    "sizeMB": 0.01,
                    "createdAt": "2026-01-01T00:00:00",
                    "retryCount": 0,
                },
                "batch-002": {
                    "status": "pending",
                    "files": ["b.py"],
                    "count": 1,
                    "sizeMB": 0.01,
                    "createdAt": "2026-01-01T00:00:00",
                },
                "batch-003": {
                    "status": "done",
                    "files": ["c.py"],
                    "count": 1,
                    "sizeMB": 0.01,
                    "createdAt": "2026-01-01T00:00:00",
                },
            }
        task_dir = heavy.SCRATCH / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "taskName": task_name,
            "progress": "started",
            "targetPath": str(tmp_path),
            "subtasks": batches,
            "batchSize": 1,
            "totalBatches": len(batches),
            "lastUpdate": "2026-01-01T00:00:00",
        }
        (task_dir / "status.json").write_text(json.dumps(status))
        return task_dir

    def test_retry_failed_batch(self, tmp_path):
        """retry=True 能重新执行 failed 批次。"""
        self._make_task(tmp_path)
        result = heavy.heavy_execute("test-retry", "batch-001", retry=True)
        assert result is not None
        assert result.get("batchId") == "batch-001"

    def test_retry_skips_done_batch(self, tmp_path):
        """retry=True 不能重试 done 批次。"""
        self._make_task(tmp_path)
        result = heavy.heavy_execute("test-retry", "batch-003", retry=True)
        # done 不在 allowed 里
        assert result is None

    def test_retry_increments_count(self, tmp_path):
        """重试后 retryCount 应递增。"""
        self._make_task(tmp_path)
        heavy.heavy_execute("test-retry", "batch-001", retry=True)
        st = json.loads(
            (heavy.SCRATCH / "test-retry" / "status.json").read_text()
        )
        assert st["subtasks"]["batch-001"]["retryCount"] == 1
        assert "lastRetryAt" in st["subtasks"]["batch-001"]

    def test_retry_finds_next_failed(self, tmp_path):
        """不传 batch_id，retry 模式优先找 failed。"""
        self._make_task(tmp_path)
        result = heavy.heavy_execute("test-retry", retry=True)
        assert result is not None
        assert result.get("batchId") == "batch-001"

    def test_no_retry_finds_pending_only(self, tmp_path):
        """不传 retry=False 只找 pending，跳过 failed。"""
        self._make_task(tmp_path)
        result = heavy.heavy_execute("test-retry")
        assert result is not None
        assert result.get("batchId") == "batch-002"


class TestHeavyResume:
    """heavy_resume 断点续传测试。"""

    def _make_task(self, tmp_path, task_name="test-resume"):
        batches = {
            "batch-001": {
                "status": "failed",
                "files": ["a.py"],
                "count": 1,
                "sizeMB": 0.01,
                "createdAt": "2026-01-01T00:00:00",
                "retryCount": 0,
            },
            "batch-002": {
                "status": "pending",
                "files": ["b.py"],
                "count": 1,
                "sizeMB": 0.01,
                "createdAt": "2026-01-01T00:00:00",
            },
            "batch-003": {
                "status": "done",
                "files": ["c.py"],
                "count": 1,
                "sizeMB": 0.01,
                "createdAt": "2026-01-01T00:00:00",
            },
        }
        task_dir = heavy.SCRATCH / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "taskName": task_name,
            "progress": "started",
            "targetPath": str(tmp_path),
            "subtasks": batches,
            "batchSize": 1,
            "totalBatches": len(batches),
            "lastUpdate": "2026-01-01T00:00:00",
        }
        (task_dir / "status.json").write_text(json.dumps(status))
        return task_dir

    def test_resume_finds_all_retryable(self, tmp_path):
        """resume 能找到所有 failed+pending 批次。"""
        self._make_task(tmp_path)
        result = heavy.heavy_resume("test-resume")
        assert result["resumed"] == 2
        assert result["total"] == 3
        assert result["remaining"] >= 0

    def test_resume_no_retryable(self, tmp_path):
        """所有批次完成时 resume 返回 0。"""
        task_dir = heavy.SCRATCH / "test-done"
        task_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "taskName": "test-done",
            "progress": "started",
            "targetPath": str(tmp_path),
            "subtasks": {
                "batch-001": {"status": "done", "files": [], "count": 0, "sizeMB": 0},
            },
            "batchSize": 1,
            "totalBatches": 1,
            "lastUpdate": "2026-01-01T00:00:00",
        }
        (task_dir / "status.json").write_text(json.dumps(status))
        result = heavy.heavy_resume("test-done")
        assert result["resumed"] == 0

    def test_resume_nonexistent_task(self):
        """不存在的任务返回 error。"""
        result = heavy.heavy_resume("nonexistent-task")
        assert "error" in result

    def test_resume_returns_details(self, tmp_path):
        """resume 返回每个批次的详细信息。"""
        self._make_task(tmp_path)
        result = heavy.heavy_resume("test-resume")
        assert "details" in result
        assert len(result["details"]) == 2


class TestHeavyExecuteAllRetry:
    """heavy_execute_all(retry=True) 测试。"""

    def test_execute_all_includes_failed(self, tmp_path):
        """retry=True 时 execute_all 包含 failed 批次。"""
        task_dir = heavy.SCRATCH / "test-all-retry"
        task_dir.mkdir(parents=True, exist_ok=True)
        status = {
            "taskName": "test-all-retry",
            "progress": "started",
            "targetPath": str(tmp_path),
            "subtasks": {
                "batch-001": {
                    "status": "failed",
                    "files": ["a.py"],
                    "count": 1,
                    "sizeMB": 0.01,
                    "createdAt": "2026-01-01T00:00:00",
                    "retryCount": 0,
                },
                "batch-002": {
                    "status": "pending",
                    "files": ["b.py"],
                    "count": 1,
                    "sizeMB": 0.01,
                    "createdAt": "2026-01-01T00:00:00",
                },
                "batch-003": {
                    "status": "done",
                    "files": [],
                    "count": 0,
                    "sizeMB": 0,
                    "createdAt": "2026-01-01T00:00:00",
                },
            },
            "batchSize": 1,
            "totalBatches": 3,
            "lastUpdate": "2026-01-01T00:00:00",
        }
        (task_dir / "status.json").write_text(json.dumps(status))
        results = heavy.heavy_execute_all("test-all-retry", retry=True)
        assert len(results) == 2  # failed + pending, 不含 done
