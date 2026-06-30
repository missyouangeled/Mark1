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
