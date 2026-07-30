"""内置审计锁扣实现：包装 audit 子系统。"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)
from typing import Any

from ..audit.checker import LLMChecker
from ..audit.pinning import ConstraintPinner
from ..audit.report import send_alert, write_report
from ..audit.snapshot_reader import OpenClawSnapshotReader
from ..audit.summary_extractor import OpenClawSummaryExtractor


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
        self._pinner = ConstraintPinner()

    def audit_compact(
        self,
        pre_compact_snapshot: dict[str, Any],
        post_compact_summary: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """同步审计：对比 compact 前后 + 约束重注入。"""
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

            # 5. 约束重注入（无论审计结果如何，都重新注入关键约束）
            # 灵感来源：arxiv Governance Decay 论文的 Constraint Pinning
            # compact 后关键约束可能被摘要丢失，重新注入确保安全
            inject_path = self._pinner.inject_to_file()
            self._pinner.inject_via_broker()

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
                "pinnedConstraintsPath": inject_path,
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
        pre_compact_snapshot: dict[str, Any],
        post_compact_summary: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """异步审计：入队立即返回，不阻塞 compact。"""
        thread = threading.Thread(
            target=self._async_run,
            args=(pre_compact_snapshot, post_compact_summary),
            daemon=True,
        )
        thread.start()

        return {"queued": True, "taskId": f"audit-{thread.ident}"}

    def _async_run(self, pre: dict[str, Any], post: dict[str, Any]) -> None:
        """异步执行审计（异常写入 broker，不影响主流程）。"""
        try:
            self.audit_compact(pre, post)
        except Exception as e:
            # 审计自身失败不影响主流程，但必须留痕
            try:
                from ..utils import _append_broker, _now_iso
                _append_broker(
                    "armor",
                    "mark42.armor.audit.async_error",
                    f"Post-Compact Audit 异步执行失败: {e}",
                    "warn",
                    str(e),
                    {"error": str(e), "timestamp": _now_iso()},
                )
            except Exception as e:
                logger.warning("ignored error: %s", e)
