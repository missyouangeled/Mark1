"""ArcLock 健康监控锁扣接口。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class HealthLock(Protocol):
    """系统健康监控锁扣。"""

    def check_health(self) -> dict[str, Any]:
        """返回当前系统健康状态。

        {"disk": ..., "memory": ..., "cpu": ..., "alerts": [...]}
        """
        ...
