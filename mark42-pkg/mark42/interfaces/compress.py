"""ArcLock 压缩锁扣接口。

实现方可以是 Mark42 armor、Headroom、或任何第三方压缩方案。
不需要继承任何类，只要方法签名匹配就能"吸上"。
"""

from __future__ import annotations
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class CompressLock(Protocol):
    """上下文压缩锁扣。

    实现方可以是 Mark42 armor、Headroom、或任何第三方压缩方案。
    """

    def check(self) -> Dict[str, Any]:
        """检查当前上下文状态。

        返回: {"usagePercent": float, "severity": str, ...}
        """
        ...

    def compress(self, dry_run: bool = True, **kwargs: Any) -> Dict[str, Any]:
        """执行上下文压缩。

        dry_run=True: 只分析不执行
        dry_run=False: 真实执行

        返回: {"action": str, "before": float, "after": float, ...}
        """
        ...

    def diagnose(self) -> Dict[str, Any]:
        """压缩诊断（可选，返回详细分析）。"""
        ...
