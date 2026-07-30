"""ArcLock 熔断器锁扣接口。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BreakerLock(Protocol):
    """熔断器锁扣。"""

    def can_call(self, key: str) -> bool:
        """当前是否可以调用。"""
        ...

    def record_success(self, key: str) -> None:
        """记录成功。"""
        ...

    def record_failure(self, key: str, reason: str = "") -> None:
        """记录失败。"""
        ...

    def status(self) -> dict[str, Any]:
        """所有熔断器状态。"""
        ...
