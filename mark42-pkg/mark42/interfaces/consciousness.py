"""ArcLock 意识/自愈锁扣接口。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConsciousnessLock(Protocol):
    """自愈意识锁扣。C1-C5 完整流程。"""

    def self_check(self) -> dict[str, Any]:
        """C1: 自检，返回发现的问题列表。"""
        ...

    def assess(self, issue: dict[str, Any]) -> dict[str, Any]:
        """C2: 评估确定性，返回动作建议。"""
        ...

    def handle_issue(self, issue: dict[str, Any],
                     dry_run: bool = True) -> dict[str, Any]:
        """主入口：C5->C2->C3/C4 完整路由。"""
        ...
