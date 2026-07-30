"""ArcLock 混沌工程锁扣接口。"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChaosLock(Protocol):
    """混沌工程锁扣。"""

    def list_experiments(self) -> list[dict[str, Any]]:
        """列出可用实验。"""
        ...

    def run_experiment(self, name: str,
                       dry_run: bool = True) -> dict[str, Any]:
        """执行实验。"""
        ...
