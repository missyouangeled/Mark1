"""内置循环引擎锁扣实现：包装 engine.py。"""

from __future__ import annotations
from typing import Any, Dict


class BuiltinEngine:
    """将 engine.py 包装为 EngineLock 接口。"""

    def register_loop(self, name: str, template: str,
                      interval: int, task: str) -> bool:
        from ..engine import engine_start
        try:
            engine_start(task=task, interval_s=interval, template=template)
            return True
        except Exception:
            return False

    def run_loop(self, name: str) -> Dict[str, Any]:
        from ..engine import engine_run_loop
        try:
            engine_run_loop(name)
            return {"status": "ok", "loop": name}
        except Exception as e:
            return {"status": "error", "loop": name, "error": str(e)}

    def list_loops(self) -> Dict[str, Any]:
        from ..engine import _load_loops
        loops = _load_loops()
        return loops if isinstance(loops, dict) else {"loops": loops}
