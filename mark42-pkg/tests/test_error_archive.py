"""pytest tests for mark42/error_archive.py"""

import json
import pytest
from pathlib import Path

from mark42 import error_archive
from mark42.error_archive import ErrorArchive, STATUS_NEW, STATUS_RESOLVED, STATUS_AUTO_APPROVED, STATUS_REJECTED


@pytest.fixture
def temp_archive_dir(tmp_path, monkeypatch):
    """临时 archive 目录 fixture。"""
    archive_dir = tmp_path / "error-archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    # 修改模块里的路径常量
    monkeypatch.setattr(error_archive, "ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(error_archive, "ENTRIES_FILE", archive_dir / "entries.jsonl")
    monkeypatch.setattr(error_archive, "APPROVAL_LOG_FILE", archive_dir / "approvals.jsonl")
    monkeypatch.setattr(error_archive, "CONFIG_FILE", archive_dir / "config.json")

    return archive_dir


class TestErrorArchive:
    """测试 ErrorArchive 错误档案类。"""

    def test_record_new_entry(self, temp_archive_dir):
        """测试记录新条目。"""
        arc = ErrorArchive()

        entry = arc.record(
            category="test_category",
            signature="test:signature:001",
            diagnosis="测试诊断",
        )

        assert entry.id is not None
        assert entry.category == "test_category"
        assert entry.signature == "test:signature:001"
        assert entry.diagnosis == "测试诊断"
        assert entry.occurrence_count == 1
        assert entry.resolution_status == STATUS_NEW

    def test_record_existing_entry_increments_count(self, temp_archive_dir):
        """测试记录已存在的条目应增加计数。"""
        arc = ErrorArchive()

        # 第一次记录
        entry1 = arc.record(category="test_category", signature="test:signature:001")
        assert entry1.occurrence_count == 1

        # 第二次记录（同 signature）
        entry2 = arc.record(category="test_category", signature="test:signature:001")
        assert entry2.occurrence_count == 2
        assert entry2.id == entry1.id  # 应该是同一个条目

    def test_get_entry(self, temp_archive_dir):
        """测试根据 ID 获取条目。"""
        arc = ErrorArchive()

        entry = arc.record(category="test_category", signature="test:signature:001")
        retrieved = arc.get(entry.id)

        assert retrieved is not None
        assert retrieved.id == entry.id
        assert retrieved.signature == "test:signature:001"

    def test_get_nonexistent_entry_returns_none(self, temp_archive_dir):
        """测试获取不存在的条目应返回 None。"""
        arc = ErrorArchive()
        assert arc.get("nonexistent-id") is None

    def test_lookup_exact_match(self, temp_archive_dir):
        """测试精确匹配查找。"""
        arc = ErrorArchive()

        arc.record(category="test_category", signature="test:signature:001")
        found = arc.lookup(signature="test:signature:001", category="test_category")

        assert found is not None
        assert found.signature == "test:signature:001"

    def test_list_entries(self, temp_archive_dir):
        """测试列出条目。"""
        arc = ErrorArchive()

        arc.record(category="cat1", signature="sig1")
        arc.record(category="cat2", signature="sig2")
        arc.record(category="cat1", signature="sig3")

        # 全部列出
        all_entries = arc.list_entries()
        assert len(all_entries) == 3

        # 按 category 过滤
        cat1_entries = arc.list_entries(category="cat1")
        assert len(cat1_entries) == 2

    def test_list_entries_by_status(self, temp_archive_dir):
        """测试按状态过滤列出条目。"""
        arc = ErrorArchive()

        arc.record(category="cat1", signature="sig1", resolution_status=STATUS_NEW)
        arc.record(category="cat1", signature="sig2", resolution_status=STATUS_RESOLVED)

        new_entries = arc.list_entries(status=STATUS_NEW)
        assert len(new_entries) == 1

        resolved_entries = arc.list_entries(status=STATUS_RESOLVED)
        assert len(resolved_entries) == 1

    def test_approve_for_auto(self, temp_archive_dir):
        """测试授权自动执行。"""
        arc = ErrorArchive()

        entry = arc.record(category="safe_category", signature="test:sig")
        result = arc.approve_for_auto(entry.id, scope="exact_match")

        assert result["ok"] is True
        assert "已授权" in result["reason"]

        updated = arc.get(entry.id)
        assert updated.auto_approved is True
        assert updated.auto_approval_scope == "exact_match"
        assert updated.resolution_status == STATUS_AUTO_APPROVED

    def test_approve_for_auto_blacklisted_category(self, temp_archive_dir):
        """测试黑名单类别应拒绝授权。"""
        arc = ErrorArchive()

        entry = arc.record(category="user_data_modification", signature="test:sig")
        result = arc.approve_for_auto(entry.id)

        assert result["ok"] is False
        assert "黑名单" in result["reason"]

    def test_approve_for_auto_invalid_scope(self, temp_archive_dir):
        """测试无效 scope 应拒绝。"""
        arc = ErrorArchive()

        entry = arc.record(category="cat", signature="sig")
        result = arc.approve_for_auto(entry.id, scope="invalid_scope")

        assert result["ok"] is False

    def test_reject_entry(self, temp_archive_dir):
        """测试拒绝条目。"""
        arc = ErrorArchive()

        entry = arc.record(category="cat", signature="sig")
        result = arc.reject(entry.id, notes="测试拒绝原因")

        assert result["ok"] is True

        updated = arc.get(entry.id)
        assert updated.resolution_status == STATUS_REJECTED
        assert updated.resolution_notes == "测试拒绝原因"

    def test_reject_nonexistent_entry(self, temp_archive_dir):
        """测试拒绝不存在的条目。"""
        arc = ErrorArchive()
        result = arc.reject("nonexistent-id")
        assert result["ok"] is False

    def test_increment_auto_count(self, temp_archive_dir):
        """测试自动批准计数递增。"""
        arc = ErrorArchive()

        entry = arc.record(
            category="safe_category",
            signature="test:sig",
            resolution_status=STATUS_AUTO_APPROVED,
            auto_approve_scope="exact_match",
        )

        result = arc.increment_auto_count(entry.id)
        assert result["allowed"] is True
        assert result["require_reconfirm"] is False
        assert result["count"] == 2  # 初始是 1，增加后是 2

    def test_increment_auto_count_blacklisted(self, temp_archive_dir):
        """测试黑名单类别自动计数应被阻止。"""
        arc = ErrorArchive()

        entry = arc.record(
            category="user_data_modification",
            signature="test:sig",
            resolution_status=STATUS_AUTO_APPROVED,
            auto_approve_scope="exact_match",
        )

        result = arc.increment_auto_count(entry.id)
        assert result["allowed"] is False

    def test_stats(self, temp_archive_dir):
        """测试统计功能。"""
        arc = ErrorArchive()

        arc.record(category="cat1", signature="sig1", resolution_status=STATUS_NEW)
        arc.record(category="cat2", signature="sig2", resolution_status=STATUS_RESOLVED)
        arc.record(
            category="cat3",
            signature="sig3",
            resolution_status=STATUS_AUTO_APPROVED,
            auto_approve_scope="exact_match",
        )

        stats = arc.stats()
        assert stats["total"] == 3
        assert stats["auto_approved_count"] == 1
        assert STATUS_NEW in stats["by_status"]
        assert STATUS_RESOLVED in stats["by_status"]
        assert STATUS_AUTO_APPROVED in stats["by_status"]
