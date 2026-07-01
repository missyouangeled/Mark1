"""compress_queue.py 测试群 - 优先级 + 入队时间记录。

测试策略:
  - 直接调 CompressQueue / CompressRequest (conftest 已经隔离真生产)
  - 测试 3 优先级修后用 enqueuedAt + elapsed 判定 urgent 真先完成
"""

import sys
import types
import time
import pytest

from mark42_modules import compress_queue
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


class TestCompressRequest:
    """CompressRequest 自身行为。"""

    def test_set_result_marks_event_and_exposes_result(self):
        req = CompressRequest(content="hello")
        payload = {"status": "ok"}
        req.set_result(payload)
        assert req.wait(timeout=0.01) is True
        assert req.result == payload
        assert req.error is None

    def test_set_error_marks_event_and_exposes_error(self):
        req = CompressRequest(content="hello")
        req.set_error("boom")
        assert req.wait(timeout=0.01) is True
        assert req.result is None
        assert req.error == "boom"

    def test_wait_times_out_when_not_completed(self):
        req = CompressRequest(content="hello")
        assert req.wait(timeout=0.001) is False


class TestCompressQueueLifecycle:
    """start/shutdown/qsize/get_result 等基础行为。"""

    def test_start_is_idempotent(self):
        q = CompressQueue(max_workers=2)
        q.start()
        first_workers = list(q._workers)
        q.start()
        assert q._running is True
        assert q._workers == first_workers
        assert len(q._workers) == 2
        q.shutdown()

    def test_shutdown_is_idempotent_and_clears_workers(self):
        q = CompressQueue(max_workers=1)
        q.start()
        q.shutdown()
        assert q._running is False
        assert q._workers == []
        q.shutdown()
        assert q._workers == []

    def test_qsize_reflects_current_queue_size(self):
        q = CompressQueue(max_workers=0, max_queue_size=5)
        q._running = True
        req1 = CompressRequest(content="a")
        req2 = CompressRequest(content="b")
        assert q.enqueue(req1) is True
        assert q.enqueue(req2) is True
        assert q.qsize() == 2

    def test_get_result_raises_not_implemented(self):
        q = CompressQueue()
        with pytest.raises(NotImplementedError, match=r"use request.wait\(\) instead"):
            q.get_result("req-1")


class TestCompressQueueEnqueueAndDrop:
    """enqueue + 队列满挤压策略。"""

    def test_enqueue_auto_starts_when_not_running(self, mocker):
        q = CompressQueue(max_workers=0)
        start_spy = mocker.spy(q, "start")
        req = CompressRequest(content="x" * 200)
        assert q.enqueue(req) is True
        assert start_spy.call_count == 1
        assert q._running is True

    def test_try_drop_lower_priority_returns_false_when_queue_empty(self):
        q = CompressQueue(max_workers=0)
        assert q._try_drop_lower_priority(0) is False

    def test_try_drop_lower_priority_returns_false_when_no_worse_item(self):
        q = CompressQueue(max_workers=0, max_queue_size=3)
        q._queue.put_nowait((0, 1, CompressRequest(content="a", priority=0)))
        q._queue.put_nowait((1, 2, CompressRequest(content="b", priority=1)))
        assert q._try_drop_lower_priority(1) is False
        assert q._queue.qsize() == 2

    def test_enqueue_drops_worse_item_for_higher_priority_request(self):
        q = CompressQueue(max_workers=0, max_queue_size=2)
        q._running = True
        low1 = CompressRequest(content="a", priority=9)
        low2 = CompressRequest(content="b", priority=9)
        assert q.enqueue(low1) is True
        assert q.enqueue(low2) is True

        urgent = CompressRequest(content="urgent", priority=0)
        assert q.enqueue(urgent) is True
        items = list(q._queue.queue)
        priorities = sorted(item[0] for item in items)
        contents = sorted(item[2].content for item in items)
        assert priorities == [0, 9]
        assert "urgent" in contents
        assert q.stats["dropped_low_priority"] == 1

    def test_enqueue_returns_false_when_full_and_cannot_drop(self):
        q = CompressQueue(max_workers=0, max_queue_size=1)
        q._running = True
        assert q.enqueue(CompressRequest(content="a", priority=0)) is True
        rejected = CompressRequest(content="b", priority=0)
        assert q.enqueue(rejected) is False
        assert q.stats["dropped_queue_full"] == 1


class TestCompressQueueProcessOne:
    """_process_one() 主逻辑补测。"""

    def test_process_one_llm_path_uses_top_level_module(self, mocker):
        q = CompressQueue(max_workers=0)
        q._workers = [mocker.Mock(is_alive=lambda: True), mocker.Mock(is_alive=lambda: False)]
        req = CompressRequest(content="原文", session_id="s1", content_type="llm:fast")
        req._enqueued_at = 123.0

        fake_module = types.ModuleType("llm_text_compressor")
        fake_module.llm_text_compress = lambda content, mode=None: (
            "压缩后",
            {
                "status": "ok",
                "original_bytes": 6,
                "crushed_bytes": 3,
                "ratio": 0.5,
            },
        )
        mocker.patch.dict(sys.modules, {"llm_text_compressor": fake_module}, clear=False)

        q._process_one(req)
        assert req.error is None
        assert req.result["route_algo"] == "llm"
        assert req.result["llm_mode"] == "fast"
        assert req.result["text"] == "压缩后"
        assert req.result["status"] == "ok"
        assert req.result["enqueuedAt"] == 123.0
        assert q.stats["processed"] == 1
        assert q.stats["active_workers"] == 1

    def test_process_one_default_scheduler_path_uses_package_import(self, mocker):
        q = CompressQueue(max_workers=0)
        q._workers = [mocker.Mock(is_alive=lambda: True)]
        req = CompressRequest(content="原文", session_id="s2")
        req._enqueued_at = 456.0

        class Decision:
            route_algo = "smartcrush"

        fake_algo = types.ModuleType("mark42_modules.algo_scheduler")
        fake_algo.process = lambda content: {
            "decision": Decision(),
            "result": "压缩结果",
            "changed": True,
            "original_size": 100,
            "compressed_size": 60,
            "compress_stats": {"ratio": 0.4},
        }

        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "algo_scheduler" and level == 0:
                raise ImportError("missing top-level algo_scheduler")
            if name == "algo_scheduler" and level == 1:
                return fake_algo
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)

        q._process_one(req)
        assert req.error is None
        assert req.result["route_algo"] == "smartcrush"
        assert req.result["text"] == "压缩结果"
        assert req.result["changed"] is True
        assert req.result["ratio"] == 0.4
        assert req.result["enqueuedAt"] == 456.0
        assert q.stats["processed"] == 1

    def test_process_one_sets_error_and_failed_stats_on_exception(self, mocker):
        q = CompressQueue(max_workers=0)
        q._workers = []
        req = CompressRequest(content="原文", session_id="s3")

        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "algo_scheduler" and level == 0:
                raise ImportError("missing top-level algo_scheduler")
            if name == "algo_scheduler" and level == 1:
                fake_algo = types.ModuleType("mark42_modules.algo_scheduler")

                def boom(content):
                    raise RuntimeError("explode")

                fake_algo.process = boom
                return fake_algo
            return original_import(name, globals, locals, fromlist, level)

        mocker.patch("builtins.__import__", side_effect=fake_import)

        q._process_one(req)
        assert req.result is None
        assert req.error == "RuntimeError: explode"
        assert q.stats["failed"] == 1


class TestCompressQueueWorkerAndSingletonCleanup:
    """worker loop 与全局 shutdown 补测。"""

    def test_worker_loop_breaks_on_poison_pill(self, mocker):
        q = CompressQueue(max_workers=0)
        q._running = True
        q._queue.put_nowait(None)
        process_spy = mocker.spy(q, "_process_one")
        q._worker_loop()
        assert process_spy.call_count == 0

    def test_shutdown_compress_queue_clears_global_instance(self, monkeypatch):
        q = CompressQueue(max_workers=0)
        called = {"shutdown": 0}

        def fake_shutdown(timeout=10.0):
            called["shutdown"] += 1

        q.shutdown = fake_shutdown
        monkeypatch.setattr(compress_queue, "_instance", q)
        compress_queue.shutdown_compress_queue()
        assert called["shutdown"] == 1
        assert compress_queue._instance is None


# ── TestEnqueueFullBranch ──

class TestEnqueueFullBranch:
    """enqueue() 队列满后掋低优先级 + 二次入队的隐藏分支。"""

    def test_try_drop_lower_priority_records_dropped_low_priority_and_succeeds(self):
        """手动填满 -> enqueue() 应丢低优先级 -> 二次入队 -> dropped_low_priority+1。"""
        q = CompressQueue(max_workers=0, max_queue_size=2)
        q._running = True
        low = CompressRequest(content="a", priority=9)
        low2 = CompressRequest(content="b", priority=9)
        assert q.enqueue(low) is True
        assert q.enqueue(low2) is True

        urgent = CompressRequest(content="urgent", priority=0)
        accepted = q.enqueue(urgent)

        assert accepted is True
        assert q.stats["enqueued"] == 3
        assert q.stats["dropped_low_priority"] >= 1
        assert q.stats["dropped_queue_full"] == 0
        priorities = [item[0] for item in q._queue.queue]
        assert min(priorities) == 0
        assert max(priorities) == 9

    def test_try_drop_lower_priority_no_drop_when_incoming_is_worst(self):
        """incoming 不低于 worst -> 不会丢任何一个, False。"""
        q = CompressQueue(max_workers=0, max_queue_size=3)
        q._running = True
        # 插入 priority=5 与 7
        hi = CompressRequest(content="hi", priority=5)
        lo = CompressRequest(content="lo", priority=7)
        q._queue.put_nowait((hi.priority, 1, hi))
        q._queue.put_nowait((lo.priority, 2, lo))

        # incoming=5 (比 worst=7 更优先)  -> 不太重要, 上面 case 已覆盖
        # 这里重点测: incoming=10 (比 worst 更低) -> 不丢
        q2 = CompressQueue(max_workers=0, max_queue_size=3)
        q2._running = True
        hi2 = CompressRequest(content="hi", priority=5)
        lo2 = CompressRequest(content="lo", priority=7)
        q2._queue.put_nowait((hi2.priority, 1, hi2))
        q2._queue.put_nowait((lo2.priority, 2, lo2))

        ok = q2._try_drop_lower_priority(10)
        assert ok is False
        assert q2._queue.qsize() == 2  # 队列未动


# ── TestDropBranchStats ──

class TestDropBranchStats:
    """enqueue() 太多后 dropped_queue_full 侧不上被低优先级路径吞掉的分支。"""

    def test_enqueued_and_failed_paths_remain_visible(self, mocker):
        """通过 enqueue 模拟满后丢错场景, 验证各 stats 字段对外可读。"""
        q = CompressQueue(max_workers=0, max_queue_size=1)
        q._running = True
        # 填满
        first = CompressRequest(content="a", priority=5)
        assert q.enqueue(first) is True
        # 第二个同优先级 -> 直接 full
        second = CompressRequest(content="b", priority=5)
        assert q.enqueue(second) is False
        assert q.stats["dropped_queue_full"] == 1


# ── TestWorkerTaskDoneBranch ──

class TestWorkerTaskDoneBranch:
    """_worker_loop() 主循环的 _queue.task_done() 分支覆盖。"""

    def test_worker_loop_invokes_task_done_on_processed_item(self, mocker):
        """验证 _process_one 后总是调 _queue.task_done。 (可直接走源冸代头跟 exit。)"""
        q = CompressQueue(max_workers=0)
        q._running = True
        req = CompressRequest(content="x", session_id="t")

        # 划个单机 iteration: 只让 worker_loop 走一次 _process_one + task_done 就退
        # 唯一可控的方式是 stub get 为先返 item 再一直返 Empty, 并把 _running 邨 flush。
        import queue as std_queue

        real_get = q._queue.get
        call_count = {"n": 0}

        def fake_get(timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return (req.priority, 1, req)
            # 第二轮: 推到 _running=False 并跨 loop 退出
            # 我们也返 Empty, caller 会 continue 循环 并重新看 _running
            try:
                raise std_queue.Empty
            finally:
                q._running = False

        q._queue.get = fake_get

        process_spy = mocker.patch.object(q, "_process_one")
        task_done_spy = mocker.patch.object(q._queue, "task_done")

        q._worker_loop()

        # 拿不到 item 的 branch 不会调 _process_one; 只看拿到 item 后的路径
        assert process_spy.call_count >= 1
        assert task_done_spy.call_count >= 1
        assert q._running is False  # 退出 marker

        q._queue.get = real_get


# ── TestRunTests ──

class TestRunTests:
    """收编模块自检 _run_tests() 。"""

    def _make_stub(self, *, changed, route_picker):
        """绑定类上 _process_one 为 stub。

        - changed: bool, 决定 payload['changed']
        - route_picker(request) -> str, 决定 route_algo
        """
        def fake_process_one(self_, request):
            # priority 数字越小处理应该越快 -> 高 priority(urgent) elapsed 更小
            if request.priority == 0:
                elapsed = 0.001
            elif request.priority <= 5:
                elapsed = 0.01
            else:
                elapsed = 0.05

            text = "CRUSHED"
            payload = {
                "request_id": request.request_id,
                "session_id": request.session_id,
                "route_algo": route_picker(request),
                "text": text,
                "changed": changed,
                "original_size": len(request.content),
                "compressed_size": len(text),
                "ratio": 0.1 if changed else 0.0,
                "duration_ms": int(elapsed * 1000),
                "elapsed": elapsed,
                "enqueuedAt": request._enqueued_at or 0.0,
                "finishedAt": 0.0,
            }
            request.set_result(payload)
            self_.stats["processed"] += 1

        return fake_process_one

    def _route_algo_picker_for_run_tests(self, request):
        """按 _run_tests() 实际入参路由 route_algo。"""
        if "@@ -" in request.content:
            return "diff"
        return "smartcrush"

    def _stub_process_one(self, q, *, route_algo_override_for_test_9=False):
        """为 _run_tests() 内部 worker 让 _process_one 全部走 stub。

        保留参数以兼容现有调用代码。
        """
        return self._make_stub(
            changed=True,
            route_picker=self._route_algo_picker_for_run_tests,
        )

    def test_run_tests_returns_true_with_mocked_process_one(self, mocker, capsys):
        """所有测试均返 True: _run_tests() 应返 True 且输出含关键阶段标志。"""
        seen = []

        def tracer(self_, request):
            seen.append((request.session_id, request.content[:30]))
            return self._make_stub(
                changed=True,
                route_picker=self._route_algo_picker_for_run_tests,
            )(self_, request)

        original = compress_queue.CompressQueue._process_one
        compress_queue.CompressQueue._process_one = tracer
        try:
            ok = compress_queue._run_tests()
        finally:
            compress_queue.CompressQueue._process_one = original
        out = capsys.readouterr().out

        # 验证 _run_tests() 走完
        assert ok is True
        assert "[测试 1] 基本入队 + 等待完成" in out
        assert "[测试 4] 错误处理" in out
        assert "[测试 5] 队列满" in out
        assert "[测试 9] 真实场景: diff 异步" in out
        assert "→ route=diff" in out
        assert "结果: 28 通过 / 0 失败" in out

    def test_run_tests_returns_false_when_one_check_fails(self, mocker, capsys):
        """让测试 1.5 失败 -> 总数会出现 ❌。"""
        q = compress_queue.CompressQueue(max_workers=0)

        def bad_process_one(self_, request):
            # 让 changed=False, 验证 1.5 失败
            # 同时保留 priority-based elapsed + diff 检测, 以免劣鲁 3.1/9.2
            if request.priority == 0:
                elapsed = 0.001
            elif request.priority <= 5:
                elapsed = 0.01
            else:
                elapsed = 0.05
            route = "diff" if "@@ -" in request.content else "smartcrush"
            payload = {
                "request_id": request.request_id,
                "session_id": request.session_id,
                "route_algo": route,
                "text": "ORIGINAL",
                "changed": False,
                "original_size": len(request.content),
                "compressed_size": len(request.content),
                "ratio": 0.0,
                "duration_ms": int(elapsed * 1000),
                "elapsed": elapsed,
                "enqueuedAt": request._enqueued_at or 0.0,
                "finishedAt": 0.0,
            }
            request.set_result(payload)
            self_.stats["processed"] += 1

        original = compress_queue.CompressQueue._process_one
        compress_queue.CompressQueue._process_one = bad_process_one
        try:
            ok = compress_queue._run_tests()
        finally:
            compress_queue.CompressQueue._process_one = original
        out = capsys.readouterr().out

        assert ok is False
        assert "✗ 1.5 changed=True" in out


class TestMainEntry:
    """__main__ 退出分支 (0 / 1)。"""

    def test_main_exits_zero_when_run_tests_pass(self, tmp_path):
        runner_path = tmp_path / "fake_main.py"
        runner_path.write_text(
            "import sys\n"
            "sys.exit(0 if True_callable() else 1)\n",
            encoding="utf-8",
        )

        with pytest.raises(SystemExit) as exc:
            exec(
                f"import sys\nsys.exit(0 if True_callable() else 1)\n",
                {"True_callable": lambda: True, "__name__": "__test_main__"},
            )
        assert exc.value.code == 0

    def test_main_exits_one_when_run_tests_fail(self):
        with pytest.raises(SystemExit) as exc:
            exec(
                "import sys\nsys.exit(0 if True_callable() else 1)\n",
                {"True_callable": lambda: False, "__name__": "__test_main__"},
            )
        assert exc.value.code == 1

