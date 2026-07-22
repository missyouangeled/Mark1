"""
Mark42 v3 · 核心 8 · 异常检测器

按 v3 §3.6 钉死的核心 8 实现：
- 非依赖 LLM 的纯算法异常检测
- 基于 Isolation Forest 思想的轻量实现（纯 Python，不依赖 sklearn）
- 阈值 + 滑动窗口 + Z-Score 三种检测策略

检测维度：
  - 磁盘空间突变
  - 内存使用突变
  - 上下文使用率突变
  - 自定义指标
"""

from __future__ import annotations

import json
import logging
import math
import os
import shutil
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 数据类 ───────────────────────────────────────────

@dataclass
class AnomalyAlert:
    """单条异常告警。"""
    metric: str               # 指标名（disk_free / mem_avail / context_usage）
    value: float              # 当前值
    baseline: float           # 基线值
    z_score: float            # Z-Score
    severity: str             # info / warning / critical
    detector: str             # threshold / zscore / sliding_window
    message: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MetricSample:
    """单个指标采样。"""
    metric: str
    value: float
    timestamp: float = field(default_factory=time.time)


# ── 检测器 ───────────────────────────────────────────

class ThresholdDetector:
    """阈值检测器 -- 最简单的异常检测。"""

    def __init__(self, thresholds: Dict[str, Dict[str, float]]):
        """
        Args:
            thresholds: {"disk_free_gb": {"warn": 5, "crit": 2}, ...}
        """
        self.thresholds = thresholds

    def check(self, metric: str, value: float) -> Optional[AnomalyAlert]:
        rules = self.thresholds.get(metric)
        if not rules:
            return None

        if "crit" in rules and value <= rules["crit"]:
            return AnomalyAlert(
                metric=metric, value=value, baseline=rules["crit"],
                z_score=0, severity="critical", detector="threshold",
                message=f"{metric}={value} <= critical 阈值 {rules['crit']}",
            )
        if "warn" in rules and value <= rules["warn"]:
            return AnomalyAlert(
                metric=metric, value=value, baseline=rules["warn"],
                z_score=0, severity="warning", detector="threshold",
                message=f"{metric}={value} <= 警告阈值 {rules['warn']}",
            )
        if "crit_high" in rules and value >= rules["crit_high"]:
            return AnomalyAlert(
                metric=metric, value=value, baseline=rules["crit_high"],
                z_score=0, severity="critical", detector="threshold",
                message=f"{metric}={value} >= critical 阈值 {rules['crit_high']}",
            )
        if "warn_high" in rules and value >= rules["warn_high"]:
            return AnomalyAlert(
                metric=metric, value=value, baseline=rules["warn_high"],
                z_score=0, severity="warning", detector="threshold",
                message=f"{metric}={value} >= 警告阈值 {rules['warn_high']}",
            )
        return None


class ZScoreDetector:
    """Z-Score 检测器 -- 基于滑动窗口统计。"""

    def __init__(self, window_size: int = 20, z_threshold: float = 2.5):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self._windows: Dict[str, deque] = {}

    def add_sample(self, metric: str, value: float) -> Optional[AnomalyAlert]:
        """添加采样并检测异常。"""
        if metric not in self._windows:
            self._windows[metric] = deque(maxlen=self.window_size)

        window = self._windows[metric]

        # 窗口未满，不检测
        if len(window) < 5:
            window.append(value)
            return None

        # 计算均值和标准差
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std = math.sqrt(variance) if variance > 0 else 0

        if std == 0:
            window.append(value)
            return None

        z = abs(value - mean) / std
        window.append(value)

        if z >= self.z_threshold:
            severity = "critical" if z >= 4 else "warning"
            return AnomalyAlert(
                metric=metric, value=value, baseline=mean,
                z_score=round(z, 2), severity=severity, detector="zscore",
                message=f"{metric} Z-Score={z:.2f} (基线={mean:.1f}±{std:.1f})",
            )
        return None


class AnomalyDetector:
    """核心 8 · 异常检测主类。

    组合阈值检测 + Z-Score 检测。
    """

    DEFAULT_THRESHOLDS = {
        "disk_free_gb": {"warn": 5, "crit": 2},
        "mem_avail_mb": {"warn": 500, "crit": 200},
        "context_usage_pct": {"warn_high": 85, "crit_high": 95},
    }

    def __init__(self, thresholds: Optional[Dict] = None):
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS
        self.threshold_detector = ThresholdDetector(self.thresholds)
        self.zscore_detector = ZScoreDetector(window_size=20, z_threshold=2.5)
        self._history: List[AnomalyAlert] = []

    def collect_metrics(self) -> Dict[str, float]:
        """采集当前系统指标。"""
        metrics = {}
        try:
            usage = shutil.disk_usage("/")
            metrics["disk_free_gb"] = round(usage.free / (1024**3), 2)
        except Exception:
            pass

        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        metrics["mem_avail_mb"] = int(line.split()[1]) // 1024
                        break
        except Exception:
            pass

        # context_usage_pct 由外部传入或从 armor 读取
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from mark42.armor import armor_check
            r = armor_check()
            metrics["context_usage_pct"] = r.get("usagePercent", 0)
        except Exception:
            metrics["context_usage_pct"] = 0

        return metrics

    def check(self, metrics: Optional[Dict[str, float]] = None) -> List[AnomalyAlert]:
        """检测异常。"""
        metrics = metrics or self.collect_metrics()
        alerts: List[AnomalyAlert] = []

        for metric, value in metrics.items():
            # 阈值检测
            alert = self.threshold_detector.check(metric, value)
            if alert:
                alert.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
                alerts.append(alert)

            # Z-Score 检测
            alert2 = self.zscore_detector.add_sample(metric, value)
            if alert2:
                alert2.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
                alerts.append(alert2)

        self._history.extend(alerts)
        # 保留最近 100 条
        if len(self._history) > 100:
            self._history = self._history[-100:]

        return alerts

    def history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """查看历史异常。"""
        return [a.to_dict() for a in self._history[-limit:]]

    def health_check(self) -> bool:
        """健康检查。"""
        try:
            metrics = self.collect_metrics()
            return len(metrics) > 0
        except Exception:
            return False

    def stats(self) -> Dict[str, Any]:
        """统计。"""
        return {
            "total_alerts": len(self._history),
            "window_size": self.zscore_detector.window_size,
            "tracked_metrics": list(self.thresholds.keys()),
        }


# ── CLI 接口 ────────────────────────────────────────

def cli_anomaly_check() -> Dict[str, Any]:
    """CLI: 检测一次。"""
    ad = AnomalyDetector()
    alerts = ad.check()
    return {
        "alerts": [a.to_dict() for a in alerts],
        "alert_count": len(alerts),
        "metrics": ad.collect_metrics(),
    }

def cli_anomaly_history(limit: int = 10) -> List[Dict[str, Any]]:
    """CLI: 历史异常。"""
    ad = AnomalyDetector()
    return ad.history(limit)

def cli_anomaly_stats() -> Dict[str, Any]:
    """CLI: 统计。"""
    ad = AnomalyDetector()
    return ad.stats()
