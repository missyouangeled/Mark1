"""测试 builtin_chaos.py 插件模块。"""

import pytest
from typing import Any, Dict, List


class TestBuiltinChaos:
    """测试 BuiltinChaos 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        assert BuiltinChaos is not None

    def test_implements_chaos_lock_interface(self):
        """测试实现了 ChaosLock 接口。"""
        from scripts.mark42_modules.interfaces.chaos import ChaosLock
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        
        instance = BuiltinChaos.__new__(BuiltinChaos)
        assert isinstance(instance, ChaosLock)

    def test_init_creates_chaos_engine_impl(self, mocker):
        """测试 __init__ 正确创建 ChaosEngine 实例。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_instance = mock_engine_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        mock_engine_class.assert_called_once()
        assert chaos._impl == mock_instance

    def test_list_experiments_forwards_to_impl(self, mocker):
        """测试 list_experiments 方法正确转发到实现。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        mock_experiments: List[Dict[str, Any]] = [
            {"name": "latency-injection", "description": "Inject network latency"},
            {"name": "cpu-hog", "description": "Consume CPU resources"},
        ]
        mock_impl.list_experiments.return_value = mock_experiments
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.list_experiments()
        
        mock_impl.list_experiments.assert_called_once()
        assert result == mock_experiments

    def test_list_experiments_empty_list(self, mocker):
        """测试 list_experiments 返回空列表的情况。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        mock_impl.list_experiments.return_value = []
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.list_experiments()
        assert result == []

    def test_run_experiment_default_dry_run_true(self, mocker):
        """测试 run_experiment 默认 dry_run=True。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        mock_result = {"status": "simulated", "changes": 0}
        mock_impl.run_experiment.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp")
        
        mock_impl.run_experiment.assert_called_once_with("test-exp", dry_run=True)
        assert result == mock_result

    def test_run_experiment_with_dry_run_false(self, mocker):
        """测试 run_experiment 显式指定 dry_run=False。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        mock_result = {"status": "executed", "changes": 5}
        mock_impl.run_experiment.return_value = mock_result
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp", dry_run=False)
        
        mock_impl.run_experiment.assert_called_once_with("test-exp", dry_run=False)
        assert result == mock_result

    def test_run_experiment_handles_to_dict_result(self, mocker):
        """测试 run_experiment 处理有 to_dict 方法的返回值。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        mock_result_obj = mocker.MagicMock()
        mock_result_obj.to_dict.return_value = {"from_to_dict": True, "data": "test"}
        mock_impl.run_experiment.return_value = mock_result_obj
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp")
        
        mock_result_obj.to_dict.assert_called_once()
        assert result == {"from_to_dict": True, "data": "test"}

    def test_run_experiment_handles_raw_dict_result(self, mocker):
        """测试 run_experiment 处理直接返回字典的情况。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        mock_dict_result = {"raw": True, "value": 42}
        mock_impl.run_experiment.return_value = mock_dict_result
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp")
        assert result == mock_dict_result

    def test_run_experiment_handles_non_dict_result(self, mocker):
        """测试 run_experiment 处理非字典类型的返回值。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        # 返回字符串而非字典
        mock_impl.run_experiment.return_value = "success-string"
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp")
        assert result == {"result": "success-string"}

    def test_run_experiment_handles_object_without_to_dict(self, mocker):
        """测试 run_experiment 处理没有 to_dict 方法的对象。"""
        mock_engine_class = mocker.patch(
            'scripts.mark42_modules.chaos_engine.ChaosEngine'
        )
        mock_impl = mock_engine_class.return_value
        
        # 返回一个普通对象，没有 to_dict 方法
        class PlainObj:
            def __str__(self):
                return "plain-object"
        
        mock_impl.run_experiment.return_value = PlainObj()
        
        from scripts.mark42_modules.plugins.builtin_chaos import BuiltinChaos
        chaos = BuiltinChaos()
        
        result = chaos.run_experiment("test-exp")
        assert result == {"result": "plain-object"}
