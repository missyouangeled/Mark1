"""Test failure_contract.py R13-D 降级响应契约。"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mark42_modules.failure_contract import (
    CORE_FAILURE_CONFIG,
    CORE_REGISTRY_DIR,
    FailureContract,
    FailureContractGenerator,
    create_contract_for_core,
    failure_md_exists,
    remove_failure_md,
    render_failure_md,
    write_failure_md,
)

CST = timezone(timedelta(hours=8))


class TestFailureContract:
    """测试 FailureContract 数据类"""

    def test_9_fields_exist(self):
        """9 字段完整性"""
        contract = FailureContract(
            status="degraded",
            core_id="core_1_main_consciousness",
            core_name="主意识引擎",
            criticality="critical",
            missing_capabilities=["高层推理"],
            fallback_active="降级到 armor_consciousness",
            auto_recovery_in_progress=True,
            estimated_recovery="30 秒",
            user_action_required=False,
            reason="测试原因",
        )
        # 验证 9 个字段都存在且可访问
        assert contract.status == "degraded"
        assert contract.core_id == "core_1_main_consciousness"
        assert contract.core_name == "主意识引擎"
        assert contract.criticality == "critical"
        assert contract.missing_capabilities == ["高层推理"]
        assert contract.fallback_active == "降级到 armor_consciousness"
        assert contract.auto_recovery_in_progress is True
        assert contract.estimated_recovery == "30 秒"
        assert contract.user_action_required is False
        assert contract.reason == "测试原因"

    def test_to_dict(self):
        """to_dict 方法正常工作"""
        contract = FailureContract(
            status="failed",
            core_id="core_2_armor_consciousness",
            core_name="铠甲意识层",
            criticality="degradable",
            missing_capabilities=["上下文压缩"],
            fallback_active="降级到简单截断",
            auto_recovery_in_progress=False,
            estimated_recovery="未知",
            user_action_required=True,
            reason="API 超时",
        )
        d = contract.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "failed"
        assert d["core_id"] == "core_2_armor_consciousness"
        assert len(d) == 10  # 9 个字段

    def test_is_ok(self):
        """is_ok 方法"""
        contract = FailureContract(
            status="ok",
            core_id="core_1",
            core_name="测试核心",
            criticality="critical",
            missing_capabilities=[],
            fallback_active="",
            auto_recovery_in_progress=False,
            estimated_recovery="",
            user_action_required=False,
            reason="",
        )
        assert contract.is_ok() is True
        contract.status = "degraded"
        assert contract.is_ok() is False

    def test_is_failed(self):
        """is_failed 方法"""
        contract = FailureContract(
            status="failed",
            core_id="core_1",
            core_name="测试核心",
            criticality="critical",
            missing_capabilities=["A"],
            fallback_active="B",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=True,
            reason="test",
        )
        assert contract.is_failed() is True
        contract.status = "degraded"
        assert contract.is_failed() is False

    def test_is_degraded(self):
        """is_degraded 方法"""
        contract = FailureContract(
            status="degraded",
            core_id="core_1",
            core_name="测试核心",
            criticality="critical",
            missing_capabilities=["A"],
            fallback_active="B",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=True,
            reason="test",
        )
        assert contract.is_degraded() is True
        contract.status = "failed"
        assert contract.is_degraded() is False


class TestFailureContractGenerator:
    """测试 FailureContractGenerator 类"""

    def test_create_generator(self):
        """生成器实例化"""
        generator = FailureContractGenerator()
        assert generator is not None

    def test_generate_ok_status(self):
        """生成 ok 状态的 contract"""
        generator = FailureContractGenerator()
        contract = generator.generate(
            core_id="core_3_memory_vector_engine",
            status="ok",
            criticality="degradable",
        )
        assert contract.status == "ok"
        assert contract.is_ok() is True
        assert contract.missing_capabilities == []
        assert contract.fallback_active == ""
        assert contract.auto_recovery_in_progress is False

    def test_generate_degraded_status(self):
        """生成 degraded 状态的 contract"""
        generator = FailureContractGenerator()
        contract = generator.generate(
            core_id="core_3_memory_vector_engine",
            status="degraded",
            criticality="degradable",
            reason="服务超时",
        )
        assert contract.status == "degraded"
        assert contract.is_degraded() is True
        assert len(contract.missing_capabilities) > 0
        assert "降级" in contract.fallback_active

    def test_generate_failed_status(self):
        """生成 failed 状态的 contract"""
        generator = FailureContractGenerator()
        contract = generator.generate(
            core_id="core_1_main_consciousness",
            status="failed",
            criticality="critical",
            reason="API 密钥失效",
            auto_recovery=False,
            user_action_required=True,
        )
        assert contract.status == "failed"
        assert contract.is_failed() is True
        assert contract.auto_recovery_in_progress is False
        assert contract.user_action_required is True

    def test_generate_down_converts_to_failed(self):
        """down 状态转换为 failed"""
        generator = FailureContractGenerator()
        contract = generator.generate(
            core_id="core_4_text_compressor",
            status="down",
            criticality="optional",
            reason="进程退出",
        )
        assert contract.status == "failed"

    def test_get_core_name(self):
        """获取核心人类可读名称"""
        generator = FailureContractGenerator()
        name = generator.get_core_name("core_1_main_consciousness")
        assert name == "主意识引擎"

    def test_get_missing_capabilities(self):
        """获取核心缺失能力列表"""
        generator = FailureContractGenerator()
        caps = generator.get_missing_capabilities("core_3_memory_vector_engine")
        assert isinstance(caps, list)
        assert len(caps) > 0
        assert "语义相似度检索" in caps

    def test_unknown_core_id(self):
        """未知 core_id 时的默认行为"""
        generator = FailureContractGenerator()
        contract = generator.generate(
            core_id="unknown_core",
            status="degraded",
            criticality="optional",
        )
        assert contract.core_id == "unknown_core"
        assert contract.core_name == "unknown_core"
        assert contract.missing_capabilities == []


class TestRenderFailureMd:
    """测试 render_failure_md 函数"""

    def test_render_degraded(self):
        """渲染 degraded 状态的 markdown"""
        contract = FailureContract(
            status="degraded",
            core_id="core_3_memory_vector_engine",
            core_name="记忆向量引擎",
            criticality="degradable",
            missing_capabilities=["语义相似度检索", "L2.5 记忆召回"],
            fallback_active="降级到 L1 关键词匹配",
            auto_recovery_in_progress=True,
            estimated_recovery="30 秒",
            user_action_required=False,
            reason="服务响应超时",
        )
        md = render_failure_md(contract)
        assert "# FAILURE:" in md
        assert "记忆向量引擎" in md
        assert "语义相似度检索" in md
        assert "降级到 L1 关键词匹配" in md
        assert "30 秒" in md

    def test_render_failed_critical(self):
        """渲染 critical 核心 failed 状态"""
        contract = FailureContract(
            status="failed",
            core_id="core_1_main_consciousness",
            core_name="主意识引擎",
            criticality="critical",
            missing_capabilities=["高层推理", "复杂决策"],
            fallback_active="完全降级到 v2 规则引擎",
            auto_recovery_in_progress=False,
            estimated_recovery="需人工干预",
            user_action_required=True,
            reason="API 服务不可达",
        )
        md = render_failure_md(contract)
        assert "关键核心失败" in md
        assert "需人工干预" in md

    def test_render_with_custom_time(self):
        """自定义生成时间"""
        custom_time = datetime(2024, 1, 15, 10, 30, 0, tzinfo=CST)
        contract = FailureContract(
            status="degraded",
            core_id="core_1",
            core_name="测试核心",
            criticality="optional",
            missing_capabilities=["A"],
            fallback_active="B",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=False,
            reason="test",
        )
        md = render_failure_md(contract, generated_at=custom_time)
        assert "2024-01-15 10:30:00" in md

    def test_render_contains_all_fields(self):
        """markdown 包含所有关键字段"""
        contract = FailureContract(
            status="failed",
            core_id="core_7_pii_redact",
            core_name="PII 脱敏引擎",
            criticality="optional",
            missing_capabilities=["敏感信息识别"],
            fallback_active="降级到正则匹配",
            auto_recovery_in_progress=True,
            estimated_recovery="10 秒",
            user_action_required=False,
            reason="模块导入失败",
        )
        md = render_failure_md(contract)
        assert "core_7_pii_redact" in md
        assert "PII 脱敏引擎" in md
        assert "敏感信息识别" in md
        assert "正则匹配" in md
        assert "10 秒" in md


class TestFileOperations:
    """测试 FAILURE.md 文件操作"""

    def test_write_failure_md(self, tmp_path):
        """写入 FAILURE.md"""
        # 临时修改目录
        original_dir = CORE_REGISTRY_DIR
        import mark42_modules.failure_contract as fc

        fc.CORE_REGISTRY_DIR = tmp_path

        contract = FailureContract(
            status="degraded",
            core_id="test_core",
            core_name="测试核心",
            criticality="optional",
            missing_capabilities=["测试能力"],
            fallback_active="测试兜底",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=False,
            reason="测试",
        )

        path = write_failure_md("test_core", contract)
        assert path.exists()
        assert path.name == "FAILURE.md"

        content = path.read_text(encoding="utf-8")
        assert "测试核心" in content

        # 恢复
        fc.CORE_REGISTRY_DIR = original_dir

    def test_remove_failure_md(self, tmp_path):
        """删除 FAILURE.md"""
        import mark42_modules.failure_contract as fc

        original_dir = CORE_REGISTRY_DIR
        fc.CORE_REGISTRY_DIR = tmp_path

        contract = FailureContract(
            status="degraded",
            core_id="test_core",
            core_name="测试核心",
            criticality="optional",
            missing_capabilities=["A"],
            fallback_active="B",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=False,
            reason="test",
        )
        write_failure_md("test_core", contract)

        result = remove_failure_md("test_core")
        assert result is True
        assert not (tmp_path / "test_core" / "FAILURE.md").exists()

        # 再次删除应该返回 False
        result = remove_failure_md("test_core")
        assert result is False

        fc.CORE_REGISTRY_DIR = original_dir

    def test_failure_md_exists(self, tmp_path):
        """检查 FAILURE.md 是否存在"""
        import mark42_modules.failure_contract as fc

        original_dir = CORE_REGISTRY_DIR
        fc.CORE_REGISTRY_DIR = tmp_path

        assert failure_md_exists("test_core") is False

        contract = FailureContract(
            status="degraded",
            core_id="test_core",
            core_name="测试核心",
            criticality="optional",
            missing_capabilities=["A"],
            fallback_active="B",
            auto_recovery_in_progress=True,
            estimated_recovery="10s",
            user_action_required=False,
            reason="test",
        )
        write_failure_md("test_core", contract)

        assert failure_md_exists("test_core") is True

        fc.CORE_REGISTRY_DIR = original_dir


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_create_contract_for_core_critical_failed(self):
        """critical 核心 failed 状态"""
        contract = create_contract_for_core(
            core_id="core_1_main_consciousness",
            status="failed",
            criticality="critical",
            reason="API 服务不可用",
        )
        assert contract.status == "failed"
        assert contract.criticality == "critical"
        assert contract.user_action_required is True
        assert contract.auto_recovery_in_progress is False
        assert contract.estimated_recovery == "需人工干预"

    def test_create_contract_for_core_degradable_degraded(self):
        """degradable 核心 degraded 状态"""
        contract = create_contract_for_core(
            core_id="core_3_memory_vector_engine",
            status="degraded",
            criticality="degradable",
            reason="响应超时",
        )
        assert contract.status == "degraded"
        assert contract.criticality == "degradable"
        assert contract.user_action_required is False
        assert contract.auto_recovery_in_progress is True
        assert contract.estimated_recovery == "30 秒"

    def test_create_contract_for_core_optional_down(self):
        """optional 核心 down 状态"""
        contract = create_contract_for_core(
            core_id="core_4_text_compressor",
            status="down",
            criticality="optional",
            reason="进程退出",
        )
        assert contract.status == "failed"  # down 转换为 failed
        assert contract.criticality == "optional"
        assert contract.auto_recovery_in_progress is True
        assert contract.estimated_recovery == "10 秒"


class TestCoreFailureConfig:
    """测试 8 个核心的预定义配置"""

    def test_all_8_cores_configured(self):
        """8 个核心都有配置"""
        assert len(CORE_FAILURE_CONFIG) == 8

    def test_each_core_has_name(self):
        """每个核心都有 human-readable name"""
        for core_id, config in CORE_FAILURE_CONFIG.items():
            assert "core_name" in config
            assert isinstance(config["core_name"], str)
            assert len(config["core_name"]) > 0

    def test_each_core_has_missing_capabilities(self):
        """每个核心都有缺失能力列表"""
        for core_id, config in CORE_FAILURE_CONFIG.items():
            assert "missing_capabilities" in config
            assert isinstance(config["missing_capabilities"], list)
            assert len(config["missing_capabilities"]) > 0

    def test_each_core_has_fallbacks(self):
        """每个核心都有 fallback 配置"""
        for core_id, config in CORE_FAILURE_CONFIG.items():
            assert "fallbacks" in config
            assert isinstance(config["fallbacks"], dict)
            assert "degraded" in config["fallbacks"]
            assert "failed" in config["fallbacks"]
