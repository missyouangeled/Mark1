"""Heavy DAG 测试（方案 44 Phase 4）。

重点钉住：
    1. 环检测必须拒绝；
    2. 同拓扑层内才允许并发，跨层串行；
    3. 默认 unknown risk / external_write_unknown -> 串行；
    4. 预算超限必须拒绝；
    5. 图校验在执行前完成，不合格的图不执行。
"""

from __future__ import annotations


from mark42.heavy_graph import (
    DEFAULT_RISK,
    DEFAULT_SIDE_EFFECT,
    EXECUTORS,
    ResourceBudget,
    TaskGraph,
    TaskNode,
    validate_graph,
)


def _node(nid: str, *, deps=None, executor="bash", risk=None, side_effect=None,
          resources=None):
    return TaskNode(
        id=nid,
        action=f"do {nid}",
        dependencies=deps or [],
        executor=executor,
        risk=risk or DEFAULT_RISK,
        side_effect=side_effect or DEFAULT_SIDE_EFFECT,
        resources=resources or ResourceBudget(),
    )


def _graph(nodes, **kw):
    return TaskGraph(
        graph_id="g1",
        nodes=nodes,
        total_budget=kw.get("budget", ResourceBudget(max_external_writes=100, max_model_calls=100)),
        **{k: v for k, v in kw.items() if k != "budget"},
    )


# ── 资源预算 ──────────────────────────────────────────


class TestResourceBudget:
    def test_can_consume_equal(self):
        a = ResourceBudget(max_parallel=2, max_memory_mb=1024)
        b = ResourceBudget(max_parallel=2, max_memory_mb=1024)
        assert a.can_consume(b)

    def test_cannot_consume_exceeds(self):
        a = ResourceBudget(max_parallel=1)
        b = ResourceBudget(max_parallel=2)
        assert not a.can_consume(b)

    def test_subtract_returns_new(self):
        a = ResourceBudget(max_parallel=4, max_memory_mb=2048)
        b = ResourceBudget(max_parallel=1, max_memory_mb=512)
        c = a.subtract(b)
        assert c.max_parallel == 3
        assert c.max_memory_mb == 1536
        assert a.max_parallel == 4  # 原值不变

    def test_subtract_floor_zero(self):
        a = ResourceBudget(max_parallel=1)
        b = ResourceBudget(max_parallel=5)
        assert a.subtract(b).max_parallel == 0

    def test_is_exhausted(self):
        b = ResourceBudget(max_wall_time_s=0)
        assert b.is_exhausted()

    def test_not_exhausted(self):
        assert not ResourceBudget().is_exhausted()

    def test_negative_external_writes_exhausted(self):
        b = ResourceBudget(max_external_writes=-1)
        assert b.is_exhausted()


# ── TaskNode ──────────────────────────────────────────


class TestTaskNode:
    def test_defaults_are_high_risk(self):
        """未知 risk / side_effect 默认按高风险串行。"""
        n = TaskNode(id="x", action="do")
        assert n.is_high_risk() is True
        assert n.risk == "unknown"
        assert n.side_effect == "external_write_unknown"

    def test_low_risk_read_only_not_high_risk(self):
        n = TaskNode(id="x", action="do", risk="low", side_effect="read_only",
                    executor="bash")
        assert n.is_high_risk() is False

    def test_explicit_high_risk(self):
        n = TaskNode(id="x", action="do", risk="high", side_effect="local_write",
                     executor="bash")
        assert n.is_high_risk() is True

    def test_external_write_always_high_risk(self):
        n = TaskNode(id="x", action="do", risk="low", side_effect="external_write",
                     executor="bash")
        assert n.is_high_risk() is True


# ── 拓扑分层 ──────────────────────────────────────────


class TestTopoLayers:
    def test_linear_chain(self):
        g = _graph([_node("a"), _node("b", deps=["a"]), _node("c", deps=["b"])])
        layers = g.topo_layers()
        assert layers == [["a"], ["b"], ["c"]]

    def test_parallel_roots(self):
        g = _graph([_node("a"), _node("b"), _node("c", deps=["a", "b"])])
        layers = g.topo_layers()
        assert layers[0] == ["a", "b"]
        assert layers[1] == ["c"]

    def test_diamond(self):
        g = _graph([
            _node("a"),
            _node("b", deps=["a"]),
            _node("c", deps=["a"]),
            _node("d", deps=["b", "c"]),
        ])
        layers = g.topo_layers()
        assert layers[0] == ["a"]
        assert set(layers[1]) == {"b", "c"}
        assert layers[2] == ["d"]

    def test_cycle_returns_partial(self):
        g = _graph([_node("a", deps=["b"]), _node("b", deps=["a"])])
        layers = g.topo_layers()
        assert layers == []  # 全在环里

    def test_empty_graph(self):
        assert _graph([]).topo_layers() == []


# ── 图校验 ────────────────────────────────────────────


class TestGraphValidation:
    def test_valid_graph_passes(self):
        g = _graph([_node("a"), _node("b", deps=["a"])])
        assert validate_graph(g).ok

    def test_duplicate_id_rejected(self):
        g = _graph([_node("a"), _node("a")])
        rep = validate_graph(g)
        assert not rep.ok
        assert "duplicate_id" in rep.codes()

    def test_missing_dependency_rejected(self):
        g = _graph([_node("a", deps=["ghost"])])
        rep = validate_graph(g)
        assert not rep.ok
        assert "missing_dependency" in rep.codes()

    def test_cycle_rejected(self):
        g = _graph([_node("a", deps=["b"]), _node("b", deps=["a"])])
        rep = validate_graph(g)
        assert not rep.ok
        assert "cycle" in rep.codes()

    def test_bad_executor_rejected(self):
        n = _node("a", executor="nuclear")
        g = _graph([n])
        rep = validate_graph(g)
        assert not rep.ok
        assert "bad_executor" in rep.codes()

    def test_bad_risk_rejected(self):
        n = _node("a", risk="extreme")
        g = _graph([n])
        rep = validate_graph(g)
        assert "bad_risk" in rep.codes()

    def test_bad_side_effect_rejected(self):
        n = _node("a", side_effect="time_travel")
        g = _graph([n])
        rep = validate_graph(g)
        assert "bad_side_effect" in rep.codes()

    def test_budget_exceeded_rejected(self):
        big_budget = ResourceBudget(max_parallel=100, max_memory_mb=99999)
        small_total = ResourceBudget(max_parallel=1, max_memory_mb=100)
        n = _node("a", resources=big_budget)
        g = TaskGraph(graph_id="g", nodes=[n], total_budget=small_total)
        rep = validate_graph(g)
        assert "budget_exceeded" in rep.codes()

    def test_multiple_errors_collected(self):
        g = _graph([
            _node("a", executor="bad", risk="extreme"),
            _node("a", deps=["ghost"]),
        ])
        rep = validate_graph(g)
        assert len(rep.errors) >= 3

    def test_empty_graph_valid(self):
        assert validate_graph(_graph([])).ok

    def test_executor_enums_all_accepted(self):
        nodes = [_node(f"n{e}", executor=e) for e in EXECUTORS]
        g = _graph(nodes)
        assert validate_graph(g).ok


# ── 计划哈希稳定性（方案 §7.7）───────────────────────


class TestPlanStability:
    def test_same_nodes_same_layers(self):
        g1 = _graph([_node("c", deps=["a", "b"]), _node("a"), _node("b", deps=["a"])])
        g2 = _graph([_node("a"), _node("b", deps=["a"]), _node("c", deps=["a", "b"])])
        assert g1.topo_layers() == g2.topo_layers()

    def test_different_deps_different_layers(self):
        g1 = _graph([_node("a"), _node("b")])
        g2 = _graph([_node("a"), _node("b", deps=["a"])])
        assert g1.topo_layers() != g2.topo_layers()
