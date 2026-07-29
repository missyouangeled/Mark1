"""内置熔断器锁扣实现：包装 CircuitBreaker 类。"""

from __future__ import annotations
from typing import Any, Dict


class BuiltinBreaker:
    """将 CircuitBreaker 类包装为 BreakerLock 接口。"""

    def __init__(self):
        from ..circuit_breaker import CircuitBreaker
        self._impl = CircuitBreaker()

    def can_call(self, key: str) -> bool:
        return self._impl.can_call(key)

    def record_success(self, key: str) -> None:
        self._impl.record_success(key)

    def record_failure(self, key: str, reason: str = "") -> None:
        self._impl.record_failure(key, reason=reason)

    def status(self) -> Dict[str, Any]:
        states = self._impl.list_all()
        return {
            "breakers": states,
            "total": len(states),
        }
