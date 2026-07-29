"""ArcLock 记忆搜索锁扣接口。"""

from __future__ import annotations
from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class MemoryLock(Protocol):
    """记忆/向量搜索锁扣。"""

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """语义搜索，返回相关文档列表。

        返回: [{"content": str, "score": float, "source": str}, ...]
        """
        ...

    def index(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """索引文档。

        返回: {"indexed": int, "status": str}
        """
        ...

    def health(self) -> bool:
        """后端是否可用。"""
        ...
