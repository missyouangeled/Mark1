"""ArcLock 错误档案锁扣接口。"""

from __future__ import annotations
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class ArchiveLock(Protocol):
    """错误档案锁扣。记录和查询历史故障。"""

    def lookup(self, signature: str, **kwargs: Any) -> Any:
        """查找历史记录。"""
        ...

    def add(self, entry: Dict[str, Any]) -> str:
        """添加新记录，返回 ID。"""
        ...

    def approve(self, entry_id: str) -> bool:
        """批准某条记录为可自动执行。"""
        ...
