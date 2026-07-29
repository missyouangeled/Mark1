"""测试 builtin_compress.py 插件模块。"""

import pytest
from typing import Any, Dict


class TestBuiltinCompress:
    """测试 BuiltinCompress 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        assert BuiltinCompress is not None

    def test_implements_compress_lock_interface(self):
        """测试实现了 CompressLock 接口。"""
        from scripts.mark42_modules.interfaces.compress import CompressLock
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        
        instance = BuiltinCompress.__new__(BuiltinCompress)
        assert isinstance(instance, CompressLock)

    def test_check_calls_armor_check(self, mocker):
        """测试 check 方法调用 armor_check。"""
        mock_armor_check = mocker.patch(
            'scripts.mark42_modules.armor.armor_check'
        )
        mock_result: Dict[str, Any] = {
            "usagePercent": 65.5,
            "severity": "normal",
            "totalTokens": 1000,
        }
        mock_armor_check.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        result = compress.check()
        
        mock_armor_check.assert_called_once()
        assert result == mock_result

    def test_check_handles_armor_exception(self, mocker):
        """测试 check 处理 armor_check 抛出异常的情况。"""
        mock_armor_check = mocker.patch(
            'scripts.mark42_modules.armor.armor_check'
        )
        mock_armor_check.side_effect = Exception("armor error")
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        # 如果 armor_check 抛出异常，应该向上传递
        with pytest.raises(Exception, match="armor error"):
            compress.check()

    def test_compress_default_dry_run_true(self, mocker):
        """测试 compress 方法默认 dry_run=True。"""
        mock_armor_compress = mocker.patch(
            'scripts.mark42_modules.armor.armor_compress'
        )
        mock_result: Dict[str, Any] = {
            "action": "analyzed",
            "before": 1000,
            "after": 1000,
            "savings": 0,
        }
        mock_armor_compress.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        result = compress.compress()
        
        mock_armor_compress.assert_called_once_with(dry_run=True)
        assert result == mock_result

    def test_compress_with_dry_run_false(self, mocker):
        """测试 compress 方法显式指定 dry_run=False。"""
        mock_armor_compress = mocker.patch(
            'scripts.mark42_modules.armor.armor_compress'
        )
        mock_result: Dict[str, Any] = {
            "action": "compressed",
            "before": 1000,
            "after": 600,
            "savings": 400,
        }
        mock_armor_compress.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        result = compress.compress(dry_run=False)
        
        mock_armor_compress.assert_called_once_with(dry_run=False)
        assert result == mock_result

    def test_compress_ignores_extra_kwargs(self, mocker):
        """测试 compress 方法忽略额外的 kwargs。"""
        mock_armor_compress = mocker.patch(
            'scripts.mark42_modules.armor.armor_compress'
        )
        mock_result: Dict[str, Any] = {"action": "test"}
        mock_armor_compress.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        # 传入额外的 kwargs，但 armor_compress 只会收到 dry_run
        result = compress.compress(dry_run=True, extra_param="ignored", another=42)
        
        mock_armor_compress.assert_called_once_with(dry_run=True)
        assert result == mock_result

    def test_compress_handles_armor_exception(self, mocker):
        """测试 compress 处理 armor_compress 抛出异常的情况。"""
        mock_armor_compress = mocker.patch(
            'scripts.mark42_modules.armor.armor_compress'
        )
        mock_armor_compress.side_effect = RuntimeError("compression failed")
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        with pytest.raises(RuntimeError, match="compression failed"):
            compress.compress()

    def test_diagnose_calls_compaction_diagnose(self, mocker):
        """测试 diagnose 方法调用 compaction_diagnose。"""
        mock_compaction_diagnose = mocker.patch(
            'scripts.mark42_modules.compaction_diag.compaction_diagnose'
        )
        mock_result: Dict[str, Any] = {
            "redundant_chunks": 15,
            "potential_savings": 2500,
            "recommendations": ["remove_old_context", "merge_similar"],
        }
        mock_compaction_diagnose.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        result = compress.diagnose()
        
        mock_compaction_diagnose.assert_called_once()
        assert result == mock_result

    def test_diagnose_handles_exception(self, mocker):
        """测试 diagnose 处理 compaction_diagnose 抛出异常的情况。"""
        mock_compaction_diagnose = mocker.patch(
            'scripts.mark42_modules.compaction_diag.compaction_diagnose'
        )
        mock_compaction_diagnose.side_effect = ValueError("diagnose error")
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        with pytest.raises(ValueError, match="diagnose error"):
            compress.diagnose()

    def test_all_methods_return_dict(self, mocker):
        """测试所有方法都返回字典。"""
        mock_armor_check = mocker.patch(
            'scripts.mark42_modules.armor.armor_check',
            return_value={"test": "check"}
        )
        mock_armor_compress = mocker.patch(
            'scripts.mark42_modules.armor.armor_compress',
            return_value={"test": "compress"}
        )
        mock_compaction_diagnose = mocker.patch(
            'scripts.mark42_modules.compaction_diag.compaction_diagnose',
            return_value={"test": "diagnose"}
        )
        
        from scripts.mark42_modules.plugins.builtin_compress import BuiltinCompress
        compress = BuiltinCompress()
        
        result_check = compress.check()
        result_compress = compress.compress()
        result_diagnose = compress.diagnose()
        
        assert isinstance(result_check, dict)
        assert isinstance(result_compress, dict)
        assert isinstance(result_diagnose, dict)
