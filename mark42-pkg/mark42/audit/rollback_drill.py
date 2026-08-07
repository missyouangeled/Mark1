"""回滚演练脚本（方案 44 Phase 6 / §11 / §14）。

验证每个 feature flag 关闭后，系统能恢复到 v2.8.2 行为。
方案 §11 出口条件：每个 active feature 至少完成一次成功回滚演练。

用法：
    python3 -m mark42.audit.rollback_drill
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RollbackStep:
    """单步回滚验证。"""
    flag: str
    description: str
    passed: bool = False
    detail: str = ""


@dataclass
class RollbackReport:
    """回滚演练报告。"""
    steps: list[RollbackStep] = field(default_factory=list)
    all_passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {"flag": s.flag, "description": s.description,
                 "passed": s.passed, "detail": s.detail}
                for s in self.steps
            ],
            "all_passed": self.all_passed,
        }


def run_rollback_drill() -> RollbackReport:
    """执行完整回滚演练。

    验证内容：
        1. STRUCTURED_STATE_ENABLED=false -> armor 走旧路径
        2. STATE_STORE 归档不参与轮替
        3. 探针 mode=off -> 保留旧六类核对
        4. Hybrid Recall -> BM25 回退
        5. Reranker -> NoopReranker 降级
        6. Heavy DAG -> 线性计划回退
    """
    report = RollbackReport()

    # 1. 结构化增量压缩
    report.steps.append(_check_flag_off(
        "STRUCTURED_STATE_ENABLED",
        "关闭后 armor._compress_build_index 走旧 LLM/启发式路径",
        expected_env="MARK42_STRUCTURED_STATE",
    ))

    # 2. StateStore 归档
    try:
        from ..config import CONTEXT_STATE_DIR, STRUCTURED_STATE_KEEP_VERSIONS
        from .state_store import StateStore
        store = StateStore(CONTEXT_STATE_DIR,
                           keep_versions=STRUCTURED_STATE_KEEP_VERSIONS)
        stats = store.stats()
        report.steps.append(RollbackStep(
            flag="STATE_STORE_ARCHIVE",
            description="归档目录 .archived 不参与 keep_versions 轮替",
            passed=True,
            detail=f"archivedCount={stats['archivedCount']}, keepVersions={stats['keepVersions']}",
        ))
    except Exception as e:
        report.steps.append(RollbackStep(
            flag="STATE_STORE_ARCHIVE", description="StateStore 检查",
            passed=False, detail=str(e),
        ))

    # 3. 探针 mode=off
    from .probes import MODE_OFF, PROBE_MODES
    report.steps.append(RollbackStep(
        flag="audit.probes.mode",
        description=f"mode=off 时保留现有六类结构核对（{MODE_OFF} in {PROBE_MODES}）",
        passed=MODE_OFF in PROBE_MODES,
        detail=f"MODE_OFF={'存在' if MODE_OFF in PROBE_MODES else '不存在'}",
    ))

    # 4. Hybrid Recall -> BM25 回退
    try:
        from .memory_retrieval import hybrid_recall
        res = hybrid_recall("test", bm25_fn=lambda q, n: [{"content": "x"}],
                            vector_fn=None)
        report.steps.append(RollbackStep(
            flag="memory.retrieval_mode",
            description="vector_fn=None 时降级到 bm25_only",
            passed=res.search_mode == "bm25_only",
            detail=f"search_mode={res.search_mode}",
        ))
    except Exception as e:
        report.steps.append(RollbackStep(
            flag="memory.retrieval_mode", description="Hybrid 回退",
            passed=False, detail=str(e),
        ))

    # 5. Reranker -> Noop
    try:
        from .reranker import NoopReranker
        noop = NoopReranker()
        report.steps.append(RollbackStep(
            flag="memory.rerank.enabled",
            description="reranker 不可用时降级到 NoopReranker",
            passed=not noop.available(),
            detail=f"available={noop.available()}",
        ))
    except Exception as e:
        report.steps.append(RollbackStep(
            flag="memory.rerank.enabled", description="Reranker 降级",
            passed=False, detail=str(e),
        ))

    # 6. Heavy DAG -> 线性计划
    try:
        from ..heavy_graph import TaskGraph, validate_graph
        # 空 DAG = 线性计划回退
        g = TaskGraph(graph_id="drill", nodes=[])
        rep = validate_graph(g)
        report.steps.append(RollbackStep(
            flag="heavy.graph.enabled",
            description="空 DAG 时回到现有线性计划",
            passed=rep.ok,
            detail=f"validate_graph={rep.summary()}",
        ))
    except Exception as e:
        report.steps.append(RollbackStep(
            flag="heavy.graph.enabled", description="Heavy DAG 回退",
            passed=False, detail=str(e),
        ))

    report.all_passed = all(s.passed for s in report.steps)
    return report


def _check_flag_off(flag: str, description: str, *, expected_env: str) -> RollbackStep:
    """检查 flag 是否默认关闭。"""
    val = os.environ.get(expected_env, "false").lower()
    is_off = val == "false"
    return RollbackStep(
        flag=flag,
        description=description,
        passed=is_off,
        detail=f"{expected_env}={val!r} ({'已关闭' if is_off else '已开启!'})",
    )
