"""compression_algorithms.py 测试群。

覆盖:
  - get_ragranker() 工厂 (单例)
  - ragrank(query, chunks) 包装函数
  - RAGRanker.rank_and_truncate 排序 + 截断契约

设计:
  - chunks 字段: content (不是 text) / score
  - rank_and_truncate: 不修改原 chunks, 返回新 list
  - 字段名按实际: algorithm / original_chunks / kept_chunks /
    truncated_chunks / original_bytes / truncated_bytes / ratio
"""

from unittest.mock import MagicMock

import pytest

from mark42_modules import compression_algorithms


class TestRAGRankerFactory:
    """get_ragranker() 工厂测试群。"""

    def test_factory_singleton(self):
        r1 = compression_algorithms.get_ragranker()
        r2 = compression_algorithms.get_ragranker()
        assert r1 is r2

    def test_factory_returns_instance(self):
        r = compression_algorithms.get_ragranker()
        assert r is not None
        assert hasattr(r, "rank_and_truncate")


class TestRagrank:
    """ragrank() 包装函数测试群。"""

    def test_ragrank_empty_chunks(self):
        """空 chunks -> ([], stats), 不崩。"""
        result, stats = compression_algorithms.ragrank("query", [])
        assert result == []
        assert isinstance(stats, dict)
        assert stats["original_chunks"] == 0
        assert stats["kept_chunks"] == 0

    def test_ragrank_keeps_top_k_by_score(self):
        """3 chunks, top_k=3 (默认) -> 全部保留, 按 score 降序。"""
        chunks = [
            {"content": "低相关", "score": 0.3},
            {"content": "高相关", "score": 0.9},
            {"content": "中相关", "score": 0.6},
        ]
        result, stats = compression_algorithms.ragrank("query", chunks)
        # 全部保留
        assert len(result) == 3
        # 按 score 降序
        scores = [c.get("score") for c in result]
        assert scores == sorted(scores, reverse=True)
        # 第一个应是 score=0.9
        assert result[0]["score"] == 0.9
        # stats 正确
        assert stats["original_chunks"] == 3
        assert stats["kept_chunks"] == 3

    def test_ragrank_truncates_long_chunks(self):
        """max_chunk=300 token, 长 content 会被截断 + 标记 truncated=True。"""
        # 造一个 > 300 token 的 chunk
        long_content = "这是一段很长的中文内容。" * 100  # 中文 1.5 字符/token
        chunks = [
            {"content": long_content, "score": 0.8},
            {"content": "短", "score": 0.5},
        ]
        result, stats = compression_algorithms.ragrank("query", chunks)
        # 第一个应是 score=0.8 的, 且被截断
        assert result[0]["truncated"] is True
        # truncated_chunks >= 1
        assert stats["truncated_chunks"] >= 1

    def test_ragrank_does_not_modify_original(self):
        """rank_and_truncate 不应修改入参 chunks。"""
        chunks = [
            {"content": "短", "score": 0.5},
            {"content": "中", "score": 0.7},
        ]
        original_copy = [dict(c) for c in chunks]
        compression_algorithms.ragrank("query", chunks)
        # 原 chunks 不应被改
        assert chunks == original_copy

    def test_ragrank_top_k_limit(self):
        """top_k=2, 3 个 chunks -> 只保留 2 个。"""
        ranker = compression_algorithms.RAGRanker(top_k=2)
        chunks = [
            {"content": f"chunk{i}", "score": float(i) / 10}
            for i in range(1, 4)  # score: 0.1, 0.2, 0.3
        ]
        result, stats = ranker.rank_and_truncate("query", chunks)
        assert len(result) == 2
        assert stats["kept_chunks"] == 2
        # 保留的应是 score 最高的 2 个 (0.3, 0.2)
        assert result[0]["score"] == 0.3
        assert result[1]["score"] == 0.2

    def test_ragrank_metadata_contains_ratio(self):
        """stats['ratio'] 反映截断后的字节节省率。"""
        chunks = [
            {"content": "x" * 10000, "score": 0.5},  # 长内容
        ]
        result, stats = compression_algorithms.ragrank("query", chunks)
        assert "ratio" in stats
        # 长 content 截断后应有 ratio > 0
        assert stats["ratio"] > 0.0
