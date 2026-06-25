"""
Mark42 上下文压缩算法 - 借鉴 Headroom 设计

当前仅保留 RAGRanker：
- RAGRanker: RAG 片段排序 + 截断

Day 11: SmartCrusher 已拆出到独立模块 smart_crusher.py
"""


class RAGRanker:
    """借鉴 Headroom Search Ranker：RAG 片段排序 + 截断"""

    def __init__(self,
                 top_k: int = 3,
                 max_chunk_tokens: int = 300,
                 min_chunk_tokens: int = 50):
        self.top_k = top_k
        self.max_chunk = max_chunk_tokens
        self.min_chunk = min_chunk_tokens

    def rank_and_truncate(self,
                          query: str,
                          chunks: list[dict]) -> tuple[list[dict], dict]:
        """输入 [{content, score, source}], 输出 (top-k 截断版 list, 统计 dict)

        不修改原 chunks, 返回新 list
        """
        stats = {
            "algorithm": "rag_ranker",
            "original_chunks": len(chunks),
            "kept_chunks": 0,
            "truncated_chunks": 0,
            "original_bytes": 0,
            "truncated_bytes": 0,
            "ratio": 0.0,
        }

        if not chunks:
            return chunks, stats

        for c in chunks:
            content = c.get("content", "")
            if isinstance(content, str):
                stats["original_bytes"] += len(content.encode('utf-8'))

        sorted_chunks = sorted(
            chunks,
            key=lambda c: c.get("score", 0.0),
            reverse=True
        )

        top = sorted_chunks[:self.top_k]
        stats["kept_chunks"] = len(top)

        result: list[dict] = []
        for chunk in top:
            new_chunk = dict(chunk)
            content = new_chunk.get("content", "")

            if not isinstance(content, str):
                result.append(new_chunk)
                continue

            tokens = self._estimate_tokens(content)
            if tokens > self.max_chunk:
                new_chunk["content"] = self._truncate(content, self.max_chunk)
                new_chunk["truncated"] = True
                new_chunk["truncated_from_tokens"] = tokens
                stats["truncated_chunks"] += 1
            else:
                new_chunk["truncated"] = False

            stats["truncated_bytes"] += len(new_chunk["content"].encode('utf-8'))
            result.append(new_chunk)

        if stats["original_bytes"] > 0:
            stats["ratio"] = 1.0 - (stats["truncated_bytes"] / stats["original_bytes"])

        return result, stats

    def _estimate_tokens(self, text: str) -> int:
        """粗略估计 token 数: 中文 1.5 字符/token, 英文 4 字符/token"""
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english = len(text) - chinese
        return int(chinese / 1.5 + english / 4)

    def _truncate(self, text: str, max_tokens: int) -> str:
        """按 max_tokens 截断, 加标记"""
        max_chars = int(max_tokens * 1.5) + int(max_tokens * 4)
        if len(text) > max_chars:
            return text[:max_chars] + f"\n... (truncated to {max_tokens} tokens)"
        return text


_ragranker_singleton: RAGRanker | None = None


def get_ragranker() -> RAGRanker:
    global _ragranker_singleton
    if _ragranker_singleton is None:
        _ragranker_singleton = RAGRanker()
    return _ragranker_singleton


def ragrank(query: str, chunks: list[dict]) -> tuple[list[dict], dict]:
    """公开 API: RAG 排序 + 截断"""
    return get_ragranker().rank_and_truncate(query, chunks)


def _run_ragrank_tests():
    print()
    print("=" * 60)
    print("RAGRanker 单元测试")
    print("=" * 60)

    ranker = RAGRanker(top_k=3, max_chunk_tokens=100, min_chunk_tokens=20)

    test1_input = [
        {"content": "短文本", "score": 0.5, "source": "src1"},
        {"content": "A" * 1000, "score": 0.9, "source": "src2"},
        {"content": "B" * 500, "score": 0.7, "source": "src3"},
        {"content": "C" * 200, "score": 0.3, "source": "src4"},
        {"content": "D" * 100, "score": 0.8, "source": "src5"},
    ]
    test1_output, test1_stats = ranker.rank_and_truncate("test", test1_input)
    print(f"\n[测试 1] 5 chunks 排序 + 截断到 top-3")
    print(f"  原 chunks: {test1_stats['original_chunks']}")
    print(f"  保留: {test1_stats['kept_chunks']}")
    print(f"  被截断: {test1_stats['truncated_chunks']}")
    print(f"  压缩率: {test1_stats['ratio'] * 100:.1f}%")
    print(f"  排序后: {[c['source'] for c in test1_output]}")
    assert test1_stats['kept_chunks'] == 3
    assert test1_output[0]['source'] == 'src2'
    assert test1_output[1]['source'] == 'src5'
    assert test1_output[2]['source'] == 'src3'
    assert test1_output[0]['truncated'] is True
    print("  ✓ 通过")

    test2_output, test2_stats = ranker.rank_and_truncate("test", [])
    print(f"\n[测试 2] 空输入")
    print(f"  保留: {test2_stats['kept_chunks']}")
    assert test2_stats['kept_chunks'] == 0
    print("  ✓ 通过")

    ranker_test = RAGRanker()
    test_cn = "你好世界" * 50
    test_en = "hello world " * 50
    cn_tokens = ranker_test._estimate_tokens(test_cn)
    en_tokens = ranker_test._estimate_tokens(test_en)
    print(f"\n[测试 3] token 估算")
    print(f"  200 字符中文 → {cn_tokens} tokens")
    print(f"  600 字符英文 → {en_tokens} tokens")
    assert cn_tokens > 100
    assert 100 < en_tokens < 200
    print("  ✓ 通过")

    print()
    print("=" * 60)
    print("RAGRanker 全部测试通过 ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if _run_ragrank_tests() else 1)
