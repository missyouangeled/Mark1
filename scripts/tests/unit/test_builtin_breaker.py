"""测试 builtin_breaker.py 插件模块。"""

import pytest
from typing import Any, Dict


class TestBuiltinBreaker:
    """测试 BuiltinBreaker 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        assert BuiltinBreaker is not None

    def test_implements_breaker_lock_interface(self):
        """测试实现了 BreakerLock 接口。"""
        from scripts.mark42_modules.interfaces.circuit_breaker import BreakerLock
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        
        instance = BuiltinBreaker.__new__(BuiltinBreaker)
        assert isinstance(instance, BreakerLock)

    def test_init_creates_circuit_breaker_impl(self, mocker):
        """测试 __init__ 正确创建 CircuitBreaker 实例。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_instance = mock_breaker_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        mock_breaker_class.assert_called_once()
        assert breaker._impl == mock_instance

    def test_can_call_forwards_to_impl(self, mocker):
        """测试 can_call 方法正确转发到实现。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        mock_impl.can_call.return_value = True
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        result = breaker.can_call("test-key")
        
        mock_impl.can_call.assert_called_once_with("test-key")
        assert result is True

    def test_can_call_returns_false_when_blocked(self, mocker):
        """测试 can_call 在熔断器打开时返回 False。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        mock_impl.can_call.return_value = False
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        result = breaker.can_call("blocked-key")
        assert result is False

    def test_record_success_forwards_to_impl(self, mocker):
        """测试 record_success 方法正确转发到实现。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        breaker.record_success("test-key")
        
        mock_impl.record_success.assert_called_once_with("test-key")

    def test_record_failure_forwards_to_impl_with_reason(self, mocker):
        """测试 record_failure 方法带 reason 时正确转发。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        breaker.record_failure("test-key", reason="network error")
        
        mock_impl.record_failure.assert_called_once_with("test-key", reason="network error")

    def test_record_failure_forwards_to_impl_without_reason(self, mocker):
        """测试 record_failure 方法不带 reason 时使用默认空字符串。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        breaker.record_failure("test-key")
        
        mock_impl.record_failure.assert_called_once_with("test-key", reason="")

    def test_status_returns_breakers_and_total(self, mocker):
        """测试 status 方法返回正确的结构。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        
        mock_states = [
            {"key": "api1", "state": "closed", "failures": 0},
            {"key": "api2", "state": "open", "failures": 5},
        ]
        mock_impl.list_all.return_value = mock_states
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        result = breaker.status()
        
        mock_impl.list_all.assert_called_once()
        assert result["breakers"] == mock_states
        assert result["total"] == 2

    def test_status_with_empty_breakers(self, mocker):
        """测试 status 方法在没有熔断器时返回空列表。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        mock_impl.list_all.return_value = []
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        result = breaker.status()
        
        assert result["breakers"] == []
        assert result["total"] == 0

    def test_status_result_structure(self, mocker):
        """测试 status 返回的字典包含正确的键。"""
        mock_breaker_class = mocker.patch(
            'scripts.mark42_modules.circuit_breaker.CircuitBreaker'
        )
        mock_impl = mock_breaker_class.return_value
        mock_impl.list_all.return_value = [{"key": "test"}]
        
        from scripts.mark42_modules.plugins.builtin_breaker import BuiltinBreaker
        breaker = BuiltinBreaker()
        
        result = breaker.status()
        
        assert "breakers" in result
        assert "total" in result
        assert isinstance(result["breakers"], list)
        assert isinstance(result["total"], int)
