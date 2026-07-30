"""
module_health.py 单元测试

测试覆盖:
- 健康状态检查
- 异常检测/报警
- 状态转换（healthy -> degraded -> down）
- 所有公开函数
"""

import sys
import pytest
from unittest.mock import MagicMock, patch

# 导入待测试模块
from mark42.module_health import (
    ModuleHealth,
    ModuleHealthMonitor,
)


class TestModuleHealth:
    """测试 ModuleHealth 数据类"""

    def test_module_health_creation(self):
        """测试创建健康状态对象"""
        health = ModuleHealth(
            module_id="test-module",
            module_name="测试模块",
            status="green",
        )
        assert health.module_id == "test-module"
        assert health.module_name == "测试模块"
        assert health.status == "green"

    def test_module_health_to_dict(self):
        """测试 to_dict 方法"""
        health = ModuleHealth(
            module_id="armor",
            module_name="上下文铠甲",
            status="green",
            latency_ms=50,
            error_rate=0.0,
            saturation=0.5,
            traffic_per_min=10,
            contract_passed=True,
        )
        result = health.to_dict()
        assert result["module_id"] == "armor"
        assert result["status"] == "green"
        assert result["latency_ms"] == 50

    def test_golden_signals_ok_all_good(self):
        """测试所有信号都正常时 golden_signals_ok 为 True"""
        health = ModuleHealth(
            module_id="test",
            module_name="测试",
            status="green",
            latency_ms=100,  # 小于 2000
            error_rate=0.01,  # 小于 0.05
            saturation=0.5,   # 小于 0.8
        )
        assert health.golden_signals_ok is True

    def test_golden_signals_ok_high_latency(self):
        """测试高延迟时 golden_signals_ok 为 False"""
        health = ModuleHealth(
            module_id="test",
            module_name="测试",
            status="green",
            latency_ms=2500,  # 超过 2000
            error_rate=0.01,
            saturation=0.5,
        )
        assert health.golden_signals_ok is False

    def test_golden_signals_ok_high_error_rate(self):
        """测试高错误率时 golden_signals_ok 为 False"""
        health = ModuleHealth(
            module_id="test",
            module_name="测试",
            status="green",
            latency_ms=100,
            error_rate=0.1,  # 超过 0.05
            saturation=0.5,
        )
        assert health.golden_signals_ok is False

    def test_golden_signals_ok_high_saturation(self):
        """测试高饱和度时 golden_signals_ok 为 False"""
        health = ModuleHealth(
            module_id="test",
            module_name="测试",
            status="green",
            latency_ms=100,
            error_rate=0.01,
            saturation=0.9,  # 超过 0.8
        )
        assert health.golden_signals_ok is False

    def test_is_degraded_property(self):
        """测试 is_degraded 属性"""
        health_green = ModuleHealth(module_id="1", module_name="测试", status="green")
        health_yellow = ModuleHealth(module_id="2", module_name="测试", status="yellow")
        health_red = ModuleHealth(module_id="3", module_name="测试", status="red")
        
        assert health_green.is_degraded is False
        assert health_yellow.is_degraded is True
        assert health_red.is_degraded is False

    def test_is_down_property(self):
        """测试 is_down 属性"""
        health_green = ModuleHealth(module_id="1", module_name="测试", status="green")
        health_yellow = ModuleHealth(module_id="2", module_name="测试", status="yellow")
        health_red = ModuleHealth(module_id="3", module_name="测试", status="red")
        
        assert health_green.is_down is False
        assert health_yellow.is_down is False
        assert health_red.is_down is True

    def test_fallback_active_property(self):
        """测试 fallback_active 属性"""
        health = ModuleHealth(
            module_id="test",
            module_name="测试",
            status="red",
            fallback_active="启用降级模式",
        )
        assert health.fallback_active == "启用降级模式"


class TestModuleHealthMonitor:
    """测试 ModuleHealthMonitor 监控器类"""

    def test_monitor_creation(self, mocker):
        """测试创建监控器"""
        mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        assert hasattr(monitor, "MODULES")
        assert len(monitor.MODULES) > 0

    def test_modules_list_contains_expected_modules(self, mocker):
        """测试 MODULES 列表包含预期的模块"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        module_ids = [m["id"] for m in monitor.MODULES]
        assert "armor" in module_ids
        assert "engine" in module_ids
        assert "consciousness" in module_ids
        assert "advisor" in module_ids
        assert "memory_vector" in module_ids
        assert "error_archive" in module_ids

    def test_check_armor_module(self, mocker):
        """测试检查 armor 模块"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        # 创建 mock 模块并注册到 sys.modules
        mock_armor_module = MagicMock()
        mock_armor_module.armor_check.return_value = {"usagePercent": 50}
        sys.modules["mark42.armor"] = mock_armor_module
        
        armor_mod = {"id": "armor", "name": "上下文铠甲", "check": "armor_check"}
        health = monitor._check_module(armor_mod)
        
        assert health.module_id == "armor"
        assert health.status == "green"
        assert health.saturation == 0.5
        assert health.latency_ms is not None

    def test_check_armor_high_usage_degraded(self, mocker):
        """测试 armor 高使用率时降级为 yellow"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_armor_module = MagicMock()
        mock_armor_module.armor_check.return_value = {"usagePercent": 90}
        sys.modules["mark42.armor"] = mock_armor_module
        
        armor_mod = {"id": "armor", "name": "上下文铠甲", "check": "armor_check"}
        health = monitor._check_module(armor_mod)
        
        assert health.status == "yellow"

    def test_check_armor_exception(self, mocker):
        """测试 armor 检查异常时状态为 red"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_armor_module = MagicMock()
        mock_armor_module.armor_check.side_effect = Exception("check failed")
        sys.modules["mark42.armor"] = mock_armor_module
        
        armor_mod = {"id": "armor", "name": "上下文铠甲", "check": "armor_check"}
        health = monitor._check_module(armor_mod)
        
        assert health.status == "red"
        assert health.contract_passed is False

    def test_check_engine_module_with_active_loops(self, mocker):
        """测试检查 engine 模块 - 有活跃循环时 green"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_engine_module = MagicMock()
        mock_engine_module._load_loops.return_value = {
            "loop1": {"status": "running"},
            "loop2": {"status": "registered"},
        }
        sys.modules["mark42.engine"] = mock_engine_module
        
        engine_mod = {"id": "engine", "name": "循环引擎", "check": "engine_status"}
        health = monitor._check_module(engine_mod)
        
        assert health.status == "green"
        assert health.traffic_per_min == 2

    def test_check_engine_module_no_active_but_total(self, mocker):
        """测试检查 engine 模块 - 无活跃但有循环时 red"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_engine_module = MagicMock()
        mock_engine_module._load_loops.return_value = {"loop1": {"status": "stopped"}}
        sys.modules["mark42.engine"] = mock_engine_module
        
        engine_mod = {"id": "engine", "name": "循环引擎", "check": "engine_status"}
        health = monitor._check_module(engine_mod)
        
        assert health.status == "red"

    def test_check_engine_module_empty(self, mocker):
        """测试检查 engine 模块 - 空列表时 yellow"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_engine_module = MagicMock()
        mock_engine_module._load_loops.return_value = {}
        sys.modules["mark42.engine"] = mock_engine_module
        
        engine_mod = {"id": "engine", "name": "循环引擎", "check": "engine_status"}
        health = monitor._check_module(engine_mod)
        
        assert health.status == "yellow"

    def test_check_engine_module_exception(self, mocker):
        """测试检查 engine 模块异常时状态为 red"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_engine_module = MagicMock()
        mock_engine_module._load_loops.side_effect = Exception("load failed")
        sys.modules["mark42.engine"] = mock_engine_module
        
        engine_mod = {"id": "engine", "name": "循环引擎", "check": "engine_status"}
        health = monitor._check_module(engine_mod)
        
        assert health.status == "red"

    def test_check_consciousness_module_healthy(self, mocker):
        """测试检查 consciousness 模块 - 健康时 green"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_result = MagicMock()
        mock_result.healthy = True
        mock_result.issues = []
        
        mock_cons_class = MagicMock()
        mock_cons_class.return_value.self_check.return_value = mock_result
        
        mock_cons_module = MagicMock()
        mock_cons_module.Consciousness = mock_cons_class
        sys.modules["mark42.consciousness"] = mock_cons_module
        
        cons_mod = {"id": "consciousness", "name": "战甲意识层", "check": "consciousness_check"}
        health = monitor._check_module(cons_mod)
        
        assert health.status == "green"
        assert health.error_rate == 0.0

    def test_check_consciousness_module_with_issues(self, mocker):
        """测试检查 consciousness 模块 - 有问题时 yellow"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_result = MagicMock()
        mock_result.healthy = False
        mock_result.issues = ["issue1"]  # 1 个问题 = 0.1 error_rate
        
        mock_cons_class = MagicMock()
        mock_cons_class.return_value.self_check.return_value = mock_result
        
        mock_cons_module = MagicMock()
        mock_cons_module.Consciousness = mock_cons_class
        sys.modules["mark42.consciousness"] = mock_cons_module
        
        cons_mod = {"id": "consciousness", "name": "战甲意识层", "check": "consciousness_check"}
        health = monitor._check_module(cons_mod)
        
        assert health.status == "yellow"
        assert health.error_rate == 0.1  # len(issues) / 10.0

    def test_check_advisor_module_disabled(self, mocker):
        """测试检查 advisor 模块 - 未启用时 yellow"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_client = MagicMock()
        mock_client.enabled = False
        
        mock_advisor_module = MagicMock()
        mock_advisor_module.AdvisorClient.return_value = mock_client
        sys.modules["mark42.advisor_client"] = mock_advisor_module
        
        advisor_mod = {"id": "advisor", "name": "主动交流", "check": "advisor_ping"}
        health = monitor._check_module(advisor_mod)
        
        assert health.status == "yellow"
        assert health.fallback_active == "advisor_not_enabled"

    def test_check_advisor_module_enabled_success(self, mocker):
        """测试检查 advisor 模块 - 已启用且 ping 成功时 green"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_ping_result = MagicMock()
        mock_ping_result.success = True
        mock_ping_result.verdict.elapsed_ms = 50
        
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.ping.return_value = mock_ping_result
        
        mock_advisor_module = MagicMock()
        mock_advisor_module.AdvisorClient.return_value = mock_client
        sys.modules["mark42.advisor_client"] = mock_advisor_module
        
        advisor_mod = {"id": "advisor", "name": "主动交流", "check": "advisor_ping"}
        health = monitor._check_module(advisor_mod)
        
        assert health.status == "green"
        assert health.latency_ms == 50

    def test_check_advisor_module_enabled_failure(self, mocker):
        """测试检查 advisor 模块 - 已启用但 ping 失败时 red"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_ping_result = MagicMock()
        mock_ping_result.success = False
        mock_ping_result.verdict.elapsed_ms = 100
        mock_ping_result.fallback_reason = "connection_timeout"
        
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.ping.return_value = mock_ping_result
        
        mock_advisor_module = MagicMock()
        mock_advisor_module.AdvisorClient.return_value = mock_client
        sys.modules["mark42.advisor_client"] = mock_advisor_module
        
        advisor_mod = {"id": "advisor", "name": "主动交流", "check": "advisor_ping"}
        health = monitor._check_module(advisor_mod)
        
        assert health.status == "red"
        assert health.fallback_active == "connection_timeout"

    def test_check_memory_vector_module_success(self, mocker):
        """测试检查 memory_vector 模块 - 二进制和索引都存在时 green"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        memory_mod = {"id": "memory_vector", "name": "向量引擎", "check": "qmd_check"}
        
        mocker.patch("shutil.which", return_value="/usr/bin/qmd")
        mocker.patch("os.path.isfile", return_value=True)
        
        health = monitor._check_module(memory_mod)
        
        assert health.status == "green"

    def test_check_memory_vector_module_missing_file(self, mocker):
        """测试检查 memory_vector 模块 - 缺少文件时 red"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        memory_mod = {"id": "memory_vector", "name": "向量引擎", "check": "qmd_check"}
        
        mocker.patch("shutil.which", return_value=None)
        mocker.patch("os.path.isfile", return_value=False)
        
        health = monitor._check_module(memory_mod)
        
        assert health.status == "red"
        assert health.fallback_active == "L1_keyword_only"

    def test_check_error_archive_module(self, mocker):
        """测试检查 error_archive 模块 - 总是 green"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_archive_module = MagicMock()
        mock_archive_module.ErrorArchive.return_value.list_entries.return_value = []
        sys.modules["mark42.error_archive"] = mock_archive_module
        
        archive_mod = {"id": "error_archive", "name": "错误档案", "check": "archive_list"}
        health = monitor._check_module(archive_mod)
        
        assert health.status == "green"

    def test_check_module_golden_signals_trigger_degrade(self, mocker):
        """测试 golden signals 触线时从 green 降级到 yellow"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        mock_armor_module = MagicMock()
        mock_armor_module.armor_check.return_value = {"usagePercent": 50}
        sys.modules["mark42.armor"] = mock_armor_module
        
        # mock time.monotonic 制造高延迟
        call_count = [0]
        def mock_time():
            call_count[0] += 1
            return 0 if call_count[0] == 1 else 3.0  # 3000ms 延迟
        
        mocker.patch("time.monotonic", mock_time)
        
        armor_mod = {"id": "armor", "name": "上下文铠甲", "check": "armor_check"}
        health = monitor._check_module(armor_mod)
        
        # 高延迟触线，应该降级到 yellow
        assert health.status == "yellow"

    def test_check_all_modules(self, mocker):
        """测试检查所有模块"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        # mock 所有模块
        mock_armor_module = MagicMock()
        mock_armor_module.armor_check.return_value = {"usagePercent": 50}
        sys.modules["mark42.armor"] = mock_armor_module
        
        mock_engine_module = MagicMock()
        mock_engine_module._load_loops.return_value = {"loop1": {"status": "running"}}
        sys.modules["mark42.engine"] = mock_engine_module
        
        mock_result = MagicMock()
        mock_result.healthy = True
        mock_result.issues = []
        mock_cons_module = MagicMock()
        mock_cons_module.Consciousness.return_value.self_check.return_value = mock_result
        sys.modules["mark42.consciousness"] = mock_cons_module
        
        mock_ping_result = MagicMock()
        mock_ping_result.success = True
        mock_ping_result.verdict.elapsed_ms = 50
        mock_client = MagicMock()
        mock_client.enabled = True
        mock_client.ping.return_value = mock_ping_result
        mock_advisor_module = MagicMock()
        mock_advisor_module.AdvisorClient.return_value = mock_client
        sys.modules["mark42.advisor_client"] = mock_advisor_module
        
        mocker.patch("shutil.which", return_value="/usr/bin/qmd")
        mocker.patch("os.path.isfile", return_value=True)
        
        mock_archive_module = MagicMock()
        mock_archive_module.ErrorArchive.return_value.list_entries.return_value = []
        sys.modules["mark42.error_archive"] = mock_archive_module
        
        results = monitor.check_all()
        
        assert len(results) == len(monitor.MODULES)

    def test_summary(self, mocker):
        """测试 summary 方法"""
        mocker.patch("pathlib.Path.mkdir")
        monitor = ModuleHealthMonitor()
        
        # mock check_all 返回混合状态
        mock_check_all = MagicMock(return_value=[
            ModuleHealth(module_id="1", module_name="模块1", status="green"),
            ModuleHealth(module_id="2", module_name="模块2", status="green"),
            ModuleHealth(module_id="3", module_name="模块3", status="yellow"),
            ModuleHealth(module_id="4", module_name="模块4", status="red"),
        ])
        mocker.patch.object(monitor, "check_all", mock_check_all)
        
        summary = monitor.summary()
        
        assert summary["total"] == 4
        assert summary["green"] == 2
        assert summary["yellow"] == 1
        assert summary["red"] == 1
        assert len(summary["modules"]) == 4
