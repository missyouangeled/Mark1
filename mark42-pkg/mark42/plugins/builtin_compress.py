"""内置压缩锁扣实现：包装 armor.py。"""

from __future__ import annotations

from typing import Any


class BuiltinCompress:
    """将 armor.py 的函数包装为 CompressLock 接口。"""

    def check(self) -> dict[str, Any]:
        from ..armor import armor_check
        return armor_check()

    def compress(self, dry_run: bool = True, **kwargs: Any) -> dict[str, Any]:
        from ..armor import armor_compress
        return armor_compress(dry_run=dry_run)

    def diagnose(self) -> dict[str, Any]:
        from ..compaction_diag import compaction_diagnose
        return compaction_diagnose()
