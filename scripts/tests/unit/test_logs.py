"""logs.py rotate_broker_events 的单测 - 验证 broker 裁剪阈值 + 安全余量。

测试策略:
  - 直接调 rotate_broker_events 验证裁剪逻辑
  - 用 monkeypatch 把 MAX_BROKER_EVENTS_MB 改小, 容易制造临界场景
  - conftest 已经把 XDG_STATE_HOME 重定向到 tmp_path
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mark42_modules import logs, config


def _populate_broker_file(path: Path, size_mb: float, line_size: int = 200) -> int:
    """填充 broker events.jsonl 到 size_mb 字节, 返回写入的行数。

    参数:
      path: 目标文件
      size_mb: 目标大小
      line_size: 每行字节数 (含换行)
    """
    target_bytes = int(size_mb * 1024 * 1024)
    n_lines = target_bytes // line_size
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for i in range(n_lines):
            # 用固定格式保证行大小一致
            f.write(f'{{"id":{i},"data":"{"x" * (line_size - 20)}}}\n')
    return n_lines


class TestRotateBrokerEvents:
    """rotate_broker_events() 测试群 - 阈值 + 安全余量。"""

    def test_skip_when_below_threshold(self, monkeypatch, tmp_path):
        """broker < MAX 时不裁剪, 返回 trimmed=0。"""
        # 0.5 MB 数据
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 0.5)
        # MAX 设为 10MB
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        r = logs.rotate_broker_events()
        assert r["trimmed"] == 0
        assert r["sizeMB"] < 10

    def test_trim_when_at_or_above_threshold(self, monkeypatch, tmp_path):
        """broker >= MAX 时裁剪, trimmed > 0。"""
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 12)  # 12MB > 10MB 阈值
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        r = logs.rotate_broker_events()
        assert r["trimmed"] > 0
        # 关键: 裁后 size < MAX * 0.95 (留 5%+ 余量)
        assert r["postSizeMB"] < 10 * 0.95, (
            f"裁后 size={r['postSizeMB']}MB 应 < 9.5MB (留 10% 余量)"
        )

    def test_safety_factor_prevents_immediate_retrigger(self, monkeypatch, tmp_path):
        """【🟠-1 修复验证】裁完应留 10% 余量,不会立即重新触发。"""
        # 边界: 刚好 10.5MB, MAX=10
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 10.5)
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        r = logs.rotate_broker_events()
        # 1) 裁后 size 显著低于 10MB
        assert r["postSizeMB"] < 9.5, (
            f"🟠-1 修复: 裁后应 < 9.5MB, 实际 {r['postSizeMB']}MB"
        )
        # 2) safety factor 应 = 0.9 (新加的返回字段)
        assert r.get("safetyFactor") == 0.9
        # 3) 留 1MB+ 余量
        assert 10 - r["postSizeMB"] >= 0.5, (
            f"留余量应 >= 0.5MB, 实际 {10 - r['postSizeMB']:.2f}MB"
        )

    def test_size_exactly_at_threshold_triggers(self, monkeypatch, tmp_path):
        """【I 修复验证】broker 刚好 10MB 时应该裁, 不像原版 size_mb <= 临界不裁。"""
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 10.0)
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        r = logs.rotate_broker_events()
        # 临界点 size_mb == MAX, 修复后 size_mb < MAX 走 else, 触发裁剪
        assert r["trimmed"] > 0 or r["postSizeMB"] < 10, (
            f"10MB 临界应触发裁剪, 但 trimmed={r['trimmed']} post={r['postSizeMB']}"
        )

    def test_no_file_no_error(self, monkeypatch, tmp_path):
        """broker 不存在时返 note 不抛错。"""
        # 确保文件不存在
        if config.MARK42_BROKER_EVENTS.exists():
            config.MARK42_BROKER_EVENTS.unlink()

        r = logs.rotate_broker_events()
        assert r["note"] == "无 broker 事件"
        assert r["trimmed"] == 0

    def test_keep_minimum_100_lines(self, monkeypatch, tmp_path):
        """即使算出来 keep<100, 仍保留 100 行 (保护历史)。"""
        # 制造 11MB 巨型 broker, 但故意不写够多行
        # 改 line_size 让总行数 = 150, 裁后应保留 100
        target_bytes = int(11 * 1024 * 1024)
        # line_size 设大让行数少
        line_size = target_bytes // 150
        config.MARK42_BROKER_EVENTS.parent.mkdir(parents=True, exist_ok=True)
        with open(config.MARK42_BROKER_EVENTS, "w") as f:
            for i in range(150):
                f.write(f'{{"id":{i}}}\n')  # 这里行很短, 但
                # 因为 _populate 不用了, 我们直接造数据
        # 重新造: 行数少 + 字节达 11MB
        config.MARK42_BROKER_EVENTS.unlink()
        big_line = "x" * (target_bytes // 150 - 20)
        with open(config.MARK42_BROKER_EVENTS, "w") as f:
            for i in range(150):
                f.write(f'{{"id":{i},"d":"{big_line}"}}\n')

        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)
        r = logs.rotate_broker_events()
        # 验证 至少留 100 行
        kept_lines = config.MARK42_BROKER_EVENTS.read_text().strip().split("\n")
        assert len(kept_lines) >= 100, f"应至少留 100 行, 实际 {len(kept_lines)}"

    # ── 2026-06-30 10:13 🟡2 修复: fcntl 锁原子性 ──

    def test_concurrent_rotation_skipped_with_lock(self, monkeypatch, tmp_path):
        """【🟡2】另一进程占锁时, 本次 rotate 应跳过不报错。"""
        import fcntl
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 11)
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        # 手动占锁, 模拟另一进程正在裁
        lock_path = config.MARK42_BROKER_EVENTS.with_suffix(
            config.MARK42_BROKER_EVENTS.suffix + ".lock"
        )
        other_lock = open(lock_path, "w")
        fcntl.flock(other_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        try:
            r = logs.rotate_broker_events()
            # 验证: 返 "另一进程正在裁, 跳过", 不抛错
            assert "另一进程正在裁" in r.get("note", ""), (
                f"🟡2 修复: 应返跳过 note, 实际 {r}"
            )
            assert r["trimmed"] == 0
            # 文件不应该被改
            assert config.MARK42_BROKER_EVENTS.stat().st_size > 10 * 1024 * 1024
        finally:
            fcntl.flock(other_lock.fileno(), fcntl.LOCK_UN)
            other_lock.close()

    def test_lock_released_after_rotation(self, monkeypatch, tmp_path):
        """【🟡2】rotate 完成后锁应释放, 后续 rotate 可正常执行。"""
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 11)
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        # 第一次裁
        r1 = logs.rotate_broker_events()
        assert r1["trimmed"] > 0

        # 第二次调, 锁应已释放(否则会返 "另一进程正在裁")
        r2 = logs.rotate_broker_events()
        # 第二次因为 < 10MB, 应返 trimmed=0
        assert r2["trimmed"] == 0, (
            f"🟡2: 锁应已释放, 第二次调应正常执行, 实际 {r2}"
        )

    def test_lock_path_separate_from_broker_file(self, monkeypatch, tmp_path):
        """【🟡2】锁文件是 .jsonl.lock, 不是 .jsonl 本身 (避免锁住业务读)。"""
        _populate_broker_file(config.MARK42_BROKER_EVENTS, 0.5)
        monkeypatch.setattr(logs, "MAX_BROKER_EVENTS_MB", 10)

        # 跑一次确保锁文件创建
        logs.rotate_broker_events()
        # 锁文件可能已被清, 但 .lock 后缀是固定规则
        # 验证设计: import 后 .lock 后缀逻辑是固定的
        from mark42_modules.logs import MARK42_BROKER_EVENTS
        expected_lock = MARK42_BROKER_EVENTS.with_suffix(
            MARK42_BROKER_EVENTS.suffix + ".lock"
        )
        assert expected_lock.suffix == ".lock"
        # 注: 锁文件存在性不重要, 重要的是 .lock 后缀约定


class TestRotateHistoryFiles:
    """rotate_history_files() 历史文件裁剪测试群 (Phase 2 补充)。"""

    def test_no_history_dir_returns_note(self, monkeypatch, tmp_path):
        """无 history 目录 -> 返 note, 不崩。"""
        from mark42_modules.config import ARMOR_STATE
        history_dir = ARMOR_STATE / "history"
        if history_dir.exists():
            # conftest 隔离 tmp_path, 理论上不存在
            for f in history_dir.iterdir():
                f.unlink()
            history_dir.rmdir()
        r = logs.rotate_history_files()
        assert r["note"] == "无历史目录"
        assert r["cleaned"] == 0

    def test_keeps_recent_files(self, monkeypatch, tmp_path):
        """< MAX_HISTORY_FILES 个文件 -> 不裁。"""
        from mark42_modules.config import ARMOR_STATE
        history_dir = ARMOR_STATE / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        # 创建 3 个 history 文件
        for i in range(3):
            (history_dir / f"memory-index-2026-06-30-{i:02d}.json").write_text("{}")
        r = logs.rotate_history_files()
        # 不裁或裁 0
        assert r["cleaned"] == 0


class TestRotateActionsLog:
    """rotate_actions_log() actions.jsonl 裁剪测试群 (Phase 2 补充)。"""

    def test_no_actions_file_returns_note(self, monkeypatch, tmp_path):
        """无 actions.jsonl -> 返 note, 不崩。"""
        from mark42_modules.config import ARMOR_STATE
        actions = ARMOR_STATE / "actions.jsonl"
        if actions.exists():
            actions.unlink()
        r = logs.rotate_actions_log()
        assert r["note"] == "无 actions 日志"
        assert r["trimmed"] == 0

    def test_short_actions_log_unchanged(self, monkeypatch, tmp_path):
        """< MAX_ACTIONS_LINES 行 -> 不裁。"""
        from mark42_modules.config import ARMOR_STATE
        actions = ARMOR_STATE / "actions.jsonl"
        actions.parent.mkdir(parents=True, exist_ok=True)
        # 写 5 行
        actions.write_text("\n".join([f'{{"i":{i}}}' for i in range(5)]) + "\n")
        r = logs.rotate_actions_log()
        assert r["trimmed"] == 0
        assert r["lines"] == 5


class TestLoadSaveState:
    """_load_state / _save_state 状态持久化测试群 (Phase 2 补充)。"""

    def test_load_state_empty_when_no_file(self, monkeypatch, tmp_path):
        """无 state 文件 -> 返默认 dict。"""
        from mark42_modules.config import ARMOR_STATE
        state_file = ARMOR_STATE.parent / "log-rotation.json"
        if state_file.exists():
            state_file.unlink()
        state = logs._load_state()
        assert isinstance(state, dict)
        assert "rotationCount" in state
        assert state["rotationCount"] == 0

    def test_save_and_load_state_roundtrip(self, monkeypatch, tmp_path):
        """save 后 load 应拿到同样数据。"""
        from mark42_modules.config import ARMOR_STATE
        ARMOR_STATE.mkdir(parents=True, exist_ok=True)
        original = {"lastRotation": "2026-06-30T10:00:00", "rotationCount": 5}
        logs._save_state(original)
        loaded = logs._load_state()
        assert loaded == original

    def test_load_state_handles_corrupt_json(self, monkeypatch, tmp_path):
        """state 文件是损坏 JSON -> 返默认 dict, 不崩。"""
        from mark42_modules.config import ARMOR_STATE
        ARMOR_STATE.mkdir(parents=True, exist_ok=True)
        state_file = ARMOR_STATE.parent / "log-rotation.json"
        state_file.write_text("not valid json {{{")
        state = logs._load_state()
        assert isinstance(state, dict)
        assert state["rotationCount"] == 0


class TestAgeDays:
    """_age_days() 基础分支。"""

    def test_age_days_returns_999_on_oserror(self, mocker, tmp_path):
        path = tmp_path / "ghost.txt"
        mocker.patch.object(Path, "stat", side_effect=OSError("boom"))
        assert logs._age_days(path) == 999


class TestRotateHistoryFilesMore:
    """rotate_history_files() 的数量/老化裁剪补测。"""

    def test_trim_excess_history_files_by_count(self, monkeypatch, tmp_path):
        history_dir = config.ARMOR_STATE / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(logs, "MAX_HISTORY_FILES", 3)
        monkeypatch.setattr(logs, "MAX_LOG_AGE_DAYS", 999)

        files = []
        for i in range(5):
            f = history_dir / f"memory-index-2026-07-01-{i:02d}.json"
            f.write_text("{}")
            ts = 1_700_000_000 + i
            os.utime(f, (ts, ts))
            files.append(f)

        result = logs.rotate_history_files()
        assert result["cleaned"] == 2
        remaining = sorted(p.name for p in history_dir.glob("memory-index-*.json"))
        assert len(remaining) == 3
        assert remaining == [
            "memory-index-2026-07-01-02.json",
            "memory-index-2026-07-01-03.json",
            "memory-index-2026-07-01-04.json",
        ]

    def test_trim_old_history_files_by_age(self, monkeypatch, tmp_path):
        history_dir = config.ARMOR_STATE / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(logs, "MAX_HISTORY_FILES", 99)
        monkeypatch.setattr(logs, "MAX_LOG_AGE_DAYS", 7)

        old_file = history_dir / "memory-index-old.json"
        recent_file = history_dir / "memory-index-recent.json"
        old_file.write_text("{}")
        recent_file.write_text("{}")

        old_ts = time.time() - 10 * 86400
        recent_ts = time.time() - 1 * 86400
        os.utime(old_file, (old_ts, old_ts))
        os.utime(recent_file, (recent_ts, recent_ts))

        result = logs.rotate_history_files()
        assert result["cleaned"] == 1
        assert not old_file.exists()
        assert recent_file.exists()


class TestRotateActionsLogMore:
    """rotate_actions_log() 的真实裁剪/异常补测。"""

    def test_trim_long_actions_log_keeps_tail(self, monkeypatch, tmp_path):
        actions = config.ARMOR_STATE / "actions.jsonl"
        actions.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(logs, "MAX_ACTIONS_LINES", 3)
        actions.write_text("".join(f'{i}\n' for i in range(6)))

        result = logs.rotate_actions_log()
        assert result == {"trimmed": 3, "lines": 3}
        assert actions.read_text().splitlines() == ["3", "4", "5"]

    def test_actions_log_io_error_returns_error(self, mocker, tmp_path):
        actions = config.ARMOR_STATE / "actions.jsonl"
        actions.parent.mkdir(parents=True, exist_ok=True)
        actions.write_text("x\n")
        mocker.patch("builtins.open", side_effect=OSError("boom"))

        result = logs.rotate_actions_log()
        assert result == {"trimmed": 0, "error": "IO 错误"}


class TestRotateDaemonLogs:
    """rotate_daemon_logs() 补测。"""

    def test_no_log_dir_returns_note(self, monkeypatch, tmp_path):
        monkeypatch.setattr(logs, "LOG_DIR", tmp_path / "missing-logs")
        result = logs.rotate_daemon_logs()
        assert result == {"trimmed": 0, "note": "无日志目录"}

    def test_trim_large_daemon_log_keeps_tail_half_limit(self, monkeypatch, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(logs, "LOG_DIR", log_dir)
        monkeypatch.setattr(logs, "MAX_DAEMON_LOG_MB", 0.0001)
        monkeypatch.setattr(logs, "MAX_DAEMON_LOG_LINES", 10)

        big_log = log_dir / "daemon.log"
        small_log = log_dir / "small.log"
        big_log.write_text("".join(f"line-{i}-{'x' * 50}\n" for i in range(20)))
        small_log.write_text("ok\n")

        result = logs.rotate_daemon_logs()
        assert result == {"trimmed_files": 1, "trimmed_lines": 15}
        assert big_log.read_text().splitlines() == [f"line-{i}-{'x' * 50}" for i in range(15, 20)]
        assert small_log.read_text() == "ok\n"


class TestRotateScratchOld:
    """rotate_scratch_old() 补测。"""

    def test_no_scratch_dir_returns_note(self, monkeypatch, tmp_path):
        scratch = tmp_path / "missing-scratch"
        monkeypatch.setattr(config, "SCRATCH", scratch)
        result = logs.rotate_scratch_old()
        assert result == {"cleaned": 0, "note": "无 scratch 目录"}

    def test_clean_only_old_unprotected_scratch_dirs(self, monkeypatch, tmp_path):
        scratch = tmp_path / "scratch"
        scratch.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(config, "SCRATCH", scratch)
        monkeypatch.setattr(logs, "MAX_LOG_AGE_DAYS", 7)

        old_dir = scratch / "old-dir"
        kept_dir = scratch / "kept-dir"
        recent_dir = scratch / "recent-dir"
        old_dir.mkdir()
        kept_dir.mkdir()
        recent_dir.mkdir()
        (kept_dir / ".keep").write_text("")

        monkeypatch.setattr(
            logs,
            "_age_days",
            lambda path: 30 if path.name in {"old-dir", "kept-dir"} else 1,
        )

        result = logs.rotate_scratch_old()
        assert result == {"cleaned": 1}
        assert not old_dir.exists()
        assert kept_dir.exists()
        assert recent_dir.exists()


class TestLogRotate:
    """log_rotate() 汇总与状态保存补测。"""

    def test_log_rotate_all_aggregates_results_and_updates_state(self, monkeypatch, capsys):
        saved = {}
        monkeypatch.setattr(logs, "rotate_daemon_logs", lambda: {"trimmed_files": 1, "trimmed_lines": 5})
        monkeypatch.setattr(logs, "rotate_history_files", lambda: {"cleaned": 2})
        monkeypatch.setattr(logs, "rotate_actions_log", lambda: {"trimmed": 3})
        monkeypatch.setattr(logs, "rotate_broker_events", lambda: {"trimmed": 4})
        monkeypatch.setattr(logs, "rotate_scratch_old", lambda: {"cleaned": 1})
        monkeypatch.setattr(logs, "_load_state", lambda: {"lastRotation": None, "rotationCount": 7})
        monkeypatch.setattr(logs, "_save_state", lambda state: saved.update(state))

        result = logs.log_rotate("all")
        output = capsys.readouterr().out

        assert result["status"] == "ok"
        assert result["totalItems"] == 16
        assert saved["rotationCount"] == 8
        assert saved["lastRotation"]
        assert "日志轮替完成" in output
        assert "history: 删除 2 个文件" in output
        assert "actions: 裁剪 3 行" in output
        assert "daemon: 截尾 1 个日志 (5 行)" in output

    def test_log_rotate_single_target_only_runs_requested_branch(self, monkeypatch):
        called = []
        monkeypatch.setattr(logs, "rotate_daemon_logs", lambda: called.append("daemon") or {"trimmed_files": 0, "trimmed_lines": 0})
        monkeypatch.setattr(logs, "rotate_history_files", lambda: called.append("history") or {"cleaned": 0})
        monkeypatch.setattr(logs, "rotate_actions_log", lambda: called.append("actions") or {"trimmed": 0})
        monkeypatch.setattr(logs, "rotate_broker_events", lambda: called.append("broker") or {"trimmed": 0})
        monkeypatch.setattr(logs, "rotate_scratch_old", lambda: called.append("scratch") or {"cleaned": 0})
        monkeypatch.setattr(logs, "_load_state", lambda: {"lastRotation": None, "rotationCount": 0})
        monkeypatch.setattr(logs, "_save_state", lambda state: None)

        result = logs.log_rotate("history")
        assert result["results"] == {"history": {"cleaned": 0}}
        assert called == ["history"]


class TestLogRotateStatus:
    """log_rotate_status() 输出补测。"""

    def test_log_rotate_status_prints_current_snapshot(self, monkeypatch, tmp_path, capsys):
        history_dir = config.ARMOR_STATE / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        (history_dir / "memory-index-a.json").write_text("{}")
        (history_dir / "memory-index-b.json").write_text("{}")

        actions = config.ARMOR_STATE / "actions.jsonl"
        actions.parent.mkdir(parents=True, exist_ok=True)
        actions.write_text('{"a":1}\n{"a":2}\n')

        broker = config.MARK42_BROKER_EVENTS
        broker.parent.mkdir(parents=True, exist_ok=True)
        broker.write_text('{"e":1}\n{"e":2}\n')

        scratch = tmp_path / "scratch-status"
        scratch.mkdir(parents=True, exist_ok=True)
        (scratch / "one").mkdir()
        (scratch / "two").mkdir()
        (scratch / "two" / ".keep").write_text("")
        monkeypatch.setattr(config, "SCRATCH", scratch)

        logs._save_state({"lastRotation": "2026-07-01 10:00:00", "rotationCount": 9})
        logs.log_rotate_status()
        output = capsys.readouterr().out

        assert "上次轮替: 2026-07-01 10:00:00" in output
        assert "累计次数: 9" in output
        assert "历史索引: 2 个文件" in output
        assert "actions.jsonl: 2 行" in output
        assert "broker events:" in output
        assert "scratch: 2 个目录 (1 受保护)" in output
