"""内置错误档案锁扣实现：包装 ErrorArchive 类。"""

from __future__ import annotations
from typing import Any, Dict


class BuiltinArchive:
    """将 ErrorArchive 类包装为 ArchiveLock 接口。"""

    def __init__(self):
        from ..error_archive import ErrorArchive
        self._impl = ErrorArchive()

    def lookup(self, signature: str, **kwargs: Any) -> Any:
        category = kwargs.get("category", "")
        entry = self._impl.lookup(signature, category=category)
        if entry is None:
            return None
        return entry.to_dict() if hasattr(entry, "to_dict") else entry

    def add(self, entry: Dict[str, Any]) -> str:
        result = self._impl.record(
            category=entry.get("category", ""),
            signature=entry.get("signature", ""),
            error_summary=entry.get("summary", ""),
            root_cause=entry.get("root_cause", ""),
            fix_applied=entry.get("fix", ""),
        )
        if isinstance(result, dict):
            return result.get("entry_id", "")
        return str(result)

    def approve(self, entry_id: str) -> bool:
        result = self._impl.approve_for_auto(entry_id)
        if isinstance(result, dict):
            return result.get("status") in ("ok", "approved")
        return bool(result)
