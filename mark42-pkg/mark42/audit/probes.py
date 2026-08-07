"""能力探针：压缩后**响应能力**代理测试（方案 44 建设项 B / Phase 0 冻结 schema）。

与现有结构审计的区别（方案 §5.2 明确要求，不得混为一谈）
--------------------------------------------------------
现有 `audit/checker.py` + `AUDIT_CATEGORIES` 回答的是：
    「压缩后，标题 / 人名 / 规则 / 文件记录**是否还在**」——即**证据存在性**。

本模块回答的是：
    「给定该证据时，模型**能否给出合规响应**」——即**响应能力**。

两套分数**分别保存，不混成同一个维度**。映射关系（供报告关联，不做合并）：

    Intent      ←→ recent_topics / projects
    Continuity  ←→ recent_topics / projects
    Decision    ←→ decisions
    Artifact    ←→ artifacts
    Evidence    ←→ decisions
    Instruction ←→ preferences

⚠️ 能力边界（方案 §6.2 / §18 反复强调）
--------------------------------------
探针通过**无工具的直接模型调用**运行，只收集文本响应：

    - 不进入 OpenClaw 主会话；
    - 不暴露任何工具；
    - 不写主记忆。

因此它只能证明「给定快照时模型响应是否合规」，
**不能等价证明真实 Agent 会话行为**。报告中必须显式声明这一点。

本文件属 Phase 0：只冻结 schema 与确定性评分，不含 LLM 调用编排。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

# ── 版本 ──────────────────────────────────────────────

#: 探针 schema 版本。Phase 0 冻结，Phase 1 的 fixture 依赖此版本。
PROBE_SCHEMA_VERSION = 1

#: 评分 prompt 版本——必须随报告一起保存（方案 §5.3：禁止只存最终分数）
SCORING_PROMPT_VERSION = 1


# ── 六类能力维度（方案 §5.2）────────────────────────────

PROBE_INTENT = "intent"
PROBE_CONTINUITY = "continuity"
PROBE_DECISION = "decision"
PROBE_ARTIFACT = "artifact"
PROBE_EVIDENCE = "evidence"
PROBE_INSTRUCTION = "instruction"

PROBE_DIMENSIONS: tuple[str, ...] = (
    PROBE_INTENT,
    PROBE_CONTINUITY,
    PROBE_DECISION,
    PROBE_ARTIFACT,
    PROBE_EVIDENCE,
    PROBE_INSTRUCTION,
)

#: 与现有结构审计类别的映射（只用于报告关联，**不合并分数**）
PROBE_TO_AUDIT_CATEGORY: dict[str, tuple[str, ...]] = {
    PROBE_INTENT: ("recent_topics", "projects"),
    PROBE_CONTINUITY: ("recent_topics", "projects"),
    PROBE_DECISION: ("decisions",),
    PROBE_ARTIFACT: ("artifacts",),
    PROBE_EVIDENCE: ("decisions",),
    PROBE_INSTRUCTION: ("preferences",),
}

#: 各维度的自然语言问法（Phase 1 实际调用时使用）
PROBE_QUESTIONS: dict[str, str] = {
    PROBE_INTENT: "当前这个会话的目标是什么？",
    PROBE_CONTINUITY: "下一步应该做什么？",
    PROBE_DECISION: "有哪些关键决定，以及哪些方案被否决了？",
    PROBE_ARTIFACT: "改过哪些文件，它们现在是什么状态？",
    PROBE_EVIDENCE: "你刚才那个结论的来源在哪里？",
    PROBE_INSTRUCTION: "当前有哪些必须遵守的硬约束？",
}


# ── 评分协议（方案 §5.3）──────────────────────────────

#: 单维度满分
PROBE_MAX_SCORE = 5

#: 总分 = 6 维 × 5 分
PROBE_TOTAL_MAX = PROBE_MAX_SCORE * len(PROBE_DIMENSIONS)

#: 分数语义。0 含「违反约束」——因此约束违规必然拿 0 分。
SCORE_RUBRIC: dict[int, str] = {
    5: "完整、可追溯、无虚构",
    4: "主体正确，有轻微遗漏",
    3: "可继续工作，但缺部分关键细节",
    2: "需要人工补上下文",
    1: "严重错误或混淆",
    0: "完全丢失、答非所问或违反约束",
}


# ── SLO（方案 §5.5）───────────────────────────────────

#: 总分下限。低于此值视为质量不达标。
SLO_MIN_TOTAL = 24

#: 单项下限更严的维度——Instruction 关乎约束遵循，Evidence 关乎召回可追溯
SLO_STRICT_DIMENSIONS: tuple[str, ...] = (PROBE_INSTRUCTION, PROBE_EVIDENCE)
SLO_STRICT_MIN = 4

#: 连续 N 次均值下降超过该比例即触发回归事件
SLO_REGRESSION_WINDOW = 3
SLO_REGRESSION_DROP_PCT = 0.10


# ── 运行模式（方案 §5.4）──────────────────────────────

MODE_OFF = "off"
MODE_SHADOW = "shadow"
MODE_WARN = "warn"
MODE_GATE = "gate"

PROBE_MODES: tuple[str, ...] = (MODE_OFF, MODE_SHADOW, MODE_WARN, MODE_GATE)

#: ⚠️ gate 模式的**不承诺项**（方案 §5.4 修订要点）：
#:    官方 compact 返回后会话已经改变，gate **不承诺自动撤销 compact**。
#:    没有经官方验证的恢复通道时，gate 只能：保留证据 + 停止后续 active 升级 + 告警。
GATE_CANNOT_AUTO_REVERT = True


# ── 数据模型 ──────────────────────────────────────────


@dataclass
class ProbeSpec:
    """单个探针定义。"""

    dimension: str
    question: str
    #: 确定性断言：期望在响应中出现的关键词（任一命中即算覆盖）
    expect_any: list[str] = field(default_factory=list)
    #: 确定性断言：**必须全部**出现的关键词
    expect_all: list[str] = field(default_factory=list)
    #: 一旦出现即判为违规（例如约束探针里出现英文回答）
    forbid: list[str] = field(default_factory=list)
    #: 该维度是否参与严格 SLO
    strict: bool = False
    #: 该探针依赖的 ContextState 字段，用于「无证据时不该扣模型分」的判定
    requires_fields: list[str] = field(default_factory=list)

    def probe_id(self) -> str:
        """稳定 ID：同定义必得同 ID，便于跨轮次对比。"""
        blob = json.dumps(
            {
                "d": self.dimension,
                "q": self.question,
                "any": sorted(self.expect_any),
                "all": sorted(self.expect_all),
                "forbid": sorted(self.forbid),
            },
            ensure_ascii=False, sort_keys=True,
        )
        return f"{self.dimension}-{hashlib.sha256(blob.encode()).hexdigest()[:8]}"


@dataclass
class ProbeOutcome:
    """单个探针的执行结果。

    方案 §5.3：**禁止只存最终分数**。judge 相关字段必须落盘。
    """

    dimension: str
    probe_id: str
    score: int
    #: deterministic | judge | skipped
    method: str = "deterministic"
    reason: str = ""
    #: 原始模型响应（脱敏后）。judge 路径必须保留。
    raw_response: str = ""
    judge_model: str = ""
    judge_prompt_version: int = SCORING_PROMPT_VERSION
    judge_raw: str = ""
    #: 命中 / 缺失的断言明细，便于回指具体问题
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    violated: list[str] = field(default_factory=list)
    #: 无证据可考时标记——此时低分不应归因于模型
    evidence_absent: bool = False

    def is_violation(self) -> bool:
        """是否触发约束违规（必然 0 分）。"""
        return bool(self.violated)


@dataclass
class ProbeReport:
    """一轮探针的完整报告。"""

    schema_version: int = PROBE_SCHEMA_VERSION
    mode: str = MODE_SHADOW
    outcomes: list[ProbeOutcome] = field(default_factory=list)
    total_score: int = 0
    max_score: int = PROBE_TOTAL_MAX
    slo_ok: bool = True
    slo_failures: list[str] = field(default_factory=list)
    #: 无来源的新增事实 → hallucination，单次审计直接失败（方案 §5.5）
    hallucination_detected: bool = False
    judge_fallback_count: int = 0
    #: ⚠️ 声明：代理测试不等价于生产 Agent 行为（方案 §6.2 强制要求）
    disclaimer: str = (
        "本报告由无工具的隔离模型调用产生，只能证明「给定快照时模型响应是否合规」，"
        "不能等价证明真实 Agent 会话行为。"
    )
    timestamp: str = ""
    trace_id: str = ""
    error: str = ""

    def by_dimension(self) -> dict[str, ProbeOutcome]:
        return {o.dimension: o for o in self.outcomes}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── 默认探针集 ────────────────────────────────────────


def default_probe_specs() -> list[ProbeSpec]:
    """六类默认探针（Phase 0 冻结）。

    `expect_*` 关键词故意保持**通用**：具体断言由 fixture 场景各自覆盖，
    避免默认集把某个项目的专有名词写死。
    """
    return [
        ProbeSpec(
            dimension=PROBE_INTENT,
            question=PROBE_QUESTIONS[PROBE_INTENT],
            requires_fields=["session_intent", "active_task"],
        ),
        ProbeSpec(
            dimension=PROBE_CONTINUITY,
            question=PROBE_QUESTIONS[PROBE_CONTINUITY],
            requires_fields=["next_steps", "active_task"],
        ),
        ProbeSpec(
            dimension=PROBE_DECISION,
            question=PROBE_QUESTIONS[PROBE_DECISION],
            requires_fields=["decisions"],
        ),
        ProbeSpec(
            dimension=PROBE_ARTIFACT,
            question=PROBE_QUESTIONS[PROBE_ARTIFACT],
            requires_fields=["artifacts"],
        ),
        ProbeSpec(
            dimension=PROBE_EVIDENCE,
            question=PROBE_QUESTIONS[PROBE_EVIDENCE],
            requires_fields=["evidence_refs", "decisions"],
            strict=True,
        ),
        ProbeSpec(
            dimension=PROBE_INSTRUCTION,
            question=PROBE_QUESTIONS[PROBE_INSTRUCTION],
            requires_fields=["constraints"],
            strict=True,
        ),
    ]


# ── 确定性评分（方案 §5.3：先确定性，无法确定才 judge）──

#: 判定「疑似推断冒充事实」的措辞
_HEDGE_AS_FACT_PATTERNS = (
    re.compile(r"(?:肯定|一定|确实|毫无疑问)(?:是|有|会)"),
)

#: 判定「明确标注为推断」的措辞——出现这些**不算**hallucination
_INFERENCE_MARKERS = (
    "我的推断", "我猜", "可能", "不确定", "推测", "看起来像", "这是我的判断",
)


def score_deterministic(
    spec: ProbeSpec,
    response: str,
    *,
    evidence_absent: bool = False,
) -> ProbeOutcome:
    """确定性评分：只用断言，不调模型。

    评分逻辑（方案 §5.3 rubric 的可执行化）：
        - 触发 forbid            → 0 分（违规）
        - expect_all 有缺失      → 按缺失比例降级
        - expect_any 全不命中    → 最多 2 分
        - 全部命中且非空         → 5 分
        - 无断言可用             → 返回 method="skipped"，交给 judge

    Args:
        evidence_absent: 上游 ContextState 里本就没有该维度的证据。
            此时低分不应归因于模型能力——标记出来，让趋势分析排除。
    """
    text = (response or "").strip()

    violated = [f for f in spec.forbid if f and f in text]
    if violated:
        return ProbeOutcome(
            dimension=spec.dimension,
            probe_id=spec.probe_id(),
            score=0,
            method="deterministic",
            reason="命中禁止项（违反约束）",
            raw_response=text[:2000],
            violated=violated,
            evidence_absent=evidence_absent,
        )

    if not text:
        return ProbeOutcome(
            dimension=spec.dimension,
            probe_id=spec.probe_id(),
            score=0,
            method="deterministic",
            reason="空响应",
            evidence_absent=evidence_absent,
        )

    has_assertions = bool(spec.expect_all or spec.expect_any)
    if not has_assertions:
        return ProbeOutcome(
            dimension=spec.dimension,
            probe_id=spec.probe_id(),
            score=0,
            method="skipped",
            reason="无确定性断言，需 judge 评分",
            raw_response=text[:2000],
            evidence_absent=evidence_absent,
        )

    matched: list[str] = []
    missing: list[str] = []

    for kw in spec.expect_all:
        (matched if kw in text else missing).append(kw)

    any_hits = [kw for kw in spec.expect_any if kw in text]
    matched.extend(any_hits)

    score = PROBE_MAX_SCORE
    reason_parts: list[str] = []

    if spec.expect_all:
        miss_ratio = len(missing) / len(spec.expect_all)
        if miss_ratio >= 1.0:
            score = 0
            reason_parts.append("必需项全部缺失")
        elif miss_ratio > 0.5:
            score = 1
            reason_parts.append("必需项缺失过半")
        elif miss_ratio > 0.0:
            score = 3
            reason_parts.append("必需项部分缺失")

    if spec.expect_any and not any_hits:
        score = min(score, 2)
        reason_parts.append("可选项全部未命中")

    return ProbeOutcome(
        dimension=spec.dimension,
        probe_id=spec.probe_id(),
        score=score,
        method="deterministic",
        reason="；".join(reason_parts) or "全部断言命中",
        raw_response=text[:2000],
        matched=matched,
        missing=missing,
        evidence_absent=evidence_absent,
    )


def detect_hallucination(response: str, known_evidence: list[str]) -> bool:
    """检测「无来源的新增事实」（方案 §5.5：直接判审计失败）。

    保守策略——**只在措辞明确把未知内容说成确定事实时**才报：
        - 明确标注为推断（"我猜"/"可能"）→ 不报；
        - 用了"肯定是/一定有"这类断言词，且内容不在已知证据里 → 报。

    Args:
        response: 模型响应
        known_evidence: 已知证据文本片段列表

    Returns:
        True 表示检出 hallucination。
    """
    text = (response or "").strip()
    if not text:
        return False

    # 明确标注推断的，不算 hallucination（召回与推断分离已被遵守）
    if any(m in text for m in _INFERENCE_MARKERS):
        return False

    evidence_blob = "\n".join(known_evidence or [])
    for pat in _HEDGE_AS_FACT_PATTERNS:
        for m in pat.finditer(text):
            # 取断言词后面一小段，看是否有证据支撑
            tail = text[m.end():m.end() + 30].strip()
            if not tail:
                continue
            probe = tail[:8]
            if probe and probe not in evidence_blob:
                return True
    return False


# ── SLO 判定 ──────────────────────────────────────────


def evaluate_slo(report: ProbeReport) -> ProbeReport:
    """按方案 §5.5 判定 SLO，回填 `slo_ok` / `slo_failures`。

    规则：
        1. 总分不得低于 SLO_MIN_TOTAL；
        2. Instruction 与 Evidence 单项不得低于 SLO_STRICT_MIN；
        3. 任何约束违规直接失败；
        4. hallucination 直接失败。

    `evidence_absent` 的维度不计入严格单项判定——上游本就没给证据时，
    把低分算作模型缺陷会污染趋势（这是"比较两端不同源"的老毛病）。
    """
    failures: list[str] = []
    by_dim = report.by_dimension()

    report.total_score = sum(o.score for o in report.outcomes)

    if report.total_score < SLO_MIN_TOTAL:
        failures.append(
            f"total_below_slo: {report.total_score}/{report.max_score} "
            f"< {SLO_MIN_TOTAL}"
        )

    for dim in SLO_STRICT_DIMENSIONS:
        out = by_dim.get(dim)
        if out is None:
            failures.append(f"missing_strict_dimension: {dim}")
            continue
        if out.evidence_absent:
            continue
        if out.score < SLO_STRICT_MIN:
            failures.append(
                f"strict_dimension_below_min: {dim}={out.score} < {SLO_STRICT_MIN}"
            )

    for out in report.outcomes:
        if out.is_violation():
            failures.append(
                f"constraint_violation: {out.dimension} -> {out.violated}"
            )

    if report.hallucination_detected:
        failures.append("hallucination_detected")

    report.slo_failures = failures
    report.slo_ok = not failures
    return report


def detect_regression(history: list[int], *, window: int = SLO_REGRESSION_WINDOW,
                      drop_pct: float = SLO_REGRESSION_DROP_PCT) -> bool:
    """连续 `window` 次均值相对前 `window` 次下降超过 `drop_pct` 即回归。

    Args:
        history: 按时间升序的总分序列

    Returns:
        True 表示应触发回归事件。
    """
    if window <= 0 or len(history) < window * 2:
        return False
    recent = history[-window:]
    prior = history[-window * 2:-window]
    prior_avg = sum(prior) / len(prior)
    if prior_avg <= 0:
        return False
    recent_avg = sum(recent) / len(recent)
    return (prior_avg - recent_avg) / prior_avg > drop_pct


def build_report(
    outcomes: list[ProbeOutcome],
    *,
    mode: str = MODE_SHADOW,
    timestamp: str = "",
    trace_id: str = "",
    hallucination: bool = False,
) -> ProbeReport:
    """组装并评估报告（一步到位，避免调用方忘记跑 SLO）。"""
    if mode not in PROBE_MODES:
        raise ValueError(f"未知探针模式: {mode!r}，合法值 {PROBE_MODES}")
    report = ProbeReport(
        mode=mode,
        outcomes=list(outcomes),
        timestamp=timestamp,
        trace_id=trace_id,
        hallucination_detected=hallucination,
        judge_fallback_count=sum(1 for o in outcomes if o.method == "judge"),
    )
    return evaluate_slo(report)
