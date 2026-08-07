"""内置审计锁扣实现：包装 audit 子系统（方案 44 Phase 1 扩展）。

扩展自 Phase 0 基线，新增：
    - 能力探针（`audit/probes.py`）—— shadow 模式，不阻止生产 compact
    - 约束静态完整性 + 约束 ID 重注入（`audit/constraint_identity.py`）
    - 质量趋势存储（`audit/trends.py`）
    - 统一事件信封（方案 §10.2）

现有六类结构核对（LLMChecker / RuleChecker）保持不变，作为第一道防线。
探针在其后运行，两类分数分别落盘。

⚠️ 能力边界（方案 §6.2 / §18 反复强调）
--------------------------------------
Phase 1 只跑 shadow 模式 + 探针接入，不引入 gate/gate 模式、
不阻塞生产 compact、不触发任何用户可见行为。
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from ..audit import AuditResult
from ..audit.checker import LLMChecker
from ..audit.constraint_identity import ConstraintRecord, IntegrityReport
from ..audit.pinning import ConstraintPinner
from ..audit.probes import (
    MODE_SHADOW,
    ProbeReport,
    ProbeSpec,
    build_report,
    default_probe_specs,
    detect_hallucination,
    score_deterministic,
)
from ..audit.report import send_alert, write_report
from ..audit.snapshot_reader import OpenClawSnapshotReader
from ..audit.summary_extractor import OpenClawSummaryExtractor
from ..audit.trends import (
    TrendStore,
    sample_from_reports,
    slo_status,
)
from ..config import MARK42_STATE

logger = logging.getLogger(__name__)

#: 探针趋势存储路径
_PROBE_TRENDS_PATH = MARK42_STATE / "trends" / "quality-trends.jsonl"


class BuiltinAudit:
    """Post-Compact Audit 默认实现。

    流程：
        1. SnapshotReader 读 compact 前快照
        2. SummaryExtractor 读 compact 后摘要
        3. Checker 对比（现有六类结构核对）
        4. Report 写报告 + 告警
        5. 约束重注入（ConstraintPinner）
        6. 能力探针（shadow 模式，不阻塞）
        7. 约束静态完整性
        8. 质量趋势存储
    """

    def __init__(
        self,
        *,
        probe_mode: str = MODE_SHADOW,
        probe_specs: list[ProbeSpec] | None = None,
        trends_path: str | None = None,
    ) -> None:
        self._snapshot_reader = OpenClawSnapshotReader()
        self._summary_extractor = OpenClawSummaryExtractor()
        self._checker = LLMChecker()
        self._pinner = ConstraintPinner()
        self._probe_specs = probe_specs or default_probe_specs()
        self._probe_mode = probe_mode
        self._trends = TrendStore(trends_path or _PROBE_TRENDS_PATH)

    def audit_compact(
        self,
        pre_compact_snapshot: dict[str, Any],
        post_compact_summary: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """同步审计：对比 compact 前后 + 约束重注入 + 探针 + 趋势。"""
        trace_id = f"audit-{threading.get_ident()}"
        try:
            # 1. 读快照关键信息
            snapshot = self._snapshot_reader.find_latest_before(
                pre_compact_snapshot.get("timestamp", "")
            )
            if snapshot is None:
                return self._skip("compact 前快照不存在", trace_id=trace_id)

            pre_info = self._snapshot_reader.extract_key_info(snapshot)

            # 2. 读 compact 后摘要
            summary_ref = self._summary_extractor.find_post_compact_summary(
                post_compact_summary.get("timestamp", "")
            )
            if summary_ref is None:
                return self._skip("compact 后摘要不存在", trace_id=trace_id)

            post_text = self._summary_extractor.extract_summary_text(summary_ref)

            # 3. 对比（现有六类结构核对）
            result = self._checker.check(pre_info, post_text)

            # 4. 写报告 + 告警
            report_path = write_report(result, snapshot, summary_ref)
            send_alert(result, report_path)

            # 5. 约束重注入（现有行为，保持不变）
            inject_path = self._pinner.inject_to_file()
            self._pinner.inject_via_broker()

            # 6. 能力探针（shadow 模式，不阻塞 production compact）
            probe_report = self._run_probes_compact(post_text, trace_id=trace_id)

            # 7. 约束静态完整性（沿用现有 pinner 提取的约束）
            constraint_report = self._run_constraint_check(post_text, trace_id=trace_id)

            # 8. 质量趋势存储
            self._record_trends(result, probe_report, constraint_report,
                               trace_id=trace_id)

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
                "probe": {
                    "totalScore": probe_report.total_score,
                    "sloOk": probe_report.slo_ok,
                    "sloFailures": list(probe_report.slo_failures),
                    "hallucination": probe_report.hallucination_detected,
                    "judgeFallbackCount": probe_report.judge_fallback_count,
                },
                "constraint": {
                    "survivalRate": constraint_report.survival_rate(),
                    "hardSurvivalRate": constraint_report.hard_survival_rate(),
                    "blocking": constraint_report.blocking,
                    "reinjectCount": len(constraint_report.reinject_ids),
                },
                "traceId": trace_id,
            }

        except Exception as e:
            logger.exception("审计异常")
            return {
                "verdict": "error",
                "reason": str(e),
                "score": 0.0,
                "traceId": trace_id,
            }

    def _run_probes_compact(
        self,
        post_text: str,
        *,
        trace_id: str = "",
    ) -> ProbeReport:
        """运行能力探针（shadow 模式：只记录，不阻止 compact）。

        Phase 1 只做确定性评分，不调 judge 模型。
        judge 路径在 Phase 2 启用。
        """
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        outcomes = []
        for spec in self._probe_specs:
            out = score_deterministic(spec, post_text)
            # ⚠️ 确定性评分只是"关键词命中"，不等价于"模型真能响应"
            # 但 Phase 1 shadow 阶段足够建立基线
            outcomes.append(out)

        # hallucination 检测（保守策略：只报明确断言）
        known_evidence = [spec.question for spec in self._probe_specs]
        hallucination = detect_hallucination(post_text, known_evidence)

        return build_report(
            outcomes,
            mode=self._probe_mode,
            timestamp=timestamp,
            trace_id=trace_id,
            hallucination=hallucination,
        )

    def _run_constraint_check(
        self,
        post_text: str,
        *,
        trace_id: str = "",
    ) -> IntegrityReport:
        """运行约束静态完整性检测。

        从现有 ConstraintPinner 提取的约束文本中提取记录，
        核对压缩后存活状态。
        """
        from datetime import datetime, timezone

        from ..audit.constraint_identity import (
            build_constraint_record,
            check_static_integrity,
            dedupe_records,
        )
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        # 从 pinner 提取约束
        pinned = self._pinner.extract_pinned_constraints()
        if not pinned:
            return IntegrityReport(detector_failed=True,
                                   detector_error="pinner 返回空约束",
                                   trace_id=trace_id, timestamp=timestamp)

        # 拆成单行 → 构建记录 → 去重 → 核对
        records: list[ConstraintRecord] = []
        for line in pinned.split("\n"):
            line = line.strip()
            if line and len(line) > 6:
                records.append(build_constraint_record(line, source_file="pinned"))

        records = dedupe_records(records)
        return check_static_integrity(records, post_text,
                                      trace_id=trace_id, timestamp=timestamp)

    def _record_trends(
        self,
        result: AuditResult,
        probe_report: ProbeReport,
        constraint_report: IntegrityReport,
        *,
        trace_id: str = "",
    ) -> None:
        """把本轮审计结果记入趋势存储。"""
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        sample = sample_from_reports(
            probe_report=probe_report,
            structure_score=result.score,
            structure_verdict=result.verdict,
            constraint_survival=constraint_report.survival_rate(),
            constraint_hard_survival=constraint_report.hard_survival_rate(),
            constraint_blocking=constraint_report.blocking,
            timestamp=timestamp,
            trace_id=trace_id,
            version="2.8.2",
        )
        self._trends.append(sample)

    def _skip(self, reason: str, *, trace_id: str = "") -> dict[str, Any]:
        return {
            "verdict": "skip",
            "reason": reason,
            "score": 0.0,
            "traceId": trace_id,
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
            try:
                from ..utils import _append_broker, _now_iso
                _append_broker(
                    "armor",
                    "mark42.armor.audit.async_error",
                    f"审计异步执行失败: {e}",
                    "warn",
                    str(e),
                    {"error": str(e), "timestamp": _now_iso()},
                )
            except Exception as e:
                logger.warning("ignored error: %s", e)

    def trends_summary(self, **kw) -> dict[str, Any]:
        """返回趋势摘要（供外部查询）。"""
        sm = self._trends.summarize(**kw)
        st = slo_status(sm)
        return {"summary": sm.to_dict(), "slo": st}
