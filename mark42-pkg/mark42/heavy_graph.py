"""Heavy DAG：依赖图 + 并发预算 + 局部重规划（方案 44 建设项 D / Phase 4）。

当前不足（方案 §7.1）
--------------------
现有 Heavy 已能分析和拆分重任务，但仍偏"步骤列表"：

    - 无显式依赖图与环检测
    - 只并发无依赖节点（实际是串行）
    - 无 CPU、内存、模型调用、外部写操作的统一预算
    - 无 checkpoint 与断点恢复
    - 某节点失败后只停住，不重规划受影响分支

本模块新增（方案 §7.2-7.5）
--------------------------
    - TaskNode / TaskGraph 数据模型
    - 图校验：唯一 ID、无环、依赖存在、预算不超限
    - DAG Executor：拓扑层内并发、checkpoint、断点恢复
    - LocalReplanner：只重规划失败分支，JSON Patch 格式
    - ResourceBudget：统一预算管理

设计原则
--------
    - 默认 dry-run，展示拓扑层级和预计资源
    - 外部写操作和高风险节点默认串行
    - 节点失败冻结下游，不影响已完成或无关分支
    - 重规划不得越权改已批准动作
    - 新增高风险动作 / 扩大写入范围 / 超预算时必须重新问用户

⚠️ executor 枚举（方案 §7.2）
---------------------------
首版只允许 bash / python / mark42_action / manual。
未知值在图校验阶段拒绝。risk 默认 unknown，side_effect 默认
external_write_unknown -- 未被规则或人工明确降级前，一律按高风险串行。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 允许的 executor 枚举
EXECUTORS = ("bash", "python", "mark42_action", "manual")

#: risk 默认值
DEFAULT_RISK = "unknown"
DEFAULT_SIDE_EFFECT = "external_write_unknown"

#: 允许的 risk 级别
RISK_LEVELS = ("low", "medium", "high", "unknown")

#: 允许的 side_effect 级别
SIDE_EFFECTS = ("none", "read_only", "local_write", "external_write", "external_write_unknown")

#: 默认并发上限
DEFAULT_MAX_PARALLEL = 2

#: 默认单节点超时（秒）
DEFAULT_NODE_TIMEOUT = 300


# ── 重试策略 ──────────────────────────────────────────


@dataclass
class RetryPolicy:
    """节点重试策略。"""
    max_retries: int = 0
    backoff_s: float = 1.0
    #: 重试前是否需要人工确认
    require_confirmation: bool = False


# ── 资源预算 ──────────────────────────────────────────


@dataclass
class ResourceBudget:
    """统一资源预算（方案 §7.5）。

    每个节点和整图各有预算。执行器在分配前检查是否超限。
    """
    max_parallel: int = DEFAULT_MAX_PARALLEL
    max_wall_time_s: int = 3600
    max_memory_mb: int = 2048
    max_model_calls: int = 50
    max_external_writes: int = 10
    max_replans: int = 3
    node_timeout_s: int = DEFAULT_NODE_TIMEOUT

    def can_consume(self, other: ResourceBudget) -> bool:
        """判断剩余预算是否能容纳另一个节点的需求。"""
        return (
            self.max_parallel >= other.max_parallel and
            self.max_wall_time_s >= other.max_wall_time_s and
            self.max_memory_mb >= other.max_memory_mb and
            self.max_model_calls >= other.max_model_calls and
            self.max_external_writes >= other.max_external_writes
        )

    def subtract(self, other: ResourceBudget) -> ResourceBudget:
        """扣减预算（返回新实例，不修改原值）。"""
        return ResourceBudget(
            max_parallel=max(0, self.max_parallel - other.max_parallel),
            max_wall_time_s=max(0, self.max_wall_time_s - other.max_wall_time_s),
            max_memory_mb=max(0, self.max_memory_mb - other.max_memory_mb),
            max_model_calls=max(0, self.max_model_calls - other.max_model_calls),
            max_external_writes=max(0, self.max_external_writes - other.max_external_writes),
            max_replans=self.max_replans,
            node_timeout_s=self.node_timeout_s,
        )

    def is_exhausted(self) -> bool:
        """预算是否耗尽。"""
        return (
            self.max_wall_time_s <= 0
            or self.max_memory_mb <= 0
            or self.max_model_calls <= 0
            or self.max_external_writes < 0
        )


# ── 节点 ─────────────────────────────────────────────


@dataclass
class TaskNode:
    """DAG 中的一个任务节点。

    ⚠️ risk 默认 unknown，side_effect 默认 external_write_unknown --
    未被规则或人工明确降级前，一律按高风险串行节点处理（方案 §7.2）。
    """

    id: str
    action: str
    dependencies: list[str] = field(default_factory=list)
    resources: ResourceBudget = field(default_factory=ResourceBudget)
    risk: str = DEFAULT_RISK
    side_effect: str = DEFAULT_SIDE_EFFECT
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    checkpoint: bool = False
    executor: str = "manual"

    def is_high_risk(self) -> bool:
        """是否按高风险串行处理。"""
        return (
            self.risk in ("high", "unknown")
            or self.side_effect in ("external_write", "external_write_unknown")
            or self.executor == "manual"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "action": self.action,
            "dependencies": list(self.dependencies),
            "risk": self.risk,
            "side_effect": self.side_effect,
            "executor": self.executor,
            "checkpoint": self.checkpoint,
        }


# ── 图 ────────────────────────────────────────────────


@dataclass
class TaskGraph:
    """任务依赖图。"""

    graph_id: str
    nodes: list[TaskNode] = field(default_factory=list)
    max_parallel: int = DEFAULT_MAX_PARALLEL
    total_budget: ResourceBudget = field(default_factory=ResourceBudget)
    plan_version: int = 1

    def node_map(self) -> dict[str, TaskNode]:
        return {n.id: n for n in self.nodes}

    def topo_layers(self) -> list[list[str]]:
        """按拓扑序分层，同层内可并发。

        返回 [[layer0_ids], [layer1_ids], ...]
        """
        deps: dict[str, set[str]] = {}
        for n in self.nodes:
            deps[n.id] = set(n.dependencies)
        layers: list[list[str]] = []
        done: set[str] = set()
        remaining = set(deps)
        while remaining:
            ready = {nid for nid in remaining if deps[nid] <= done}
            if not ready:
                # 有环 -- 返回已解析的层，调用方用 validate 发现有环
                break
            layers.append(sorted(ready))
            done |= ready
            remaining -= ready
        return layers


# ── 图校验 ────────────────────────────────────────────

class GraphValidationError:
    """单条校验错误。"""
    def __init__(self, code: str, detail: str = "", node_id: str = "") -> None:
        self.code = code
        self.detail = detail
        self.node_id = node_id

    def __str__(self) -> str:
        loc = f"[{self.node_id}] " if self.node_id else ""
        return f"{loc}{self.code}: {self.detail}"


@dataclass
class GraphValidationResult:
    """图校验结果。"""
    ok: bool = True
    errors: list[GraphValidationError] = field(default_factory=list)

    def codes(self) -> list[str]:
        return [e.code for e in self.errors]

    def summary(self) -> str:
        if self.ok:
            return "ok"
        return "; ".join(str(e) for e in self.errors[:10])


def validate_graph(graph: TaskGraph) -> GraphValidationResult:
    """校验任务图（方案 §7.3：图先校验后执行）。

    检查项：
        1. 唯一 ID
        2. 依赖存在
        3. 无环
        4. executor 合法
        5. risk / side_effect 合法
        6. 预算不超限
    """
    result = GraphValidationResult()
    ids: set[str] = set()
    node_map = graph.node_map()

    # 1. 唯一 ID
    for n in graph.nodes:
        if n.id in ids:
            result.errors.append(GraphValidationError(
                "duplicate_id", f"重复的节点 ID: {n.id}", n.id))
            continue
        ids.add(n.id)

    # 2. 依赖存在
    for n in graph.nodes:
        for dep in n.dependencies:
            if dep not in node_map:
                result.errors.append(GraphValidationError(
                    "missing_dependency",
                    f"依赖 {dep!r} 不存在", n.id))

    # 3. 无环（拓扑排序是否覆盖全部节点）
    layers = graph.topo_layers()
    resolved = {nid for layer in layers for nid in layer}
    unresolved = ids - resolved
    if unresolved:
        result.errors.append(GraphValidationError(
            "cycle", f"检测到环，未解析节点: {sorted(unresolved)}"))

    # 4. executor 合法
    for n in graph.nodes:
        if n.executor not in EXECUTORS:
            result.errors.append(GraphValidationError(
                "bad_executor",
                f"executor={n.executor!r} 不在 {EXECUTORS} 中", n.id))

    # 5. risk / side_effect 合法
    for n in graph.nodes:
        if n.risk not in RISK_LEVELS:
            result.errors.append(GraphValidationError(
                "bad_risk", f"risk={n.risk!r} 不在 {RISK_LEVELS} 中", n.id))
        if n.side_effect not in SIDE_EFFECTS:
            result.errors.append(GraphValidationError(
                "bad_side_effect",
                f"side_effect={n.side_effect!r} 不在 {SIDE_EFFECTS} 中", n.id))

    # 6. 预算不超限
    for n in graph.nodes:
        if not graph.total_budget.can_consume(n.resources):
            result.errors.append(GraphValidationError(
                "budget_exceeded",
                "节点预算超出总预算", n.id))

    result.ok = not result.errors
    return result
