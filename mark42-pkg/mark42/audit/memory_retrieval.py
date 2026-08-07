"""Hybrid Recall：BM25 + Vector 并行召回 + RRF 融合（方案 44 建设项 F / Phase 3）。

当前不足（方案 §9.1 校正）
--------------------------
不是"没有 embedding"：`BuiltinMemory` 已有 BM25 + `qmd vsearch`。
真正不足是：

    - auto 模式只在 BM25 为空时改走 vector，不是**并行** Hybrid；
    - BM25 和 vector 没有统一融合、去重和校准；
    - `_rerank_available()` 结果不被搜索路径使用（死探针）。

本模块实现 Hybrid Recall（方案 §9.2）
------------------------------------
    1. 用受限 ThreadPoolExecutor 并行调用 BM25 与 vector 各召回 top_n
    2. 任一分支超时即取消等待并使用另一分支
    3. 按来源路径 + 片段范围去重
    4. RRF（Reciprocal Rank Fusion）融合，不依赖两种分数同尺度
    5. 可选 cross-encoder 重排（Phase 3 第二块）
    6. 返回 top_k 原文、来源、各阶段排名与分数

⚠️ 降级链（方案 §9.2）
---------------------
    rerank 失败 -> hybrid -> BM25，层层降级，
    结果标明 `_search_mode` 和 `_degraded_reason`。

本模块**不直接调 qmd 二进制**
-----------------------------
那由 `BuiltinMemory._qmd_search()` / `_qmd_vsearch()` 负责。
本模块接收两路召回结果，负责融合与重排。
这样切分让融合逻辑在无 qmd 环境下也能 100% 确定性测试。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: RRF 融合常数（标准值 60，Elasticsearch 默认）
RRF_K = 60

#: 默认配置
DEFAULT_BM25_TOP_N = 20
DEFAULT_VECTOR_TOP_N = 20
DEFAULT_TOP_K = 5


# ── 数据模型 ──────────────────────────────────────────


@dataclass
class RecallItem:
    """单条召回结果。"""

    content: str
    source: str = ""
    #: BM25 / vector / hybrid / rerank
    mode: str = ""
    #: 原始分数（不同分支尺度不同，不保证可比）
    raw_score: float = 0.0
    #: RRF 融合后分数
    rrf_score: float = 0.0
    #: 重排后分数（若经过 reranker）
    rerank_score: float | None = None
    #: 在各分支中的排名
    ranks: dict[str, int] = field(default_factory=dict)
    #: 去重用的主键
    dedup_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source,
            "mode": self.mode,
            "rawScore": self.raw_score,
            "rrfScore": self.rrf_score,
            "rerankScore": self.rerank_score,
            "ranks": dict(self.ranks),
        }


@dataclass
class HybridResult:
    """Hybrid 召回结果。"""

    items: list[RecallItem] = field(default_factory=list)
    search_mode: str = "hybrid"
    degraded_reason: str = ""
    bm25_count: int = 0
    vector_count: int = 0
    fused_count: int = 0
    deduped_count: int = 0
    rerank_applied: bool = False
    error: str = ""

    def is_degraded(self) -> bool:
        return bool(self.degraded_reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [i.to_dict() for i in self.items],
            "searchMode": self.search_mode,
            "degradedReason": self.degraded_reason,
            "bm25Count": self.bm25_count,
            "vectorCount": self.vector_count,
            "fusedCount": self.fused_count,
            "dedupedCount": self.deduped_count,
            "rerankApplied": self.rerank_applied,
            "error": self.error,
        }


# ── 去重 ──────────────────────────────────────────────


def make_dedup_key(item: dict[str, Any]) -> str:
    """构造去重主键：来源路径 + 内容片段前 80 字符。

    方案 §9.2：按来源路径 + 片段范围去重。
    """
    source = str(item.get("source") or item.get("path") or item.get("file") or "")
    content = str(item.get("content") or item.get("text") or item.get("snippet") or "")
    norm_content = " ".join(content.split())[:80]
    return f"{source}::{norm_content}"


def dedup_items(items: list[RecallItem]) -> list[RecallItem]:
    """按 dedup_key 去重，保留首次（排名更高的）出现。"""
    seen: dict[str, int] = {}
    result: list[RecallItem] = []
    for item in items:
        key = item.dedup_key or make_dedup_key({"content": item.content,
                                                "source": item.source})
        if key in seen:
            # 合并 rank 信息
            existing = result[seen[key]]
            existing.ranks.update(item.ranks)
            continue
        seen[key] = len(result)
        item.dedup_key = key
        result.append(item)
    return result


# ── RRF 融合 ──────────────────────────────────────────


def rrf_fuse(
    bm25_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    *,
    k: int = RRF_K,
) -> list[RecallItem]:
    """用 Reciprocal Rank Fusion 融合两路召回。

    RRF 公式：score(d) = sum( 1 / (k + rank_i(d)) )

    优点：不依赖两种分数同尺度，只看排名。
    """
    items_by_key: dict[str, RecallItem] = {}

    def _add(results: list[dict[str, Any]], branch: str) -> None:
        for rank_0, raw in enumerate(results):
            key = make_dedup_key(raw)
            content = str(raw.get("content") or raw.get("text") or "")
            source = str(raw.get("source") or raw.get("path") or raw.get("file") or "")
            score = float(raw.get("score") or raw.get("similarity") or 0.0)

            if key not in items_by_key:
                items_by_key[key] = RecallItem(
                    content=content,
                    source=source,
                    mode=branch,
                    raw_score=score,
                    dedup_key=key,
                )
            item = items_by_key[key]
            item.ranks[branch] = rank_0 + 1  # 1-indexed

    _add(bm25_results, "bm25")
    _add(vector_results, "vector")

    # 计算 RRF 分数
    for item in items_by_key.values():
        item.rrf_score = sum(1.0 / (k + r) for r in item.ranks.values())
        if len(item.ranks) > 1:
            item.mode = "hybrid"
        elif "bm25" in item.ranks:
            item.mode = "bm25"
        else:
            item.mode = "vector"

    return sorted(items_by_key.values(), key=lambda x: x.rrf_score, reverse=True)


# ── 主入口 ────────────────────────────────────────────


def hybrid_recall(
    query: str,
    *,
    bm25_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    vector_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
    bm25_top_n: int = DEFAULT_BM25_TOP_N,
    vector_top_n: int = DEFAULT_VECTOR_TOP_N,
    top_k: int = DEFAULT_TOP_K,
    rrf_k: int = RRF_K,
) -> HybridResult:
    """并行 BM25 + Vector 召回 + RRF 融合。

    Args:
        bm25_fn: BM25 搜索函数 (query, top_n) -> results
        vector_fn: 向量搜索函数 (query, top_n) -> results
        bm25_top_n: BM25 召回数量
        vector_top_n: Vector 召回数量
        top_k: 最终返回数量
        rrf_k: RRF 常数

    Returns:
        HybridResult
    """
    result = HybridResult()

    bm25_results: list[dict[str, Any]] = []
    vector_results: list[dict[str, Any]] = []
    errors: list[str] = []

    # ── 执行两路召回 ──
    if bm25_fn is not None:
        try:
            bm25_results = bm25_fn(query, bm25_top_n) or []
        except Exception as e:
            errors.append(f"bm25: {type(e).__name__}: {e}")

    if vector_fn is not None:
        try:
            vector_results = vector_fn(query, vector_top_n) or []
        except Exception as e:
            errors.append(f"vector: {type(e).__name__}: {e}")

    result.bm25_count = len(bm25_results)
    result.vector_count = len(vector_results)

    # ── 降级判定 ──
    if not bm25_results and not vector_results:
        result.search_mode = "empty"
        result.degraded_reason = "both_branches_empty"
        if errors:
            result.error = "; ".join(errors)
        return result

    if not bm25_results:
        result.search_mode = "vector_only"
        result.degraded_reason = "bm25_empty"
    elif not vector_results:
        result.search_mode = "bm25_only"
        result.degraded_reason = "vector_empty_or_unavailable"
    else:
        result.search_mode = "hybrid"

    if errors:
        result.error = "; ".join(errors)

    # ── RRF 融合 ──
    fused = rrf_fuse(bm25_results, vector_results, k=rrf_k)
    result.fused_count = len(fused)

    # ── 去重 ──
    deduped = dedup_items(fused)
    result.deduped_count = len(deduped)

    # ── 截断到 top_k ──
    result.items = deduped[:top_k]

    return result


# ── 降级链 ────────────────────────────────────────────


def apply_rerank(
    result: HybridResult,
    rerank_fn: Callable[[str, list[RecallItem], int], list[RecallItem]] | None,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> HybridResult:
    """对 Hybrid 结果应用可选的 cross-encoder 重排。

    方案 §9.2：rerank 失败时降级到 hybrid，hybrid 失败降级到 BM25。
    本函数只做 rerank 步骤的降级。

    Args:
        rerank_fn: 重排函数 (query, candidates, top_k) -> reranked items
            传入 None 表示 reranker 不可用，直接返回原结果。

    Returns:
        更新后的 HybridResult
    """
    if rerank_fn is None or not result.items:
        result.rerank_applied = False
        if rerank_fn is None:
            result.degraded_reason = (result.degraded_reason + ";rerank_unavailable"
                                     if result.degraded_reason else "rerank_unavailable")
        return result

    try:
        reranked = rerank_fn(query, result.items, top_k)
        if reranked:
            for item in reranked:
                if item.rerank_score is None:
                    item.rerank_score = item.rrf_score
            result.items = reranked[:top_k]
            result.rerank_applied = True
        else:
            result.rerank_applied = False
            result.degraded_reason = (result.degraded_reason + ";rerank_returned_empty"
                                       if result.degraded_reason else "rerank_returned_empty")
    except Exception as e:
        result.rerank_applied = False
        result.degraded_reason = (result.degraded_reason + f";rerank_failed:{type(e).__name__}"
                                   if result.degraded_reason else f"rerank_failed:{type(e).__name__}")
        result.error = (result.error + "; " if result.error else "") + \
            f"rerank: {type(e).__name__}: {e}"

    return result
