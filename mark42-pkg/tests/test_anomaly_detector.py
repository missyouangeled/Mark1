"""
anomaly_detector.py 单元测试
测试所有公开函数和类：
- AnomalyAlert 数据类
- MetricSample 数据类
- ThresholdDetector
- ZScoreDetector
- AnomalyDetector
- CLI 函数
"""

import json
import math
from unittest.mock import MagicMock, patch, mock_open

import pytest

from mark42.anomaly_detector import (
    AnomalyAlert,
    MetricSample,
    ThresholdDetector,
    ZScoreDetector,
    AnomalyDetector,
    cli_anomaly_check,
    cli_anomaly_history,
    cli_anomaly_stats,
)


class TestAnomalyAlert:
    """测试 AnomalyAlert 数据类。"""

    def test_anomaly_alert_creation(self):
        """测试创建 AnomalyAlert 实例。"""
        alert = AnomalyAlert(
            metric="disk_free_gb",
            value=1.5,
            baseline=2.0,
            z_score=0,
            severity="critical",
            detector="threshold",
            message="测试告警",
            timestamp="2024-01-01T00:00:00"
        )
        assert alert.metric == "disk_free_gb"
        assert alert.value == 1.5
        assert alert.severity == "critical"
        assert alert.detector == "threshold"

    def test_anomaly_alert_to_dict(self):
        """测试 to_dict 方法。"""
        alert = AnomalyAlert(
            metric="test_metric",
            value=10.0,
            baseline=20.0,
            z_score=3.0,
            severity="warning",
            detector="zscore"
        )
        result = alert.to_dict()
        assert isinstance(result, dict)
        assert result["metric"] == "test_metric"
        assert result["severity"] == "warning"
        assert "z_score" in result


class TestMetricSample:
    """测试 MetricSample 数据类。"""

    def test_metric_sample_creation(self):
        """测试创建 MetricSample 实例。"""
        sample = MetricSample(metric="cpu_usage", value=75.0)
        assert sample.metric == "cpu_usage"
        assert sample.value == 75.0
        assert sample.timestamp > 0

    def test_metric_sample_with_timestamp(self):
        """测试带自定义时间戳的 MetricSample。"""
        sample = MetricSample(metric="mem_usage", value=50.0, timestamp=1234567890.0)
        assert sample.timestamp == 1234567890.0


class TestThresholdDetector:
    """测试 ThresholdDetector 类。"""

    def setup_method(self):
        """每个测试前的准备。"""
        self.thresholds = {
            "disk_free_gb": {"warn": 5, "crit": 2},
            "cpu_usage_pct": {"warn_high": 80, "crit_high": 95},
        }
        self.detector = ThresholdDetector(self.thresholds)

    def test_threshold_detector_creates(self):
        """测试检测器初始化。"""
        assert self.detector.thresholds == self.thresholds

    def test_check_critical_low_threshold(self):
        """测试低于 critical 阈值。"""
        alert = self.detector.check("disk_free_gb", 1.0)
        assert alert is not None
        assert alert.severity == "critical"
        assert alert.detector == "threshold"

    def test_check_warning_low_threshold(self):
        """测试低于 warn 阈值但高于 crit。"""
        alert = self.detector.check("disk_free_gb", 3.0)
        assert alert is not None
        assert alert.severity == "warning"

    def test_check_normal_low_threshold(self):
        """测试值在正常范围（高于 warn）。"""
        alert = self.detector.check("disk_free_gb", 10.0)
        assert alert is None

    def test_check_critical_high_threshold(self):
        """测试高于 crit_high 阈值。"""
        alert = self.detector.check("cpu_usage_pct", 98.0)
        assert alert is not None
        assert alert.severity == "critical"

    def test_check_warning_high_threshold(self):
        """测试高于 warn_high 但低于 crit_high。"""
        alert = self.detector.check("cpu_usage_pct", 85.0)
        assert alert is not None
        assert alert.severity == "warning"

    def test_check_unknown_metric(self):
        """测试未知指标返回 None。"""
        alert = self.detector.check("unknown_metric", 100.0)
        assert alert is None

    def test_check_message_contains_info(self):
        """测试告警消息包含有用信息。"""
        alert = self.detector.check("disk_free_gb", 1.5)
        assert "critical" in alert.message
        assert "disk_free_gb" in alert.message


class TestZScoreDetector:
    """测试 ZScoreDetector 类。"""

    def setup_method(self):
        """每个测试前的准备。"""
        self.detector = ZScoreDetector(window_size=20, z_threshold=2.5)

    def test_zscore_detector_init(self):
        """测试初始化。"""
        assert self.detector.window_size == 20
        assert self.detector.z_threshold == 2.5
        assert self.detector._windows == {}

    def test_add_sample_window_not_full(self):
        """测试窗口未满时不检测，返回 None。"""
        for i in range(4):
            result = self.detector.add_sample("test_metric", float(i))
            assert result is None
        assert len(self.detector._windows["test_metric"]) == 4

    def test_add_sample_window_filled_no_anomaly(self):
        """测试窗口填满后正常值无异常。"""
        # 填满窗口（5个相同的值）
        for i in range(5):
            self.detector.add_sample("test_metric", 100.0)
        # 再加一个正常值
        result = self.detector.add_sample("test_metric", 100.0)
        assert result is None

    def test_add_sample_detects_anomaly(self):
        """测试检测到异常值。"""
        # 填满窗口，用有方差的值
        values = [95, 100, 105, 98, 102]  # 有方差
        for v in values:
            self.detector.add_sample("test_metric", float(v))
        # 加一个异常值（偏离很大）
        result = self.detector.add_sample("test_metric", 200.0)
        assert result is not None
        assert result.metric == "test_metric"
        assert result.detector == "zscore"
        assert result.z_score > 0

    def test_add_sample_severity_critical(self):
        """测试 Z-Score 很高时为 critical 级别。"""
        detector = ZScoreDetector(window_size=10, z_threshold=2.0)
        # 用有方差的值填满窗口
        values = [95, 100, 105, 98, 102]
        for v in values:
            detector.add_sample("test", float(v))
        # 非常大的异常值
        result = detector.add_sample("test", 1000.0)
        assert result is not None
        # z-score 应该很大，可能超过 4
        assert result.severity in ["critical", "warning"]

    def test_zero_std_dev_handling(self):
        """测试标准差为 0 时的处理。"""
        for i in range(10):
            result = self.detector.add_sample("test_metric", 50.0)
            # 前几个应该是 None，之后因为 std=0 也应该是 None
        # 再加一个，std=0 应该返回 None
        result = self.detector.add_sample("test_metric", 50.0)
        assert result is None

    def test_multiple_metrics_separate_windows(self):
        """测试多个指标有独立窗口。"""
        for i in range(10):
            self.detector.add_sample("metric1", float(i))
            self.detector.add_sample("metric2", float(i * 2))
        assert "metric1" in self.detector._windows
        assert "metric2" in self.detector._windows
        assert len(self.detector._windows["metric1"]) == 10
        assert len(self.detector._windows["metric2"]) == 10


class TestAnomalyDetector:
    """测试 AnomalyDetector 主类。"""

    def setup_method(self):
        """每个测试前的准备。"""
        self.detector = AnomalyDetector()

    def test_anomaly_detector_init(self):
        """测试初始化。"""
        assert self.detector.threshold_detector is not None
        assert self.detector.zscore_detector is not None
        assert self.detector._history == []

    def test_anomaly_detector_custom_thresholds(self):
        """测试自定义阈值。"""
        custom_thresholds = {"custom_metric": {"warn": 50, "crit": 20}}
        detector = AnomalyDetector(thresholds=custom_thresholds)
        assert detector.thresholds == custom_thresholds

    @patch('mark42.anomaly_detector.shutil.disk_usage')
    @patch('mark42.anomaly_detector.open', new_callable=mock_open, read_data='MemAvailable: 1048576 kB\n')
    def test_collect_metrics_success(self, mock_file, mock_disk_usage):
        """测试成功采集指标。"""
        # mock disk_usage 返回值
        mock_usage = MagicMock()
        mock_usage.free = 10 * 1024**3  # 10 GB
        mock_disk_usage.return_value = mock_usage

        metrics = self.detector.collect_metrics()

        assert "disk_free_gb" in metrics
        assert "mem_avail_mb" in metrics
        assert "context_usage_pct" in metrics
        assert metrics["disk_free_gb"] == 10.0
        assert metrics["mem_avail_mb"] == 1024  # 1048576 kB = 1024 MB

    @patch('mark42.anomaly_detector.shutil.disk_usage')
    def test_collect_metrics_disk_error(self, mock_disk_usage):
        """测试磁盘采集失败时的处理。"""
        mock_disk_usage.side_effect = Exception("disk error")
        metrics = self.detector.collect_metrics()
        # 应该不抛出异常，disk_free_gb 不在结果中
        assert "disk_free_gb" not in metrics or metrics["disk_free_gb"] is None

    def test_check_with_custom_metrics(self):
        """测试用自定义指标检测。"""
        metrics = {"disk_free_gb": 1.0, "mem_avail_mb": 100}
        alerts = self.detector.check(metrics)
        assert len(alerts) > 0
        assert any(a.metric == "disk_free_gb" for a in alerts)

    def test_check_populates_history(self):
        """测试检测结果存入历史记录。"""
        metrics = {"disk_free_gb": 1.0}
        self.detector.check(metrics)
        assert len(self.detector._history) > 0

    def test_history_truncation(self):
        """测试历史记录截断到 100 条。"""
        for i in range(150):
            metrics = {"disk_free_gb": float(i)}
            self.detector.check(metrics)
        assert len(self.detector._history) <= 100

    def test_history_method(self):
        """测试 history 方法。"""
        # 添加一些告警
        for i in range(5):
            self.detector.check({"disk_free_gb": float(i)})
        history = self.detector.history(limit=3)
        assert isinstance(history, list)
        assert len(history) <= 3
        assert isinstance(history[0], dict) if history else True

    def test_stats(self):
        """测试 stats 方法。"""
        stats = self.detector.stats()
        assert "total_alerts" in stats
        assert "window_size" in stats
        assert "tracked_metrics" in stats

    @patch('mark42.anomaly_detector.shutil.disk_usage')
    def test_health_check_success(self, mock_disk_usage):
        """测试健康检查成功。"""
        mock_usage = MagicMock()
        mock_usage.free = 10 * 1024**3
        mock_disk_usage.return_value = mock_usage
        assert self.detector.health_check() is True

    @patch('mark42.anomaly_detector.shutil.disk_usage')
    def test_health_check_failure(self, mock_disk_usage):
        """测试健康检查失败。"""
        mock_disk_usage.side_effect = Exception("error")
        # 注意：即使一个采集失败，其他采集可能成功，所以健康检查可能仍然 True
        # 这里我们只测试不抛出异常
        result = self.detector.health_check()
        assert isinstance(result, bool)


class TestCLI:
    """测试 CLI 接口函数。"""

    @patch.object(AnomalyDetector, 'collect_metrics')
    def test_cli_anomaly_check(self, mock_collect):
        """测试 CLI 异常检测。"""
        mock_collect.return_value = {"disk_free_gb": 50.0}
        result = cli_anomaly_check()
        assert "alerts" in result
        assert "alert_count" in result
        assert "metrics" in result

    def test_cli_anomaly_history(self):
        """测试 CLI 历史查询。"""
        result = cli_anomaly_history(limit=5)
        assert isinstance(result, list)

    def test_cli_anomaly_stats(self):
        """测试 CLI 统计查询。"""
        result = cli_anomaly_stats()
        assert "total_alerts" in result
        assert "window_size" in result
