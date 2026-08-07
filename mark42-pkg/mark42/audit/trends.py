"""审计质量趋势存储（方案 44 建设项 B / §5.5 / Phase 1）。

职责
----
把每轮审计的**结构分数**与**探针分数**分别落盘，提供：

    - 追加式历史（JSONL，便于顺序读与轮替）
    - 趋势查询（近 N 次、按维度）
    - 回归检测（连续 3 次均值下降 >10%）
    - SLO 达标率

⚠️ 两套分数分别保存（方案 §5.2 硬要求）
--------------------------------------
`structure_score`（现有六类结构核对，0..1 的 float）与
`probe_total`（六维响应能力，0..30 的 int）**不得合并成同一个维度**。
合并等于把「证据是否存在」和「模型能否响应」混成一个数字，
出问题时无法判断该修压缩算法还是该修提示词。

⚠️ evidence_absent 不污染趋势
-----------------------------
上游本就没有某维度证据时，该维度低分不计入严格 SLO
（见 `probes.evaluate_slo`）。趋势侧同理：`degraded_run=True` 的记录
在计算能力趋势时可被排除，避免把"上游无数据"读成"模型退化"。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .probes import (
    PROBE_DIMENSIONS,
    PROBE_TOTAL_MAX,
    SLO_MIN_TOTAL,
    SLO_REGRESSION_DROP_PCT,
    SLO_REGRESSION_WINDOW,
    ProbeReport,
    detect_regression,
)

TRENDS_SCHEMA_VERSION = 1

#: 历史保留上限（行）。超出后从头截断，保留最近的。
MAX_HISTORY_LINES = 500

#: 趋势文件名
TRENDS_FILENAME = "quality-trends.jsonl"


# ── 数据模型 ──────────────────────────────────────────


@dataclass
class QualitySample:
    """一轮审计的质量样本。"""

    schema_version: int = TRENDS_SCHEMA_VERSION
    timestamp: str = ""
    trace_id: str = ""
    #: 现有六类结构核对分数（0.0..1.0）—— 与探针分数**分开存**
    structure_score: float | None = None
    structure_verdict: str = ""
    #: 六维探针总分（0..30）
    probe_total: int | None = None
    probe_max: int = PROBE_TOTAL_MAX
    #: 各维度得分
    probe_by_dimension: dict[str, int] = field(default_factory=dict)
    probe_mode: str = ""
    slo_ok: bool = True
    slo_failures: list[str] = field(default_factory=list)
    hallucination: bool = False
    judge_fallback_count: int = 0
    #: 约束静态存活率（0.0..1.0）
    constraint_survival: float | None = None
    constraint_hard_survival: float | None = None
    constraint_blocking: bool = False
    #: 本轮是否因上游证据缺失而不可比 —— 计算能力趋势时可排除
    degraded_run: bool = False
    #: Mark42 版本，便于把趋势变化关联到发布
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrendSummary:
    """趋势摘要。"""

    count: int = 0
    #: 探针总分
    probe_avg: float | None = None
    probe_latest: int | None = None
    probe_min: int | None = None
    probe_max_seen: int | None = None
    #: 结构分数（独立统计）
    structure_avg: float | None = None
    structure_latest: float | None = None
    #: 各维度均值
    dimension_avg: dict[str, float] = field(default_factory=dict)
    #: SLO 达标率
    slo_pass_rate: float | None = None
    #: 回归标志
    regression: bool = False
    regression_window: int = SLO_REGRESSION_WINDOW
    regression_drop_pct: float = SLO_REGRESSION_DROP_PCT
    #: 约束存活
    constraint_survival_avg: float | None = None
    constraint_hard_survival_min: float | None = None
    #: 被排除的降级样本数
    excluded_degraded: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 存储 ──────────────────────────────────────────────


class TrendStore:
    """趋势存储：JSONL 追加 + 原子轮替。

    选 JSONL 而非单个 JSON 数组的原因：
        追加写只需 O(1)，不必读回整个历史再重写 ——
        后者在并发或崩溃时会丢掉整份历史（这类"静默丢数据"
        正是 CASE-20260806 那批教训里最贵的一种）。
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    # ── 写 ────────────────────────────────────────────

    def append(self, sample: QualitySample) -> None:
        """追加一条样本。失败不抛异常（趋势记录不得拖垮审计主流程）。"""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(sample.to_dict(), ensure_ascii=False)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            self._rotate_if_needed()
        except OSError:
            # 趋势是观测数据，写不进去也不能影响审计结论
            pass

    def _rotate_if_needed(self, *, max_lines: int = MAX_HISTORY_LINES) -> None:
        """超出上限时保留最近 max_lines 行（原子替换）。"""
        try:
            if not self.path.exists():
                return
            with self.path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) <= max_lines:
                return
            keep = lines[-max_lines:]
            self._atomic_write_lines(keep)
        except OSError:
            pass

    def _atomic_write_lines(self, lines: list[str]) -> None:
        """原子写：先写临时文件再 rename，避免截断态被读到。"""
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent),
                                   prefix=self.path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.writelines(lines)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # ── 读 ────────────────────────────────────────────

    def load(self, *, limit: int | None = None) -> list[QualitySample]:
        """读历史样本（按时间升序）。坏行跳过，不因一行损坏丢整份历史。"""
        if not self.path.exists():
            return []
        samples: list[QualitySample] = []
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(data, dict):
                        continue
                    known = {k for k in QualitySample.__dataclass_fields__}
                    samples.append(QualitySample(
                        **{k: v for k, v in data.items() if k in known}))
        except OSError:
            return samples
        if limit is not None and limit > 0:
            return samples[-limit:]
        return samples

    # ── 分析 ──────────────────────────────────────────

    def summarize(
        self,
        *,
        limit: int | None = None,
        exclude_degraded: bool = True,
    ) -> TrendSummary:
        """汇总趋势。

        Args:
            exclude_degraded: 为 True 时，`degraded_run=True` 的样本
                不计入能力趋势（避免把「上游无数据」读成「模型退化」）。
        """
        all_samples = self.load(limit=limit)
        summary = TrendSummary()

        if exclude_degraded:
            usable = [s for s in all_samples if not s.degraded_run]
            summary.excluded_degraded = len(all_samples) - len(usable)
        else:
            usable = all_samples

        summary.count = len(usable)
        if not usable:
            return summary

        # ── 探针分数（独立）──
        probe_scores = [s.probe_total for s in usable if s.probe_total is not None]
        if probe_scores:
            summary.probe_avg = sum(probe_scores) / len(probe_scores)
            summary.probe_latest = probe_scores[-1]
            summary.probe_min = min(probe_scores)
            summary.probe_max_seen = max(probe_scores)
            summary.regression = detect_regression(probe_scores)

        # ── 结构分数（独立）──
        struct_scores = [s.structure_score for s in usable
                         if s.structure_score is not None]
        if struct_scores:
            summary.structure_avg = sum(struct_scores) / len(struct_scores)
            summary.structure_latest = struct_scores[-1]

        # ── 各维度均值 ──
        for dim in PROBE_DIMENSIONS:
            vals = [s.probe_by_dimension[dim] for s in usable
                    if dim in s.probe_by_dimension]
            if vals:
                summary.dimension_avg[dim] = sum(vals) / len(vals)

        # ── SLO 达标率 ──
        slo_known = [s for s in usable if s.probe_total is not None]
        if slo_known:
            summary.slo_pass_rate = sum(1 for s in slo_known if s.slo_ok) / len(slo_known)

        # ── 约束存活 ──
        surv = [s.constraint_survival for s in usable
                if s.constraint_survival is not None]
        if surv:
            summary.constraint_survival_avg = sum(surv) / len(surv)
        hard = [s.constraint_hard_survival for s in usable
                if s.constraint_hard_survival is not None]
        if hard:
            summary.constraint_hard_survival_min = min(hard)

        return summary

    def probe_history(self, *, exclude_degraded: bool = True) -> list[int]:
        """按时间升序的探针总分序列（回归检测输入）。"""
        samples = self.load()
        if exclude_degraded:
            samples = [s for s in samples if not s.degraded_run]
        return [s.probe_total for s in samples if s.probe_total is not None]


# ── 构造样本 ──────────────────────────────────────────


def sample_from_reports(
    *,
    probe_report: ProbeReport | None = None,
    structure_score: float | None = None,
    structure_verdict: str = "",
    constraint_survival: float | None = None,
    constraint_hard_survival: float | None = None,
    constraint_blocking: bool = False,
    timestamp: str = "",
    trace_id: str = "",
    version: str = "",
) -> QualitySample:
    """把各子报告合并为一条趋势样本。

    ⚠️ 合并的是**存储位置**，不是分数本身 —— structure 与 probe
    各自独立成字段，任何情况下都不相加、不平均。
    """
    sample = QualitySample(
        timestamp=timestamp,
        trace_id=trace_id,
        structure_score=structure_score,
        structure_verdict=structure_verdict,
        constraint_survival=constraint_survival,
        constraint_hard_survival=constraint_hard_survival,
        constraint_blocking=constraint_blocking,
        version=version,
    )

    if probe_report is not None:
        sample.probe_total = probe_report.total_score
        sample.probe_max = probe_report.max_score
        sample.probe_mode = probe_report.mode
        sample.slo_ok = probe_report.slo_ok
        sample.slo_failures = list(probe_report.slo_failures)
        sample.hallucination = probe_report.hallucination_detected
        sample.judge_fallback_count = probe_report.judge_fallback_count
        sample.probe_by_dimension = {
            o.dimension: o.score for o in probe_report.outcomes
        }
        # 任一维度证据缺失 → 本轮能力分不可比
        sample.degraded_run = any(o.evidence_absent for o in probe_report.outcomes)

    return sample


def slo_status(summary: TrendSummary) -> dict[str, Any]:
    """把趋势摘要转成可读的 SLO 状态判定。"""
    issues: list[str] = []

    if summary.probe_avg is not None and summary.probe_avg < SLO_MIN_TOTAL:
        issues.append(
            f"probe_avg_below_slo: {summary.probe_avg:.1f} < {SLO_MIN_TOTAL}")
    if summary.regression:
        issues.append(
            f"regression_detected: 近 {summary.regression_window} 次均值"
            f"下降超过 {summary.regression_drop_pct:.0%}")
    if summary.constraint_hard_survival_min is not None and \
            summary.constraint_hard_survival_min < 1.0:
        issues.append(
            f"hard_constraint_loss: 最低存活率 "
            f"{summary.constraint_hard_survival_min:.0%} < 100%")

    return {
        "ok": not issues,
        "issues": issues,
        "sampleCount": summary.count,
        "excludedDegraded": summary.excluded_degraded,
    }
