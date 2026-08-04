"""内置错误档案锁扣实现：包装 ErrorArchive 类。"""

from __future__ import annotations

from typing import Any


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

    def add(self, entry: dict[str, Any]) -> str:
        # 对齐 ErrorArchive.record() 的真实签名：
        # record(category, signature, diagnosis, context, tags, decided_by,
        #        method, notes, resolution_status, auto_approve_scope) -> ArchiveEntry
        # 历史版本传的 error_summary/root_cause/fix_applied 并不存在，
        # 会直接抛 TypeError，因此此处映射到 diagnosis/notes/context。
        summary = str(entry.get("summary", "") or "")
        root_cause = str(entry.get("root_cause", "") or "")
        fix_applied = str(entry.get("fix", "") or "")

        diagnosis = entry.get("diagnosis") or summary or root_cause

        notes_parts = []
        if root_cause:
            notes_parts.append(f"root_cause: {root_cause}")
        if fix_applied:
            notes_parts.append(f"fix: {fix_applied}")
        notes = " | ".join(notes_parts)

        context = dict(entry.get("context") or {})
        if summary:
            context.setdefault("summary", summary)
        if root_cause:
            context.setdefault("root_cause", root_cause)
        if fix_applied:
            context.setdefault("fix", fix_applied)

        tags = entry.get("tags")
        if not isinstance(tags, list):
            tags = None

        result = self._impl.record(
            category=entry.get("category", ""),
            signature=entry.get("signature", ""),
            diagnosis=str(diagnosis or ""),
            context=context or None,
            tags=tags,
            notes=notes,
        )
        # record() 返回 ArchiveEntry；兼容少数返回 dict 的实现。
        entry_id = getattr(result, "id", None)
        if entry_id:
            return str(entry_id)
        if isinstance(result, dict):
            return str(result.get("entry_id") or result.get("id") or "")
        return str(result)

    def approve(self, entry_id: str) -> bool:
        result = self._impl.approve_for_auto(entry_id)
        if isinstance(result, dict):
            # approve_for_auto() 返回 {"ok": bool, "reason": str, ...}
            if "ok" in result:
                return bool(result["ok"])
            return result.get("status") in ("ok", "approved")
        return bool(result)
