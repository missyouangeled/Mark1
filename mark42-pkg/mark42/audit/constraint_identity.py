"""约束身份与静态完整性（方案 44 建设项 C 第一层 / Phase 1）。

当前不足（方案 §6.1）
--------------------
现有 `ConstraintPinner` 能提取约束并**无条件全量重注入**，但：

    - 不知道哪些约束在压缩中丢失了；
    - 不能验证 Agent 是否仍遵守；
    - 每次都注入全部内容，浪费 token 且无法定位问题。

本模块补第一层：**静态完整性**。

    每条约束生成稳定 constraint_id
    → 保存来源文件、行号、哈希、强度
    → 压缩后核对 ID、语义摘要与来源引用
    → 先检测缺失/冲突，再按需重注入

⚠️ 失败安全降级（方案 §6.2 明确要求）
------------------------------------
检测器自身异常时，必须退回「全量重注入」的旧行为。
**宁可多注入，不可漏注入** —— 约束丢失的代价远高于多花几百 token。

第二层（隔离响应合规代理测试）在 `constraint_probe.py`，
它只能证明「给定快照时模型响应是否合规」，不等价于生产 Agent 行为。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

# ── 版本 ──────────────────────────────────────────────

CONSTRAINT_SCHEMA_VERSION = 1


# ── 分级（方案 §6.3）─────────────────────────────────

#: P0：安全、隐私、外部写操作 —— 任何失败都阻断
PRIORITY_P0 = "P0"
#: P1：用户明确工作规则 —— 失败告警并重注入
PRIORITY_P1 = "P1"
#: P2：风格与偏好 —— 只记录趋势，不阻断
PRIORITY_P2 = "P2"

PRIORITIES = (PRIORITY_P0, PRIORITY_P1, PRIORITY_P2)

#: 各级失败时的处置动作
PRIORITY_ACTIONS: dict[str, str] = {
    PRIORITY_P0: "block",
    PRIORITY_P1: "warn_and_reinject",
    PRIORITY_P2: "trend_only",
}

STRENGTH_HARD = "hard"
STRENGTH_SOFT = "soft"
STRENGTHS = (STRENGTH_HARD, STRENGTH_SOFT)


# ── 分级规则 ──────────────────────────────────────────

#: P0 关键词：安全 / 隐私 / 外部写操作 / 承载自身的服务
_P0_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"只用中文|禁止使用英文|No English|Chinese ONLY"),
    re.compile(r"(?:发送|发布)(?:邮件|推文|公开内容).*(?:先问|确认)"),
    re.compile(r"公开(?:发送|发布).*前.*(?:先问|确认)"),
    re.compile(r"(?:禁止|不得|不要).*(?:restart|stop).*gateway", re.I),
    re.compile(r"私密|隐私|不得泄露|凭据"),
    re.compile(r"召回.*推断.*分离|不得把推断伪装成事实"),
    re.compile(r"高风险.*(?:必读|先读).*崩坏案例"),
)

#: P1 关键词：用户明确工作规则
_P1_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"默认\s*dry-run|dry-run\s*默认"),
    re.compile(r"(?:新增能力|新功能).*默认(?:关闭|关|false)"),
    re.compile(r"交付前(?:必须)?自检"),
    re.compile(r"先查(?:现有能力|技能表|安装注册表)"),
    re.compile(r"(?:必须|要)留痕|写入变更流水"),
    re.compile(r"问题追根因|禁止躲避式修复"),
    re.compile(r"(?:改|修改)配置.*(?:先备份|回滚)"),
)

#: 明确属于风格偏好的标志（否则默认落 P2）
_P2_HINTS: tuple[re.Pattern[str], ...] = (
    re.compile(r"清单式收尾|列表|措辞|语气|语速|口头禅"),
    re.compile(r"称呼|叫我"),
)


def classify_priority(text: str) -> str:
    """按内容判定约束优先级。

    保守策略：命中 P0 模式即 P0；命中 P1 即 P1；其余落 P2。
    **不做模糊猜测** —— 拿不准的宁可落 P2（只记趋势），
    避免把风格偏好误判成阻断级约束、造成误阻断。
    """
    t = text or ""
    for pat in _P0_PATTERNS:
        if pat.search(t):
            return PRIORITY_P0
    for pat in _P1_PATTERNS:
        if pat.search(t):
            return PRIORITY_P1
    return PRIORITY_P2


def classify_strength(text: str, priority: str) -> str:
    """P0/P1 视为 hard，P2 视为 soft。

    hard 约束不可被模型摘要删除，只能被更新或显式撤销。
    """
    if priority in (PRIORITY_P0, PRIORITY_P1):
        return STRENGTH_HARD
    # 显式风格提示 → soft
    for pat in _P2_HINTS:
        if pat.search(text or ""):
            return STRENGTH_SOFT
    return STRENGTH_SOFT


# ── 数据模型 ──────────────────────────────────────────


@dataclass
class ConstraintRecord:
    """一条带身份的约束。

    `constraint_id` 必须**稳定**：同一条约束在不同轮次必须得到同一个 ID，
    否则跨轮对比会把「没变」误判成「丢了旧的又来了新的」。
    """

    constraint_id: str
    text: str
    source_file: str = ""
    line_no: int = 0
    text_hash: str = ""
    strength: str = STRENGTH_HARD
    priority: str = PRIORITY_P1
    #: 语义摘要（供压缩后核对，允许换说法）
    summary: str = ""
    schema_version: int = CONSTRAINT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def action_on_failure(self) -> str:
        return PRIORITY_ACTIONS.get(self.priority, "trend_only")

    def to_context_state_item(self) -> dict[str, Any]:
        """转成 ContextState.constraints 可接受的形状（带来源）。"""
        return {
            "constraint_id": self.constraint_id,
            "text": self.text,
            "summary": self.summary or self.text[:60],
            "strength": self.strength,
            "priority": self.priority,
            "source": self.source_file,
            "line": self.line_no,
            "evidence": f"{self.source_file}:{self.line_no}" if self.source_file else "",
        }


@dataclass
class IntegrityFinding:
    """单条约束的静态完整性结论。"""

    constraint_id: str
    #: preserved | degraded | lost | conflicted
    status: str
    priority: str
    strength: str
    detail: str = ""
    matched_via: str = ""

    def is_blocking(self) -> bool:
        """P0 约束丢失/冲突 → 阻断（方案 §6.3）。"""
        return self.priority == PRIORITY_P0 and self.status in ("lost", "conflicted")


@dataclass
class IntegrityReport:
    """静态完整性报告。"""

    schema_version: int = CONSTRAINT_SCHEMA_VERSION
    findings: list[IntegrityFinding] = field(default_factory=list)
    total: int = 0
    preserved: int = 0
    degraded: int = 0
    lost: int = 0
    conflicted: int = 0
    #: 需要重注入的约束 ID（缺失或降级的）
    reinject_ids: list[str] = field(default_factory=list)
    #: 是否触发阻断（存在 P0 丢失）
    blocking: bool = False
    #: 检测器自身是否失败 —— True 时调用方必须全量重注入
    detector_failed: bool = False
    detector_error: str = ""
    timestamp: str = ""
    trace_id: str = ""

    def survival_rate(self) -> float:
        """存活率：preserved / total。空集视为 1.0（没约束就没丢）。"""
        if self.total <= 0:
            return 1.0
        return self.preserved / self.total

    def hard_survival_rate(self) -> float:
        """hard 约束存活率 —— 方案 §6.5 要求压缩 10 轮后达 100%。"""
        hard = [f for f in self.findings if f.strength == STRENGTH_HARD]
        if not hard:
            return 1.0
        return sum(1 for f in hard if f.status == "preserved") / len(hard)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ── ID 生成 ───────────────────────────────────────────

#: 归一化时剔除的字符：Markdown 标记、全角/半角标点、空白
_NORMALIZE_STRIP = re.compile(r"[\s\*_`#>\-—·、，。；：！？,.;:!?()（）\[\]【】\"'“”‘’]+")


def normalize_constraint_text(text: str) -> str:
    """归一化约束文本，用于生成稳定 ID 与去重。

    目标：同一条约束即使改了标点、加粗、缩进，也要得到同一个归一化串。
    """
    return _NORMALIZE_STRIP.sub("", (text or "").strip()).lower()


def make_constraint_id(text: str, *, source_file: str = "") -> str:
    """生成稳定 constraint_id。

    只依赖**归一化文本**，不含行号 —— 行号会随文件编辑漂移，
    把它算进 ID 会导致同一条约束改一次排版就变成"新约束"。
    """
    norm = normalize_constraint_text(text)
    digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
    return f"c-{digest}"


def text_hash(text: str) -> str:
    """约束原文哈希 —— 用于检测「同一条约束内容被改写」。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


# ── 提取 ──────────────────────────────────────────────

#: 一行至少这么长才可能是有效约束（过滤 "- x" 之类噪音）
MIN_CONSTRAINT_LEN = 6
#: 超过这个长度截断为摘要
SUMMARY_MAX_LEN = 60


def build_constraint_record(
    text: str,
    *,
    source_file: str = "",
    line_no: int = 0,
) -> ConstraintRecord:
    """从一行文本构造带身份的约束记录。"""
    clean = (text or "").strip()
    priority = classify_priority(clean)
    return ConstraintRecord(
        constraint_id=make_constraint_id(clean, source_file=source_file),
        text=clean,
        source_file=source_file,
        line_no=line_no,
        text_hash=text_hash(clean),
        strength=classify_strength(clean, priority),
        priority=priority,
        summary=clean[:SUMMARY_MAX_LEN],
    )


def dedupe_records(records: list[ConstraintRecord]) -> list[ConstraintRecord]:
    """按 constraint_id 去重，保留首次出现（含最早的来源行号）。"""
    seen: dict[str, ConstraintRecord] = {}
    for r in records:
        if r.constraint_id not in seen:
            seen[r.constraint_id] = r
    return list(seen.values())


# ── 静态完整性检测 ────────────────────────────────────

#: 语义摘要匹配时，至少要命中这么多个「关键词片段」才算 degraded
_FRAGMENT_MIN_LEN = 2
_FRAGMENT_HIT_RATIO = 0.5


def check_static_integrity(
    records: list[ConstraintRecord],
    post_text: str,
    *,
    trace_id: str = "",
    timestamp: str = "",
) -> IntegrityReport:
    """核对压缩后文本里各约束的存活状态。

    判定层级（从强到弱）：
        1. 归一化全文命中          → preserved（matched_via=normalized）
        2. 语义摘要片段命中过半    → degraded（matched_via=fragments）
        3. 都没命中                → lost

    Args:
        records: 压缩前提取的约束记录
        post_text: 压缩后的摘要 / 上下文文本

    Returns:
        IntegrityReport。**本函数不抛异常** —— 内部失败会置
        `detector_failed=True`，让调用方走全量重注入的失败安全路径。
    """
    report = IntegrityReport(trace_id=trace_id, timestamp=timestamp)

    try:
        norm_post = normalize_constraint_text(post_text)
        raw_post = (post_text or "")

        for rec in records:
            norm_text = normalize_constraint_text(rec.text)
            status = "lost"
            matched_via = ""
            detail = ""

            if norm_text and norm_text in norm_post:
                status = "preserved"
                matched_via = "normalized"
            else:
                frags = _summary_fragments(rec.summary or rec.text)
                if frags:
                    hits = [f for f in frags if f in raw_post or
                            normalize_constraint_text(f) in norm_post]
                    ratio = len(hits) / len(frags)
                    if ratio >= 1.0:
                        status = "preserved"
                        matched_via = "fragments_full"
                    elif ratio >= _FRAGMENT_HIT_RATIO:
                        status = "degraded"
                        matched_via = "fragments"
                        detail = f"命中 {len(hits)}/{len(frags)} 个关键片段"
                    else:
                        detail = f"仅命中 {len(hits)}/{len(frags)} 个关键片段"

            report.findings.append(IntegrityFinding(
                constraint_id=rec.constraint_id,
                status=status,
                priority=rec.priority,
                strength=rec.strength,
                detail=detail,
                matched_via=matched_via,
            ))

        report.total = len(report.findings)
        report.preserved = sum(1 for f in report.findings if f.status == "preserved")
        report.degraded = sum(1 for f in report.findings if f.status == "degraded")
        report.lost = sum(1 for f in report.findings if f.status == "lost")
        report.conflicted = sum(1 for f in report.findings if f.status == "conflicted")
        report.reinject_ids = [
            f.constraint_id for f in report.findings
            if f.status in ("lost", "degraded", "conflicted")
        ]
        report.blocking = any(f.is_blocking() for f in report.findings)

    except Exception as e:  # noqa: BLE001 — 必须兜住，转为失败安全降级
        report.detector_failed = True
        report.detector_error = f"{type(e).__name__}: {e}"
        # 检测器坏了 → 全部标记需重注入（宁可多注入，不可漏注入）
        report.reinject_ids = [r.constraint_id for r in records]

    return report


def _summary_fragments(text: str) -> list[str]:
    """把约束摘要切成关键片段，用于语义降级判定。

    切法：按标点/空白切分，保留长度 >= _FRAGMENT_MIN_LEN 的片段。
    """
    parts = [p.strip() for p in re.split(r"[\s，。；：、,.;:!?！？()（）]+", text or "")]
    return [p for p in parts if len(p) >= _FRAGMENT_MIN_LEN]


def detect_conflicts(records: list[ConstraintRecord]) -> list[tuple[str, str, str]]:
    """检测约束之间的直接冲突。

    首版只做**可判定**的一类：同一归一化文本却有不同 text_hash
    （说明同一条约束被改写过），或同 ID 不同优先级。

    ⚠️ 不做语义冲突推断 —— 那需要 LLM 判断，属于"推断"层，
    按方案 §1.3「召回只返回证据」的原则，不在此处伪装成确定性结论。

    Returns:
        [(id_a, id_b, reason), ...]
    """
    conflicts: list[tuple[str, str, str]] = []
    by_id: dict[str, ConstraintRecord] = {}
    for r in records:
        prev = by_id.get(r.constraint_id)
        if prev is None:
            by_id[r.constraint_id] = r
            continue
        if prev.text_hash != r.text_hash:
            conflicts.append((prev.constraint_id, r.constraint_id,
                              "同 ID 不同原文哈希（约束被改写）"))
        elif prev.priority != r.priority:
            conflicts.append((prev.constraint_id, r.constraint_id,
                              f"同 ID 不同优先级（{prev.priority} vs {r.priority}）"))
    return conflicts


def select_reinject_records(
    records: list[ConstraintRecord],
    report: IntegrityReport,
) -> list[ConstraintRecord]:
    """按检测结果挑出需要重注入的约束（方案 §6.2：按需重注入）。

    失败安全：`detector_failed=True` 时返回**全部**记录，
    退回旧的「无条件全量重注入」行为。
    """
    if report.detector_failed:
        return list(records)
    wanted = set(report.reinject_ids)
    return [r for r in records if r.constraint_id in wanted]
