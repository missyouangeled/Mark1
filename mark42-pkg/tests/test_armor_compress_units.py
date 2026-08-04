"""armor_compress 拆分后的子函数单元测试（2026-08-04 新增）。

背景：
  armor_compress 原为 665 行巨型函数，2026-08-04 拆分为主编排器 + 13 个子函数。
  原有 tests/test_armor_compress.py 是端到端测试（走完整 armor_compress 流程），
  本文件补充**子函数级**单元测试，确保拆分后每个阶段可独立验证。

分组：
  TestCompactLock          — compact 锁的获取/释放/过期/损坏恢复
  TestPlatformProbe        — 平台探测期
  TestBuildIndex           — 索引构建双分支（LLM / 启发式）
  TestCooldownCheck        — 冷却期检查
  TestAlreadyCompacted     — 已压缩预检
  TestWriteActionLog       — actions.jsonl 审计写入 + bytesStatus 语义
  TestIneffectiveEscalation — 连续无效升级
"""
import json
from datetime import datetime, timedelta

from mark42 import armor


class TestCompactLock:
    """compact 锁：O_CREAT|O_EXCL 原子创建 + TTL 过期 + 损坏恢复。"""

    def test_acquire_succeeds_when_no_lock(self, armor_state):
        assert armor._try_acquire_compact_lock() is True
        assert armor._compact_lock_file().exists()

    def test_acquire_writes_pid_and_timestamp(self, armor_state):
        armor._try_acquire_compact_lock()
        data = json.loads(armor._compact_lock_file().read_text())
        assert "acquiredAt" in data
        assert data["pid"] > 0

    def test_second_acquire_fails_while_lock_fresh(self, armor_state):
        assert armor._try_acquire_compact_lock() is True
        # 同一进程再抢应失败（锁未过期）
        assert armor._try_acquire_compact_lock() is False

    def test_release_removes_lock_file(self, armor_state):
        armor._try_acquire_compact_lock()
        armor._release_compact_lock()
        assert not armor._compact_lock_file().exists()

    def test_release_is_idempotent(self, armor_state):
        # 没有锁时释放不应抛异常
        armor._release_compact_lock()
        armor._release_compact_lock()

    def test_expired_lock_is_reclaimed(self, armor_state):
        lock_file = armor._compact_lock_file()
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        # 造一个已过期的锁（TTL 620s，这里用 700s 前）
        old_ts = (datetime.now() - timedelta(seconds=700)).isoformat()
        lock_file.write_text(json.dumps({"acquiredAt": old_ts, "pid": 99999}))
        assert armor._try_acquire_compact_lock() is True
        # 应该被换成新锁
        new_data = json.loads(lock_file.read_text())
        assert new_data["pid"] != 99999

    def test_corrupted_lock_is_reclaimed(self, armor_state):
        lock_file = armor._compact_lock_file()
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("{{{ 这不是合法 JSON")
        assert armor._try_acquire_compact_lock() is True
        json.loads(lock_file.read_text())  # 应能正常解析

    def test_lock_without_timestamp_is_reclaimed(self, armor_state):
        lock_file = armor._compact_lock_file()
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text(json.dumps({"pid": 12345}))  # 缺 acquiredAt
        assert armor._try_acquire_compact_lock() is True


class TestPlatformProbe:
    """平台探测期：先等平台自己 auto-compaction，无反应才自主出手。"""

    def test_dry_run_returns_false_immediately(self):
        assert armor._platform_compact_probe(85.0, dry_run=True) is False

    def test_skip_sleep_flag_returns_false(self, monkeypatch):
        """conftest 设了 _PLATFORM_PROBE_SKIP_SLEEP=True，测试环境不真睡。"""
        monkeypatch.setattr(armor, "_PLATFORM_PROBE_SKIP_SLEEP", True, raising=False)
        assert armor._platform_compact_probe(85.0, dry_run=False) is False

    def test_detects_usage_drop_as_platform_handled(self, monkeypatch, mocker):
        """usage 下降超过 5% -> 判定平台已处理，返回 True。"""
        monkeypatch.setattr(armor, "_PLATFORM_PROBE_SKIP_SLEEP", False, raising=False)
        monkeypatch.setattr(armor.time, "sleep", lambda _: None)
        mocker.patch.object(armor, "armor_check", return_value={"usagePercent": 60.0})
        assert armor._platform_compact_probe(85.0, dry_run=False) is True

    def test_no_drop_returns_false_after_probe(self, monkeypatch, mocker):
        """usage 无变化 -> 平台无反应，返回 False 让 Mark42 出手。"""
        monkeypatch.setattr(armor, "_PLATFORM_PROBE_SKIP_SLEEP", False, raising=False)
        monkeypatch.setattr(armor.time, "sleep", lambda _: None)
        mocker.patch.object(armor, "armor_check", return_value={"usagePercent": 85.0})
        assert armor._platform_compact_probe(85.0, dry_run=False) is False

    def test_small_drop_not_treated_as_handled(self, monkeypatch, mocker):
        """只降 3%（<5% 阈值）不算平台处理。"""
        monkeypatch.setattr(armor, "_PLATFORM_PROBE_SKIP_SLEEP", False, raising=False)
        monkeypatch.setattr(armor.time, "sleep", lambda _: None)
        mocker.patch.object(armor, "armor_check", return_value={"usagePercent": 82.0})
        assert armor._platform_compact_probe(85.0, dry_run=False) is False
