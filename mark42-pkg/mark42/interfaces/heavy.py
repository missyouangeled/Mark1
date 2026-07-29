"""ArcLock 重型战甲锁扣接口。"""

from __future__ import annotations
from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class HeavyLock(Protocol):
    """重型战甲锁扣。大任务拆分+执行+监控。"""

    def submit(self, task_name: str, subtasks: List[Dict[str, Any]],
               execute_now: bool = False) -> str:
        """提交大任务，返回任务 ID。"""
        ...

    def status(self, task_id: str) -> Dict[str, Any]:
        """查询任务状态。"""
        ...

    def cancel(self, task_id: str) -> bool:
        """取消任务。"""
        ...
