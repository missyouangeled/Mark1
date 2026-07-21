"""从 compress_queue.py 提取的单元测试。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mark42.compress_queue import *


def run_tests():
    import json as _json

    passed = 0
    failed = 0

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            log.info(f"  ✓ {name}")
            passed += 1
        else:
            log.error(f"  ✗ {name}")
            failed += 1

    # ---- 测试 1: 基本入队 + 处理 ----
    log.info("\n[测试 1] 基本入队 + 等待完成")
    q = CompressQueue(max_workers=2)
    q.start()
    req = CompressRequest(
        content=_json.dumps({"items": [{"id": i, "name": "x" * 50} for i in range(20)]}),
        session_id="test-1",
    )
    assert q.enqueue(req) is True, "enqueue should succeed"
    check("1.1 入队成功", True)
    completed = req.wait(timeout=10.0)
    check("1.2 wait 10s 内完成", completed)
    check("1.3 result 或 error 至少一个存在", req.result is not None or req.error is not None)
    check("1.4 成功无 error", req.error is None)
    check("1.5 changed=True (JSON 大输入应被压缩)", req.result.get("changed") is True)
    check("1.6 route_algo=smartcrush", req.result.get("route_algo") == "smartcrush")
    log.info(
        f"  → route={req.result['route_algo']} ratio={req.result['ratio']:.1%} elapsed={req.result['elapsed']:.2f}s"
    )
    q.shutdown()

    # ---- 测试 2: 多 worker 并发 ----
    log.info("\n[测试 2] 多 worker 并发处理 10 个请求")
    q2 = CompressQueue(max_workers=3)
    q2.start()
    requests = []
    for i in range(10):
        r = CompressRequest(
            content="def foo():\n    pass\n" * 50,
            session_id=f"test-2-{i}",
        )
        requests.append(r)
        q2.enqueue(r)
    check("2.1 全部入队", q2.stats["enqueued"] == 10)
    # 等全部完成
    for r in requests:
        r.wait(timeout=15.0)
    completed_count = sum(1 for r in requests if r.result is not None)
    check("2.2 10 个全部完成", completed_count == 10)
    check("2.3 processed=10", q2.stats["processed"] == 10)
    q2.shutdown()

    # ---- 测试 3: 优先级 (urgent 先处理) ----
    log.info("\n[测试 3] 优先级队列")
    q3 = CompressQueue(max_workers=1)  # 单 worker 强制串行
    # 【Bug fix 2026-07-02】关键: 先填队列再启 worker, 让 PriorityQueue 真有机会选 urgent
    # 原版先 start() 再 enqueue(low), worker 立即抢走 low, urgent 后入队时 worker 已忙
    # → urgent 等 low 跑完才能开始 → urgent_finish > low_finish → 3.1 必然失败
    # 现与测试 5 同样手法, 直接 _queue.put_nowait, 两条都已就位再 start
    low = CompressRequest(content="def foo():\n    pass\n" * 100, session_id="low", priority=9)
    urgent = CompressRequest(content="def bar():\n    pass\n" * 100, session_id="urgent", priority=0)
    # 两边同 timestamp 入队: PriorityQueue 只看 priority, 同 priority 才看 seq
    # urgent (0) < low (9), worker 起来必先弹 urgent
    t0 = time.time()
    low._enqueued_at = t0
    urgent._enqueued_at = t0
    q3._queue.put_nowait((low.priority, 1, low))
    q3._queue.put_nowait((urgent.priority, 2, urgent))
    q3.stats["enqueued"] += 2
    q3.start()  # worker 起来后两条都已入队, PriorityQueue 必先弹 urgent (priority=0)
    urgent.wait(timeout=20.0)
    low.wait(timeout=20.0)
    # urgent 应先完成 = urgent 绝对完成时间 (enqueuedAt + elapsed) 早于 low
    urgent_finish = urgent.result["finishedAt"]
    low_finish = low.result["finishedAt"]
    check("3.1 urgent 真比 low 先完成", urgent_finish < low_finish)
    q3.shutdown()

    # ---- 测试 4: 错误处理 (异常内容不杀 worker) ----
    log.info("\n[测试 4] 错误处理")
    q4 = CompressQueue(max_workers=1)
    q4.start()
    # 正常请求
    r1 = CompressRequest(content=_json.dumps({"a": 1, "b": list(range(100))}))
    q4.enqueue(r1)
    r1.wait(timeout=10.0)
    check("4.1 第一个正常完成", r1.result is not None)
    # 极端: 超大内容 (5MB) — algo_scheduler 应该 passthrough 而不是崩
    r2 = CompressRequest(content="x" * 5_000_000)
    q4.enqueue(r2)
    r2.wait(timeout=20.0)
    check("4.2 极端内容不崩", r2.result is not None or r2.error is not None)
    check("4.3 worker 仍然存活", q4.stats["processed"] + q4.stats["failed"] >= 1)
    # 再来一个正常请求, 确认 worker 没死
    r3 = CompressRequest(content=_json.dumps({"c": 2}))
    q4.enqueue(r3)
    r3.wait(timeout=10.0)
    check("4.4 worker 仍能处理后续", r3.result is not None)
    q4.shutdown()

    # ---- 测试 5: 队列满 + 优先级丢弃 (不启 worker, 精确控制) ----
    log.info("\n[测试 5] 队列满 (max=3) — 不启 worker 模拟积压")
    q5 = CompressQueue(max_workers=0, max_queue_size=3)  # workers=0 不启线程
    # 不 start() 避免起 worker; 直接操作 PriorityQueue
    # 手动填满 (绕过 running 检查)
    reqs = []
    for i in range(3):
        r = CompressRequest(content="def foo():\n    pass\n" * 50, priority=5)
        reqs.append(r)
        q5._queue.put_nowait((r.priority, i + 1, r))
        q5.stats["enqueued"] += 1
    check("5.1 3 个已填满", q5._queue.qsize() == 3)
    # 第 4 个: 优先级 5, 没有更低优先级的可丢弃 → 直接拒
    r4 = CompressRequest(content="x" * 100, priority=5)
    accepted = q5.enqueue(r4)
    check("5.2 同优先级超额被拒", accepted is False)
    check("5.3 dropped_queue_full >= 1", q5.stats["dropped_queue_full"] >= 1)
    # 第 5 个: 优先级 0 (紧急) → 应能挤掉一个低优先级
    r5 = CompressRequest(content="y" * 100, priority=0)
    accepted = q5.enqueue(r5)
    check("5.4 紧急请求可挤掉低优先级", accepted is True)
    check("5.5 dropped_low_priority >= 1", q5.stats["dropped_low_priority"] >= 1)

    # ---- 测试 6: 单例模式 ----
    log.info("\n[测试 6] 单例")
    a = get_compress_queue()
    b = get_compress_queue()
    check("6.1 get_compress_queue 返回单例", a is b)
    check("6.2 单例已启动", a._running is True)
    # 不 shutdown, 留给进程退出 (daemon=True 会自动清理)

    # ---- 测试 7: shutdown 后入队 ----
    log.info("\n[测试 7] shutdown 安全性")
    q7 = CompressQueue(max_workers=1)
    q7.start()
    q7.shutdown()
    # shutdown 后再 enqueue → auto-start 触发
    r = CompressRequest(content="def x():\n    pass\n" * 20)
    accepted = q7.enqueue(r)
    check("7.1 shutdown 后 enqueue auto-start", accepted is True)
    r.wait(timeout=10.0)
    check("7.2 处理成功", r.result is not None)
    q7.shutdown()

    # ---- 测试 8: stats 准确性 ----
    log.info("\n[测试 8] stats 准确")
    q8 = CompressQueue(max_workers=2)
    q8.start()
    n_ok = 5
    reqs = [CompressRequest(content=_json.dumps({"i": i, "v": "x" * 30})) for i in range(n_ok)]
    for r in reqs:
        q8.enqueue(r)
    for r in reqs:
        r.wait(timeout=10.0)
    check(f"8.1 enqueued={n_ok}", q8.stats["enqueued"] == n_ok)
    check(f"8.2 processed={n_ok}", q8.stats["processed"] == n_ok)
    check("8.3 failed=0", q8.stats["failed"] == 0)
    q8.shutdown()

    # ---- 测试 9: 真实 diff 走异步 ----
    log.info("\n[测试 9] 真实场景: diff 异步")
    q9 = CompressQueue(max_workers=2)
    q9.start()
    diff_content = "@@ -1,50 +1,50 @@\n" + "\n".join(f" line{i}" for i in range(50)) + "\n-old\n+new\n" * 3
    r = CompressRequest(content=diff_content, session_id="real-diff")
    q9.enqueue(r)
    r.wait(timeout=10.0)
    check("9.1 diff 异步处理", r.result is not None)
    check("9.2 route_algo=diff", r.result["route_algo"] == "diff")
    log.info(f"  → route={r.result['route_algo']} ratio={r.result['ratio']:.1%}")
    q9.shutdown()

    log.info("")
    log.info("=" * 60)
    log.info(f"结果: {passed} 通过 / {failed} 失败")
    log.info("=" * 60)
    return failed == 0

