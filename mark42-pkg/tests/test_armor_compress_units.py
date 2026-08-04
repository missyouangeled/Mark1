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


class TestBuildIndex:
    """索引构建：LLM 优先，失败回退启发式分类。"""

    def test_llm_path_sets_strategy_and_model_flag(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value={
            "preserved": {"activeProjects": ["Mark42"]},
            "discarded": {"summary": "闲聊"},
            "degradationDetected": None,
            "suggestedAction": "monitor",
            "_llm_meta": {"model": "doubao-seed-2.0-pro"},
        })
        msgs = [{"role": "user", "content": "hi"}]
        index = armor._compress_build_index(msgs, 80.0, {}, 85.0)
        assert index["strategyUsed"] == "llm-analyze"
        assert index["modelGenerated"] is True
        assert index["llmMeta"]["model"] == "doubao-seed-2.0-pro"

    def test_heuristic_path_when_llm_returns_none(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        msgs = [{"role": "user", "content": "hi"}]
        index = armor._compress_build_index(msgs, 80.0, {}, 85.0)
        assert index["strategyUsed"] == "heuristic-classify"
        assert index["modelGenerated"] is False

    def test_empty_messages_skips_llm_entirely(self, mocker):
        spy = mocker.patch.object(armor, "_llm_analyze", return_value=None)
        index = armor._compress_build_index([], 80.0, {}, 85.0)
        spy.assert_not_called()
        assert index["strategyUsed"] == "heuristic-classify"

    def test_heuristic_preserves_user_identity(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        index = armor._compress_build_index([], 80.0, {}, 85.0)
        assert "点点" in index["preserved"]["userIdentity"]

    def test_heuristic_recommends_compact_above_alert(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        index = armor._compress_build_index([], 90.0, {}, 85.0)
        assert index["recommendedAction"] == "/compact"

    def test_heuristic_recommends_monitor_below_alert(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        index = armor._compress_build_index([], 75.0, {}, 85.0)
        assert index["recommendedAction"] == "monitor"

    def test_usage_above_90_marks_lost_in_middle(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        index = armor._compress_build_index([], 95.0, {}, 85.0)
        assert index["degradationDetected"] == "lost-in-middle"

    def test_algo_stats_passed_through(self, mocker):
        mocker.patch.object(armor, "_llm_analyze", return_value=None)
        stats = {"algorithm": "smartcrush", "saved": 1234}
        index = armor._compress_build_index([], 80.0, stats, 85.0)
        assert index["algoStats"] == stats


class TestCooldownCheck:
    """冷却期检查：30 分钟内不重复 compact。"""

    def test_returns_none_when_no_cooldown_file(self, armor_state):
        index, path = {}, armor_state / "memory-index.json"
        assert armor._compress_check_cooldown(index, path, {}) is None

    def test_blocks_when_within_cooldown(self, armor_state):
        f = armor._compact_cooldown_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"lastCompactTs": armor._now_iso()}))
        index, path = {}, armor_state / "memory-index.json"
        result = armor._compress_check_cooldown(index, path, {"usagePercent": 80})
        assert result is not None
        assert result["action"] == "skip-cooldown"
        assert index["compactTriggered"] is False
        assert index["compressionEffective"] is False

    def test_passes_when_cooldown_expired(self, armor_state):
        f = armor._compact_cooldown_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        old = (datetime.now() - timedelta(seconds=2000)).isoformat()
        f.write_text(json.dumps({"lastCompactTs": old}))
        index, path = {}, armor_state / "memory-index.json"
        assert armor._compress_check_cooldown(index, path, {}) is None

    def test_corrupted_cooldown_file_does_not_block(self, armor_state):
        f = armor._compact_cooldown_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("不是 JSON")
        index, path = {}, armor_state / "memory-index.json"
        assert armor._compress_check_cooldown(index, path, {}) is None

    def test_blocked_result_persists_index_to_disk(self, armor_state):
        f = armor._compact_cooldown_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"lastCompactTs": armor._now_iso()}))
        path = armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_check_cooldown({}, path, {})
        assert path.exists()
        assert json.loads(path.read_text())["compactError"].startswith("cooldown-")


class TestAlreadyCompacted:
    """已压缩预检：session 含 compaction 条目时跳过，避免摘要膨胀。"""

    def _make_session(self, tmp_path, content):
        f = tmp_path / "session.jsonl"
        f.write_text(content)
        return f

    def test_returns_none_for_clean_session(self, tmp_path, armor_state):
        s = self._make_session(tmp_path, '{"type":"message","role":"user"}\n')
        index, path = {}, armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        assert armor._compress_check_already_compacted(s, index, path, 80.0, {}) is None

    def test_blocks_on_compaction_entry_no_space(self, tmp_path, armor_state):
        s = self._make_session(tmp_path, '{"type":"compaction","summary":"x"}\n')
        index, path = {}, armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        result = armor._compress_check_already_compacted(s, index, path, 80.0, {})
        assert result["action"] == "skip-already-compacted"
        assert index["compactError"] == "session-already-compacted"

    def test_blocks_on_compaction_entry_with_space(self, tmp_path, armor_state):
        """兼容 '"type": "compaction"' 带空格的 JSON 格式。"""
        s = self._make_session(tmp_path, '{"type": "compaction", "summary": "x"}\n')
        index, path = {}, armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        result = armor._compress_check_already_compacted(s, index, path, 80.0, {})
        assert result["action"] == "skip-already-compacted"

    def test_records_pre_bytes_from_file_size(self, tmp_path, armor_state):
        content = '{"type":"compaction"}\n'
        s = self._make_session(tmp_path, content)
        index, path = {}, armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_check_already_compacted(s, index, path, 80.0, {})
        assert index["preCompactBytes"] == len(content)

    def test_writes_cooldown_marker_on_block(self, tmp_path, armor_state):
        s = self._make_session(tmp_path, '{"type":"compaction"}\n')
        index, path = {}, armor_state / "memory-index.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_check_already_compacted(s, index, path, 80.0, {})
        cd = armor._compact_cooldown_file()
        assert cd.exists()
        assert json.loads(cd.read_text())["reason"] == "already-compacted"

    def test_missing_file_returns_none_gracefully(self, tmp_path, armor_state):
        s = tmp_path / "nonexistent.jsonl"
        index, path = {}, armor_state / "memory-index.json"
        assert armor._compress_check_already_compacted(s, index, path, 80.0, {}) is None


class TestWriteActionLog:
    """actions.jsonl 审计写入 + bytesStatus 四态语义标记。"""

    def _read_last(self, log_path):
        return json.loads(log_path.read_text().strip().split("\n")[-1])

    def test_dry_run_marks_skipped(self, armor_state):
        log = armor_state / "actions.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_write_action_log({}, armor_state / "i.json", log, 80.0, True)
        assert self._read_last(log)["bytesStatus"] == "skipped-dry-run"
        assert self._read_last(log)["action"] == "compress-dryrun"

    def test_captured_when_both_bytes_present(self, armor_state):
        log = armor_state / "actions.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        index = {"preCompactBytes": 1000, "postCompactBytes": 600, "bytesSaved": 400}
        armor._compress_write_action_log(index, armor_state / "i.json", log, 80.0, False)
        entry = self._read_last(log)
        assert entry["bytesStatus"] == "captured"
        assert entry["bytesSaved"] == 400

    def test_error_status_when_compact_error_set(self, armor_state):
        log = armor_state / "actions.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        index = {"compactError": "timeout"}
        armor._compress_write_action_log(index, armor_state / "i.json", log, 80.0, False)
        assert self._read_last(log)["bytesStatus"] == "error"

    def test_not_attempted_when_nothing_happened(self, armor_state):
        log = armor_state / "actions.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_write_action_log({}, armor_state / "i.json", log, 50.0, False)
        assert self._read_last(log)["bytesStatus"] == "not-attempted"

    def test_appends_not_overwrites(self, armor_state):
        log = armor_state / "actions.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        armor._compress_write_action_log({}, armor_state / "i.json", log, 80.0, True)
        armor._compress_write_action_log({}, armor_state / "i.json", log, 80.0, True)
        assert len(log.read_text().strip().split("\n")) == 2


class TestIneffectiveEscalation:
    """连续 ≥3 次压缩无效 → 升级 broker 事件。"""

    def _write_history(self, history_dir, effective_flags):
        history_dir.mkdir(parents=True, exist_ok=True)
        for i, flag in enumerate(effective_flags):
            (history_dir / f"memory-index-2026080{i}-000000.json").write_text(
                json.dumps({"compressionEffective": flag})
            )

    def test_skips_when_current_run_effective(self, armor_state):
        h = armor_state / "history"
        self._write_history(h, [False, False, False])
        # 本次有效 -> 不升级
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": True}, h, 80.0)

    def test_escalates_on_three_consecutive_failures(self, armor_state, mocker):
        spy = mocker.patch.object(armor, "_append_broker")
        h = armor_state / "history"
        self._write_history(h, [False, False, False])
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": False}, h, 80.0)
        spy.assert_called_once()
        assert "ineffective" in spy.call_args[0][1]

    def test_no_escalation_with_only_two_failures(self, armor_state, mocker):
        spy = mocker.patch.object(armor, "_append_broker")
        h = armor_state / "history"
        self._write_history(h, [False, False])
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": False}, h, 80.0)
        spy.assert_not_called()

    def test_no_escalation_when_mixed_results(self, armor_state, mocker):
        spy = mocker.patch.object(armor, "_append_broker")
        h = armor_state / "history"
        self._write_history(h, [False, True, False])
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": False}, h, 80.0)
        spy.assert_not_called()

    def test_corrupted_history_file_is_skipped(self, armor_state, mocker):
        spy = mocker.patch.object(armor, "_append_broker")
        h = armor_state / "history"
        self._write_history(h, [False, False, False])
        (h / "memory-index-broken.json").write_text("不是 JSON")
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": False}, h, 80.0)
        # 损坏文件被跳过，剩下 3 个仍触发升级
        spy.assert_called_once()

    def test_missing_history_dir_does_not_crash(self, armor_state):
        armor._compress_check_ineffective_escalation(
            {"compressionEffective": False}, armor_state / "nonexistent", 80.0)
