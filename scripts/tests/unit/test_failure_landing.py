"""
Mark42 v3 R13-D · FAILURE.md 降级契约落地测试

测试核心降级时 FAILURE.md 自动生成，恢复时自动清理。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import mark42_modules.core_registry as cr
from mark42_modules.failure_contract import (
    _core_failure_path,
    create_contract_for_core,
    failure_md_exists,
    remove_failure_md,
    write_failure_md,
)


@pytest.fixture
def temp_registry_dir(tmp_path):
    """临时注册表目录，测试后自动清理。"""
    original_dir = cr.REGISTRY_DIR
    # 创建临时目录
    temp_dir = tmp_path / "core-registry"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 替换常量
    with mock.patch("mark42_modules.core_registry.REGISTRY_DIR", temp_dir):
        with mock.patch("mark42_modules.core_registry.REGISTRY_FILE", temp_dir / "registry.json"):
            with mock.patch("mark42_modules.failure_contract.CORE_REGISTRY_DIR", temp_dir):
                yield temp_dir


@pytest.fixture
def registry(temp_registry_dir):
    """创建干净的 CoreRegistry 实例。"""
    return cr.CoreRegistry()


class TestFailureContractIntegration:
    """测试 failure_contract 模块的基础功能。"""

    def test_create_contract_for_core_down(self, temp_registry_dir):
        """测试为 down 状态的核心创建契约。"""
        contract = create_contract_for_core(
            core_id="core_1_main_consciousness",
            status="down",
            criticality="critical",
            reason="gateway 不可达",
        )
        
        assert contract.core_id == "core_1_main_consciousness"
        assert contract.status == "failed"  # down 映射为 failed
        assert contract.criticality == "critical"
        assert contract.reason == "gateway 不可达"

    def test_create_contract_for_core_degraded(self, temp_registry_dir):
        """测试为 degraded 状态的核心创建契约。"""
        contract = create_contract_for_core(
            core_id="core_2_armor_consciousness",
            status="degraded",
            criticality="degradable",
            reason="响应超时",
        )
        
        assert contract.core_id == "core_2_armor_consciousness"
        assert contract.status == "degraded"
        assert contract.criticality == "degradable"

    def test_write_failure_md_creates_file(self, temp_registry_dir):
        """测试写入 FAILURE.md 会创建文件。"""
        contract = create_contract_for_core(
            core_id="core_1_main_consciousness",
            status="down",
            criticality="critical",
            reason="测试故障",
        )
        
        path = write_failure_md("core_1_main_consciousness", contract)
        
        assert path.exists()
        assert path.name == "FAILURE.md"
        assert "core_1_main_consciousness" in path.parent.name
        assert failure_md_exists("core_1_main_consciousness")

    def test_remove_failure_md_removes_file(self, temp_registry_dir):
        """测试删除 FAILURE.md。"""
        contract = create_contract_for_core(
            core_id="core_1_main_consciousness",
            status="down",
            criticality="critical",
            reason="测试故障",
        )
        write_failure_md("core_1_main_consciousness", contract)
        
        assert failure_md_exists("core_1_main_consciousness")
        
        result = remove_failure_md("core_1_main_consciousness")
        
        assert result is True
        assert not failure_md_exists("core_1_main_consciousness")

    def test_remove_failure_md_nonexistent_returns_false(self, temp_registry_dir):
        """测试删除不存在的 FAILURE.md 返回 False。"""
        result = remove_failure_md("core_nonexistent")
        assert result is False


class TestCoreRegistryProbeAllFailureHandling:
    """测试 probe_all 方法中的 FAILURE.md 自动生成/清理。"""

    def test_probe_all_core_down_creates_failure_md(self, temp_registry_dir, registry):
        """测试核心 down 时自动生成 FAILURE.md。"""
        # mock probe_core 返回 down
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "down", "reason": "测试故障"}
            
            # 先确保所有核心都是 healthy
            for core_id in registry.cores:
                registry.cores[core_id].status = "healthy"
            
            # 只让第一个核心 down
            first_core = list(registry.cores.keys())[0]
            mock_probe.side_effect = lambda cid: (
                {"status": "down", "reason": "测试故障"} if cid == first_core else {"status": "healthy"}
            )
            
            registry.probe_all()
            
            # 验证 down 的核心有 FAILURE.md
            assert failure_md_exists(first_core)
            
            # 验证其他 healthy 核心没有 FAILURE.md
            for core_id in list(registry.cores.keys())[1:3]:  # 只检查前几个
                if core_id != first_core:
                    assert not failure_md_exists(core_id)

    def test_probe_all_core_degraded_creates_failure_md(self, temp_registry_dir, registry):
        """测试核心 degraded 时自动生成 FAILURE.md。"""
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            # 先确保所有核心都是 healthy
            for core_id in registry.cores:
                registry.cores[core_id].status = "healthy"
            
            first_core = list(registry.cores.keys())[0]
            mock_probe.side_effect = lambda cid: (
                {"status": "degraded", "reason": "性能下降"} if cid == first_core else {"status": "healthy"}
            )
            
            registry.probe_all()
            
            assert failure_md_exists(first_core)

    def test_probe_all_core_recovery_removes_failure_md(self, temp_registry_dir, registry):
        """测试核心恢复 healthy 时自动删除 FAILURE.md。"""
        first_core = list(registry.cores.keys())[0]
        
        # 先创建 FAILURE.md（模拟之前是 down）
        contract = create_contract_for_core(first_core, "down", "critical", "之前故障")
        write_failure_md(first_core, contract)
        registry.cores[first_core].status = "down"
        
        assert failure_md_exists(first_core)
        
        # mock probe_core 返回 healthy
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "healthy"}
            
            registry.probe_all()
            
            # 验证 FAILURE.md 已被删除
            assert not failure_md_exists(first_core)

    def test_probe_all_core_stays_healthy_no_failure_md(self, temp_registry_dir, registry):
        """测试核心保持 healthy 时不会创建 FAILURE.md。"""
        # 确保没有 FAILURE.md
        for core_id in list(registry.cores.keys())[:3]:
            remove_failure_md(core_id)
        
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "healthy"}
            
            registry.probe_all()
            
            # 验证没有创建 FAILURE.md
            for core_id in list(registry.cores.keys())[:3]:
                assert not failure_md_exists(core_id)

    def test_probe_all_core_stays_down_failure_md_exists(self, temp_registry_dir, registry):
        """测试核心保持 down 状态时 FAILURE.md 继续存在。"""
        first_core = list(registry.cores.keys())[0]
        
        # 先创建 FAILURE.md
        contract = create_contract_for_core(first_core, "down", "critical", "故障")
        write_failure_md(first_core, contract)
        registry.cores[first_core].status = "down"
        
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "down", "reason": "仍然故障"}
            
            registry.probe_all()
            
            # 验证 FAILURE.md 仍然存在（不会被删除）
            assert failure_md_exists(first_core)


class TestCoreRegistryQuarantineFailureHandling:
    """测试 quarantine 方法中的 FAILURE.md 生成。"""

    def test_quarantine_creates_failure_md(self, temp_registry_dir, registry):
        """测试隔离核心时自动生成 FAILURE.md。"""
        first_core = list(registry.cores.keys())[0]
        
        # 确保核心初始状态是 healthy
        registry.cores[first_core].status = "healthy"
        assert not failure_md_exists(first_core)
        
        # 执行隔离
        result = registry.quarantine(first_core, reason="手动隔离测试")
        
        assert result is True
        assert registry.cores[first_core].status == "quarantined"
        assert failure_md_exists(first_core)

    def test_quarantine_nonexistent_core_no_failure_md(self, temp_registry_dir, registry):
        """测试隔离不存在的核心时不创建 FAILURE.md。"""
        result = registry.quarantine("core_nonexistent", reason="不存在的核心")
        
        assert result is False
        assert not failure_md_exists("core_nonexistent")


class TestCoreRegistryRestoreFailureHandling:
    """测试 restore 方法中的 FAILURE.md 清理。"""

    def test_restore_to_healthy_removes_failure_md(self, temp_registry_dir, registry):
        """测试核心恢复为 healthy 时删除 FAILURE.md。"""
        first_core = list(registry.cores.keys())[0]
        
        # 先隔离并创建 FAILURE.md
        registry.quarantine(first_core, reason="隔离测试")
        assert failure_md_exists(first_core)
        assert registry.cores[first_core].status == "quarantined"
        
        # mock probe_core 返回 healthy
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "healthy"}
            
            result = registry.restore(first_core)
            
            assert result is True
            assert registry.cores[first_core].status == "healthy"
            assert not failure_md_exists(first_core)

    def test_restore_to_down_keeps_failure_md(self, temp_registry_dir, registry):
        """测试核心恢复但仍为 down 时保留 FAILURE.md。"""
        first_core = list(registry.cores.keys())[0]
        
        # 先隔离并创建 FAILURE.md
        registry.quarantine(first_core, reason="隔离测试")
        assert failure_md_exists(first_core)
        
        # mock probe_core 返回 down
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "down", "reason": "仍不可用"}
            
            result = registry.restore(first_core)
            
            assert result is True
            assert registry.cores[first_core].status == "down"
            # FAILURE.md 应该继续存在（因为核心仍然不可用）
            assert failure_md_exists(first_core)

    def test_restore_nonexistent_core(self, temp_registry_dir, registry):
        """测试恢复不存在的核心。"""
        result = registry.restore("core_nonexistent")
        assert result is False


class TestFailureMdContent:
    """测试 FAILURE.md 文件内容格式。"""

    def test_failure_md_contains_required_fields(self, temp_registry_dir):
        """测试 FAILURE.md 包含必要的契约字段。"""
        contract = create_contract_for_core(
            core_id="core_1_main_consciousness",
            status="down",
            criticality="critical",
            reason="gateway 不可达",
        )
        
        path = write_failure_md("core_1_main_consciousness", contract)
        content = path.read_text(encoding="utf-8")
        
        # 验证关键内容
        assert "core_1_main_consciousness" in content
        assert "主意识引擎" in content
        assert "FAILED" in content or "failed" in content or "DOWN" in content
        assert "critical" in content.lower() or "关键核心" in content
        assert "gateway 不可达" in content
        assert "缺失的能力" in content or "缺失能力" in content
        assert "兜底方案" in content or "fallback" in content.lower()

    def test_failure_md_contains_timestamp(self, temp_registry_dir):
        """测试 FAILURE.md 包含生成时间。"""
        contract = create_contract_for_core(
            core_id="core_3_memory_vector_engine",
            status="degraded",
            criticality="degradable",
            reason="响应慢",
        )
        
        path = write_failure_md("core_3_memory_vector_engine", contract)
        content = path.read_text(encoding="utf-8")
        
        # 验证包含时间戳格式
        assert "生成时间" in content or "timestamp" in content.lower()


class TestMultipleCoresFailureHandling:
    """测试多个核心同时故障的场景。"""

    def test_multiple_cores_down_creates_multiple_failure_md(self, temp_registry_dir, registry):
        """测试多个核心 down 时各自生成 FAILURE.md。"""
        cores = list(registry.cores.keys())[:3]
        
        # 先确保都是 healthy
        for core_id in cores:
            registry.cores[core_id].status = "healthy"
            remove_failure_md(core_id)
        
        # mock 前两个核心 down，第三个 healthy
        def mock_probe(cid):
            if cid in cores[:2]:
                return {"status": "down", "reason": f"{cid} 故障"}
            return {"status": "healthy"}
        
        with mock.patch("mark42_modules.core_registry.probe_core", side_effect=mock_probe):
            registry.probe_all()
            
            # 前两个应该有 FAILURE.md
            assert failure_md_exists(cores[0])
            assert failure_md_exists(cores[1])
            # 第三个不应该有
            assert not failure_md_exists(cores[2])

    def test_multiple_cores_recovery_removes_multiple_failure_md(self, temp_registry_dir, registry):
        """测试多个核心同时恢复时删除各自的 FAILURE.md。"""
        cores = list(registry.cores.keys())[:3]
        
        # 先让所有核心 down 并创建 FAILURE.md
        for core_id in cores:
            contract = create_contract_for_core(core_id, "down", "critical", "故障")
            write_failure_md(core_id, contract)
            registry.cores[core_id].status = "down"
        
        # 验证都有 FAILURE.md
        for core_id in cores:
            assert failure_md_exists(core_id)
        
        # 所有核心恢复 healthy
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "healthy"}
            
            registry.probe_all()
            
            # 验证所有 FAILURE.md 都被删除
            for core_id in cores:
                assert not failure_md_exists(core_id)


class TestFailureMdEdgeCases:
    """测试边缘情况。"""

    def test_unknown_status_no_failure_md(self, temp_registry_dir, registry):
        """测试 unknown 状态不创建 FAILURE.md。"""
        first_core = list(registry.cores.keys())[0]
        registry.cores[first_core].status = "healthy"
        
        with mock.patch("mark42_modules.core_registry.probe_core") as mock_probe:
            mock_probe.return_value = {"status": "unknown", "reason": "未知状态"}
            
            registry.probe_all()
            
            # unknown 状态不应该创建 FAILURE.md
            assert not failure_md_exists(first_core)

    def test_failure_md_path_is_core_specific(self, temp_registry_dir):
        """测试不同核心的 FAILURE.md 在不同目录。"""
        contract1 = create_contract_for_core("core_1_main_consciousness", "down", "critical", "故障1")
        contract2 = create_contract_for_core("core_2_armor_consciousness", "down", "degradable", "故障2")
        
        path1 = write_failure_md("core_1_main_consciousness", contract1)
        path2 = write_failure_md("core_2_armor_consciousness", contract2)
        
        # 路径不同
        assert path1 != path2
        # 父目录是 core_id
        assert path1.parent.name == "core_1_main_consciousness"
        assert path2.parent.name == "core_2_armor_consciousness"
        # 文件名都是 FAILURE.md
        assert path1.name == "FAILURE.md"
        assert path2.name == "FAILURE.md"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
