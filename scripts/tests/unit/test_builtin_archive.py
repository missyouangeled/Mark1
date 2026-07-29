"""测试 builtin_archive.py 插件模块。"""

import pytest
from typing import Any, Dict


class TestBuiltinArchive:
    """测试 BuiltinArchive 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        assert BuiltinArchive is not None

    def test_implements_archive_lock_interface(self):
        """测试实现了 ArchiveLock 接口。"""
        from scripts.mark42_modules.interfaces.error_archive import ArchiveLock
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        
        instance = BuiltinArchive.__new__(BuiltinArchive)
        assert isinstance(instance, ArchiveLock)

    def test_init_creates_error_archive_impl(self, mocker):
        """测试 __init__ 正确创建 ErrorArchive 实例。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_instance = mock_error_archive_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        mock_error_archive_class.assert_called_once()
        assert archive._impl == mock_instance

    def test_lookup_with_category_forwards_to_impl(self, mocker):
        """测试 lookup 方法正确转发参数到实现。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        
        # 创建一个模拟的 entry 对象
        mock_entry = mocker.MagicMock()
        mock_entry.to_dict.return_value = {"id": "123", "signature": "test-err"}
        mock_impl.lookup.return_value = mock_entry
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.lookup("test-sig", category="test-category")
        
        mock_impl.lookup.assert_called_once_with("test-sig", category="test-category")
        mock_entry.to_dict.assert_called_once()
        assert result == {"id": "123", "signature": "test-err"}

    def test_lookup_without_category(self, mocker):
        """测试 lookup 不指定 category 时使用默认值。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        
        mock_entry = mocker.MagicMock()
        mock_entry.to_dict.return_value = {"id": "456"}
        mock_impl.lookup.return_value = mock_entry
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.lookup("test-sig")
        
        mock_impl.lookup.assert_called_once_with("test-sig", category="")
        assert result == {"id": "456"}

    def test_lookup_returns_none_when_entry_not_found(self, mocker):
        """测试 lookup 在找不到条目时返回 None。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.lookup.return_value = None
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.lookup("non-existent")
        assert result is None

    def test_lookup_handles_entry_without_to_dict(self, mocker):
        """测试 lookup 处理没有 to_dict 方法的 entry。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        
        # 返回一个普通字典而非有 to_dict 方法的对象
        raw_entry = {"id": "789", "raw": True}
        mock_impl.lookup.return_value = raw_entry
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.lookup("test-sig")
        assert result == raw_entry

    def test_add_forwards_all_fields_to_impl(self, mocker):
        """测试 add 方法正确转发所有字段到 record 方法。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.record.return_value = "entry-id-123"
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        test_entry: Dict[str, Any] = {
            "category": "test-cat",
            "signature": "test-sig",
            "summary": "error happened",
            "root_cause": "bug",
            "fix": "applied patch",
        }
        
        result = archive.add(test_entry)
        
        mock_impl.record.assert_called_once_with(
            category="test-cat",
            signature="test-sig",
            error_summary="error happened",
            root_cause="bug",
            fix_applied="applied patch",
        )
        assert result == "entry-id-123"

    def test_add_handles_dict_result_from_impl(self, mocker):
        """测试 add 处理实现返回字典的情况。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.record.return_value = {"entry_id": "dict-entry-id"}
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        test_entry: Dict[str, Any] = {"signature": "test"}
        result = archive.add(test_entry)
        
        assert result == "dict-entry-id"

    def test_add_uses_default_values_for_missing_fields(self, mocker):
        """测试 add 对缺失字段使用空字符串。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.record.return_value = "id"
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        # 空的 entry 字典
        test_entry: Dict[str, Any] = {}
        archive.add(test_entry)
        
        mock_impl.record.assert_called_once_with(
            category="",
            signature="",
            error_summary="",
            root_cause="",
            fix_applied="",
        )

    def test_approve_forwards_to_impl(self, mocker):
        """测试 approve 方法正确转发到实现。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.approve_for_auto.return_value = True
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.approve("entry-123")
        
        mock_impl.approve_for_auto.assert_called_once_with("entry-123")
        assert result is True

    def test_approve_handles_dict_result_ok_status(self, mocker):
        """测试 approve 处理返回字典且 status 为 ok 的情况。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.approve_for_auto.return_value = {"status": "ok"}
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.approve("entry-123")
        assert result is True

    def test_approve_handles_dict_result_approved_status(self, mocker):
        """测试 approve 处理返回字典且 status 为 approved 的情况。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.approve_for_auto.return_value = {"status": "approved"}
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.approve("entry-123")
        assert result is True

    def test_approve_handles_dict_result_other_status(self, mocker):
        """测试 approve 处理返回字典但 status 不是 ok/approved 的情况。"""
        mock_error_archive_class = mocker.patch(
            'scripts.mark42_modules.error_archive.ErrorArchive'
        )
        mock_impl = mock_error_archive_class.return_value
        mock_impl.approve_for_auto.return_value = {"status": "rejected"}
        
        from scripts.mark42_modules.plugins.builtin_archive import BuiltinArchive
        archive = BuiltinArchive()
        
        result = archive.approve("entry-123")
        assert result is False
