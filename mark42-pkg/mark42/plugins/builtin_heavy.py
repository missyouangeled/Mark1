"""内置重型战甲锁扣实现：包装 heavy.py。"""

from __future__ import annotations

import uuid
from typing import Any


class BuiltinHeavy:
    """将 heavy.py 包装为 HeavyLock 接口。"""

    def submit(self, task_name: str, subtasks: list[dict[str, Any]],
               execute_now: bool = False) -> str:
        from ..heavy import heavy_execute, heavy_start
        task_id = task_name or str(uuid.uuid4())[:8]
        heavy_start(
            path_str=subtasks[0].get("path", ".") if subtasks else ".",
            task_name=task_id,
            context_aware=True,
        )
        if execute_now:
            heavy_execute(task_name=task_id, execute_now=True)
        return task_id

    def status(self, task_id: str) -> dict[str, Any]:
        from ..heavy import heavy_detect
        try:
            return heavy_detect(task_id)
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def cancel(self, task_id: str) -> bool:
        from ..heavy import heavy_finish
        try:
            heavy_finish(task_id)
            return True
        except Exception:
            return False
