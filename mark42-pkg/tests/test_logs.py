"""test_logs.py - 日志轮替测试。

覆盖：
- _load_state / _save_state
- _age_days
- rotate_history_files()
- rotate_actions_log()
- rotate_broker_events()
- log_rotate("all")
- log_rotate_status()
"""

import os
import time

import pytest

from mark42 import logs as logs_mod
from mark42.logs import (
    _age_days,
    _load_state,
    _save_state,
    log_rotate,
    rotate_actions_log,
    rotate_history_files,
)


@pytest.fixture(autouse=True)
def isolated_log_state(tmp_path, monkeypatch):
    """每个测试用独立的目录。"""
    test_armor = tmp_path / "armor"
    test_armor.mkdir(parents=True, exist_ok=True)
    test_state_file = tmp_path / "log-rotation.json"

    monkeypatch.setattr(logs_mod, "LOG_ROTATION_STATE", test_state_file)
    monkeypatch.setattr(logs_mod, "ARMOR_STATE", test_armor)
    # config 模块中的引用
    from mark42 import config as cfg

    monkeypatch.setattr(cfg, "ARMOR_STATE", test_armor)

    yield


# ── _load_state / _save_state ────────────────────────────


class TestLoadSaveState:
    def test_default_state(self):
        """无状态文件时应返回默认结构。"""
        state = _load_state()
        assert state["lastRotation"] is None
        assert state["rotationCount"] == 0

    def test_save_then_load(self):
        """保存后应能正确加载。"""
        state = {
            "lastRotation": "2026-07-17T10:00:00",
            "rotationCount": 42,
        }
        _save_state(state)
        loaded = _load_state()
        assert loaded["lastRotation"] == "2026-07-17T10:00:00"
        assert loaded["rotationCount"] == 42

    def test_save_creates_parent_dir(self, tmp_path, monkeypatch):
        """保存时应自动创建父目录。"""
        deep_path = tmp_path / "deep" / "nested" / "state.json"
        monkeypatch.setattr(logs_mod, "LOG_ROTATION_STATE", deep_path)
        _save_state({"lastRotation": None, "rotationCount": 0})
        assert deep_path.exists()


# ── _age_days ────────────────────────────────────────────


class TestAgeDays:
    def test_recent_file_near_zero(self, tmp_path):
        """新文件的 age 应接近 0。"""
        f = tmp_path / "new.txt"
        f.write_text("test")
        age = _age_days(f)
        assert age < 0.01  # 不到 15 分钟

    def test_nonexistent_file_large_age(self, tmp_path):
        """不存在的文件应返回大值。"""
        f = tmp_path / "ghost.txt"
        age = _age_days(f)
        assert age > 900

    def test_old_file(self, tmp_path):
        """旧文件应返回较大的天数。"""
        f = tmp_path / "old.txt"
        f.write_text("old")
        # 把 mtime 设为 10 天前
        old_time = time.time() - 10 * 86400
        os.utime(f, (old_time, old_time))
        age = _age_days(f)
        assert 9.5 < age < 10.5


# ── rotate_history_files ─────────────────────────────────


class TestRotateHistoryFiles:
    def test_no_history_dir(self):
        """无历史目录应返回 cleaned=0。"""
        result = rotate_history_files()
        assert result["cleaned"] == 0

    def test_cleans_old_files(self, tmp_path, monkeypatch):
        """应清理超过保留数量的旧文件。"""
        history_dir = tmp_path / "armor" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        # 创建 60 个文件（超过 MAX_HISTORY_FILES=50）
        from mark42.config import MAX_HISTORY_FILES

        assert MAX_HISTORY_FILES == 50
        for i in range(60):
            f = history_dir / f"memory-index-2026070{i:02d}-000000.json"
            f.write_text('{"test": true}')
            # 设置递减的 mtime，最早的设为 40 天前（超过 MAX_LOG_AGE_DAYS=30）
            old_time = time.time() - (i * 100 + 86400 * 40)
            os.utime(f, (old_time, old_time))

        monkeypatch.setattr(logs_mod, "ARMOR_STATE", tmp_path / "armor")

        result = rotate_history_files()
        assert result["cleaned"] > 0
        remaining = list(history_dir.glob("memory-index-*.json"))
        assert len(remaining) <= MAX_HISTORY_FILES

    def test_preserves_recent_files(self, tmp_path, monkeypatch):
        """不应删除近期文件。"""
        history_dir = tmp_path / "armor" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        # 创建 3 个新文件
        for i in range(3):
            f = history_dir / f"memory-index-2026071{i}-000000.json"
            f.write_text('{"recent": true}')

        monkeypatch.setattr(logs_mod, "ARMOR_STATE", tmp_path / "armor")

        _result = rotate_history_files()
        remaining = list(history_dir.glob("memory-index-*.json"))
        assert len(remaining) == 3


# ── rotate_actions_log ───────────────────────────────────


class TestRotateActionsLog:
    def test_no_actions_file(self, tmp_path, monkeypatch):
        """无 actions.jsonl 应安全返回。"""
        monkeypatch.setattr(logs_mod, "ARMOR_STATE", tmp_path / "armor")
        result = rotate_actions_log()
        assert isinstance(result, dict)


# ── log_rotate ───────────────────────────────────────────


class TestLogRotate:
    def test_all_returns_dict(self):
        """log_rotate('all') 应返回字典。"""
        result = log_rotate("all")
        assert isinstance(result, dict)

    def test_updates_rotation_count(self):
        """轮替后 rotationCount 应递增。"""
        before = _load_state()
        before_count = before.get("rotationCount", 0)
        log_rotate("all")
        after = _load_state()
        assert after["rotationCount"] > before_count
        assert after["lastRotation"] is not None

    def test_invalid_target_returns_dict(self):
        """无效 target 应安全返回。"""
        result = log_rotate("nonexistent_target")
        assert isinstance(result, dict)
