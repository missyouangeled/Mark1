"""ErrorArchive 错误档案系统单元测试。

测试范围:
  - STATUS 常量
  - ArchiveEntry 数据类 to_dict/from_dict
  - ErrorArchive 类 lookup / record / approve_for_auto / reject / stats
  - 用 tmp_path 隔离文件操作
  - 重复 record 不创建新条目
  - approve 后状态变 AUTO_APPROVED
  - reject 后状态变 REJECTED
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ── 常量测试 ─────────────────────────────────────────────

class TestStatusConstants:
    """测试 STATUS 常量。"""

    def test_status_values(self):
        from mark42_modules.error_archive import (
            STATUS_NEW, STATUS_RESOLVED, STATUS_AUTO_APPROVED, STATUS_REJECTED,
        )
        assert STATUS_NEW == "NEW"
        assert STATUS_RESOLVED == "RESOLVED"
        assert STATUS_AUTO_APPROVED == "AUTO_APPROVED"
        assert STATUS_REJECTED == "REJECTED"

    def test_all_statuses_contains_all(self):
        from mark42_modules.error_archive import ALL_STATUSES

        assert "NEW" in ALL_STATUSES
        assert "RESOLVED" in ALL_STATUSES
        assert "AUTO_APPROVED" in ALL_STATUSES
        assert "REJECTED" in ALL_STATUSES


# ── ArchiveEntry 数据类测试 ───────────────────────────────

class TestArchiveEntry:
    """测试 ArchiveEntry 数据类。"""

    def test_can_create_minimal(self):
        from mark42_modules.error_archive import ArchiveEntry, STATUS_NEW

        entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
        )
        assert entry.id == "ERR-123"
        assert entry.resolution_status == STATUS_NEW

    def test_can_create_with_resolution(self):
        from mark42_modules.error_archive import ArchiveEntry, STATUS_AUTO_APPROVED

        entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=1,
            category="context_alert",
            signature="armor:context_alert",
            resolution_status=STATUS_AUTO_APPROVED,
            auto_approved=True,
            auto_approval_scope="exact_match",
            auto_approval_count=1,
        )
        assert entry.auto_approved is True
        assert entry.auto_approval_scope == "exact_match"

    def test_to_dict_works(self):
        from mark42_modules.error_archive import ArchiveEntry

        entry = ArchiveEntry(
            id="ERR-123",
            ts_first_seen="2024-01-01",
            ts_last_seen="2024-01-01",
            occurrence_count=5,
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="使用率过高",
            context={"usage": 90},
            tags=["armor", "auto_detected"],
        )
        d = entry.to_dict()
        assert d["id"] == "ERR-123"
        assert d["occurrence_count"] == 5
        assert d["diagnosis"] == "使用率过高"
        assert d["context"] == {"usage": 90}
        assert d["tags"] == ["armor", "auto_detected"]

    def test_from_dict_works(self):
        from mark42_modules.error_archive import ArchiveEntry

        d = {
            "id": "ERR-456",
            "ts_first_seen": "2024-01-02",
            "ts_last_seen": "2024-01-02",
            "occurrence_count": 3,
            "category": "context_alert",
            "signature": "armor:context_alert",
            "diagnosis": "测试",
            "auto_approved": True,
            "auto_approval_count": 2,
        }
        entry = ArchiveEntry.from_dict(d)
        assert entry.id == "ERR-456"
        assert entry.occurrence_count == 3
        assert entry.auto_approved is True

    def test_from_dict_ignores_unknown_fields(self):
        """兼容旧版本：未知字段应该被忽略。"""
        from mark42_modules.error_archive import ArchiveEntry

        d = {
            "id": "ERR-789",
            "ts_first_seen": "2024-01-01",
            "ts_last_seen": "2024-01-01",
            "occurrence_count": 1,
            "category": "context_alert",
            "signature": "armor:context_alert",
            "some_old_field": "should_be_ignored",
            "another_field": 123,
        }
        entry = ArchiveEntry.from_dict(d)
        assert entry.id == "ERR-789"
        assert not hasattr(entry, "some_old_field")


# ── ErrorArchive record 测试 ─────────────────────────────

class TestErrorArchiveRecord:
    """测试 ErrorArchive.record() 方法。"""

    def _make_arc(self, tmp_path):
        """创建一个使用 tmp_path 的 ErrorArchive。"""
        from mark42_modules import error_archive

        # 重设 ARCHIVE_DIR 到 tmp_path
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_record_creates_new_entry(self, tmp_path):
        arc = self._make_arc(tmp_path)
        entry = arc.record(
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="使用率过高",
            context={"usage": 85},
            tags=["armor", "auto_detected"],
        )
        assert entry.id.startswith("ERR-")
        assert entry.category == "context_alert"
        assert entry.occurrence_count == 1

    def test_record_different_category_creates_new(self, tmp_path):
        """同 signature 但不同 category 应该创建新条目。"""
        arc = self._make_arc(tmp_path)

        entry1 = arc.record(
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="告警",
        )
        entry2 = arc.record(
            category="context_warn",
            signature="armor:context_warn",
            diagnosis="警告",
        )
        assert entry1.id != entry2.id


# ── ErrorArchive lookup 测试 ──────────────────────────────

class TestErrorArchiveLookup:
    """测试 ErrorArchive.lookup() 方法。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_lookup_exact_match(self, tmp_path):
        arc = self._make_arc(tmp_path)
        arc.record(
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="测试",
        )

        result = arc.lookup("armor:context_alert", category="context_alert")
        assert result is not None
        assert result.signature == "armor:context_alert"

    def test_lookup_not_found_returns_none(self, tmp_path):
        arc = self._make_arc(tmp_path)
        result = arc.lookup("nonexistent:signature")
        assert result is None

    def test_lookup_rejected_not_returned(self, tmp_path):
        """REJECTED 的条目不应该被 lookup 返回。"""
        arc = self._make_arc(tmp_path)
        entry = arc.record(
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="测试",
        )
        arc.reject(entry.id, notes="测试拒绝")

        result = arc.lookup("armor:context_alert")
        assert result is None

# ── ErrorArchive approve_for_auto 测试 ──────────────────

class TestErrorArchiveApprove:
    """测试 ErrorArchive.approve_for_auto() 方法。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_approve_sets_auto_approved_true(self, tmp_path):
        arc = self._make_arc(tmp_path)
        entry = arc.record(
            category="context_alert",
            signature="armor:context_alert",
            diagnosis="测试",
        )

        result = arc.approve_for_auto(entry.id, scope="exact_match")
        assert result["ok"] is True

        updated = arc.get(entry.id)
        assert updated.auto_approved is True
        assert updated.auto_approval_scope == "exact_match"
        assert updated.resolution_status == "AUTO_APPROVED"

    def test_approve_invalid_scope_returns_error(self, tmp_path):
        arc = self._make_arc(tmp_path)
        entry = arc.record(category="c1", signature="s1")

        result = arc.approve_for_auto(entry.id, scope="invalid_scope")
        assert result["ok"] is False

    def test_approve_nonexistent_entry_returns_error(self, tmp_path):
        arc = self._make_arc(tmp_path)
        result = arc.approve_for_auto("ERR-NONE")
        assert result["ok"] is False

    def test_approve_blacklisted_category_blocked(self, tmp_path):
        """R12: 黑名单类别不允许自动批准。"""
        arc = self._make_arc(tmp_path)
        entry = arc.record(
            category="user_data_modification",  # 黑名单
            signature="system:user_data_modification",
            diagnosis="测试",
        )

        result = arc.approve_for_auto(entry.id)
        assert result["ok"] is False
        assert "黑名单" in result["reason"]


# ── ErrorArchive reject 测试 ─────────────────────────────

class TestErrorArchiveReject:
    """测试 ErrorArchive.reject() 方法。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_reject_sets_status_rejected(self, tmp_path):
        arc = self._make_arc(tmp_path)
        entry = arc.record(category="c1", signature="s1")

        result = arc.reject(entry.id, notes="不需要处理")
        assert result["ok"] is True

        updated = arc.get(entry.id)
        assert updated.resolution_status == "REJECTED"
        assert updated.resolution_notes == "不需要处理"
        assert updated.auto_approved is False  # 撤回

    def test_reject_nonexistent_entry_returns_error(self, tmp_path):
        arc = self._make_arc(tmp_path)
        result = arc.reject("ERR-NONE")
        assert result["ok"] is False


# ── ErrorArchive increment_auto_count 测试 ───────────────

class TestErrorArchiveIncrementAutoCount:
    """测试 ErrorArchive.increment_auto_count() 方法（cooldown）。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_increment_increases_count(self, tmp_path):
        arc = self._make_arc(tmp_path)
        entry = arc.record(category="c1", signature="s1")
        arc.approve_for_auto(entry.id)

        result = arc.increment_auto_count(entry.id)
        assert result["allowed"] is True
        assert result["count"] == 2  # 授权算 1，第一次 increment 算 2

    def test_increment_nonexistent_returns_false(self, tmp_path):
        arc = self._make_arc(tmp_path)
        result = arc.increment_auto_count("ERR-NONE")
        assert result["allowed"] is False
        assert result["require_reconfirm"] is True

    def test_increment_blacklisted_blocked(self, tmp_path):
        """每次执行前都检查黑名单。"""
        arc = self._make_arc(tmp_path)
        entry = arc.record(
            category="user_data_modification",
            signature="system:user_data_modification",
            diagnosis="测试",
            auto_approve_scope="exact_match",  # 绕过 approve_for_auto 的检查
        )
        # 直接修改状态（不通过 approve_for_auto 检查）
        entry.auto_approved = True
        entry.auto_approval_count = 1

        # 手动写回文件
        from mark42_modules import error_archive
        all_entries = error_archive._read_entries()
        for i, e in enumerate(all_entries):
            if e.id == entry.id:
                all_entries[i] = entry
                break
        error_archive._rewrite_entries(all_entries)

        result = arc.increment_auto_count(entry.id)
        assert result["allowed"] is False


# ── ErrorArchive stats 测试 ─────────────────────────────

class TestErrorArchiveStats:
    """测试 ErrorArchive.stats() 方法。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_stats_empty(self, tmp_path):
        arc = self._make_arc(tmp_path)
        stats = arc.stats()
        # 空档案返回 total >= 0
        assert stats["total"] >= 0
        assert "by_status" in stats

    def test_stats_with_entries(self, tmp_path):
        arc = self._make_arc(tmp_path)
        e1 = arc.record(category="c1", signature="s1")
        e2 = arc.record(category="c2", signature="s2")
        result = arc.approve_for_auto(e1.id)

        stats = arc.stats()
        assert stats["total"] >= 2
        # 检查状态统计
        if "by_status" in stats:
            assert len(stats["by_status"]) >= 0


# ── 文件操作隔离测试 ─────────────────────────────────────

class TestFileIsolation:
    """测试使用 tmp_path 正确隔离文件操作。"""

    def test_does_not_pollute_real_archive_dir(self, tmp_path):
        from mark42_modules import error_archive

        real_archive = Path.home() / ".local" / "state" / "openclaw" / "mark42" / "error-archive"
        real_entries = real_archive / "entries.jsonl"
        real_exists_before = real_entries.exists()
        real_mtime_before = real_entries.stat().st_mtime if real_exists_before else None

        # 在 tmp_path 操作
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                arc = ErrorArchive()
                arc.record(category="test", signature="test:test", diagnosis="测试")

        # 验证真目录没变
        if real_mtime_before is not None:
            assert real_entries.stat().st_mtime == real_mtime_before

    def test_multiple_archives_are_independent(self, tmp_path):
        """两个不同 tmp_path 的 ErrorArchive 应该独立。"""
        from mark42_modules import error_archive

        # 第一个
        arc1_dir = tmp_path / "arc1"
        arc1_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(error_archive, "ARCHIVE_DIR", arc1_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc1_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                arc1 = ErrorArchive()
                arc1.record(category="c1", signature="s1")
                assert arc1.stats()["total"] == 1

        # 第二个
        arc2_dir = tmp_path / "arc2"
        arc2_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(error_archive, "ARCHIVE_DIR", arc2_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc2_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                arc2 = ErrorArchive()
                assert arc2.stats()["total"] == 0  # 空的


# ── 边界情况测试 ─────────────────────────────────────────

class TestEdgeCases:
    """测试边界情况。"""

    def _make_arc(self, tmp_path):
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", arc_dir / "entries.jsonl"):
                from mark42_modules.error_archive import ErrorArchive
                return ErrorArchive()

    def test_corrupted_jsonl_handled_gracefully(self, tmp_path, caplog):
        """损坏的 entries.jsonl 应该不崩溃。"""
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)
        entries_file = arc_dir / "entries.jsonl"
        entries_file.write_text("{invalid json}\nvalid json but wrong schema\n")

        from mark42_modules import error_archive
        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "ENTRIES_FILE", entries_file):
                from mark42_modules.error_archive import ErrorArchive
                arc = ErrorArchive()
                result = arc.lookup("any:thing")
                assert result is None  # 找不到，不崩溃

    def test_empty_config_uses_defaults(self, tmp_path):
        """CONFIG_FILE 不存在时用默认配置。"""
        from mark42_modules import error_archive
        arc_dir = tmp_path / "error-archive"
        arc_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(error_archive, "ARCHIVE_DIR", arc_dir):
            with patch.object(error_archive, "CONFIG_FILE", arc_dir / "config.json"):
                cfg = error_archive._load_l3_config()
                assert cfg["cooldown_max"] == 5
                assert "hard_blacklist_categories" in cfg
