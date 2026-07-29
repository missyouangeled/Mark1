"""ArcLock 审计锁扣接口。

压缩后自动核对：对比 compact 前快照与 compact 后摘要，
判断关键信息是否丢失。

实现方可以是 Mark42 内置 LLM 审计、规则审计、或第三方审计方案。
不需要继承任何类，只要方法签名匹配就能"吸上"。
"""

from __future__ import annotations
from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class AuditLock(Protocol):
    """压缩后审计锁扣。"""

    def audit_compact(
        self,
        pre_compact_snapshot: Dict[str, Any],
        post_compact_summary: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """对比 compact 前快照与 compact 后摘要，返回核对报告。

        Args:
            pre_compact_snapshot: compact 前的快照引用
                {"source": str, "path": str, "timestamp": str, ...}
            post_compact_summary: compact 后的摘要引用
                {"source": str, "path": str, "timestamp": str, ...}

        Returns:
            {"verdict": "pass"|"partial"|"fail",
             "score": float,
             "findings": [...],
             "recommendation": str,
             "reportPath": str}
        """
        ...

    def audit_compact_async(
        self,
        pre_compact_snapshot: Dict[str, Any],
        post_compact_summary: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """异步版本：入队立即返回，不阻塞 compact 流程。

        Returns:
            {"queued": True, "taskId": str}
        """
        ...
