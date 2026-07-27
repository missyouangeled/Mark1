"""ArcLock 循环引擎锁扣接口。"""

from __future__ import annotations
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class EngineLock(Protocol):
    """循环引擎锁扣。管理 Observe->Decide->Act->Verify 循环。"""

    def register_loop(self, name: str, template: str,
                      interval: int, task: str) -> bool:
        """注册一个 Loop。"""
        ...

    def run_loop(self, name: str) -> Dict[str, Any]:
        """执行一次 Loop。"""
        ...

    def list_loops(self) -> Dict[str, Any]:
        """列出所有 Loop 状态。"""
        ...
