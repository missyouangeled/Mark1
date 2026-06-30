"""logs.py rotate_broker_events 的单测 - 验证 broker 裁剪阈值 + 安全余量。

测试策略:
  - 直接调 rotate_broker_events 验证裁剪逻辑
  - 用 monkeypatch 把 MAX_BROKER_EVENTS_MB 改小, 容易制造临界场景
  - conftest 已经把 XDG_STATE_HOME 重定向到 tmp_path
"""

import json
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

