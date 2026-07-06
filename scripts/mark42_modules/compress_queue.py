"""Mark42 异步压缩队列（Day 7 - 压缩子系统异步化改造）

设计文档:
- 开发手册: docs/design/mark42-开发手册-压缩子系统.md (5.x 节)
- 设计目标: armor_compress 同步阻塞 → 后台 worker 处理

设计取舍:
- OpenClaw engine daemon 是同步 while+sleep 循环, 非 asyncio
- 本模块用 threading + queue.Queue 实现 (轻、与 sync daemon 兼容)
- 提供 asyncio-style API (enqueue / start / shutdown) 但底层是线程
- 未来 OpenClaw 升级为 asyncio 时, 本模块可直接迁移

接口:
  CompressRequest: 数据封装
  CompressQueue: 队列 + worker pool
    - enqueue(req) -> bool  非阻塞
    - start() -> None         启动 worker
    - shutdown(timeout=10) -> None
    - get_result(req_id, timeout=None) -> dict | None  同步等待
  get_compress_queue() -> CompressQueue  单例
  armor_compress_async() -> dict        armor.py 异步入口 (包装 enqueue)

创建日期: 2026-06-25 07:42
"""

import logging
import queue as std_queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any


log = logging.getLogger("mark42.compress_queue")


QUEUE_POLL_TIMEOUT = 0.05


@dataclass
class CompressRequest:
    """压缩请求封装"""
    content: str
    session_id: str = "unknown"
    content_type: str = "auto"          # auto | json | code | diff | log | text
    priority: int = 0                    # 0=normal, 1=urgent, 2=low (数值小优先级高)
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:8]}")
    created_at: float = field(default_factory=time.time)
    # 【M 修复 2026-06-30】加 _enqueued_at: 记录该 request 实际入队时间戳
    # 原 created_at 是创建时间, 不等于入队时间
    # 测试 3 (优先级) 用这个字段才能真验证 "urgent 先于 low" (需 enqueue 后 priority 高者先出)
    _enqueued_at: float | None = field(default=None, init=False, repr=False)
    # 结果回调
    _result: dict | None = field(default=None, init=False, repr=False)
    _result_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _error: str | None = field(default=None, init=False, repr=False)

    def set_result(self, result: dict) -> None:
        self._result = result
        self._result_event.set()

    def set_error(self, error: str) -> None:
        self._error = error
        self._result_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """等待处理完成. True=完成, False=超时"""
        return self._result_event.wait(timeout=timeout)

    @property
    def result(self) -> dict | None:
        return self._result

    @property
    def error(self) -> str | None:
        return self._error


class CompressQueue:
    """异步压缩队列 (线程实现)"""

    def __init__(self, max_workers: int = 2, max_queue_size: int = 100):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        # 优先级队列: 元组 (priority, seq, request)  保证 FIFO 同优先级
        self._queue: std_queue.PriorityQueue = std_queue.PriorityQueue(maxsize=max_queue_size)
        self._workers: list[threading.Thread] = []
        self._running = False
        self._lock = threading.Lock()
        self._seq = 0
        # 统计
        self.stats = {
            "enqueued": 0,
            "processed": 0,
            "failed": 0,
            "dropped_queue_full": 0,
            "dropped_low_priority": 0,
            "active_workers": 0,
        }

    def start(self) -> None:
        """启动 worker 线程池"""
        with self._lock:
            if self._running:
                return
            self._running = True
            for i in range(self.max_workers):
                t = threading.Thread(
                    target=self._worker_loop,
                    name=f"compress-worker-{i}",
                    daemon=True,  # daemon=True 让主程序退出时自动 kill
                )
                t.start()
                self._workers.append(t)
            log.info(f"compress queue started with {self.max_workers} workers")

    def shutdown(self, timeout: float = 10.0) -> None:
        """关闭队列 (等待 in-flight 完成)"""
        with self._lock:
            if not self._running:
                return
            self._running = False
        # 等所有 worker 退出
        deadline = time.time() + timeout
        for w in self._workers:
            remaining = max(0.1, deadline - time.time())
            w.join(timeout=remaining)
        self._workers.clear()
        log.info("compress queue shutdown complete")

    def enqueue(self, request: CompressRequest) -> bool:
        """非阻塞入队. 成功返回 True, 队列满返回 False"""
        if not self._running:
            log.warning("enqueue called but queue not started; auto-starting")
            self.start()
        with self._lock:
            self._seq += 1
            seq = self._seq
        # 优先级队列: (priority, seq, request)
        item = (request.priority, seq, request)
        # 【M 修复 2026-06-30】记入队时间戳, 供测试 3 验证 priority 真的影响处理顺序
        request._enqueued_at = time.time()
        try:
            self._queue.put_nowait(item)
            self.stats["enqueued"] += 1
            return True
        except std_queue.Full:
            # 队列满: 尝试丢弃一个最低优先级 (若 request 本身优先级更高)
            if self._try_drop_lower_priority(request.priority):
                try:
                    self._queue.put_nowait(item)
                    self.stats["enqueued"] += 1
                    self.stats["dropped_low_priority"] += 1
                    return True
                except std_queue.Full:
                    pass
            self.stats["dropped_queue_full"] += 1
            log.warning(f"queue full, dropped request {request.request_id}")
            return False

    def _try_drop_lower_priority(self, incoming_priority: int) -> bool:
        """尝试丢弃一个比 incoming_priority 低的元素"""
        with self._queue.mutex:
            # 找到优先级最低 (数字最大) 的元素
            items = list(self._queue.queue)
            if not items:
                return False
            worst = max(items, key=lambda x: x[0])  # priority 数字最大 = 最低
            if worst[0] > incoming_priority:
                # 真有比 incoming 更低优先级的, 移除它
                try:
                    self._queue.queue.remove(worst)
                    return True
                except ValueError:
                    return False
            return False

    def _worker_loop(self) -> None:
        """worker 主循环"""
        while self._running:
            try:
                item = self._queue.get(timeout=QUEUE_POLL_TIMEOUT)
            except std_queue.Empty:
                continue
            if item is None:  # poison pill
                break
            _, _, request = item
            self._process_one(request)
            self._queue.task_done()

    def _process_one(self, request: CompressRequest) -> None:
        """处理单个请求 (带 try/except 防护)"""
        with self._lock:
            self.stats["active_workers"] = sum(
                1 for w in self._workers if w.is_alive()
            )
        t0 = time.time()
        try:
            # Phase 2 目标 1: content_type="llm:..." 走 LLM 压缩
            if request.content_type.startswith("llm:"):
                mode = request.content_type.split(":", 1)[1]
                try:
                    from llm_text_compressor import llm_text_compress
                except ImportError:
                    from .llm_text_compressor import llm_text_compress
                text_result, llm_stats = llm_text_compress(request.content, mode=mode)
                # 把 llm_stats 转成统一格式
                payload = {
                    "request_id": request.request_id,
                    "session_id": request.session_id,
                    "route_algo": "llm",
                    "llm_mode": mode,
                    "text": text_result,
                    "status": llm_stats.get("status", "unknown"),
                    "original_size": llm_stats.get("original_bytes", len(request.content)),
                    "compressed_size": llm_stats.get("crushed_bytes", len(text_result.encode("utf-8"))),
                    "ratio": llm_stats.get("ratio", 0.0),
                    "duration_ms": int((time.time() - t0) * 1000),
                    "elapsed": time.time() - t0,
                    "enqueuedAt": request._enqueued_at,  # 【M】入队时间
                    "finishedAt": time.time(),  # 【M】实际完成时间
                }
                request.set_result(payload)
                self.stats["processed"] += 1
                log.debug(f"processed {request.request_id} LLM({mode}) "
                          f"status={payload['status']} ratio={payload['ratio']:.1%}")
                return

            # 默认: 走 algo_scheduler 智能路由
            try:
                from algo_scheduler import process
            except ImportError:
                from .algo_scheduler import process
            result = process(request.content)
            # 把 result 转成 dict 序列化
            payload = {
                "request_id": request.request_id,
                "session_id": request.session_id,
                "route_algo": result["decision"].route_algo,
                "text": result.get("result", ""),
                "changed": result.get("changed", False),
                "original_size": result.get("original_size", len(request.content)),
                "compressed_size": result.get("compressed_size", len(result.get("result", ""))),
                "ratio": result.get("compress_stats", {}).get("ratio", 0.0) if result.get("compress_stats") else 0.0,
                "duration_ms": int((time.time() - t0) * 1000),
                "elapsed": time.time() - t0,
                "enqueuedAt": request._enqueued_at,  # 【M】入队时间
                "finishedAt": time.time(),  # 【M】实际完成时间 = 测试判定依据
            }
            request.set_result(payload)
            self.stats["processed"] += 1
            log.debug(f"processed {request.request_id} route={payload['route_algo']} "
                      f"ratio={payload['ratio']:.1%}")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            request.set_error(err)
            self.stats["failed"] += 1
            log.error(f"failed {request.request_id}: {err}\n{traceback.format_exc()}")

    def get_result(self, request_id: str, timeout: float | None = None) -> dict | None:
        """通过 request_id 找请求并等待结果 (实验性, 简单遍历)"""
        # PriorityQueue 不支持按 id 找, 这里用最简单方式: 等入队的 request
        # 调用方一般会保存 request 对象, 用 request.wait() 即可
        # 此方法仅供 fallback
        raise NotImplementedError("use request.wait() instead")

    def qsize(self) -> int:
        return self._queue.qsize()


# 全局单例
_instance: CompressQueue | None = None
_instance_lock = threading.Lock()


def get_compress_queue(max_workers: int = 2, max_queue_size: int = 100) -> CompressQueue:
    """获取全局单例 (懒启动)"""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = CompressQueue(max_workers=max_workers, max_queue_size=max_queue_size)
            _instance.start()
        return _instance


def shutdown_compress_queue() -> None:
    """关闭全局队列 (测试用)"""
    global _instance
    with _instance_lock:
        if _instance is not None:
            _instance.shutdown()
            _instance = None


# ----------------------------------------------------------------------
# 自检 / 烟测
# ----------------------------------------------------------------------
def _run_tests() -> bool:
    import json as _json
    passed = 0
    failed = 0

    def check(name: str, cond: bool):
        nonlocal passed, failed
        if cond:
            print(f"  ✓ {name}")
            passed += 1
        else:
            print(f"  ✗ {name}")
            failed += 1

    # ---- 测试 1: 基本入队 + 处理 ----
    print("\n[测试 1] 基本入队 + 等待完成")
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
    print(f"  → route={req.result['route_algo']} ratio={req.result['ratio']:.1%} "
          f"elapsed={req.result['elapsed']:.2f}s")
    q.shutdown()

    # ---- 测试 2: 多 worker 并发 ----
    print("\n[测试 2] 多 worker 并发处理 10 个请求")
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
    print("\n[测试 3] 优先级队列")
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
    print("\n[测试 4] 错误处理")
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
    print("\n[测试 5] 队列满 (max=3) — 不启 worker 模拟积压")
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
    print("\n[测试 6] 单例")
    a = get_compress_queue()
    b = get_compress_queue()
    check("6.1 get_compress_queue 返回单例", a is b)
    check("6.2 单例已启动", a._running is True)
    # 不 shutdown, 留给进程退出 (daemon=True 会自动清理)

    # ---- 测试 7: shutdown 后入队 ----
    print("\n[测试 7] shutdown 安全性")
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
    print("\n[测试 8] stats 准确")
    q8 = CompressQueue(max_workers=2)
    q8.start()
    n_ok = 5
    reqs = [CompressRequest(content=_json.dumps({"i": i, "v": "x" * 30}))
            for i in range(n_ok)]
    for r in reqs:
        q8.enqueue(r)
    for r in reqs:
        r.wait(timeout=10.0)
    check(f"8.1 enqueued={n_ok}", q8.stats["enqueued"] == n_ok)
    check(f"8.2 processed={n_ok}", q8.stats["processed"] == n_ok)
    check("8.3 failed=0", q8.stats["failed"] == 0)
    q8.shutdown()

    # ---- 测试 9: 真实 diff 走异步 ----
    print("\n[测试 9] 真实场景: diff 异步")
    q9 = CompressQueue(max_workers=2)
    q9.start()
    diff_content = "@@ -1,50 +1,50 @@\n" + "\n".join(f" line{i}" for i in range(50)) + "\n-old\n+new\n" * 3
    r = CompressRequest(content=diff_content, session_id="real-diff")
    q9.enqueue(r)
    r.wait(timeout=10.0)
    check("9.1 diff 异步处理", r.result is not None)
    check("9.2 route_algo=diff", r.result["route_algo"] == "diff")
    print(f"  → route={r.result['route_algo']} ratio={r.result['ratio']:.1%}")
    q9.shutdown()

    print()
    print("=" * 60)
    print(f"结果: {passed} 通过 / {failed} 失败")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    import sys
    # 配置 logging 让错误可见
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    sys.exit(0 if _run_tests() else 1)
