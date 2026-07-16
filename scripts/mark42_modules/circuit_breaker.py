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
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class BreakerState:
    """单个熔断器的状态。"""
    core_id: str
    status: str = "closed"  # closed | open | half_open
    consecutive_failures: int = 0
    opened_at: Optional[float] = None   # time.monotonic() 时间戳
    half_open_at: Optional[float] = None
    recovery_timeout_s: float = 30.0     # 断路后 30s 半开试探
    failure_threshold: int = 3           # 连续失败 3 次断路

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_id": self.core_id,
            "status": self.status,
            "consecutive_failures": self.consecutive_failures,
            "opened_at": self.opened_at,
            "recovery_in_s": self._recovery_in_s(),
        }

    def _recovery_in_s(self) -> Optional[float]:
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

    def __init__(self):
        self._breakers: Dict[str, BreakerState] = {}

    def _get(self, core_id: str) -> BreakerState:
        if core_id not in self._breakers:
            self._breakers[core_id] = BreakerState(core_id=core_id)
        return self._breakers[core_id]

    def can_call(self, core_id: str) -> bool:
        """是否可以调用该核心（未断路或半开试探中）。"""
        b = self._get(core_id)

        if b.status == "closed":
            return True

        if b.status == "open":
            # 检查是否到了半开时间
            if b.opened_at and (time.monotonic() - b.opened_at) >= b.recovery_timeout_s:
                b.status = "half_open"
                b.half_open_at = time.monotonic()
                logger.info("熔断器 %s 半开试探", core_id)
                return True
            return False

        if b.status == "half_open":
            return True  # 半开只允许一次试探

        return True

    def record_success(self, core_id: str):
        """记录成功调用。"""
        b = self._get(core_id)
        if b.status != "closed":
            logger.info("熔断器 %s 恢复（%s -> closed）", core_id, b.status)
        b.status = "closed"
        b.consecutive_failures = 0
        b.opened_at = None
        b.half_open_at = None

    def record_failure(self, core_id: str, reason: str = ""):
        """记录失败调用。"""
        b = self._get(core_id)
        b.consecutive_failures += 1

        if b.status == "half_open":
            # 半开试探失败，重新断路
            b.status = "open"
            b.opened_at = time.monotonic()
            logger.warning("熔断器 %s 半开试探失败，重新断路: %s", core_id, reason)
            return

        if b.consecutive_failures >= b.failure_threshold and b.status == "closed":
            b.status = "open"
            b.opened_at = time.monotonic()
            logger.warning("熔断器 %s 断路（连续失败 %d 次）: %s",
                          core_id, b.consecutive_failures, reason)

    def get_state(self, core_id: str) -> Dict[str, Any]:
        """获取熔断器状态。"""
        # 先检查是否该半开
        self.can_call(core_id)
        return self._get(core_id).to_dict()

    def list_all(self) -> list[Dict[str, Any]]:
        """列出所有非 closed 熔断器状态。"""
        # 检查所有 open 状态是否该半开
        for core_id in list(self._breakers.keys()):
            self.can_call(core_id)
        return [b.to_dict() for b in self._breakers.values() if b.status != "closed"]

    def reset(self, core_id: str):
        """手动重置熔断器。"""
        b = self._get(core_id)
        b.status = "closed"
        b.consecutive_failures = 0
        b.opened_at = None
        b.half_open_at = None
        logger.info("熔断器 %s 手动重置", core_id)

    def reset_all(self):
        """重置所有熔断器。"""
        for core_id in list(self._breakers.keys()):
            self.reset(core_id)
