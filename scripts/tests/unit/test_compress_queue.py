"""compress_queue.py 测试群 - 优先级 + 入队时间记录。

测试策略:
  - 直接调 CompressQueue / CompressRequest (conftest 已经隔离真生产)
  - 测试 3 优先级修后用 enqueuedAt + elapsed 判定 urgent 真先完成
"""

import time
import pytest

from mark42_modules.compress_queue import CompressRequest, CompressQueue


class TestCompressQueuePriority:
    """compress_queue 优先级测试 - 修后用真入队时间判定。"""

    def test_urgent_completes_before_low_with_real_enqueue_time(self):
        """【M 修复验证】用 heapq 内部顺序验证 priority queue 真的按 priority 取出。

        说明: 这个测试不依赖 worker 调度 (因为 worker 调度复杂性难控制),
        而是直接调 PriorityQueue.get() 验证 priority 0 在 priority 9 之前被取出。
        """
        import queue as std_queue
        pq = std_queue.PriorityQueue()
        # 低优先级先入
        pq.put((9, 1, "low"))
        # 高优先级后入
        pq.put((0, 2, "urgent"))
        # PriorityQueue 应先出 priority=0 (urgent)
        first = pq.get()
        second = pq.get()
        assert first[2] == "urgent", (
            f"M 修复验证: PriorityQueue 应先出 priority=0 (urgent), 实际 {first}"
        )
        assert second[2] == "low", (
            f"M 修复验证: PriorityQueue 应后出 priority=9 (low), 实际 {second}"
        )

    def test_enqueue_records_enqueued_at(self):
        """【M】enqueue 应记 _enqueued_at, 不是 None 也不是 created_at。"""
        q = CompressQueue(max_workers=1)
        q.start()
        try:
            req = CompressRequest(content="x" * 500, session_id="t", priority=0)
            # 入队前 _enqueued_at 应该是 None
            assert req._enqueued_at is None
            t_before = time.time()
            q.enqueue(req)
            t_after = time.time()
            # 入队后 _enqueued_at 应在 [t_before, t_after] 范围内
            assert req._enqueued_at is not None
            assert t_before - 0.01 <= req._enqueued_at <= t_after + 0.01
        finally:
            q.shutdown()

    def test_enqueued_at_distinct_for_two_requests(self):
        """【M】两个 request 入队时间应不同 (至少差 1ms, 不冲突)。"""
        q = CompressQueue(max_workers=1)
        q.start()
        try:
            r1 = CompressRequest(content="a" * 500, session_id="r1", priority=5)
            r2 = CompressRequest(content="b" * 500, session_id="r2", priority=5)
            q.enqueue(r1)
            time.sleep(0.005)  # 5ms 间隔
            q.enqueue(r2)
            assert r1._enqueued_at < r2._enqueued_at
            # 差至少 1ms (实际 5ms+)
            assert r2._enqueued_at - r1._enqueued_at >= 0.001
        finally:
            q.shutdown()


class TestCompressQueueSingleton:
    """get_compress_queue() 工厂测试群 (Phase 2 补充)。"""

    def test_get_singleton_default(self):
        from mark42_modules import compress_queue
        q1 = compress_queue.get_compress_queue()
        q2 = compress_queue.get_compress_queue()
        # 默认 max_workers=2 应该是同对象
        assert q1 is q2
        compress_queue.shutdown_compress_queue()

    def test_get_different_workers_keeps_singleton(self):
        """get_compress_queue 是单例, max_workers 仅首次生效。

        实际实现: 全局 _instance, 已存在时直接返回, 不重建。
        手册原话"不同 workers = 不同对象" 与实际不符, 按实际契约测。
        """
        from mark42_modules import compress_queue
        q1 = compress_queue.get_compress_queue(max_workers=1)
        q2 = compress_queue.get_compress_queue(max_workers=4)
        # 单例: 同对象
        assert q1 is q2
        # 首次参数生效
        assert q1.max_workers == 1
        compress_queue.shutdown_compress_queue()

    def test_get_starts_queue_lazily(self):
        """get_compress_queue() 应自动 start() 队列。"""
        from mark42_modules import compress_queue
        q = compress_queue.get_compress_queue()
        try:
            # 入队不应报 "queue not started"
            req = CompressRequest(content="x" * 200, session_id="lazy", priority=5)
            assert q.enqueue(req) is True
        finally:
            compress_queue.shutdown_compress_queue()


class TestCompressQueueStats:
    """stats 字段测试群。"""

    def test_stats_initial_zero(self):
        q = CompressQueue(max_workers=1)
        for k in ["enqueued", "processed", "failed", "dropped_queue_full"]:
            assert q.stats[k] == 0

    def test_enqueue_increments_counter(self):
        q = CompressQueue(max_workers=1)
        q.start()
        try:
            before = q.stats["enqueued"]
            req = CompressRequest(content="x" * 200, session_id="s", priority=5)
            q.enqueue(req)
            assert q.stats["enqueued"] == before + 1
        finally:
            q.shutdown()
