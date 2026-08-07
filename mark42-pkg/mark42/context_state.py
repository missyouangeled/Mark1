"""ContextState：结构化上下文状态契约（方案 44 建设项 A / Phase 0 冻结）。

背景
----
`armor._compress_build_index()` 每次从会话尾部**全量**重新生成 `memory-index.json`：

    - LLM 返回形状可能漂移，字段不稳定；
    - 没有"旧摘要 + 新增消息"的确定性合并协议；
    - 不记录本轮覆盖到哪个消息 / 字节位置；
    - 全量重分析既贵，又容易让早期决策被后续摘要覆盖。

本模块定义**版本化的状态契约**，作为增量压缩的数据地基。

⚠️ 边界（方案 §4 / §18 明确）
-----------------------------
1. `ContextState` 与 `source_cursor` 都是**新增旁路能力**，不是既有接入点；
2. 只能旁路扩展 Armor，**不修改也不替代 OpenClaw 官方 compact 流程**；
3. `memory-index.json` 保留为兼容视图，由 ContextState 渲染生成；
4. 本模块**纯数据契约 + 校验**，不含 LLM 调用、不含文件写入编排。

设计原则
--------
- 召回与推断分离：evidence 与 inferences 永不混存；
- 无来源的新增事实拒绝入库（`require_evidence`）；
- 游标失效即全量回退，禁止猜测续接；
- schema_version 由配置迁移器管理，向后兼容。
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# ── 版本 ──────────────────────────────────────────────

#: 当前 ContextState schema 版本。
#: 变更规则：新增可选字段不升版本；删除/重命名/语义变更必须升版本并写迁移。
CONTEXT_STATE_SCHEMA_VERSION = 1

#: 状态文件名（落盘时使用，实际路径由 armor 侧决定）
CONTEXT_STATE_FILENAME = "context-state.json"


# ── 枚举与常量 ────────────────────────────────────────

#: 约束强度。hard 不可被模型摘要删除，只能被更新或显式撤销。
CONSTRAINT_STRENGTH = ("hard", "soft")

#: 约束优先级（方案 §6.3）。P0 任何失败都阻断；P1 告警并重注入；P2 只记趋势。
CONSTRAINT_PRIORITY = ("P0", "P1", "P2")

#: active_task 允许的状态。
TASK_STATUS = ("pending", "in_progress", "blocked", "done")

#: 置信度下限——低于此值的条目不得作为事实使用。
MIN_FACT_CONFIDENCE = 0.5

#: 单个列表字段的最大条目数，防止状态无边界膨胀。
MAX_ITEMS_PER_FIELD = 200

#: 需要携带来源引用的字段（方案 §4.2）。
EVIDENCE_REQUIRED_FIELDS = ("decisions", "constraints", "artifacts")


# ── 游标失效原因 ──────────────────────────────────────

class CursorInvalidReason:
    """游标失效原因常量（方案 §4.2：失效即全量回退）。"""

    OK = "ok"
    NO_CURSOR = "no_cursor"
    SESSION_MISMATCH = "session_mismatch"
    INODE_CHANGED = "inode_changed"
    FILE_ROTATED = "file_rotated"
    FILE_TRUNCATED = "file_truncated"
    OFFSET_OUT_OF_RANGE = "offset_out_of_range"
    PREFIX_HASH_MISMATCH = "prefix_hash_mismatch"
    MESSAGE_ID_GAP = "message_id_gap"
    SCHEMA_VERSION_MISMATCH = "schema_version_mismatch"
    MALFORMED = "malformed"


# ── 数据模型 ──────────────────────────────────────────


@dataclass
class SourceCursor:
    """来源游标：记录本轮增量覆盖到哪里。

    方案 §4.2 首版固定字段：session_id、来源文件标识、inode、
    已读字节偏移、最后消息 ID、观测文件大小、前缀哈希。

    任一项不符即失效并全量回退——**禁止猜测续接**。
    """

    session_id: str = ""
    source_path: str = ""
    inode: int = 0
    byte_offset: int = 0
    last_message_id: str = ""
    observed_size: int = 0
    prefix_hash: str = ""
    #: 已消费的消息条数，用于连续性检查
    message_count: int = 0
    updated_at: str = ""

    def is_populated(self) -> bool:
        """游标是否已被填充过（未填充等于首次全量）。"""
        return bool(self.session_id and self.source_path)

    def validate_against(
        self,
        *,
        session_id: str,
        inode: int,
        current_size: int,
        prefix_hash: str,
        observed_last_message_id: str | None = None,
    ) -> str:
        """对照当前文件实况校验游标有效性。

        Args:
            session_id: 当前会话 ID
            inode: 来源文件当前 inode（0 表示调用方无法取得，跳过该项）
            current_size: 来源文件当前字节大小
            prefix_hash: 对 `[0, byte_offset)` 区间重算出的前缀哈希
                （空串表示调用方未计算，跳过该项）
            observed_last_message_id: 在 `byte_offset` 之前实际读到的最后一条
                消息 ID。传入 None 表示调用方不做该项校验；传入具体值时必须与
                游标记录一致，否则判定消息 ID 断裂。

        Returns:
            `CursorInvalidReason` 中的一个常量。`OK` 表示可安全增量续接。
        """
        if not self.is_populated():
            return CursorInvalidReason.NO_CURSOR
        if session_id and self.session_id != session_id:
            return CursorInvalidReason.SESSION_MISMATCH
        # inode 变化 = 文件被替换/轮替，旧偏移无意义
        if inode and self.inode and inode != self.inode:
            return CursorInvalidReason.INODE_CHANGED
        # 文件变小 = 被截断或重写
        if current_size < self.observed_size:
            return CursorInvalidReason.FILE_TRUNCATED
        # 偏移越过文件尾
        if self.byte_offset > current_size:
            return CursorInvalidReason.OFFSET_OUT_OF_RANGE
        # 前缀哈希不符 = 已读区间内容被改写
        if self.prefix_hash and prefix_hash and self.prefix_hash != prefix_hash:
            return CursorInvalidReason.PREFIX_HASH_MISMATCH
        # 消息 ID 断裂：调用方给出了实测值，但与游标记录不一致
        if (
            observed_last_message_id is not None
            and self.last_message_id
            and observed_last_message_id != self.last_message_id
        ):
            return CursorInvalidReason.MESSAGE_ID_GAP
        return CursorInvalidReason.OK


@dataclass
class ContextState:
    """结构化上下文状态（方案 §4.2）。

    字段要求：
        - decisions/constraints/artifacts 必须携带来源游标或消息 ID；
        - active_task 只能有一个当前状态，历史进入 completed_work；
        - 不确定信息标 confidence，不得自动写成事实；
        - 推断必须单列 inferences，不能混入 evidence。
    """

    schema_version: int = CONTEXT_STATE_SCHEMA_VERSION
    session_intent: str = ""
    active_task: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    completed_work: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[dict[str, Any]] = field(default_factory=list)
    next_steps: list[dict[str, Any]] = field(default_factory=list)
    source_cursor: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    #: 推断单列（方案 §4.2）——永不与 evidence 混存
    inferences: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextState:
        """从 dict 构造，忽略未知字段（向后兼容新版本写的额外字段）。"""
        if not isinstance(data, dict):
            raise TypeError(f"ContextState 需要 dict，收到 {type(data).__name__}")
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_json(cls, text: str) -> ContextState:
        return cls.from_dict(json.loads(text))

    # ── 便捷访问 ──────────────────────────────────────

    def cursor(self) -> SourceCursor:
        """把 source_cursor dict 还原为 SourceCursor。"""
        data = self.source_cursor or {}
        known = {f for f in SourceCursor.__dataclass_fields__}
        return SourceCursor(**{k: v for k, v in data.items() if k in known})

    def set_cursor(self, cursor: SourceCursor) -> None:
        self.source_cursor = asdict(cursor)

    def hard_constraints(self) -> list[dict[str, Any]]:
        """返回所有 hard 约束——这些不可被摘要删除。"""
        return [c for c in self.constraints if c.get("strength") == "hard"]

    def item_count(self) -> int:
        """状态内条目总数，用于观测状态体积。"""
        return sum(
            len(getattr(self, f))
            for f in (
                "decisions", "constraints", "artifacts", "completed_work",
                "open_questions", "next_steps", "evidence_refs", "inferences",
            )
        )

    def fingerprint(self) -> str:
        """内容指纹：忽略 generated_at，用于判定"同输入是否同结果"。"""
        payload = self.to_dict()
        payload.pop("generated_at", None)
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


# ── 校验 ──────────────────────────────────────────────


@dataclass
class ValidationIssue:
    """单条校验问题。"""

    field: str
    index: int | None
    code: str
    message: str

    def __str__(self) -> str:
        loc = self.field if self.index is None else f"{self.field}[{self.index}]"
        return f"{loc}: {self.code} — {self.message}"


@dataclass
class ValidationReport:
    """校验报告。`ok` 为 False 时调用方必须拒绝入库并全量回退。"""

    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def codes(self) -> list[str]:
        return [i.code for i in self.issues]

    def summary(self) -> str:
        if self.ok:
            return "ok"
        return "; ".join(str(i) for i in self.issues[:10])


_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def validate_context_state(
    state: ContextState,
    *,
    require_evidence: bool = True,
    max_items: int = MAX_ITEMS_PER_FIELD,
) -> ValidationReport:
    """校验 ContextState 是否符合契约。

    Args:
        state: 待校验状态
        require_evidence: 为 True 时，decisions/constraints/artifacts
            必须携带来源引用；无来源的新增事实拒绝入库（方案 §4.3）。
        max_items: 单字段最大条目数

    Returns:
        ValidationReport。`ok=False` 时调用方必须回退，不得部分接受。
    """
    issues: list[ValidationIssue] = []

    def add(f: str, idx: int | None, code: str, msg: str) -> None:
        issues.append(ValidationIssue(field=f, index=idx, code=code, message=msg))

    # ── schema 版本 ──
    if not isinstance(state.schema_version, int) or state.schema_version < 1:
        add("schema_version", None, "bad_schema_version",
            f"必须是 >=1 的整数，收到 {state.schema_version!r}")
    elif state.schema_version > CONTEXT_STATE_SCHEMA_VERSION:
        add("schema_version", None, "future_schema_version",
            f"状态版本 {state.schema_version} 高于本代码支持的 "
            f"{CONTEXT_STATE_SCHEMA_VERSION}，需先升级迁移器")

    # ── 时间戳 ──
    if state.generated_at and not _ISO_RE.match(state.generated_at):
        add("generated_at", None, "bad_timestamp",
            f"需要 ISO-8601 形状，收到 {state.generated_at!r}")

    # ── active_task 唯一性 ──
    at = state.active_task
    if at:
        if not isinstance(at, dict):
            add("active_task", None, "bad_type", "必须是 dict")
        else:
            status = at.get("status")
            if status is not None and status not in TASK_STATUS:
                add("active_task", None, "bad_status",
                    f"status 必须属于 {TASK_STATUS}，收到 {status!r}")
            if not at.get("title") and not at.get("description"):
                add("active_task", None, "empty_task",
                    "active_task 非空时必须至少有 title 或 description")
            # 已完成任务不应留在 active（方案 §4.3）
            if status == "done":
                add("active_task", None, "done_task_still_active",
                    "status=done 的任务必须移入 completed_work")

    # ── 列表字段通用检查 ──
    list_fields = (
        "decisions", "constraints", "artifacts", "completed_work",
        "open_questions", "next_steps", "evidence_refs", "inferences",
    )
    for fname in list_fields:
        items = getattr(state, fname)
        if not isinstance(items, list):
            add(fname, None, "bad_type", "必须是 list")
            continue
        if len(items) > max_items:
            add(fname, None, "too_many_items",
                f"{len(items)} 条超过上限 {max_items}")
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                add(fname, idx, "bad_item_type",
                    f"条目必须是 dict，收到 {type(item).__name__}")
                continue
            # confidence 合法性
            conf = item.get("confidence")
            if conf is not None:
                if not isinstance(conf, (int, float)) or isinstance(conf, bool):
                    add(fname, idx, "bad_confidence",
                        f"confidence 必须是数字，收到 {conf!r}")
                elif not (0.0 <= float(conf) <= 1.0):
                    add(fname, idx, "confidence_out_of_range",
                        f"confidence 必须在 0..1，收到 {conf}")
            # 来源引用
            if require_evidence and fname in EVIDENCE_REQUIRED_FIELDS:
                if not _has_evidence(item):
                    add(fname, idx, "missing_evidence",
                        "缺少来源引用（需 evidence / message_id / source / cursor 之一）")

    # ── 约束专项 ──
    seen_cids: set[str] = set()
    for idx, c in enumerate(state.constraints):
        if not isinstance(c, dict):
            continue
        strength = c.get("strength")
        if strength is not None and strength not in CONSTRAINT_STRENGTH:
            add("constraints", idx, "bad_strength",
                f"strength 必须属于 {CONSTRAINT_STRENGTH}，收到 {strength!r}")
        prio = c.get("priority")
        if prio is not None and prio not in CONSTRAINT_PRIORITY:
            add("constraints", idx, "bad_priority",
                f"priority 必须属于 {CONSTRAINT_PRIORITY}，收到 {prio!r}")
        cid = c.get("constraint_id")
        if cid:
            if cid in seen_cids:
                add("constraints", idx, "duplicate_constraint_id",
                    f"constraint_id 重复: {cid}")
            seen_cids.add(cid)
        if not c.get("text") and not c.get("summary"):
            add("constraints", idx, "empty_constraint",
                "约束必须有 text 或 summary")

    # ── 推断不得混入 evidence ──
    for idx, inf in enumerate(state.inferences):
        if not isinstance(inf, dict):
            continue
        if inf.get("is_fact") is True:
            add("inferences", idx, "inference_marked_fact",
                "inferences 条目不得标记 is_fact=True（召回与推断分离）")

    # ── 决策 supersedes 链引用完整性 ──
    decision_ids = {
        d.get("decision_id") for d in state.decisions
        if isinstance(d, dict) and d.get("decision_id")
    }
    for idx, d in enumerate(state.decisions):
        if not isinstance(d, dict):
            continue
        sup = d.get("supersedes")
        if sup:
            refs = sup if isinstance(sup, list) else [sup]
            for r in refs:
                if r not in decision_ids:
                    add("decisions", idx, "dangling_supersedes",
                        f"supersedes 指向不存在的 decision_id: {r!r}")

    return ValidationReport(ok=not issues, issues=issues)


def _has_evidence(item: dict[str, Any]) -> bool:
    """判断条目是否携带可追溯来源。"""
    for key in ("evidence", "evidence_ref", "message_id", "source",
                "source_path", "cursor", "line"):
        val = item.get(key)
        if val not in (None, "", [], {}):
            return True
    return False


# ── 工具函数 ──────────────────────────────────────────


def now_iso() -> str:
    """本地时区 ISO 时间戳（与 utils._now_iso 保持同形状）。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_empty_state(*, session_intent: str = "") -> ContextState:
    """构造一个通过校验的空状态（首次运行 / 全量回退后的起点）。"""
    return ContextState(
        schema_version=CONTEXT_STATE_SCHEMA_VERSION,
        session_intent=session_intent,
        generated_at=now_iso(),
    )


def compute_prefix_hash(data: bytes) -> str:
    """计算已读区间前缀哈希（游标校验用）。"""
    return hashlib.sha256(data).hexdigest()[:32]


def render_memory_index_view(state: ContextState) -> dict[str, Any]:
    """把 ContextState 渲染成兼容的 memory-index 视图（方案 §4.4）。

    目的：`memory-index.json` 的既有消费方不受影响。
    本函数**只读**，不写文件。
    """
    preserved: dict[str, Any] = {
        "sessionIntent": state.session_intent,
        "activeTask": state.active_task,
        "decisions": [
            d.get("summary") or d.get("text", "") for d in state.decisions
        ][:20],
        "constraints": [
            c.get("summary") or c.get("text", "") for c in state.constraints
        ][:30],
        "artifacts": [
            a.get("path", "") for a in state.artifacts if a.get("path")
        ][:50],
        "nextSteps": [
            n.get("summary") or n.get("text", "") for n in state.next_steps
        ][:20],
    }
    return {
        "generatedAt": state.generated_at or now_iso(),
        "modelGenerated": True,
        "strategyUsed": "structured-incremental",
        "schemaVersion": state.schema_version,
        "preserved": preserved,
        "discarded": {"summary": "见 completed_work", "count": len(state.completed_work)},
        "inferences": state.inferences,
        "stateFingerprint": state.fingerprint(),
        "itemCount": state.item_count(),
    }
