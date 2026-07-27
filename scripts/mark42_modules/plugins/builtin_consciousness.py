"""内置意识/自愈锁扣实现：包装 Consciousness 类。"""

from __future__ import annotations
from typing import Any, Dict


class BuiltinConsciousness:
    """将 Consciousness 类包装为 ConsciousnessLock 接口。"""

    def __init__(self):
        from ..consciousness import Consciousness
        self._impl = Consciousness()

    def self_check(self) -> Dict[str, Any]:
        result = self._impl.self_check()
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return result if isinstance(result, dict) else {"result": str(result)}

    def assess(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        result = self._impl.assess_certainty(issue)
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return result if isinstance(result, dict) else {"result": str(result)}

    def handle_issue(self, issue: Dict[str, Any],
                     dry_run: bool = True) -> Dict[str, Any]:
        return self._impl.handle_issue(issue, dry_run=dry_run)
