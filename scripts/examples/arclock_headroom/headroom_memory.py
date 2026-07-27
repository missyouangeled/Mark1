"""
Headroom MemoryLock Adapter - 第三方 ArcLock 适配器示例

这是一个完整的第三方向量搜索适配器实现，演示如何将
Headroom 记忆服务接入到 Mark42 的 ArcLock 通用适配层接口。

特点:
- 不 import 任何 mark42 内部模块
- 只需要方法签名匹配 Protocol 就能"吸上"
- 用 stub/mock 模拟向量搜索（不依赖真实向量数据库）
"""

from __future__ import annotations
from typing import Any, Dict, List
import random
import time


class HeadroomMemory:
    """Headroom 记忆/向量搜索适配器。

    实现 ArcLock 的 MemoryLock Protocol，不需要继承任何类。
    只要方法签名正确，就能被 Mark42 的 ArcLock 注册器识别。
    """

    def __init__(self, api_key: str = "", index_name: str = "mark42-memory",
                 base_url: str = "https://api.headroom.ai",
                 embedding_model: str = "all-MiniLM-L6-v2"):
        """初始化适配器。

        参数来自 arclock.yaml 配置文件的 config 节。
        """
        self.api_key = api_key
        self.index_name = index_name
        self.base_url = base_url
        self.embedding_model = embedding_model
        self._mock_documents: List[Dict[str, Any]] = self._init_seed_data()

    def _init_seed_data(self) -> List[Dict[str, Any]]:
        """初始化一些种子文档，模拟已索引的记忆数据。"""
        return [
            {
                "id": "doc_001",
                "content": "Mark42 是一个具有自愈能力的 AI 助手框架，采用战甲设计",
                "vector": [random.random() for _ in range(384)],
                "metadata": {"source": "docs/intro.md", "timestamp": 1690000000},
            },
            {
                "id": "doc_002",
                "content": "ArcLock 通用适配层让第三方实现可以'咔嗒'吸上 Mark42 接口",
                "vector": [random.random() for _ in range(384)],
                "metadata": {"source": "docs/design/arclock.md", "timestamp": 1690000001},
            },
            {
                "id": "doc_003",
                "content": "CompressLock 负责上下文压缩，支持 Headroom、armor 等实现",
                "vector": [random.random() for _ in range(384)],
                "metadata": {"source": "docs/design/compress.md", "timestamp": 1690000002},
            },
            {
                "id": "doc_004",
                "content": "MemoryLock 负责向量搜索，支持 Pinecone、Chroma、QMD 等实现",
                "vector": [random.random() for _ in range(384)],
                "metadata": {"source": "docs/design/memory.md", "timestamp": 1690000003},
            },
            {
                "id": "doc_005",
                "content": "Protocol 是 PEP 544 定义的结构化子类型，支持鸭子类型",
                "vector": [random.random() for _ in range(384)],
                "metadata": {"source": "docs/design/protocol.md", "timestamp": 1690000004},
            },
        ]

    def _mock_vector_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """模拟向量搜索，返回相关文档。

        真实实现中应该:
        1. 用 embedding 模型生成 query 向量
        2. 调用向量数据库的 search API
        3. 返回结果

        这里用简单的关键词匹配 + 随机分数模拟相关性。
        """
        time.sleep(0.01)  # 模拟搜索延迟

        query_lower = query.lower()
        results = []

        for doc in self._mock_documents:
            # 简单的关键词匹配模拟相关性
            content_lower = doc["content"].lower()
            matches = sum(1 for word in query_lower.split() if word in content_lower)
            base_score = 0.3 + (matches * 0.2) + random.uniform(-0.1, 0.1)
            score = min(max(base_score, 0.0), 1.0)

            results.append({
                "content": doc["content"],
                "score": score,
                "source": doc["metadata"]["source"],
                "document_id": doc["id"],
            })

        # 按分数排序取 top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """语义搜索，返回相关文档列表。

        实现 MemoryLock Protocol 要求的 search() 方法。

        参数:
            query: 搜索查询字符串
            top_k: 返回结果数量

        返回格式要求:
            [{"content": str, "score": float, "source": str}, ...]
        """
        raw_results = self._mock_vector_search(query, top_k)

        # 按照 Mark42 MemoryLock 约定的格式返回
        return [
            {
                "content": r["content"],
                "score": r["score"],
                "source": r["source"],
            }
            for r in raw_results
        ]

    def index(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """索引文档。

        实现 MemoryLock Protocol 要求的 index() 方法。

        参数:
            documents: 文档列表，每个文档应包含 content、metadata 等字段

        返回格式要求:
            {"indexed": int, "status": str}
        """
        time.sleep(0.01)  # 模拟索引延迟

        for i, doc in enumerate(documents):
            new_doc = {
                "id": f"doc_{len(self._mock_documents) + i + 1:03d}",
                "content": doc.get("content", ""),
                "vector": [random.random() for _ in range(384)],
                "metadata": doc.get("metadata", {"source": "user_input", "timestamp": int(time.time())}),
            }
            self._mock_documents.append(new_doc)

        return {
            "indexed": len(documents),
            "status": "success",
            "total_documents": len(self._mock_documents),
        }

    def health(self) -> bool:
        """后端是否可用。

        实现 MemoryLock Protocol 要求的 health() 方法。
        用于启动时检查和运行时健康监控。
        """
        # 真实实现中应该 ping 一下向量数据库
        # 这里模拟 99% 可用性
        return random.random() > 0.01


# ── 独立运行时的快速测试 ──

if __name__ == "__main__":
    # 这个演示证明：第三方代码不需要任何 mark42 依赖就能独立运行
    print("=" * 60)
    print("Headroom MemoryLock Adapter - 独立测试（不依赖 Mark42）")
    print("=" * 60)

    adapter = HeadroomMemory(api_key="test-key", index_name="mark42-test")

    print("\n1. health() - 健康检查:")
    is_healthy = adapter.health()
    print(f"   healthy: {is_healthy}")

    print("\n2. search('ArcLock 设计') - 向量搜索:")
    results = adapter.search("ArcLock 设计", top_k=3)
    for i, result in enumerate(results, 1):
        print(f"   [{i}] score={result['score']:.3f}, source={result['source']}")
        print(f"       content: {result['content'][:50]}...")

    print("\n3. index() - 索引新文档:")
    new_docs = [
        {"content": "第三方适配器可以实现 hot-swap 热替换", "metadata": {"source": "user"}},
        {"content": "鸭子类型是 Python Protocol 的核心特性", "metadata": {"source": "user"}},
    ]
    result = adapter.index(new_docs)
    print(f"   indexed: {result['indexed']}")
    print(f"   status: {result['status']}")
    print(f"   total_documents: {result['total_documents']}")

    print("\n4. search('鸭子类型') - 验证新文档可搜索:")
    results = adapter.search("鸭子类型", top_k=2)
    for i, result in enumerate(results, 1):
        print(f"   [{i}] score={result['score']:.3f}, source={result['source']}")
        if "鸭子类型" in result["content"]:
            print(f"       ✅ 新文档被检索到！")

    print("\n✅ 第三方 MemoryLock 适配器可以完全独立运行！")
    print("   只要方法签名正确，就能被 ArcLock 注册器'吸上'。")
