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

import queue as std_queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field

from .log_setup import get_logger

log = get_logger(__name__)


QUEUE_POLL_TIMEOUT = 0.05


@dataclass
class CompressRequest:
    """压缩请求封装"""

    content: str
    session_id: str = "unknown"
    content_type: str = "auto"  # auto | json | code | diff | log | text
    priority: int = 0  # 0=normal, 1=urgent, 2=low (数值小优先级高)
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
            self.stats["active_workers"] = sum(1 for w in self._workers if w.is_alive())
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
                log.debug(
                    f"processed {request.request_id} LLM({mode}) "
                    f"status={payload['status']} ratio={payload['ratio']:.1%}"
                )
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
            log.debug(f"processed {request.request_id} route={payload['route_algo']} ratio={payload['ratio']:.1%}")
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
    """运行测试（已提取到 tests/test_compress_queue.py）。"""
    from tests.test_compress_queue import run_tests

    return run_tests()


if __name__ == "__main__":
    # 配置 logging 让错误可见
    import logging
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    sys.exit(0 if _run_tests() else 1)
