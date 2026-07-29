"""内置审计锁扣实现：包装 audit 子系统。"""

from __future__ import annotations

import threading
from typing import Any, Dict

from ..audit import AuditResult
from ..audit.snapshot_reader import OpenClawSnapshotReader
from ..audit.summary_extractor import OpenClawSummaryExtractor
from ..audit.checker import LLMChecker
from ..audit.report import write_report, send_alert


class BuiltinAudit:
    """Post-Compact Audit 默认实现。

    流程：
        1. SnapshotReader 读 compact 前快照
        2. SummaryExtractor 读 compact 后摘要
        3. Checker 对比
        4. Report 写报告 + 告警
    """

    def __init__(self) -> None:
        self._snapshot_reader = OpenClawSnapshotReader()
        self._summary_extractor = OpenClawSummaryExtractor()
        self._checker = LLMChecker()

    def audit_compact(
        self,
        pre_compact_snapshot: Dict[str, Any],
        post_compact_summary: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """同步审计：对比 compact 前后。"""
        try:
            # 1. 读快照关键信息
            snapshot = self._snapshot_reader.find_latest_before(
                pre_compact_snapshot.get("timestamp", "")
            )
            if snapshot is None:
                return {
                    "verdict": "skip",
                    "reason": "compact 前快照不存在",
                    "score": 0.0,
                }

            pre_info = self._snapshot_reader.extract_key_info(snapshot)

            # 2. 读 compact 后摘要
            summary_ref = self._summary_extractor.find_post_compact_summary(
                post_compact_summary.get("timestamp", "")
            )
            if summary_ref is None:
                return {
                    "verdict": "skip",
                    "reason": "compact 后摘要不存在",
                    "score": 0.0,
                }

            post_text = self._summary_extractor.extract_summary_text(summary_ref)

            # 3. 对比
            result = self._checker.check(pre_info, post_text)

            # 4. 写报告 + 告警
            report_path = write_report(result, snapshot, summary_ref)
            send_alert(result, report_path)

            return {
                "verdict": result.verdict,
                "score": result.score,
                "findings": [
                    {
                        "category": f.category,
                        "item": f.item,
                        "status": f.status,
                        "detail": f.detail,
                    }
                    for f in result.findings
                ],
                "recommendation": result.recommendation,
                "reportPath": report_path,
                "error": result.error,
            }

        except Exception as e:
            return {
                "verdict": "error",
                "reason": str(e),
                "score": 0.0,
            }

    def audit_compact_async(
        self,
        pre_compact_snapshot: Dict[str, Any],
        post_compact_summary: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """异步审计：入队立即返回，不阻塞 compact。"""
        thread = threading.Thread(
            target=self._async_run,
            args=(pre_compact_snapshot, post_compact_summary),
            daemon=True,
        )
        thread.start()

        return {"queued": True, "taskId": f"audit-{thread.ident}"}

    def _async_run(self, pre: Dict[str, Any], post: Dict[str, Any]) -> None:
        """异步执行审计（吞掉所有异常，不影响主流程）。"""
        try:
            self.audit_compact(pre, post)
        except Exception:
            pass  # 审计自身失败不影响主流程
