"""局部重规划 + Checkpoint（方案 44 建设项 D / Phase 4 第二块）。

方案 §7.4：节点失败时冻结下游，不影响已完成或无关分支。
重规划只能调整未执行节点，不得偷偷改已批准动作。

设计原则
--------
- LocalReplanner 输入只含失败节点 + 直接下游 + 剩余预算 + 已完成摘要
- 输出必须是 JSON Patch，经过 TaskGraphValidator 后生成 plan_version+1
- 禁止让模型重写整张图
- 新增高风险动作 / 扩大写入范围 / 超预算时必须重新问用户
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .heavy_graph import (
    GraphValidationResult,
    ResourceBudget,
    TaskGraph,
    TaskNode,
    validate_graph,
)

#: 允许的 patch 操作
REPLAN_OPS = ("retry", "skip", "replace", "split", "merge")

#: 重规划不允许触碰的字段
REPLAN_PROTECTED = ("graph_id", "total_budget")


@dataclass
class ReplanRequest:
    """重规划请求。"""

    failed_node_id: str
    failure_reason: str = ""
    #: 受影响的下游节点 ID（直接 + 间接）
    affected_downstream: list[str] = field(default_factory=list)
    #: 剩余预算
    remaining_budget: ResourceBudget = field(default_factory=ResourceBudget)
    #: 已完成节点的不可变输出摘要
    completed_summaries: dict[str, str] = field(default_factory=dict)
    #: 允许的动作白名单
    allowed_ops: tuple[str, ...] = REPLAN_OPS


@dataclass
class ReplanResult:
    """重规划结果。"""

    ok: bool = False
    plan_version: int = 0
    patches: list[dict[str, Any]] = field(default_factory=list)
    rejected_reason: str = ""
    requires_user_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "planVersion": self.plan_version,
            "patches": list(self.patches),
            "rejectedReason": self.rejected_reason,
            "requiresUserApproval": self.requires_user_approval,
        }


def local_replan(
    graph: TaskGraph,
    request: ReplanRequest,
    patches: list[dict[str, Any]],
) -> ReplanResult:
    """应用局部重规划 patch（方案 §7.4）。

    Args:
        graph: 当前图（不会被修改）
        request: 重规划请求
        patches: 候选 patch 列表，每条形如
            {"op": "retry", "node_id": "x"}
            {"op": "skip", "node_id": "x"}
            {"op": "replace", "node_id": "x", "new_node": {...}}
            {"op": "split", "node_id": "x", "into": [{...}, {...}]}
            {"op": "merge", "node_ids": ["x", "y"], "into": {...}}

    Returns:
        ReplanResult。ok=True 时 plan_version 已 +1。
        ok=False 时 patches 被拒绝，调用方应停住问用户。
    """
    result = ReplanResult(plan_version=graph.plan_version)

    # 1. 校验 patch 格式
    for patch in patches:
        if not isinstance(patch, dict):
            result.rejected_reason = f"patch 不是 dict: {type(patch).__name__}"
            return result
        op = patch.get("op")
        if op not in request.allowed_ops:
            result.rejected_reason = f"不允许的操作: {op!r}"
            return result

    # 2. 构建新图（深拷 + 应用 patch）
    new_nodes = [TaskNode(**{k: v for k, v in n.__dict__.items()})
                 for n in graph.nodes]
    node_map = {n.id: n for n in new_nodes}

    for patch in patches:
        op = patch["op"]
        nid = patch.get("node_id", "")

        if op == "retry":
            # 重置节点状态，不改结构
            if nid not in node_map:
                result.rejected_reason = f"retry 目标不存在: {nid!r}"
                return result

        elif op == "skip":
            # 跳过节点：从图中移除，下游依赖也要清掉
            if nid not in node_map:
                result.rejected_reason = f"skip 目标不存在: {nid!r}"
                return result
            new_nodes = [n for n in new_nodes if n.id != nid]
            # 清理下游对它的依赖
            for n in new_nodes:
                if nid in n.dependencies:
                    n.dependencies = [d for d in n.dependencies if d != nid]
            node_map = {n.id: n for n in new_nodes}

        elif op == "replace":
            new_node_data = patch.get("new_node", {})
            if not isinstance(new_node_data, dict) or "id" not in new_node_data:
                result.rejected_reason = "replace new_node 缺少 id"
                return result
            replacement = TaskNode(
                id=new_node_data["id"],
                action=new_node_data.get("action", ""),
                dependencies=new_node_data.get("dependencies", []),
                executor=new_node_data.get("executor", "manual"),
                risk=new_node_data.get("risk", "unknown"),
                side_effect=new_node_data.get("side_effect", "external_write_unknown"),
                resources=ResourceBudget(**new_node_data.get("resources", {})),
            )
            # ⚠️ 新节点如果比原节点风险更高 -> 需要用户确认
            old = node_map.get(nid)
            if old and _risk_increased(old, replacement):
                result.requires_user_approval = True

            if nid in node_map:
                idx = next(i for i, n in enumerate(new_nodes) if n.id == nid)
                new_nodes[idx] = replacement
            else:
                new_nodes.append(replacement)
            node_map[replacement.id] = replacement

        elif op == "split":
            into = patch.get("into", [])
            if not isinstance(into, list) or len(into) < 2:
                result.rejected_reason = "split 至少要分成 2 个节点"
                return result
            # 原节点的依赖传给子节点
            old = node_map.get(nid)
            old_deps = list(old.dependencies) if old else []
            # 子节点 ID 列表，用于更新下游依赖
            child_ids = [p["id"] for p in into if "id" in p]
            # 移除原节点
            new_nodes = [n for n in new_nodes if n.id != nid]
            for part in into:
                child = TaskNode(
                    id=part["id"],
                    action=part.get("action", ""),
                    dependencies=part.get("dependencies", old_deps),
                    executor=part.get("executor", "manual"),
                    risk=part.get("risk", "unknown"),
                    side_effect=part.get("side_effect", "external_write_unknown"),
                )
                new_nodes.append(child)
                node_map[child.id] = child
            # 更新下游：把对原节点的依赖替换成对所有子节点的依赖
            for n in new_nodes:
                if nid in n.dependencies:
                    n.dependencies = [d for d in n.dependencies if d != nid] + child_ids

        elif op == "merge":
            node_ids = patch.get("node_ids", [])
            into = patch.get("into", {})
            if len(node_ids) < 2 or "id" not in into:
                result.rejected_reason = "merge 至少 2 个节点，且 into 必须有 id"
                return result
            new_nodes = [n for n in new_nodes if n.id not in node_ids]
            merged = TaskNode(
                id=into["id"],
                action=into.get("action", ""),
                dependencies=into.get("dependencies", []),
                executor=into.get("executor", "manual"),
                risk=into.get("risk", "unknown"),
                side_effect=into.get("side_effect", "external_write_unknown"),
            )
            new_nodes.append(merged)
            node_map[merged.id] = merged

    # 3. 校验新图
    new_graph = TaskGraph(
        graph_id=graph.graph_id,
        nodes=new_nodes,
        max_parallel=graph.max_parallel,
        total_budget=graph.total_budget,
        plan_version=graph.plan_version + 1,
    )
    validation: GraphValidationResult = validate_graph(new_graph)
    if not validation.ok:
        result.rejected_reason = f"新图未通过校验: {validation.summary()}"
        return result

    result.ok = True
    result.plan_version = new_graph.plan_version
    result.patches = patches
    return result


def _risk_increased(old: TaskNode, new: TaskNode) -> bool:
    """判断替换后风险是否升高。"""
    risk_order = {"low": 0, "medium": 1, "high": 2, "unknown": 3}
    old_risk = risk_order.get(old.risk, 3)
    new_risk = risk_order.get(new.risk, 3)
    if new_risk > old_risk:
        return True
    side_effect_order = {"none": 0, "read_only": 1, "local_write": 2,
                         "external_write": 3, "external_write_unknown": 3}
    old_se = side_effect_order.get(old.side_effect, 3)
    new_se = side_effect_order.get(new.side_effect, 3)
    return new_se > old_se


# ── Checkpoint ────────────────────────────────────────


@dataclass
class Checkpoint:
    """图执行状态的原子快照。"""

    graph_id: str
    plan_version: int
    completed_nodes: list[str] = field(default_factory=list)
    failed_nodes: list[str] = field(default_factory=list)
    in_progress: list[str] = field(default_factory=list)
    remaining_budget: ResourceBudget = field(default_factory=ResourceBudget)
    timestamp: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "graph_id": self.graph_id,
            "plan_version": self.plan_version,
            "completed": list(self.completed_nodes),
            "failed": list(self.failed_nodes),
            "in_progress": list(self.in_progress),
            "remaining_budget": {
                "max_parallel": self.remaining_budget.max_parallel,
                "max_wall_time_s": self.remaining_budget.max_wall_time_s,
                "max_memory_mb": self.remaining_budget.max_memory_mb,
                "max_model_calls": self.remaining_budget.max_model_calls,
                "max_external_writes": self.remaining_budget.max_external_writes,
            },
            "timestamp": self.timestamp,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> Checkpoint:
        data = json.loads(text)
        rb = data.get("remaining_budget", {})
        return cls(
            graph_id=data["graph_id"],
            plan_version=data["plan_version"],
            completed_nodes=data.get("completed", []),
            failed_nodes=data.get("failed", []),
            in_progress=data.get("in_progress", []),
            remaining_budget=ResourceBudget(**rb),
            timestamp=data.get("timestamp", ""),
        )
