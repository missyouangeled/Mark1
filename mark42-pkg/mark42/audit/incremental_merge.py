"""增量上下文合并（方案 44 建设项 A / Phase 2）。

职责
----
把「旧 ContextState + 新增消息」按**确定性协议**合并成新版状态，
替代 `armor._compress_build_index()` 每次从会话尾部全量重新生成的做法。

流程（方案 §4.3）
-----------------
    1. 读取上一版 context-state.json
    2. 按 source_cursor 只读新增消息与本次即将截断区间
    3. 先做确定性抽取，再让 LLM 对「候选变更」输出 patch
    4. patch 经 schema 校验、引用校验、冲突检测
    5. 原子写入新版本，保留历史版本
    6. 任何失败都回退 `_compress_build_index()`

合并规则（方案 §4.3，全部在本模块实现为可测函数）
------------------------------------------------
    - 决策以新明确决定覆盖旧决定，但保留 supersedes 链
    - 用户明确约束不可被模型摘要删除，只能被更新或撤销
    - 文件修改以路径为键合并，记录最后状态
    - 已完成任务不得重新回到 active，除非新消息明确重开
    - 无来源的新增事实拒绝入库

⚠️ 本模块不含 LLM 调用
---------------------
LLM 交互留在 `armor` 侧（那里已有 `_llm_analyze` 的 provider 解析逻辑），
本模块只负责**接收 patch 并安全合并**。这样切分的好处：
合并逻辑可在无网络、无模型的环境下 100% 确定性测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..context_state import (
    ContextState,
    ValidationReport,
    now_iso,
    validate_context_state,
)

MERGE_SCHEMA_VERSION = 1

#: 单次 patch 允许的最大条目数（方案 §4.5 max_patch_items）
DEFAULT_MAX_PATCH_ITEMS = 100


# ── patch 操作类型 ────────────────────────────────────

OP_ADD = "add"
OP_UPDATE = "update"
OP_SUPERSEDE = "supersede"
OP_COMPLETE = "complete"
OP_REVOKE = "revoke"

PATCH_OPS = (OP_ADD, OP_UPDATE, OP_SUPERSEDE, OP_COMPLETE, OP_REVOKE)

#: patch 允许触碰的字段。**不含 source_cursor / schema_version** ——
#: 那两个由合并器自己维护，不能让模型改（否则模型可以伪造游标位置）。
PATCHABLE_FIELDS = (
    "session_intent",
    "active_task",
    "decisions",
    "constraints",
    "artifacts",
    "completed_work",
    "open_questions",
    "next_steps",
    "evidence_refs",
    "inferences",
)

#: 禁止 patch 的字段——出现即视为非法 patch
PROTECTED_FIELDS = ("schema_version", "source_cursor", "generated_at")


# ── 拒绝原因 ──────────────────────────────────────────

class RejectReason:
    """patch 被拒的原因（全部可测、可上报）。"""

    NOT_A_DICT = "patch_not_a_dict"
    UNKNOWN_FIELD = "unknown_field"
    PROTECTED_FIELD = "protected_field"
    BAD_OP = "bad_op"
    TOO_MANY_ITEMS = "too_many_items"
    MISSING_EVIDENCE = "missing_evidence"
    HARD_CONSTRAINT_DELETION = "hard_constraint_deletion"
    DONE_TASK_REACTIVATED = "done_task_reactivated"
    DANGLING_SUPERSEDES = "dangling_supersedes"
    INFERENCE_AS_FACT = "inference_as_fact"
    VALIDATION_FAILED = "post_merge_validation_failed"
    BAD_ITEM_TYPE = "bad_item_type"


@dataclass
class MergeIssue:
    """单条合并问题。"""

    code: str
    field: str = ""
    detail: str = ""

    def __str__(self) -> str:
        loc = f"{self.field}: " if self.field else ""
        return f"{loc}{self.code}{' — ' + self.detail if self.detail else ''}"


@dataclass
class MergeResult:
    """合并结果。

    `ok=False` 时调用方**必须**丢弃 `state` 并回退到旧的全量路径
    —— 部分接受是禁止的（方案 §4.3：patch 非法时零污染）。
    """

    ok: bool
    state: ContextState | None = None
    issues: list[MergeIssue] = field(default_factory=list)
    applied_ops: int = 0
    rejected_ops: int = 0
    #: 供事件上报的合并统计
    stats: dict[str, Any] = field(default_factory=dict)

    def codes(self) -> list[str]:
        return [i.code for i in self.issues]

    def summary(self) -> str:
        if self.ok:
            return f"ok (applied={self.applied_ops})"
        return "; ".join(str(i) for i in self.issues[:10])


# ── patch 校验 ────────────────────────────────────────


def validate_patch(
    patch: dict[str, Any],
    *,
    max_items: int = DEFAULT_MAX_PATCH_ITEMS,
) -> list[MergeIssue]:
    """校验 patch 结构合法性（不看语义，只看形状与权限）。

    patch 形状：

        {
          "session_intent": "新目标",              # 标量字段直接给值
          "decisions": [{"op": "add", ...}],       # 列表字段给操作数组
          "active_task": {"op": "update", ...}
        }

    Returns:
        问题列表。空列表表示形状合法。
    """
    issues: list[MergeIssue] = []

    if not isinstance(patch, dict):
        return [MergeIssue(code=RejectReason.NOT_A_DICT,
                           detail=f"收到 {type(patch).__name__}")]

    total_items = 0

    for fname, value in patch.items():
        if fname in PROTECTED_FIELDS:
            issues.append(MergeIssue(
                code=RejectReason.PROTECTED_FIELD, field=fname,
                detail="该字段由合并器维护，patch 不得触碰"))
            continue
        if fname not in PATCHABLE_FIELDS:
            issues.append(MergeIssue(
                code=RejectReason.UNKNOWN_FIELD, field=fname))
            continue

        # 标量字段：session_intent
        if fname == "session_intent":
            if not isinstance(value, str):
                issues.append(MergeIssue(
                    code=RejectReason.BAD_ITEM_TYPE, field=fname,
                    detail="session_intent 必须是字符串"))
            continue

        # active_task：单个 dict
        if fname == "active_task":
            if not isinstance(value, dict):
                issues.append(MergeIssue(
                    code=RejectReason.BAD_ITEM_TYPE, field=fname,
                    detail="active_task 必须是 dict"))
                continue
            op = value.get("op", OP_UPDATE)
            if op not in PATCH_OPS:
                issues.append(MergeIssue(
                    code=RejectReason.BAD_OP, field=fname, detail=f"op={op!r}"))
            total_items += 1
            continue

        # 列表字段：操作数组
        if not isinstance(value, list):
            issues.append(MergeIssue(
                code=RejectReason.BAD_ITEM_TYPE, field=fname,
                detail=f"{fname} 必须是 list"))
            continue

        for item in value:
            total_items += 1
            if not isinstance(item, dict):
                issues.append(MergeIssue(
                    code=RejectReason.BAD_ITEM_TYPE, field=fname,
                    detail=f"条目必须是 dict，收到 {type(item).__name__}"))
                continue
            op = item.get("op", OP_ADD)
            if op not in PATCH_OPS:
                issues.append(MergeIssue(
                    code=RejectReason.BAD_OP, field=fname, detail=f"op={op!r}"))

    if total_items > max_items:
        issues.append(MergeIssue(
            code=RejectReason.TOO_MANY_ITEMS,
            detail=f"{total_items} 条超过上限 {max_items}"))

    return issues


# ── 合并规则实现（方案 §4.3）──────────────────────────


def _item_key(item: dict[str, Any], field_name: str) -> str:
    """取条目的合并主键。

    方案 §4.3 明确：**文件修改以路径为键合并**。
    其余字段优先用显式 id，退回标题 / 归一化摘要文本。

    ⚠️ `title` 必须在候选里：active_task / completed_work 用的是 `title`，
    不把它算进主键会导致任务键永远为空串 ——
    于是“已完成任务不得重开”与“换任务要留痕”两条规则全部失效（静默失效）。
    """
    if field_name == "artifacts":
        return str(item.get("path", "")).strip()
    for key in ("decision_id", "constraint_id", "id"):
        val = item.get(key)
        if val:
            return str(val)
    text = item.get("title") or item.get("summary") or item.get("text") or ""
    return " ".join(str(text).split())[:80]


def _has_evidence(item: dict[str, Any]) -> bool:
    """与 context_state._has_evidence 保持同一口径（真值判定）。"""
    for key in ("evidence", "evidence_ref", "message_id", "source",
                "source_path", "cursor", "line"):
        if item.get(key):
            return True
    return False


def _strip_op(item: dict[str, Any]) -> dict[str, Any]:
    """去掉 patch 专用的 op 字段，得到入库形状。"""
    return {k: v for k, v in item.items() if k != "op"}


def merge_list_field(
    old_items: list[dict[str, Any]],
    ops: list[dict[str, Any]],
    field_name: str,
    *,
    require_evidence: bool = True,
) -> tuple[list[dict[str, Any]], list[MergeIssue], int]:
    """合并一个列表字段。

    Returns:
        (合并后列表, 问题列表, 成功应用的操作数)
    """
    issues: list[MergeIssue] = []
    applied = 0

    # 保序索引：key -> 在结果列表中的位置
    result = [dict(i) for i in old_items]
    index: dict[str, int] = {}
    for pos, item in enumerate(result):
        index.setdefault(_item_key(item, field_name), pos)

    for raw in ops:
        op = raw.get("op", OP_ADD)
        payload = _strip_op(raw)
        key = _item_key(payload, field_name)

        # 无来源的新增事实拒绝入库（方案 §4.3）
        if require_evidence and op in (OP_ADD, OP_UPDATE) and \
                field_name in ("decisions", "constraints", "artifacts") and \
                not _has_evidence(payload):
            issues.append(MergeIssue(
                code=RejectReason.MISSING_EVIDENCE, field=field_name,
                detail=f"条目 {key!r} 缺少来源引用"))
            continue

        # 推断不得自称事实
        if field_name == "inferences" and payload.get("is_fact") is True:
            issues.append(MergeIssue(
                code=RejectReason.INFERENCE_AS_FACT, field=field_name,
                detail=f"条目 {key!r} 标记 is_fact=True"))
            continue

        if op == OP_ADD:
            if key and key in index:
                # 同键重复 add 视为 update，避免状态里出现重复项
                result[index[key]].update(payload)
            else:
                result.append(payload)
                if key:
                    index[key] = len(result) - 1
            applied += 1

        elif op == OP_UPDATE:
            if key and key in index:
                result[index[key]].update(payload)
                applied += 1
            else:
                # 更新不存在的条目 → 退化为新增（但仍需 evidence，上面已查）
                result.append(payload)
                if key:
                    index[key] = len(result) - 1
                applied += 1

        elif op == OP_SUPERSEDE:
            # 新决定覆盖旧决定，但**保留 supersedes 链**（方案 §4.3）
            target = payload.get("supersedes")
            targets = target if isinstance(target, list) else ([target] if target else [])
            known_ids = {
                i.get("decision_id") for i in result if i.get("decision_id")
            }
            missing = [t for t in targets if t not in known_ids]
            if missing:
                issues.append(MergeIssue(
                    code=RejectReason.DANGLING_SUPERSEDES, field=field_name,
                    detail=f"supersedes 指向不存在的 id: {missing}"))
                continue
            # 旧决定标记为被取代，但不删除（链要留着）
            for i in result:
                if i.get("decision_id") in targets:
                    i["superseded_by"] = payload.get("decision_id", key)
            result.append(payload)
            if key:
                index[key] = len(result) - 1
            applied += 1

        elif op == OP_REVOKE:
            # 撤销：只允许对 soft 约束真删，hard 约束标记而不删（方案 §4.3）
            if key not in index:
                applied += 1  # 撤销不存在的东西是幂等的，不算错
                continue
            pos = index[key]
            existing = result[pos]
            if field_name == "constraints" and \
                    existing.get("strength") == "hard":
                issues.append(MergeIssue(
                    code=RejectReason.HARD_CONSTRAINT_DELETION,
                    field=field_name,
                    detail=f"hard 约束 {key!r} 不可被删除，只能更新或显式撤销"))
                continue
            existing["revoked"] = True
            existing["revoked_reason"] = payload.get("reason", "")
            applied += 1

        elif op == OP_COMPLETE:
            if key in index:
                result[index[key]]["status"] = "done"
            applied += 1

    return result, issues, applied


# ── active_task 合并 ──────────────────────────────────


def merge_active_task(
    old_task: dict[str, Any],
    patch_task: dict[str, Any],
    completed_work: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[MergeIssue], int]:
    """合并 active_task。

    规则（方案 §4.3）：
        - active_task 只能有一个当前状态，历史进入 completed_work；
        - **已完成任务不得重新回到 active**，除非新消息明确重开
          （patch 需显式带 `reopen: True`）。

    Returns:
        (新 active_task, 新 completed_work, 问题列表, 应用数)
    """
    issues: list[MergeIssue] = []
    new_completed = [dict(i) for i in completed_work]
    payload = _strip_op(patch_task)
    op = patch_task.get("op", OP_UPDATE)

    # 标记完成 → 移入 completed_work，active 清空
    if op == OP_COMPLETE:
        if old_task:
            done = dict(old_task)
            done["status"] = "done"
            done.update({k: v for k, v in payload.items() if k != "reopen"})
            new_completed.append(done)
        return {}, new_completed, issues, 1

    # 重开已完成任务：必须显式 reopen
    completed_keys = {
        _item_key(i, "completed_work") for i in new_completed
    }
    new_key = _item_key(payload, "active_task")
    if new_key and new_key in completed_keys and not payload.get("reopen"):
        issues.append(MergeIssue(
            code=RejectReason.DONE_TASK_REACTIVATED, field="active_task",
            detail=f"任务 {new_key!r} 已完成，重开需显式 reopen=True"))
        return dict(old_task), new_completed, issues, 0

    # 换任务：旧的未完成任务也要留痕（不能凭空消失）
    if old_task and _item_key(old_task, "active_task") != new_key:
        parked = dict(old_task)
        parked.setdefault("status", "pending")
        parked["parked_reason"] = "superseded_by_new_active_task"
        new_completed.append(parked)
        merged = payload
    else:
        merged = {**old_task, **payload}

    merged.pop("reopen", None)
    return merged, new_completed, issues, 1


# ── 主入口 ────────────────────────────────────────────


def merge_patch(
    old_state: ContextState,
    patch: dict[str, Any],
    *,
    require_evidence: bool = True,
    max_patch_items: int = DEFAULT_MAX_PATCH_ITEMS,
) -> MergeResult:
    """把 patch 合并进旧状态，返回新状态。

    **零污染保证**：任何一步失败都返回 `ok=False` 且 `state=None`，
    绝不返回"部分合并"的状态 —— 调用方据此回退到全量路径。

    Args:
        old_state: 上一版状态（不会被修改）
        patch: LLM 产出的候选变更
        require_evidence: 无来源的新增事实是否拒绝入库

    Returns:
        MergeResult
    """
    issues = validate_patch(patch, max_items=max_patch_items)
    if issues:
        return MergeResult(ok=False, issues=issues,
                           stats={"stage": "validate_patch"})

    # 从旧状态深拷一份（避免就地修改）
    new_state = ContextState.from_dict(old_state.to_dict())
    applied = 0

    # ── session_intent ──
    if "session_intent" in patch:
        new_state.session_intent = patch["session_intent"]
        applied += 1

    # ── active_task（要联动 completed_work）──
    if "active_task" in patch:
        task, completed, task_issues, n = merge_active_task(
            new_state.active_task, patch["active_task"], new_state.completed_work)
        issues.extend(task_issues)
        new_state.active_task = task
        new_state.completed_work = completed
        applied += n

    # ── 列表字段 ──
    for fname in PATCHABLE_FIELDS:
        if fname in ("session_intent", "active_task"):
            continue
        if fname not in patch:
            continue
        merged, field_issues, n = merge_list_field(
            getattr(new_state, fname), patch[fname], fname,
            require_evidence=require_evidence)
        issues.extend(field_issues)
        setattr(new_state, fname, merged)
        applied += n

    if issues:
        return MergeResult(ok=False, issues=issues, applied_ops=applied,
                           rejected_ops=len(issues),
                           stats={"stage": "merge_fields"})

    # ── 合并后必须通过完整 schema 校验 ──
    new_state.generated_at = now_iso()
    report: ValidationReport = validate_context_state(
        new_state, require_evidence=require_evidence)
    if not report.ok:
        return MergeResult(
            ok=False,
            issues=[MergeIssue(code=RejectReason.VALIDATION_FAILED,
                               detail=report.summary())],
            applied_ops=applied,
            stats={"stage": "post_validate", "codes": report.codes()},
        )

    return MergeResult(
        ok=True,
        state=new_state,
        applied_ops=applied,
        stats={
            "stage": "done",
            "itemCount": new_state.item_count(),
            "fingerprint": new_state.fingerprint(),
        },
    )
