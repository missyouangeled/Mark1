"""ArcLock 健康监控锁扣接口。"""

from __future__ import annotations
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class HealthLock(Protocol):
    """系统健康监控锁扣。"""

    def check_health(self) -> Dict[str, Any]:
        """返回当前系统健康状态。

        {"disk": ..., "memory": ..., "cpu": ..., "alerts": [...]}
        """
        ...
