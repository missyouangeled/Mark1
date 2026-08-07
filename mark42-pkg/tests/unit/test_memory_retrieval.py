"""Hybrid Recall + RRF 融合测试（方案 44 Phase 3）。

重点钉住：
    1. 两路并行 -> 融合 -> 去重 -> 截断，每步计数对得上；
    2. RRF 分数不依赖两种分数同尺度；
    3. 降级链：rerank 失败 -> hybrid -> bm25_only -> empty，层层标明原因；
    4. 去重保留首次（排名更高的）出现，合并 rank 信息。
"""

from __future__ import annotations


from mark42.audit.memory_retrieval import (
    HybridResult,
    RecallItem,
    apply_rerank,
    dedup_items,
    hybrid_recall,
    make_dedup_key,
    rrf_fuse,
)


def _bm25_item(content: str, source: str = "a.md", score: float = 1.0):
    return {"content": content, "source": source, "score": score}


def _vec_item(content: str, source: str = "a.md", score: float = 0.9):
    return {"content": content, "source": source, "similarity": score}


# ── 去重 ──────────────────────────────────────────────


class TestDedup:
    def test_same_source_content_deduped(self):
        key = make_dedup_key({"content": "hello", "source": "a.md"})
        key2 = make_dedup_key({"content": "hello", "source": "a.md"})
        assert key == key2

    def test_different_source_not_deduped(self):
        assert make_dedup_key({"content": "x", "source": "a.md"}) != \
               make_dedup_key({"content": "x", "source": "b.md"})

    def test_different_content_not_deduped(self):
        assert make_dedup_key({"content": "a", "source": "f"}) != \
               make_dedup_key({"content": "b", "source": "f"})

    def test_dedup_preserves_first_and_merges_ranks(self):
        items = [
            RecallItem(content="x", source="a", mode="bm25", ranks={"bm25": 1}),
            RecallItem(content="x", source="a", mode="vector", ranks={"vector": 3}),
        ]
        out = dedup_items(items)
        assert len(out) == 1
        assert out[0].ranks == {"bm25": 1, "vector": 3}

    def test_dedup_empty(self):
        assert dedup_items([]) == []


# ── RRF 融合 ──────────────────────────────────────────


class TestRRF:
    def test_item_in_both_branches_scores_higher(self):
        """同时被 BM25 和 vector 命中的条目，RRF 分数应高于只被一路命中的。"""
        bm25 = [_bm25_item("shared"), _bm25_item("only_bm")]
        vec = [_vec_item("shared"), _vec_item("only_vec")]
        fused = rrf_fuse(bm25, vec)
        by_content = {i.content: i for i in fused}
        assert by_content["shared"].rrf_score > by_content["only_bm"].rrf_score
        assert by_content["shared"].rrf_score > by_content["only_vec"].rrf_score
        assert by_content["shared"].mode == "hybrid"
        assert by_content["only_bm"].mode == "bm25"
        assert by_content["only_vec"].mode == "vector"

    def test_rrf_does_not_depend_on_score_scale(self):
        """BM25 分数 0.01 vs vector 分数 0.99 -- RRF 只看排名。"""
        bm25 = [{"content": "a", "source": "f", "score": 0.01},
                {"content": "b", "source": "f", "score": 0.001}]
        vec = [{"content": "a", "source": "f", "similarity": 0.99},
               {"content": "c", "source": "f", "similarity": 0.5}]
        fused = rrf_fuse(bm25, vec)
        top = fused[0]
        assert top.content == "a"  # 两路都排第一

    def test_empty_both(self):
        assert rrf_fuse([], []) == []

    def test_empty_one_side(self):
        bm25 = [_bm25_item("a"), _bm25_item("b")]
        fused = rrf_fuse(bm25, [])
        assert len(fused) == 2
        assert all(i.mode == "bm25" for i in fused)

    def test_rank_recorded_correctly(self):
        bm25 = [_bm25_item("a"), _bm25_item("b"), _bm25_item("c")]
        vec = [_vec_item("c"), _vec_item("a"), _vec_item("d")]
        fused = rrf_fuse(bm25, vec)
        by_content = {i.content: i for i in fused}
        assert by_content["a"].ranks == {"bm25": 1, "vector": 2}
        assert by_content["c"].ranks == {"bm25": 3, "vector": 1}
        assert by_content["d"].ranks == {"vector": 3}


# ── hybrid_recall 主入口 ─────────────────────────────


class TestHybridRecall:
    def test_full_hybrid(self):
        bm25_fn = lambda q, n: [_bm25_item("a"), _bm25_item("b")]
        vec_fn = lambda q, n: [_vec_item("a"), _vec_item("c")]
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=vec_fn, top_k=5)
        assert res.search_mode == "hybrid"
        assert res.bm25_count == 2
        assert res.vector_count == 2
        assert res.fused_count == 3  # a, b, c (a deduped)
        assert len(res.items) <= 5

    def test_bm25_only_when_vector_empty(self):
        bm25_fn = lambda q, n: [_bm25_item("a")]
        vec_fn = lambda q, n: []
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=vec_fn)
        assert res.search_mode == "bm25_only"
        assert "vector_empty" in res.degraded_reason

    def test_vector_only_when_bm25_empty(self):
        bm25_fn = lambda q, n: []
        vec_fn = lambda q, n: [_vec_item("a")]
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=vec_fn)
        assert res.search_mode == "vector_only"
        assert "bm25_empty" in res.degraded_reason

    def test_both_empty(self):
        res = hybrid_recall("test", bm25_fn=lambda q, n: [], vector_fn=lambda q, n: [])
        assert res.search_mode == "empty"
        assert res.items == []

    def test_bm25_exception_degrades_gracefully(self):
        def boom(q, n): raise RuntimeError("bm25 boom")
        vec_fn = lambda q, n: [_vec_item("a")]
        res = hybrid_recall("test", bm25_fn=boom, vector_fn=vec_fn)
        assert res.search_mode == "vector_only"
        assert "bm25" in res.error

    def test_vector_exception_degrades_gracefully(self):
        def boom(q, n): raise RuntimeError("vec boom")
        bm25_fn = lambda q, n: [_bm25_item("a")]
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=boom)
        assert res.search_mode == "bm25_only"
        assert "vector" in res.error

    def test_both_exception(self):
        res = hybrid_recall("test",
                            bm25_fn=lambda q, n: (_ for _ in ()).throw(RuntimeError("x")),
                            vector_fn=lambda q, n: (_ for _ in ()).throw(RuntimeError("y")))
        assert res.search_mode == "empty"
        assert "bm25" in res.error
        assert "vector" in res.error

    def test_top_k_truncation(self):
        bm25_fn = lambda q, n: [_bm25_item(f"b{i}") for i in range(20)]
        vec_fn = lambda q, n: [_vec_item(f"v{i}") for i in range(20)]
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=vec_fn, top_k=3)
        assert len(res.items) == 3

    def test_no_functions_returns_empty(self):
        res = hybrid_recall("test")
        assert res.search_mode == "empty"

    def test_result_dict_serializable(self):
        import json
        bm25_fn = lambda q, n: [_bm25_item("a")]
        vec_fn = lambda q, n: [_vec_item("a")]
        res = hybrid_recall("test", bm25_fn=bm25_fn, vector_fn=vec_fn)
        json.dumps(res.to_dict(), ensure_ascii=False)


# ── rerank 降级链 ─────────────────────────────────────


class TestRerank:
    def _result(self):
        res = HybridResult(search_mode="hybrid")
        res.items = [
            RecallItem(content="a", source="f", mode="hybrid", rrf_score=0.5),
            RecallItem(content="b", source="f", mode="hybrid", rrf_score=0.3),
        ]
        return res

    def test_rerank_applied(self):
        def rerank(q, items, k):
            for i in items:
                i.rerank_score = 1.0 - i.rrf_score
            return sorted(items, key=lambda x: x.rerank_score, reverse=True)
        res = apply_rerank(self._result(), rerank, "q", top_k=2)
        assert res.rerank_applied is True
        assert res.items[0].content == "b"  # 0.3 -> 0.7 > 0.5 -> 0.5

    def test_rerank_none_marks_degraded(self):
        res = apply_rerank(self._result(), None, "q")
        assert res.rerank_applied is False
        assert "rerank_unavailable" in res.degraded_reason

    def test_rerank_exception_degrades_safely(self):
        def boom(q, items, k): raise RuntimeError("rerank boom")
        res = apply_rerank(self._result(), boom, "q")
        assert res.rerank_applied is False
        assert "rerank_failed" in res.degraded_reason
        # 原始 items 不变
        assert len(res.items) == 2

    def test_rerank_empty_result_marks_degraded(self):
        def empty(q, items, k): return []
        res = apply_rerank(self._result(), empty, "q")
        assert res.rerank_applied is False
        assert "rerank_returned_empty" in res.degraded_reason

    def test_rerank_empty_input_skipped(self):
        res = HybridResult(items=[])
        apply_rerank(res, lambda q, i, k: i, "q")
        assert res.rerank_applied is False

    def test_rerank_truncates_to_top_k(self):
        def rerank(q, items, k):
            for i in items:
                i.rerank_score = 1.0
            return items
        res = self._result()
        res.items.extend([RecallItem(content=f"extra{i}") for i in range(5)])
        apply_rerank(res, rerank, "q", top_k=3)
        assert len(res.items) <= 3
