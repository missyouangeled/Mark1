"""compress_queue.py 单元测试（pytest 形式）。

原为脚本式 run_tests()，转换为 pytest 可收集函数以纳入覆盖率统计。
注意：本模块涉及真实线程队列，每个测试自建 CompressQueue 并 shutdown，避免状态泄漏。
"""

import json
import time

from mark42.compress_queue import (
    CompressQueue,
    CompressRequest,
    get_compress_queue,
)


# ── 测试 1: 基本入队 + 处理 ──

def test_basic_enqueue_and_complete():
    q = CompressQueue(max_workers=2)
    q.start()
    try:
        req = CompressRequest(
            content=json.dumps({"items": [{"id": i, "name": "x" * 50} for i in range(20)]}),
            session_id="test-1",
        )
        assert q.enqueue(req) is True
        completed = req.wait(timeout=10.0)
        assert completed
        assert req.result is not None or req.error is not None
        assert req.error is None
        assert req.result.get("changed") is True
        assert req.result.get("route_algo") == "smartcrush"
    finally:
        q.shutdown()


# ── 测试 2: 多 worker 并发 ──

def test_multi_worker_concurrent():
    q = CompressQueue(max_workers=3)
    q.start()
    try:
        requests = []
        for i in range(10):
            r = CompressRequest(content="def foo():\n    pass\n" * 50, session_id=f"test-2-{i}")
            requests.append(r)
            q.enqueue(r)
        assert q.stats["enqueued"] == 10
        for r in requests:
            r.wait(timeout=15.0)
        completed_count = sum(1 for r in requests if r.result is not None)
        assert completed_count == 10
        assert q.stats["processed"] == 10
    finally:
        q.shutdown()


# ── 测试 3: 优先级（urgent 先处理）──

def test_priority_urgent_first():
    q = CompressQueue(max_workers=1)  # 单 worker 强制串行
    try:
        low = CompressRequest(content="def foo():\n    pass\n" * 100, session_id="low", priority=9)
        urgent = CompressRequest(content="def bar():\n    pass\n" * 100, session_id="urgent", priority=0)
        # 先填队列再启 worker，让 PriorityQueue 有机会选 urgent
        t0 = time.time()
        low._enqueued_at = t0
        urgent._enqueued_at = t0
        q._queue.put_nowait((low.priority, 1, low))
        q._queue.put_nowait((urgent.priority, 2, urgent))
        q.stats["enqueued"] += 2
        q.start()
        urgent.wait(timeout=20.0)
        low.wait(timeout=20.0)
        assert urgent.result["finishedAt"] < low.result["finishedAt"]
    finally:
        q.shutdown()


# ── 测试 4: 错误处理（异常内容不杀 worker）──

def test_error_handling_worker_survives():
    q = CompressQueue(max_workers=1)
    q.start()
    try:
        r1 = CompressRequest(content=json.dumps({"a": 1, "b": list(range(100))}))
        q.enqueue(r1)
        r1.wait(timeout=10.0)
        assert r1.result is not None

        # 极端: 超大内容 5MB，应 passthrough 而不是崩
        r2 = CompressRequest(content="x" * 5_000_000)
        q.enqueue(r2)
        r2.wait(timeout=20.0)
        assert r2.result is not None or r2.error is not None
        assert q.stats["processed"] + q.stats["failed"] >= 1

        # 确认 worker 没死
        r3 = CompressRequest(content=json.dumps({"c": 2}))
        q.enqueue(r3)
        r3.wait(timeout=10.0)
        assert r3.result is not None
    finally:
        q.shutdown()


# ── 测试 5: 队列满 + 优先级丢弃 ──

def test_queue_full_and_priority_drop():
    q = CompressQueue(max_workers=0, max_queue_size=3)  # workers=0 不启线程
    reqs = []
    for i in range(3):
        r = CompressRequest(content="def foo():\n    pass\n" * 50, priority=5)
        reqs.append(r)
        q._queue.put_nowait((r.priority, i + 1, r))
        q.stats["enqueued"] += 1
    assert q._queue.qsize() == 3

    # 同优先级超额被拒
    r4 = CompressRequest(content="x" * 100, priority=5)
    assert q.enqueue(r4) is False
    assert q.stats["dropped_queue_full"] >= 1

    # 紧急请求（priority=0）应能挤掉低优先级
    r5 = CompressRequest(content="y" * 100, priority=0)
    assert q.enqueue(r5) is True
    assert q.stats["dropped_low_priority"] >= 1


# ── 测试 6: 单例模式 ──

def test_singleton():
    a = get_compress_queue()
    b = get_compress_queue()
    assert a is b
    assert a._running is True
    # 不 shutdown，留给进程退出（daemon=True 自动清理）


# ── 测试 7: shutdown 后入队 auto-start ──

def test_shutdown_then_enqueue_autostart():
    q = CompressQueue(max_workers=1)
    q.start()
    q.shutdown()
    try:
        r = CompressRequest(content="def x():\n    pass\n" * 20)
        assert q.enqueue(r) is True  # auto-start
        r.wait(timeout=10.0)
        assert r.result is not None
    finally:
        q.shutdown()


# ── 测试 8: stats 准确性 ──

def test_stats_accuracy():
    q = CompressQueue(max_workers=2)
    q.start()
    try:
        n_ok = 5
        reqs = [CompressRequest(content=json.dumps({"i": i, "v": "x" * 30})) for i in range(n_ok)]
        for r in reqs:
            q.enqueue(r)
        for r in reqs:
            r.wait(timeout=10.0)
        assert q.stats["enqueued"] == n_ok
        assert q.stats["processed"] == n_ok
        assert q.stats["failed"] == 0
    finally:
        q.shutdown()


# ── 测试 9: 真实 diff 走异步 ──

def test_real_diff_async():
    q = CompressQueue(max_workers=2)
    q.start()
    try:
        diff_content = "@@ -1,50 +1,50 @@\n" + "\n".join(f" line{i}" for i in range(50)) + "\n-old\n+new\n" * 3
        r = CompressRequest(content=diff_content, session_id="real-diff")
        q.enqueue(r)
        r.wait(timeout=10.0)
        assert r.result is not None
        assert r.result["route_algo"] == "diff"
    finally:
        q.shutdown()
