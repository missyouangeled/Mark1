"""ContextState 构建接入（方案 44 Phase 2：结构化增量压缩接入 armor）。

职责
----
被 `armor._compress_build_index()` 的结构化分支调用。
负责：

    1. 从 session-messages 和旧状态构建新版 ContextState；
    2. 增量或全量，视 STRUCTURED_STATE_INCREMENTAL 而定；
    3. 版本化持久化至 StateStore；
    4. 返回兼容的 index dict（shadow 模式也返回旧 index 形状 + 对比日志）。

设计原则
--------
- 主干失败 → 返回 None 让 armor 走 LLM 分支（**失败安全**）
- 副路径（统计/logging）失败 → 吃日志，不影响主干
- 不修改也不替代 OpenClaw 官方 compact 流程（方案 §4.1：旁路扩展）
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import (
    CONTEXT_STATE_DIR,
    STRUCTURED_STATE_INCREMENTAL,
    STRUCTURED_STATE_KEEP_VERSIONS,
    STRUCTURED_STATE_MODE,
)
from ..context_state import (
    ContextState,
    new_empty_state,
    render_memory_index_view,
)
from .state_store import StateStore

logger = logging.getLogger(__name__)

# 全局 StateStore 实例（惰性初始化）
_store: StateStore | None = None


def _get_store() -> StateStore:
    """惰性获取 StateStore，避免 import 时目录未就绪。"""
    global _store
    if _store is None:
        _store = StateStore(
            CONTEXT_STATE_DIR,
            keep_versions=STRUCTURED_STATE_KEEP_VERSIONS,
        )
    return _store


def build_context_state_for_compress(
    session_messages: list[dict[str, Any]],
    usage: float,
    algo_stats: dict[str, Any],
    alert_pct: float,
) -> dict[str, Any] | None:
    """结构化增量压缩入口（方案 §4.4 接入点）。

    被 `armor._compress_build_index()` 的分支 1 调用。

    Returns:
        index dict（与旧 `_compress_build_index` 同形状），
        或 None 表示失败，让调用方走 LLM 分支。
    """
    store = _get_store()
    mode = STRUCTURED_STATE_MODE

    try:
        # 1. 读旧状态
        loaded = store.load_current()
        old_state = loaded.state

        # 2. 构建新版状态
        if STRUCTURED_STATE_INCREMENTAL and loaded.found:
            # 增量路径：调用 LLM 产出 patch → 合并
            new_state = _build_incremental(old_state, session_messages)
        else:
            # 全量路径：从消息重建
            new_state = _build_full(session_messages)

        if new_state is None:
            return None

        # 3. 持久化（shadow 模式也写，用于趋势 compare）
        store.save(new_state)

        # 4. 渲染兼容视图
        view = render_memory_index_view(new_state)
        view["preCompressUsage"] = usage
        view["algoStats"] = algo_stats
        view["structuredStateMode"] = mode

        if mode == "shadow":
            # shadow 模式：也跑 LLM 分支，记录对比日志
            view["strategyUsed"] = "structured-shadow"
            view["_shadowNote"] = "shadow 模式，旧 LLM 分支仍为主路径"
        else:
            view["strategyUsed"] = "structured-incremental"

        return view

    except Exception as e:
        logger.warning("结构化状态构建失败，安全回退 LLM 分支: %s", e)
        return None


def _build_incremental(
    old_state: ContextState,
    messages: list[dict[str, Any]],
) -> ContextState | None:
    """增量路径：从旧状态 + 新消息生成 patch 并合并。

    使用 LLM 分析新消息，生成结构化 patch，再由 incremental_merge.merge_patch
    安全合并。任何失败返回 None，让调用方回退全量路径。
    """
    if not messages:
        return old_state

    from ..armor import _llm_analyze
    from .incremental_merge import merge_patch

    # 用 LLM 分析新增消息
    llm_result = _llm_analyze(messages)
    if not llm_result:
        # LLM 不可用 -> 回退全量
        return None

    preserved = llm_result.get("preserved", {})
    projects = preserved.get("activeProjects", [])
    task_state = preserved.get("taskState", {})
    current_task = task_state.get("current", "") if isinstance(task_state, dict) else ""

    # 构建 patch
    patch: dict[str, Any] = {}

    if isinstance(projects, list) and projects:
        patch["session_intent"] = str(projects[0])
    elif current_task:
        patch["session_intent"] = str(current_task)

    if isinstance(projects, list) and projects:
        patch["active_task"] = {
            "op": "update",
            "title": str(projects[0])[:60],
            "status": "in_progress",
        }
    elif current_task:
        patch["active_task"] = {
            "op": "update",
            "title": str(current_task)[:60],
            "status": "in_progress",
        }

    # 新决策
    decisions = []
    if isinstance(preserved.get("recentDecisions"), list):
        for d in preserved["recentDecisions"]:
            if isinstance(d, str) and d.strip():
                decisions.append({
                    "op": "add",
                    "decision_id": f"d-inc-{hash(d) % 10**12:012x}",
                    "summary": d,
                    "evidence": "incremental-llm",
                })
    if decisions:
        patch["decisions"] = decisions

    # 新约束
    constraints = []
    if isinstance(preserved.get("preferences"), list):
        for pref in preserved["preferences"]:
            if isinstance(pref, str) and pref.strip():
                constraints.append({
                    "op": "add",
                    "constraint_id": f"c-inc-{hash(pref) % 10**12:012x}",
                    "text": pref,
                    "strength": "hard",
                    "priority": "P1",
                    "source": "incremental-llm",
                    "evidence": "incremental-llm-output",
                })
    if constraints:
        patch["constraints"] = constraints

    if not patch:
        # LLM 没提取到任何新信息 -> 旧状态不变
        return old_state

    # 安全合并
    result = merge_patch(old_state, patch)
    if result.ok and result.state is not None:
        return result.state

    # 合并失败 -> 回退全量
    return None


def _build_full(
    messages: list[dict[str, Any]],
) -> ContextState | None:
    """全量路径：从消息重建状态。

    首版用 LLM 分析结果填充（与旧 _llm_analyze 共享同一 provider）。
    Phase 2 首版简化：只做结构化空壳。
    """
    from ..armor import _llm_analyze

    llm_result = _llm_analyze(messages) if messages else None
    st = new_empty_state()

    if llm_result:
        preserved = llm_result.get("preserved", {})
        # session_intent 应该是会话目标，不是用户身份
        # LLM 返回的 activeProjects / taskState 更接近会话目标
        task_state = preserved.get("taskState", {})
        current_task = task_state.get("current", "") if isinstance(task_state, dict) else ""
        projects = preserved.get("activeProjects", [])
        if isinstance(projects, list) and projects:
            st.session_intent = str(projects[0])
        elif current_task:
            st.session_intent = str(current_task)
        if isinstance(projects, list) and projects:
            st.active_task = {
                "title": str(projects[0])[:60],
                "status": "in_progress",
            }
        elif current_task:
            st.active_task = {
                "title": str(current_task)[:60],
                "status": "in_progress",
            }
        if isinstance(preserved.get("preferences"), list):
            for pref in preserved["preferences"]:
                if isinstance(pref, str):
                    st.constraints.append({
                        "constraint_id": f"c-llm-{hash(pref) % 10**12:012x}",
                        "text": pref,
                        "strength": "hard", "priority": "P1",
                        "source": "llm-analyze",
                        "evidence": "llm-analyze-output",
                    })
        if isinstance(preserved.get("recentDecisions"), list):
            for d in preserved["recentDecisions"]:
                if isinstance(d, str):
                    st.decisions.append({
                        "decision_id": f"d-llm-{hash(d) % 10**12:012x}",
                        "summary": d,
                        "evidence": "llm-analyze-output",
                    })

    return st
