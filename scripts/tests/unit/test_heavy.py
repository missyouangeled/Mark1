"""heavy.py 测试群。

覆盖范围：
  - heavy_preflight  预检（mock os.popen）
  - heavy_detect     纯函数检测（4 个判定标准）
  - heavy_detect_human  3 种 auto_mode（ask / semi / full）
  - heavy_start      开工（创建 SCRATCH + 写 status.json + heavy.json）
  - heavy_finish     收工（全部 done 才归档，否则拒绝）
  - heavy_execute    执行单批次（生成脚本 + 队列）
  - heavy_cleanup    清理

设计要点：
  - SCRATCH 已由 conftest monkeypatch 到 tmp_path 下
  - mock os.popen 而非 subprocess.run（heavy_preflight 用 os.popen）
  - mock armor_check / armor_compress 避免真依赖
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import heavy
# SCRATCH 从 conftest scratch_dir fixture 获取


# ─────────────────────── heavy_detect ───────────────────────

class TestHeavyDetect:
    """heavy_detect 纯函数测试群。"""

    def test_nonexistent_path(self, tmp_path):
        """路径不存在时返回 exists=False。"""
        nonexistent = tmp_path / "nonexistent"
        result = heavy.heavy_detect(str(nonexistent))
        assert result["exists"] is False
        assert result["isHeavy"] is False
        assert result["advice"] == "路径不存在"
        assert str(nonexistent) == result["path"]

    def test_small_project_not_heavy(self, tmp_path, mocker):
        """10 文件 5MB 不算大工程。"""
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_text("x" * 500_000)  # 500KB each → ~5MB
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        result = heavy.heavy_detect(str(tmp_path))
        assert result["exists"] is True
        assert result["isHeavy"] is False
        assert result["reasons"] == []
        assert result["metrics"]["files"] == 10
        assert result["metrics"]["sizeMB"] < 50  # 实际 5MB

    def test_many_files_triggers_heavy(self, tmp_path, mocker):
        """60 个文件触发大工程（>= 50）。"""
        for i in range(60):
            (tmp_path / f"f{i}.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        result = heavy.heavy_detect(str(tmp_path))
        assert result["isHeavy"] is True
        assert any("文件数" in r for r in result["reasons"])

    def test_large_size_triggers_heavy(self, tmp_path, mocker):
        """总大小 >= 50MB 触发。"""
        # 1 个 60MB 文件
        (tmp_path / "big.bin").write_text("x" * (60 * 1024 * 1024))
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        result = heavy.heavy_detect(str(tmp_path))
        assert result["isHeavy"] is True
        assert any("总大小" in r for r in result["reasons"])

    def test_deep_nesting_triggers_heavy(self, tmp_path, mocker):
        """目录深度 >= 5 触发。"""
        deep = tmp_path / "a" / "b" / "c" / "d" / "e" / "f"
        deep.mkdir(parents=True)
        deep.joinpath("file.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        result = heavy.heavy_detect(str(tmp_path))
        assert result["metrics"]["maxDepth"] >= 5
        assert result["isHeavy"] is True

    def test_high_context_triggers_heavy(self, tmp_path, mocker):
        """上下文 > 70% 触发。"""
        (tmp_path / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 85.0})
        result = heavy.heavy_detect(str(tmp_path))
        assert result["isHeavy"] is True
        assert any("上下文" in r for r in result["reasons"])


# ─────────────────────── heavy_detect_human ───────────────────────

class TestHeavyDetectHuman:
    """heavy_detect_human 输出格式测试群。"""

    def test_nonexistent_path_message(self, tmp_path, capsys):
        """路径不存在时输出友好错误。"""
        heavy.heavy_detect_human(str(tmp_path / "nonexistent"), auto_mode="ask")
        out = capsys.readouterr().out
        assert "❌ 路径不存在" in out

    def test_small_project_shows_ok(self, tmp_path, mocker, capsys):
        """小工程输出 ✅。"""
        (tmp_path / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        heavy.heavy_detect_human(str(tmp_path), auto_mode="ask")
        out = capsys.readouterr().out
        assert "✅" in out
        assert "未達大工程标准" in out or "未达大工程标准" in out

    def test_full_mode_auto_starts(self, tmp_path, mocker):
        """auto_mode=full 直接调 heavy_start。"""
        # 准备大工程目录
        for i in range(60):
            (tmp_path / f"f{i}.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        # mock heavy_start 看是否被调
        mock_start = mocker.patch.object(heavy, "heavy_start")

        heavy.heavy_detect_human(str(tmp_path), auto_mode="full")

        mock_start.assert_called_once()
        args = mock_start.call_args
        assert args[0][0] == str(tmp_path)  # path_str
        # task_name 由 _auto_task_name 生成
        assert "task_name" in args.kwargs or len(args[0]) >= 2

    def test_semi_mode_timeout_auto_starts(self, tmp_path, mocker):
        """semi 模式：mock select 让 rlist 一直空 → 30s 倒计时后自动开工。

        设计：为了避免测试跑 30s，mock time.sleep 立即返回，
        同时 mock select 让 rlist 总是空（不阻塞 stdin）。
        """
        for i in range(60):
            (tmp_path / f"f{i}.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        # mock time.sleep 立即返回
        mocker.patch("time.sleep")
        # mock select 让 rlist 总是空（无人输入）
        mocker.patch.object(heavy.select, "select", return_value=([], [], []))
        # mock heavy_start 看是否被调
        mock_start = mocker.patch.object(heavy, "heavy_start")

        heavy.heavy_detect_human(str(tmp_path), auto_mode="semi")

        # 倒计时结束后应自动调 heavy_start
        mock_start.assert_called_once()


# ─────────────────────── heavy_start ───────────────────────

class TestHeavyStart:
    """heavy_start() 测试群。"""

    def test_creates_scratch_dir(self, tmp_path, mocker, scratch_dir):
        """应在 SCRATCH/task_name 创建目录。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        mocker.patch.object(heavy, "armor_compress")

        task_name = "my-test-task"
        heavy.heavy_start(str(project), task_name, context_aware=True)

        scratch_task_dir = scratch_dir / task_name
        assert scratch_task_dir.exists()
        assert (scratch_task_dir / ".keep").exists()

    def test_writes_status_json_with_batches(self, tmp_path, mocker, scratch_dir):
        """应写 status.json 包含 subtasks/batches。"""
        project = tmp_path / "project"
        project.mkdir()
        # 创建 10 个文件
        for i in range(10):
            (project / f"f{i}.txt").write_text("x" * 1000)
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        mocker.patch.object(heavy, "armor_compress")

        heavy.heavy_start(str(project), "test-task")

        status_file = scratch_dir / "test-task" / "status.json"
        assert status_file.exists()
        status = json.loads(status_file.read_text())
        assert status["taskName"] == "test-task"
        assert status["progress"] == "started"
        assert "subtasks" in status
        assert len(status["subtasks"]) >= 1  # 至少一个 batch
        assert status["totalBatches"] == len(status["subtasks"])

    def test_writes_heavy_state_json(self, tmp_path, mocker, heavy_state):
        """应在 HEAVY_STATE/ 写 task 状态。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})
        mocker.patch.object(heavy, "armor_compress")

        heavy.heavy_start(str(project), "task-state")

        heavy_state_file = heavy_state / "task-state.json"
        assert heavy_state_file.exists()
        hs = json.loads(heavy_state_file.read_text())
        assert hs["status"] == "started"
        assert hs["taskName"] == "task-state"
        assert hs["contextAware"] is True
        assert "startedAt" in hs

    def test_context_aware_triggers_compress_on_alert(self, tmp_path, mocker):
        """context_aware=True 且 usage >= ALERT 时自动触发 compress。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 90.0})  # ALERT 区间
        mock_compress = mocker.patch.object(heavy, "armor_compress")

        heavy.heavy_start(str(project), "ctx-aware", context_aware=True)

        mock_compress.assert_called_once()

    def test_context_aware_no_compress_on_normal(self, tmp_path, mocker):
        """context_aware=True 但 usage < ALERT 时不触发 compress。"""
        project = tmp_path / "project"
        project.mkdir()
        (project / "f1.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 30.0})  # < ALERT
        mock_compress = mocker.patch.object(heavy, "armor_compress")

        heavy.heavy_start(str(project), "ctx-normal", context_aware=True)

        mock_compress.assert_not_called()

    def test_nonexistent_path_no_op(self, tmp_path, capsys):
        """路径不存在时输出错误并 return（不抛异常）。"""
        heavy.heavy_start(str(tmp_path / "nonexistent"), "task")
        out = capsys.readouterr().out
        assert "❌ 路径不存在" in out


# ─────────────────────── heavy_finish ───────────────────────

class TestHeavyBatchSize:
    """P 修复: batch_size 下限 3 改 1 (单文件友好)。"""

    def test_single_file_yields_single_batch(self, tmp_path, scratch_dir, mocker):
        """【P】1 个文件 + 100% 余量 → batch_size=1, num_batches=1 (原 3, 1 切 1 批但 batch_size 3 不准确)。"""
        # 1 个文件
        for i in range(1):
            (tmp_path / f"f{i}.txt").write_text("x")
        # mock armor_check 返 0% 使用率 (剩 100% 余量)
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 0.0})
        class FakeFile:
            def read(self):
                return "10G"
        mocker.patch("os.popen", return_value=FakeFile())

        # 调 heavy_start, 不传 task_name 但 mock
        task_name = "p-single-file"
        heavy.heavy_start(str(tmp_path), task_name=task_name, context_aware=True)

        # 读 status.json, 验 num_batches
        status = json.loads((scratch_dir / task_name / "status.json").read_text())
        # num_batches 应 = 1 (单文件)
        assert status["totalBatches"] == 1, (
            f"P 修复: 1 文件应=1 批, 实际 {status['totalBatches']} 批"
        )
        # batch_size 应 = 1 (下限改了)
        assert status["batchSize"] == 1, (
            f"P 修复: 1 文件 batch_size 应=1 (下限改了), 实际 {status['batchSize']}"
        )

    def test_batch_size_lower_bound_is_one(self, tmp_path, scratch_dir, mocker):
        """【P】batch_size 公式计算 < 1 时, 应保 1 不保 3。"""
        # 0 个文件是边界, 制造 1 个测试
        for i in range(1):
            (tmp_path / f"f{i}.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 99.0})  # 几乎 0% 余量
        class FakeFile:
            def read(self):
                return "1G"
        mocker.patch("os.popen", return_value=FakeFile())

        task_name = "p-low-remaining"
        heavy.heavy_start(str(tmp_path), task_name=task_name, context_aware=True)

        status = json.loads((scratch_dir / task_name / "status.json").read_text())
        # 原 max(3, ...) 至少 3, 改后 max(1, ...) 至少 1
        assert status["batchSize"] >= 1
        # 严重上下文紧时 (1%) 1 文件 → batch_size 应=1 (而不是 3)
        # 1 * 0.01 / 200 = 0, max(1, 0) = 1
        assert status["batchSize"] == 1, (
            f"P 修复: 紧上下文 1 文件应 batch_size=1, 实际 {status['batchSize']}"
        )


class TestHeavyFinish:
    """heavy_finish() 测试群。"""

    def test_nonexistent_task(self, capsys):
        """任务不存在时输出错误。"""
        heavy.heavy_finish("nonexistent-task")
        out = capsys.readouterr().out
        assert "❌ 任务" in out and "不存在" in out

    def test_all_done_archives(self, tmp_path, mocker, heavy_state, scratch_dir):
        """所有 subtask 都 done 时归档。"""
        task_name = "task-finish-ok"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "subtasks": {
                "batch-001": {"status": "done"},
                "batch-002": {"status": "done"},
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))
        (heavy_state / f"{task_name}.json").write_text(json.dumps({
            "taskName": task_name, "status": "started",
        }))

        heavy.heavy_finish(task_name)

        hs = json.loads((heavy_state / f"{task_name}.json").read_text())
        assert hs["status"] == "finished"
        assert "finishedAt" in hs

    def test_failures_blocks_finish(self, tmp_path, capsys, scratch_dir):
        """有失败子任务时拒绝收工。"""
        task_name = "task-with-failures"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "subtasks": {
                "batch-001": {"status": "done"},
                "batch-002": {"status": "failed"},
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))

        heavy.heavy_finish(task_name)
        out = capsys.readouterr().out
        assert "不建议收工" in out or "失败" in out


# ─────────────────────── heavy_execute ───────────────────────

class TestHeavyExecute:
    """heavy_execute() 测试群。"""

    def test_first_pending_batch_executes(self, tmp_path, mocker, scratch_dir):
        """不传 batch_id 时执行第一个 pending batch。"""
        task_name = "exec-test"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["f1.txt", "f2.txt"],
                    "count": 2,
                    "sizeMB": 0.5,
                },
                "batch-002": {"status": "pending", "files": [], "count": 0, "sizeMB": 0},
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))
        (tmp_path / "project").mkdir()

        heavy.heavy_execute(task_name)

        # 状态文件中 batch-001 应变成 running
        updated = json.loads((scratch_dir / "status.json").read_text())
        assert updated["subtasks"]["batch-001"]["status"] == "running"
        assert "startedAt" in updated["subtasks"]["batch-001"]

    def test_specific_batch_id(self, tmp_path, scratch_dir):
        """传 batch_id 时执行指定 batch。"""
        task_name = "exec-specific"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {"status": "done", "files": []},
                "batch-002": {
                    "status": "pending",
                    "files": ["target.txt"],
                    "count": 1,
                    "sizeMB": 0.1,
                },
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))
        (tmp_path / "project").mkdir()

        heavy.heavy_execute(task_name, batch_id="batch-002")

        updated = json.loads((scratch_dir / "status.json").read_text())
        assert updated["subtasks"]["batch-002"]["status"] == "running"
        assert updated["subtasks"]["batch-001"]["status"] == "done"  # 未变

    def test_generates_exec_script_and_queue(self, tmp_path, scratch_dir):
        """应生成执行脚本和队列文件。"""
        task_name = "exec-script"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["f1.txt"],
                    "count": 1,
                    "sizeMB": 0.01,
                },
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))
        (tmp_path / "project").mkdir()

        heavy.heavy_execute(task_name)

        # 执行脚本应存在且可执行
        script = scratch_dir / "batch-001-exec.sh"
        assert script.exists()
        assert script.stat().st_mode & 0o100  # owner execute

        # 队列文件应包含 entry
        queue = scratch_dir / "execute-queue.jsonl"
        assert queue.exists()
        entry = json.loads(queue.read_text().strip().split("\n")[-1])
        assert entry["taskName"] == task_name
        assert entry["batchId"] == "batch-001"

    def test_no_pending_message(self, tmp_path, capsys, scratch_dir):
        """无 pending 时输出无 pending 子任务。"""
        task_name = "exec-noop"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        status = {
            "taskName": task_name,
            "subtasks": {
                "batch-001": {"status": "done"},
            },
        }
        (scratch_dir / "status.json").write_text(json.dumps(status))

        heavy.heavy_execute(task_name)
        out = capsys.readouterr().out
        assert "无 pending" in out

    # ── 2026-06-30 安全加强：默认 dry-run + 显式 execute_now 才真跑 ──

    def test_default_dry_run_does_not_start_process(self, tmp_path, scratch_dir, mocker):
        """默认不传 execute_now → 不启动任何 subprocess，但生成脚本 + 入队。"""
        task_name = "exec-default-dry"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["f1.txt"],
                    "count": 1,
                    "sizeMB": 0.01,
                },
            },
        }))
        (tmp_path / "project").mkdir()

        mock_popen = mocker.patch("subprocess.Popen")
        result = heavy.heavy_execute(task_name)

        mock_popen.assert_not_called()
        assert result["dryRun"] is True
        assert result["action"] == "queued"
        assert result["startedPid"] is None
        assert (task_scratch / "batch-001-exec.sh").exists()
        assert (task_scratch / "execute-queue.jsonl").exists()

    def test_execute_now_starts_subprocess(self, tmp_path, scratch_dir, mocker):
        """传 execute_now=True → 启动后台 bash 进程，PID 记录到 status.json。"""
        task_name = "exec-real"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["a.txt", "b.txt"],
                    "count": 2,
                    "sizeMB": 0.02,
                },
            },
        }))
        (tmp_path / "project").mkdir()

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen = mocker.patch("subprocess.Popen", return_value=mock_proc)
        result = heavy.heavy_execute(task_name, execute_now=True)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args[0] == "/bin/bash"
        assert result["dryRun"] is False
        assert result["action"] == "started"
        assert result["startedPid"] == 99999
        updated = json.loads((task_scratch / "status.json").read_text())
        assert updated["subtasks"]["batch-001"]["pid"] == 99999
        assert updated["subtasks"]["batch-001"]["dryRun"] is False
        assert "logPath" in updated["subtasks"]["batch-001"]

    def test_no_command_means_noop_script(self, tmp_path, scratch_dir):
        """不传 --command 时脚本仅 echo，不真做任何文件修改。"""
        task_name = "exec-noop-script"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["a.txt", "b.txt"],
                    "count": 2,
                    "sizeMB": 0.01,
                },
            },
        }))
        (tmp_path / "project").mkdir()

        heavy.heavy_execute(task_name)
        script_content = (task_scratch / "batch-001-exec.sh").read_text()
        assert "no-op" in script_content
        assert "a.txt" in script_content
        assert "b.txt" in script_content
        for dangerous in ["rm ", "mv ", "sed ", "dd ", ">>", "writelines(", "open("]:
            assert dangerous not in script_content, f"脚本不应含 {dangerous}"

    def test_execute_now_with_command_runs_real_command(self, tmp_path, scratch_dir, mocker):
        """传 execute_now=True + --command 才会真跑 user-provided 命令。"""
        task_name = "exec-real-cmd"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["x.txt"],
                    "count": 1,
                    "sizeMB": 0.01,
                },
            },
        }))
        (tmp_path / "project").mkdir()
        (tmp_path / "project" / "x.txt").write_text("original")

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mocker.patch("subprocess.Popen", return_value=mock_proc)
        result = heavy.heavy_execute(
            task_name,
            command="cat {f} > {f}.bak",
            execute_now=True,
        )
        assert result["action"] == "started"
        assert result["startedPid"] == 12345
        script = (task_scratch / "batch-001-exec.sh").read_text()
        assert "x.txt" in script

    def test_execute_now_subprocess_failure_handled(self, tmp_path, scratch_dir, mocker, capsys):
        """subprocess.Popen 报 OSError → 返回 start_failed, 不哭。"""
        task_name = "exec-fail"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {
                    "status": "pending",
                    "files": ["x.txt"],
                    "count": 1,
                    "sizeMB": 0.01,
                },
            },
        }))
        (tmp_path / "project").mkdir()

        mocker.patch("subprocess.Popen", side_effect=OSError("bash not found"))
        result = heavy.heavy_execute(task_name, execute_now=True)
        out = capsys.readouterr().out
        assert result["action"] == "start_failed"
        assert "bash not found" in result["error"]
        assert "❌" in out

    def test_execute_all_default_dry_run(self, tmp_path, scratch_dir, mocker):
        """heavy_execute_all 默认 dry-run，不启任何进程。"""
        task_name = "exec-all-dry"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        (task_scratch / "status.json").write_text(json.dumps({
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {"status": "pending", "files": ["a.txt"], "count": 1, "sizeMB": 0.01},
                "batch-002": {"status": "pending", "files": ["b.txt"], "count": 1, "sizeMB": 0.01},
            },
        }))
        (tmp_path / "project").mkdir()

        mock_popen = mocker.patch("subprocess.Popen")
        results = heavy.heavy_execute_all(task_name)
        mock_popen.assert_not_called()
        assert len(results) == 2
        for r in results:
            assert r["dryRun"] is True
            assert r["action"] == "queued"


# ─────────────────────── heavy_cleanup ───────────────────────

class TestHeavyCleanup:
    """heavy_cleanup() 测试群。"""

    def test_removes_scratch_dir(self, tmp_path, scratch_dir):
        """应删除 SCRATCH/task_name 目录。"""
        task_name = "cleanup-me"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        (scratch_dir / "junk.txt").write_text("x")
        assert scratch_dir.exists()

        heavy.heavy_cleanup(task_name)

        assert not scratch_dir.exists()

    def test_removes_heavy_state_json(self, tmp_path, heavy_state, scratch_dir):
        """应删除 HEAVY_STATE/task_name.json。"""
        task_name = "cleanup-state"
        scratch_dir = scratch_dir / task_name
        scratch_dir.mkdir(parents=True)
        state_file = heavy_state / f"{task_name}.json"
        state_file.write_text("{}")

        heavy.heavy_cleanup(task_name)

        assert not state_file.exists()
        assert not scratch_dir.exists()

    def test_nonexistent_task(self, capsys):
        """不存在的任务输出错误。"""
        heavy.heavy_cleanup("nonexistent-cleanup")
        out = capsys.readouterr().out
        assert "❌" in out


# ─────────────────────── heavy_preflight ───────────────────────

class TestHeavyPreflight:
    """heavy_preflight() 测试群。"""

    def test_nonexistent_path_message(self, tmp_path, capsys):
        """路径不存在时输出 ❌。"""
        heavy.heavy_preflight(str(tmp_path / "nonexistent"))
        out = capsys.readouterr().out
        assert "❌ 路径不存在" in out

    def test_existing_path_with_mocked_popen(self, tmp_path, mocker, capsys):
        """存在路径 + mock os.popen，应输出文件数和上下文余量。"""
        # 用独立 project 子目录，避免 tmp_path 根目录混入 autouse fixture 生成的 state/data 文件
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        for i in range(5):
            (project_dir / f"f{i}.txt").write_text("x" * 1000)
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 40.0})

        # mock os.popen 返回一个 fake file 对象
        class FakeFile:
            def __init__(self, content=""):
                self.content = content
            def read(self):
                return self.content

        def popen_side_effect(cmd, *args, **kwargs):
            if "free" in cmd:
                return FakeFile("16G")
            elif "df" in cmd:
                return FakeFile("100G/200G")
            return FakeFile("")

        mocker.patch("os.popen", side_effect=popen_side_effect)

        heavy.heavy_preflight(str(project_dir))
        out = capsys.readouterr().out
        assert "⚙️ 重型战甲预检" in out
        assert "📂 文件数: 5" in out
        assert "🧠 上下文余量" in out

    def test_low_remaining_warns(self, tmp_path, mocker, capsys):
        """上下文余量 < 20% 时输出 ⚠️。"""
        for i in range(3):
            (tmp_path / f"f{i}.txt").write_text("x")
        mocker.patch.object(heavy, "armor_check",
                          return_value={"usagePercent": 85.0})  # 剩余 15%
        class FakeFile:
            def read(self):
                return "1G"
        mocker.patch("os.popen", return_value=FakeFile())

        heavy.heavy_preflight(str(tmp_path))
        out = capsys.readouterr().out
        assert "⚠️" in out
        assert "不足" in out or "强烈建议" in out

    # ── 2026-06-30 O 修复: event 命名 'heavy.task.finished' → 'heavy.task.done' ──

    def test_heavy_finish_emits_done_event(self, tmp_path, scratch_dir, mocker):
        """【O 修】heavy_finish 应发 'heavy.task.done' (对齐设计 6.2,不是 'finished')。"""
        task_name = "o-test-done"
        task_scratch = scratch_dir / task_name
        task_scratch.mkdir(parents=True)
        # 全部 done
        status = {
            "taskName": task_name,
            "targetPath": str(tmp_path / "project"),
            "subtasks": {
                "batch-001": {"status": "done"},
            },
        }
        (task_scratch / "status.json").write_text(json.dumps(status))
        (tmp_path / "project").mkdir()
        # mock _append_broker 捕事件
        captured_events = []
        def mock_broker(view, event_type, *args, **kwargs):
            captured_events.append((view, event_type))
        mocker.patch.object(heavy, "_append_broker", side_effect=mock_broker)

        heavy.heavy_finish(task_name)
        # 验证事件: 用 'heavy.task.done' 不是 'heavy.task.finished'
        events = [e[1] for e in captured_events]
        assert "heavy.task.done" in events, (
            f"O 修复: 应收 'heavy.task.done', 实际 {events}"
        )
        assert "heavy.task.finished" not in events, (
            f"O 修复: 不应再发 'heavy.task.finished', 实际 {events}"
        )
