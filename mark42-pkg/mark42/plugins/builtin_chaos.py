"""内置混沌工程锁扣实现：包装 ChaosEngine 类。"""

from __future__ import annotations

from typing import Any


class BuiltinChaos:
    """将 ChaosEngine 类包装为 ChaosLock 接口。"""

    def __init__(self):
        from ..chaos_engine import ChaosEngine
        self._impl = ChaosEngine()

    def list_experiments(self) -> list[dict[str, Any]]:
        return self._impl.list_experiments()

    def run_experiment(self, name: str,
                       dry_run: bool = True) -> dict[str, Any]:
        result = self._impl.run_experiment(name, dry_run=dry_run)
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return result if isinstance(result, dict) else {"result": str(result)}
