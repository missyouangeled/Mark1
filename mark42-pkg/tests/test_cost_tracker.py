"""
cost_tracker.py 单元测试

测试覆盖:
- 成本记录（token 数、模型名、耗时）
- 统计汇总（日/周/总）
- 报告生成
- 数据持久化（文件存储）
- 所有公开函数
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# 导入待测试模块
from mark42.cost_tracker import (
    CostRecord,
    CostTracker,
    record_cost,
    MODEL_PRICING,
    COSTS_FILE,
)


class TestCostRecord:
    """测试 CostRecord 数据类"""

    def test_cost_record_creation(self):
        """测试创建成本记录"""
        record = CostRecord(
            timestamp="2026-07-29T10:00:00+00:00",
            model="doubao-seed-2.0-pro",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            cost_cny=0.01,
            caller_module="test_module",
        )
        assert record.model == "doubao-seed-2.0-pro"
        assert record.prompt_tokens == 1000
        assert record.cost_cny == 0.01

    def test_cost_record_to_dict(self):
        """测试 to_dict 方法"""
        record = CostRecord(
            timestamp="2026-07-29T10:00:00+00:00",
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_cny=0.001,
        )
        result = record.to_dict()
        assert result["model"] == "test-model"
        assert result["prompt_tokens"] == 100
        assert result["cost_cny"] == 0.001


class TestModelPricing:
    """测试模型定价表"""

    def test_pricing_has_doubao(self):
        """测试 doubao 定价存在"""
        assert "doubao-seed-2.0-pro" in MODEL_PRICING
        assert MODEL_PRICING["doubao-seed-2.0-pro"]["input"] == 0.004
        assert MODEL_PRICING["doubao-seed-2.0-pro"]["output"] == 0.012

    def test_pricing_has_glm(self):
        """测试 glm 定价存在"""
        assert "glm-5.2" in MODEL_PRICING
        assert MODEL_PRICING["glm-5.2"]["input"] == 0.002
        assert MODEL_PRICING["glm-5.2"]["output"] == 0.006

    def test_pricing_has_default(self):
        """测试默认定价存在"""
        assert "default" in MODEL_PRICING


class TestCostTracker:
    """测试 CostTracker 成本追踪器类"""

    def test_tracker_creation(self, tmp_path):
        """测试创建 CostTracker"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        assert tracker.costs_file == test_file

    def test_tracker_creates_parent_dir(self, tmp_path, mocker):
        """测试自动创建父目录"""
        mock_mkdir = mocker.patch("pathlib.Path.mkdir")
        test_file = tmp_path / "subdir" / "costs.jsonl"
        CostTracker(costs_file=test_file)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_record_calculates_cost_correctly_doubao(self, tmp_path):
        """测试 doubao 模型成本计算正确"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        # doubao: 输入 0.004/千tokens, 输出 0.012/千tokens
        # 1000 输入 = 0.004, 500 输出 = 0.006, 总计 0.01
        record = tracker.record(
            model="doubao-seed-2.0-pro",
            prompt_tokens=1000,
            completion_tokens=500,
            caller_module="test",
        )
        
        assert record.total_tokens == 1500
        assert abs(record.cost_cny - 0.01) < 0.0001  # 浮点数比较

    def test_record_calculates_cost_correctly_glm(self, tmp_path):
        """测试 glm 模型成本计算正确"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        # glm: 输入 0.002/千tokens, 输出 0.006/千tokens
        # 1000 输入 = 0.002, 500 输出 = 0.003, 总计 0.005
        record = tracker.record(
            model="glm-5.2",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        
        assert abs(record.cost_cny - 0.005) < 0.0001

    def test_record_uses_default_pricing_for_unknown_model(self, tmp_path):
        """测试未知模型使用默认定价"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        record = tracker.record(
            model="unknown-model-xyz",
            prompt_tokens=1000,
            completion_tokens=500,
        )
        
        # 默认 = doubao 价格 = 0.01
        assert abs(record.cost_cny - 0.01) < 0.0001

    def test_record_writes_to_file(self, tmp_path):
        """测试记录写入文件"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        tracker.record(
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            caller_module="test",
        )
        
        # 验证文件内容
        content = test_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["model"] == "test-model"
        assert data["prompt_tokens"] == 100

    def test_record_multiple_entries(self, tmp_path):
        """测试多条记录都被写入"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        tracker.record("model-a", 100, 50)
        tracker.record("model-b", 200, 100)
        tracker.record("model-c", 300, 150)
        
        content = test_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3

    def test_load_all_empty_file(self, tmp_path):
        """测试空文件时返回空列表"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        result = tracker._load_all()
        assert result == []

    def test_load_all_nonexistent_file(self, tmp_path):
        """测试文件不存在时返回空列表"""
        test_file = tmp_path / "nonexistent.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        result = tracker._load_all()
        assert result == []

    def test_load_all_with_data(self, tmp_path):
        """测试加载已有数据"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        tracker.record("test-model", 100, 50)
        tracker.record("test-model", 200, 100)
        
        records = tracker._load_all()
        assert len(records) == 2
        assert records[0]["prompt_tokens"] == 100
        assert records[1]["prompt_tokens"] == 200

    def test_load_all_skips_invalid_json(self, tmp_path):
        """测试跳过无效 JSON 行"""
        test_file = tmp_path / "costs.jsonl"
        # 写入混合有效和无效的 JSON
        test_file.write_text(
            '{"model":"valid","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.001,"timestamp":"2026-07-29"}\n'
            'invalid json line\n'
            '{"model":"valid2","prompt_tokens":200,"completion_tokens":100,"total_tokens":300,"cost_cny":0.002,"timestamp":"2026-07-29"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        records = tracker._load_all()
        
        # 只加载有效的 2 条
        assert len(records) == 2

    def test_get_daily_summary_empty(self, tmp_path):
        """测试无数据时的日报"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        summary = tracker.get_daily_summary("2026-07-29")
        
        assert summary["total_calls"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_cost"] == 0
        assert summary["by_model"] == {}

    def test_get_daily_summary_with_data(self, tmp_path):
        """测试有数据时的日报"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        # 同一天的两条记录
        tracker.record("model-a", 100, 50)  # 同一天
        tracker.record("model-b", 200, 100)  # 同一天
        
        # 获取今天的汇总（用 timestamp 中的日期）
        # 先读取实际的日期
        records = tracker._load_all()
        today = records[0]["timestamp"][:10]
        
        summary = tracker.get_daily_summary(today)
        
        assert summary["total_calls"] == 2
        assert summary["total_tokens"] == 450  # 150 + 300
        assert summary["total_cost"] > 0
        assert len(summary["by_model"]) == 2

    def test_get_daily_summary_filters_by_date(self, tmp_path):
        """测试日报只统计指定日期的数据"""
        test_file = tmp_path / "costs.jsonl"
        
        # 直接写入不同日期的记录
        test_file.write_text(
            '{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.001,"timestamp":"2026-07-28T10:00:00"}\n'
            '{"model":"b","prompt_tokens":200,"completion_tokens":100,"total_tokens":300,"cost_cny":0.002,"timestamp":"2026-07-29T10:00:00"}\n'
            '{"model":"c","prompt_tokens":300,"completion_tokens":150,"total_tokens":450,"cost_cny":0.003,"timestamp":"2026-07-29T11:00:00"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        summary = tracker.get_daily_summary("2026-07-29")
        
        assert summary["total_calls"] == 2  # 只算 29 号的
        assert summary["total_tokens"] == 750  # 300 + 450

    def test_get_monthly_summary_empty(self, tmp_path):
        """测试无数据时的月报"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        summary = tracker.get_monthly_summary("2026-07")
        
        assert summary["total_calls"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_cost"] == 0
        assert summary["by_day"] == {}

    def test_get_monthly_summary_with_data(self, tmp_path):
        """测试有数据时的月报"""
        test_file = tmp_path / "costs.jsonl"
        test_file.write_text(
            '{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.001,"timestamp":"2026-07-01T10:00:00"}\n'
            '{"model":"b","prompt_tokens":200,"completion_tokens":100,"total_tokens":300,"cost_cny":0.002,"timestamp":"2026-07-15T10:00:00"}\n'
            '{"model":"c","prompt_tokens":300,"completion_tokens":150,"total_tokens":450,"cost_cny":0.003,"timestamp":"2026-07-15T11:00:00"}\n'
            '{"model":"d","prompt_tokens":400,"completion_tokens":200,"total_tokens":600,"cost_cny":0.004,"timestamp":"2026-08-01T10:00:00"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        summary = tracker.get_monthly_summary("2026-07")
        
        assert summary["total_calls"] == 3  # 7 月有 3 条
        assert summary["total_tokens"] == 900  # 150 + 300 + 450
        assert len(summary["by_day"]) == 2  # 1号和15号两天

    def test_get_top_callers_empty(self, tmp_path):
        """测试无数据时的调用方排名"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        result = tracker.get_top_callers()
        assert result == []

    def test_get_top_callers_with_data(self, tmp_path):
        """测试按调用方统计"""
        test_file = tmp_path / "costs.jsonl"
        test_file.write_text(
            '{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.01,"timestamp":"2026-07-29T10:00:00","caller_module":"module-a"}\n'
            '{"model":"b","prompt_tokens":200,"completion_tokens":100,"total_tokens":300,"cost_cny":0.02,"timestamp":"2026-07-29T10:00:00","caller_module":"module-a"}\n'
            '{"model":"c","prompt_tokens":300,"completion_tokens":150,"total_tokens":450,"cost_cny":0.05,"timestamp":"2026-07-29T10:00:00","caller_module":"module-b"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        top = tracker.get_top_callers()
        
        assert len(top) == 2
        # module-b 成本更高 (0.05)，应该排第一
        assert top[0]["module"] == "module-b"
        assert top[0]["calls"] == 1
        assert top[0]["cost"] == 0.05
        assert top[1]["module"] == "module-a"
        assert top[1]["calls"] == 2
        assert top[1]["cost"] == 0.03

    def test_get_top_callers_n_parameter(self, tmp_path):
        """测试 n 参数限制返回数量"""
        test_file = tmp_path / "costs.jsonl"
        # 创建 5 个不同的调用方，每个成本不同
        lines = []
        for i in range(5):
            lines.append(f'{{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.0{i+1},"timestamp":"2026-07-29T10:00:00","caller_module":"module-{i}"}}')
        test_file.write_text("\n".join(lines) + "\n")
        
        tracker = CostTracker(costs_file=test_file)
        top = tracker.get_top_callers(n=3)
        
        assert len(top) == 3

    def test_get_top_callers_handles_unknown_module(self, tmp_path):
        """测试缺少 caller_module 时标记为 unknown"""
        test_file = tmp_path / "costs.jsonl"
        test_file.write_text(
            '{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.01,"timestamp":"2026-07-29T10:00:00"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        top = tracker.get_top_callers()
        
        assert len(top) == 1
        assert top[0]["module"] == "unknown"

    def test_export_csv(self, tmp_path):
        """测试导出 CSV 功能"""
        test_file = tmp_path / "costs.jsonl"
        test_file.write_text(
            '{"model":"a","prompt_tokens":100,"completion_tokens":50,"total_tokens":150,"cost_cny":0.001,"timestamp":"2026-07-20T10:00:00","caller_module":"mod1"}\n'
            '{"model":"b","prompt_tokens":200,"completion_tokens":100,"total_tokens":300,"cost_cny":0.002,"timestamp":"2026-07-25T10:00:00","caller_module":"mod2"}\n'
            '{"model":"c","prompt_tokens":300,"completion_tokens":150,"total_tokens":450,"cost_cny":0.003,"timestamp":"2026-07-30T10:00:00","caller_module":"mod3"}\n'
        )
        
        tracker = CostTracker(costs_file=test_file)
        output_path = tmp_path / "export.csv"
        count = tracker.export_csv("2026-07-20", "2026-07-25", str(output_path))
        
        assert count == 2  # 范围内有 2 条
        assert output_path.exists()
        content = output_path.read_text()
        assert "model" in content
        assert "prompt_tokens" in content
        assert "caller_module" in content

    def test_summarize_helper(self, tmp_path):
        """测试 _summarize 辅助函数"""
        test_file = tmp_path / "costs.jsonl"
        tracker = CostTracker(costs_file=test_file)
        
        records = [
            {"model": "a", "total_tokens": 100, "cost_cny": 0.01},
            {"model": "b", "total_tokens": 200, "cost_cny": 0.02},
            {"model": "a", "total_tokens": 150, "cost_cny": 0.015},
        ]
        
        summary = tracker._summarize(records, "test")
        
        assert summary["label"] == "test"
        assert summary["total_calls"] == 3
        assert summary["total_tokens"] == 450
        assert abs(summary["total_cost"] - 0.045) < 0.0001
        assert len(summary["by_model"]) == 2
        assert summary["by_model"]["a"]["calls"] == 2
        assert summary["by_model"]["a"]["tokens"] == 250
        assert summary["by_model"]["b"]["calls"] == 1

    def test_record_write_failure_logged(self, tmp_path, mocker):
        """测试写入失败时记录日志，不抛异常"""
        mock_log = mocker.patch("mark42.cost_tracker.logger.warning")
        test_file = tmp_path / "costs.jsonl"
        
        # mock open 来模拟写入失败
        mocker.patch("builtins.open", side_effect=OSError("disk full"))
        
        tracker = CostTracker(costs_file=test_file)
        
        # 不应抛异常
        record = tracker.record("test-model", 100, 50)
        assert record is not None  # 仍返回记录对象
        mock_log.assert_called_once()  # 应记录警告日志


class TestRecordCostFunction:
    """测试 record_cost 便捷函数"""

    def test_record_cost_creates_tracker(self, mocker):
        """测试 record_cost 内部创建 CostTracker"""
        mock_tracker_class = mocker.patch("mark42.cost_tracker.CostTracker")
        mock_instance = MagicMock()
        mock_instance.record.return_value = CostRecord(
            timestamp="2026-07-29", model="test",
            prompt_tokens=100, completion_tokens=50,
            total_tokens=150, cost_cny=0.001
        )
        mock_tracker_class.return_value = mock_instance
        
        result = record_cost("test-model", 100, 50, "test-module")
        
        mock_tracker_class.assert_called_once()
        mock_instance.record.assert_called_once_with(
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            caller_module="test-module",
        )
        assert result is not None
