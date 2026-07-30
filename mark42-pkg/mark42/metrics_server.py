"""Prometheus HTTP 端点暴露。

用 Python 标准库 http.server 实现，不引入第三方依赖。
监听 127.0.0.1:9100（可配置），/metrics 返回 Prometheus 格式指标。
"""

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logger = logging.getLogger("mark42.metrics_server")


def _collect_metrics() -> str:
    """收集 Prometheus 格式指标文本。

    复用 cli.py 中 _print_metrics() 的逻辑，但返回字符串而非打印到 stdout。
    """
    from .armor import armor_check, armor_llm_stats
    from .circuit_breaker import CircuitBreaker
    from .engine import _load_loops

    lines = []

    # ── 上下文使用率 ──
    try:
        check = armor_check()
        lines.append("# HELP mark42_context_usage_percent Context usage percentage.")
        lines.append("# TYPE mark42_context_usage_percent gauge")
        lines.append(f'mark42_context_usage_percent {check.get("usagePercent", 0)}')
        lines.append('mark42_context_severity 1')
        lines.append(f'mark42_context_window_tokens {check.get("contextWindow", 0)}')
        lines.append(f'mark42_context_estimated_tokens {check.get("estimatedTokens", 0)}')
    except Exception as e:
        lines.append(f'# armor_check error: {e}')

    # ── LLM 压缩统计 ──
    try:
        stats = armor_llm_stats()
        lines.append("# HELP mark42_compress_total Total compression operations.")
        lines.append("# TYPE mark42_compress_total counter")
        lines.append(f'mark42_compress_total {stats.get("total", 0)}')
        lines.append(f'mark42_compress_llm_success {stats.get("llmSuccess", 0)}')
        lines.append(f'mark42_compress_fallback {stats.get("fallback", 0)}')
        lines.append(f'mark42_compress_errors {stats.get("errors", 0)}')
        lines.append(f'mark42_compress_llm_rate_percent {stats.get("llmRate", 0)}')
        lines.append(f'mark42_compress_fallback_rate_percent {stats.get("fallbackRate", 0)}')
        slo = 1 if stats.get("sloBreached") else 0
        lines.append(f'mark42_compress_slo_breached {slo}')
    except Exception as e:
        lines.append(f'# llm_stats error: {e}')

    # ── Loop 状态 ──
    try:
        loops = _load_loops()
        active = sum(1 for l in loops.values() if l.get("status") == "registered")
        total = len(loops)
        lines.append("# HELP mark42_engine_loops_active Active engine loops.")
        lines.append("# TYPE mark42_engine_loops_active gauge")
        lines.append(f'mark42_engine_loops_active {active}')
        lines.append(f'mark42_engine_loops_total {total}')
        for name, loop in loops.items():
            cycle = loop.get("cycle", 0)
            lines.append(f'mark42_engine_loop_cycle{{loop="{name}"}} {cycle}')
    except Exception as e:
        lines.append(f'# engine error: {e}')

    # ── 熔断器状态 ──
    try:
        cb = CircuitBreaker()
        breaker_states = cb.list_all()
        open_count = sum(1 for b in breaker_states if b.get("status") == "open")
        half_open = sum(1 for b in breaker_states if b.get("status") == "half_open")
        lines.append("# HELP mark42_breakers_open Number of open circuit breakers.")
        lines.append("# TYPE mark42_breakers_open gauge")
        lines.append(f'mark42_breakers_open {open_count}')
        lines.append(f'mark42_breakers_half_open {half_open}')
    except Exception as e:
        lines.append(f'# breaker error: {e}')

    return "\n".join(lines) + "\n"


class _MetricsHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器。"""

    def do_GET(self):
        if self.path == "/metrics":
            body = _collect_metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            body = b"OK\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, format, *args):
        # 静默默认日志，改用 logger
        logger.debug("HTTP %s %s", self.address_string(), format % args)


class MetricsServer:
    """Prometheus 指标 HTTP 服务。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 9100):
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """启动 HTTP 服务（阻塞）。"""
        logger.info("Metrics server starting on %s:%d", self.host, self.port)
        self._server = ThreadingHTTPServer((self.host, self.port), _MetricsHandler)
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Metrics server interrupted, shutting down")
        finally:
            self._server.server_close()

    def start_background(self):
        """在后台线程启动（非阻塞）。"""
        self._server = ThreadingHTTPServer((self.host, self.port), _MetricsHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="mark42-metrics-server",
            daemon=True,
        )
        self._thread.start()
        logger.info("Metrics server started in background on %s:%d", self.host, self.port)

    def stop(self):
        """停止服务。"""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            if self._thread:
                self._thread.join(timeout=5)
            logger.info("Metrics server stopped")


def run_server(port: int = 9100, host: str = "127.0.0.1"):
    """CLI 入口：启动 metrics server。"""
    server = MetricsServer(host=host, port=port)
    server.start()
