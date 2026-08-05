"""
Mark42 v3 R-CAND-02 · Circuit Breaker 熔断器

按 v3 §0.4 候选原则 R-CAND-02 实现：
- 每个核心独立熔断器
- 连续失败 N 次后断路（默认 3 次）
- 断路后自动降级到 fallback
- 30 秒后半开试探，成功则恢复

状态机：closed（正常）-> open（断路）-> half_open（试探）-> closed/open
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@dataclass
class BreakerState:
    """单个熔断器的状态。"""
    core_id: str
    status: str = "closed"  # closed | open | half_open
    consecutive_failures: int = 0
    opened_at: float | None = None   # time.monotonic() 时间戳
    half_open_at: float | None = None
    probe_in_flight: bool = False    # 半开态是否已有一个试探请求在飞
    recovery_timeout_s: float = 30.0     # 断路后 30s 半开试探
    failure_threshold: int = 3           # 连续失败 3 次断路

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_id": self.core_id,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "opened_at": self.opened_at,
            "recovery_in_s": self._recovery_in_s(),
        }

    def _recovery_in_s(self) -> float | None:
        if self.status == "open" and self.opened_at:
            remaining = self.recovery_timeout_s - (time.monotonic() - self.opened_at)
            return round(max(0, remaining), 1)
        return None


class CircuitBreaker:
    """熔断器管理器（R-CAND-02）。

    为每个核心维护一个独立的 BreakerState。

    使用方式：
        cb = CircuitBreaker()
        if cb.can_call("core_2_armor_consciousness"):
            try:
                result = call_advisor()
                cb.record_success("core_2_armor_consciousness")
            except Exception:
                cb.record_failure("core_2_armor_consciousness")
        else:
            # 断路中，走 fallback
            result = fallback()

    状态机：
        closed -> 连续失败 >= threshold -> open
        open -> 等待 recovery_timeout_s -> half_open
        half_open -> 成功 -> closed
        half_open -> 失败 -> open（重置计时）
    """

    # 【P3-4】类级共享状态改为**显式声明**。
    # 原实现用 hasattr + type(self)._shared_xxx = ... 动态创建类属性，
    # 语义正确但 mypy 无法识别（4 处 attr-defined）。
    # 显式声明后语义完全等价：仍是类级共享，同进程所有实例共用。
    _shared_breakers: ClassVar[dict[str, BreakerState]] = {}
    _shared_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self):
        # 单例共享状态：同一进程内所有 CircuitBreaker() 实例共享 _breakers
        self._breakers = type(self)._shared_breakers
        # 保护半开试探名额的原子性（同进程多线程）
        self._lock = type(self)._shared_lock

    @classmethod
    def _reset_shared(cls):
        """重置共享状态（测试/混沌实验 cleanup 用）。"""
        if hasattr(cls, '_shared_breakers'):
            cls._shared_breakers.clear()

    def _get(self, core_id: str) -> BreakerState:
        if core_id not in self._breakers:
            self._breakers[core_id] = BreakerState(core_id=core_id)
        return self._breakers[core_id]

    def can_call(self, core_id: str) -> bool:
        """是否可以调用该核心（未断路或半开试探中）。

        半开态只放行**一个**试探请求：其余并发请求直接快速失败，
        避免恢复窗口结束瞬间大量请求同时打向还未恢复的下游（惊群）。
        """
        with self._lock:
            b = self._get(core_id)

            if b.status == "closed":
                return True

            if b.status == "open":
                # 检查是否到了半开时间
                if b.opened_at and (time.monotonic() - b.opened_at) >= b.recovery_timeout_s:
                    b.status = "half_open"
                    b.half_open_at = time.monotonic()
                    b.probe_in_flight = True     # 本次调用就是那一个试探
                    logger.info("熔断器 %s 半开试探", core_id)
                    return True
                return False

            if b.status == "half_open":
                # 已有试探在飞→拒绝；否则把试探名额交给本次调用
                if b.probe_in_flight:
                    return False
                b.probe_in_flight = True
                return True

            return True

    def record_success(self, core_id: str):
        """记录成功调用。"""
        with self._lock:
            b = self._get(core_id)
            if b.status != "closed":
                logger.info("熔断器 %s 恢复（%s -> closed）", core_id, b.status)
            b.status = "closed"
            b.consecutive_failures = 0
            b.opened_at = None
            b.half_open_at = None
            b.probe_in_flight = False

    def record_failure(self, core_id: str, reason: str = ""):
        """记录失败调用。"""
        with self._lock:
            b = self._get(core_id)
            b.consecutive_failures += 1

            if b.status == "half_open":
                # 半开试探失败，重新断路
                b.status = "open"
                b.opened_at = time.monotonic()
                b.probe_in_flight = False
                logger.warning("熔断器 %s 半开试探失败，重新断路: %s", core_id, reason)
                return

            if b.consecutive_failures >= b.failure_threshold and b.status == "closed":
                b.status = "open"
                b.opened_at = time.monotonic()
                b.probe_in_flight = False
                logger.warning("熔断器 %s 断路（连续失败 %d 次）: %s",
                              core_id, b.consecutive_failures, reason)

    def _refresh_recovery(self, core_id: str) -> None:
        """仅刷新 open -> half_open 的时间到期判定，**不**消耗试探名额。

        供 get_state / list_all 等只读观察调用使用；
        若直接调 can_call() 会把唯一试探名额误消耗在“看一眼状态”上。
        """
        with self._lock:
            b = self._get(core_id)
            if b.status == "open" and b.opened_at and \
                    (time.monotonic() - b.opened_at) >= b.recovery_timeout_s:
                b.status = "half_open"
                b.half_open_at = time.monotonic()
                b.probe_in_flight = False
                logger.info("熔断器 %s 进入半开窗口", core_id)

    def get_state(self, core_id: str) -> dict[str, Any]:
        """获取熔断器状态。"""
        # 先刷新是否该半开（不消耗试探名额）
        self._refresh_recovery(core_id)
        return self._get(core_id).to_dict()

    def list_all(self) -> list[dict[str, Any]]:
        """列出所有非 closed 熔断器状态。"""
        # 检查所有 open 状态是否该半开（不消耗试探名额）
        for core_id in list(self._breakers.keys()):
            self._refresh_recovery(core_id)
        return [b.to_dict() for b in self._breakers.values() if b.status != "closed"]

    def reset(self, core_id: str):
        """手动重置熔断器。"""
        with self._lock:
            b = self._get(core_id)
            b.status = "closed"
            b.consecutive_failures = 0
            b.opened_at = None
            b.half_open_at = None
            b.probe_in_flight = False
        logger.info("熔断器 %s 手动重置", core_id)

    def reset_all(self):
        """重置所有熔断器。"""
        for core_id in list(self._breakers.keys()):
            self.reset(core_id)
