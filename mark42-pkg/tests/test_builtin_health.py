"""测试 builtin_health.py 插件模块。"""

import pytest
import sys
from typing import Any, Dict


class TestBuiltinHealth:
    """测试 BuiltinHealth 类及其接口契约。"""

    def test_module_importable(self):
        """测试模块可以正常导入。"""
        from mark42.plugins.builtin_health import BuiltinHealth
        assert BuiltinHealth is not None

    def test_implements_health_lock_interface(self):
        """测试实现了 HealthLock 接口。"""
        from mark42.interfaces.health import HealthLock
        from mark42.plugins.builtin_health import BuiltinHealth
        
        instance = BuiltinHealth.__new__(BuiltinHealth)
        assert isinstance(instance, HealthLock)

    def _mock_psutil(self, mocker, mem_percent=50.0, disk_percent=70.0, cpu_percent=30.0):
        """辅助方法：创建 psutil mock。"""
        # 创建 mock psutil 模块
        mock_psutil = mocker.MagicMock()
        
        # 模拟内存
        mock_vm = mocker.MagicMock()
        mock_vm.percent = mem_percent
        mock_vm.available = 8 * 1024 * 1024  # 8 MB
        mock_psutil.virtual_memory.return_value = mock_vm
        
        # 模拟磁盘
        mock_disk = mocker.MagicMock()
        mock_disk.percent = disk_percent
        mock_disk.free = 10 * 1024 * 1024 * 1024  # 10 GB
        mock_psutil.disk_usage.return_value = mock_disk
        
        # 模拟 CPU
        mock_psutil.cpu_percent.return_value = cpu_percent
        
        # 注入到 sys.modules
        sys.modules['psutil'] = mock_psutil
        return mock_psutil

    def test_check_health_returns_healthy_when_no_alerts(self, mocker):
        """测试健康状况良好时返回 healthy 状态。"""
        mock_psutil = self._mock_psutil(mocker, mem_percent=50.0, disk_percent=70.0, cpu_percent=30.0)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "healthy"
        assert result["alerts"] == []
        mock_psutil.virtual_memory.assert_called_once()
        mock_psutil.disk_usage.assert_called_once_with("/")
        mock_psutil.cpu_percent.assert_called_once_with(interval=0.5)

    def test_check_health_memory_critical_alert(self, mocker):
        """测试内存使用率超过 85% 时产生 critical 告警。"""
        self._mock_psutil(mocker, mem_percent=90.0, disk_percent=50.0, cpu_percent=20.0)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "degraded"
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["type"] == "memory"
        assert result["alerts"][0]["level"] == "critical"
        assert "90.0%" in result["alerts"][0]["msg"]

    def test_check_health_disk_critical_alert(self, mocker):
        """测试磁盘使用率超过 90% 时产生 critical 告警。"""
        self._mock_psutil(mocker, mem_percent=40.0, disk_percent=95.0, cpu_percent=20.0)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "degraded"
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["type"] == "disk"
        assert result["alerts"][0]["level"] == "critical"
        assert "95.0%" in result["alerts"][0]["msg"]

    def test_check_health_cpu_warning_alert(self, mocker):
        """测试 CPU 使用率超过 90% 时产生 warning 告警。"""
        self._mock_psutil(mocker, mem_percent=40.0, disk_percent=50.0, cpu_percent=95.0)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "degraded"
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["type"] == "cpu"
        assert result["alerts"][0]["level"] == "warning"
        assert "95.0%" in result["alerts"][0]["msg"]

    def test_check_health_multiple_alerts(self, mocker):
        """测试多个资源同时超限产生多个告警。"""
        self._mock_psutil(mocker, mem_percent=90.0, disk_percent=95.0, cpu_percent=95.0)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "degraded"
        assert len(result["alerts"]) == 3
        
        alert_types = [a["type"] for a in result["alerts"]]
        assert "memory" in alert_types
        assert "disk" in alert_types
        assert "cpu" in alert_types

    def test_check_health_memory_values_calculated(self, mocker):
        """测试内存数值计算正确。"""
        mock_psutil = self._mock_psutil(mocker)
        
        # 修改内存返回值
        mock_vm = mocker.MagicMock()
        mock_vm.percent = 42.5
        mock_vm.available = 8 * 1024 * 1024  # 8 MB
        mock_psutil.virtual_memory.return_value = mock_vm
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["memory"]["percent"] == 42.5
        assert result["memory"]["available_mb"] == 8

    def test_check_health_disk_values_calculated(self, mocker):
        """测试磁盘数值计算正确。"""
        mock_psutil = self._mock_psutil(mocker)
        
        # 修改磁盘返回值
        mock_disk = mocker.MagicMock()
        mock_disk.percent = 73.2
        mock_disk.free = 20 * 1024 * 1024 * 1024  # 20 GB
        mock_psutil.disk_usage.return_value = mock_disk
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["disk"]["percent"] == 73.2
        assert result["disk"]["free_gb"] == 20

    def test_check_health_cpu_value(self, mocker):
        """测试 CPU 数值正确。"""
        mock_psutil = self._mock_psutil(mocker)
        mock_psutil.cpu_percent.return_value = 67.8
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["cpu"]["percent"] == 67.8

    def test_check_health_exception_handling(self, mocker):
        """测试发生异常时返回 error 状态。"""
        mock_psutil = self._mock_psutil(mocker)
        mock_psutil.virtual_memory.side_effect = Exception("psutil error")
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert result["status"] == "error"
        assert "error" in result
        assert result["alerts"] == []

    def test_check_health_result_structure(self, mocker):
        """测试返回结果有正确的结构。"""
        self._mock_psutil(mocker)
        
        from mark42.plugins.builtin_health import BuiltinHealth
        health = BuiltinHealth()
        
        result = health.check_health()
        
        assert "status" in result
        assert "memory" in result
        assert "disk" in result
        assert "cpu" in result
        assert "alerts" in result
        
        assert "percent" in result["memory"]
        assert "available_mb" in result["memory"]
        assert "percent" in result["disk"]
        assert "free_gb" in result["disk"]
        assert "percent" in result["cpu"]
