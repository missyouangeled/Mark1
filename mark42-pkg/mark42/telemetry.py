"""Mark42 可观测性模块（OpenTelemetry + Prometheus）。

【2026-08-03 新增】

## 设计原则（重要，改这个文件前必读）

Mark42 的核心卖点之一是 **零第三方依赖**（pyproject.toml 的 dependencies 是空的）。
接入可观测性不能破坏这一点，所以本模块遵循三条铁律：

1. **可选依赖**：opentelemetry / prometheus_client 没装时，本模块所有 API 仍可正常调用，
   只是退化成空操作（no-op）。绝不因为缺少监控库而让 Mark42 跑不起来。
2. **默认关闭**：即使装了库，也必须显式设置环境变量才会真正采集。
   守护进程默认行为不变，不会凭空多出网络请求。
3. **绝不抛异常**：监控是辅助设施。采集失败必须静默降级，
   不允许因为"记录指标失败"而中断压缩、Loop 执行等主业务。

## 启用方式

```bash
# 启用 Prometheus 指标（在 :9464 暴露 /metrics）
export MARK42_METRICS_ENABLED=1
export MARK42_METRICS_PORT=9464

# 启用 OTel 链路追踪（需要一个 OTLP 接收端，如本地 Jaeger）
export MARK42_TRACING_ENABLED=1
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

## 指标命名规范

遵循 Prometheus 官方实践（https://prometheus.io/docs/practices/naming/）：
- 统一 `mark42_` 前缀
- 时间用 `_seconds`，字节用 `_bytes`，累计计数用 `_total`
- **禁止**把 session_id / task_id / 用户标识作为标签（高基数会打爆存储）
"""

from __future__ import annotations

import functools
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# ── 开关 ──────────────────────────────────────────────────


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


TRACING_ENABLED = _env_flag("MARK42_TRACING_ENABLED")
METRICS_ENABLED = _env_flag("MARK42_METRICS_ENABLED")


def _env_port(name: str, default: int = 9464) -> int:
    """解析端口环境变量。非法值降级为默认值，绝不在 import 阶段报错。"""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        port = int(raw.strip())
    except ValueError:
        logger.warning("%s=%r 不是合法端口，降级为 %d", name, raw, default)
        return default
    if not (1 <= port <= 65535):
        logger.warning("%s=%d 超出有效端口范围，降级为 %d", name, port, default)
        return default
    return port


METRICS_PORT = _env_port("MARK42_METRICS_PORT")
SERVICE_NAME = os.environ.get("MARK42_OTEL_SERVICE_NAME", "mark42")

# ── 依赖探测（缺失即降级，不报错） ────────────────────────

_tracer: Any = None
_metrics: dict[str, Any] = {}
_prom_started = False


def _get_version_safe() -> str:
    try:
        from .config import get_version

        return get_version()
    except Exception:
        return "unknown"


def _init_tracing() -> Any:
    """初始化 OTel tracer。失败或未启用时返回 None（调用方走 no-op 分支）。"""
    if not TRACING_ENABLED:
        return None
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {"service.name": SERVICE_NAME, "service.version": _get_version_safe()}
        )
        provider = TracerProvider(resource=resource)

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        except Exception as e:
            # 没有 exporter 也能继续：span 仍会被创建，只是不外发
            logger.debug("OTLP exporter 初始化失败，仅本地创建 span: %s", e)

        trace.set_tracer_provider(provider)
        logger.info("Mark42 链路追踪已启用 (service=%s)", SERVICE_NAME)
        return trace.get_tracer("mark42")
    except ImportError:
        logger.debug("opentelemetry 未安装，链路追踪降级为空操作")
        return None
    except Exception as e:
        logger.warning("链路追踪初始化失败，降级为空操作: %s", e)
        return None


def _init_metrics() -> dict[str, Any]:
    """初始化 Prometheus 指标。失败或未启用时返回空字典。"""
    global _prom_started
    if not METRICS_ENABLED:
        return {}
    try:
        from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

        m: dict[str, Any] = {
            # Loop 执行
            "loop_runs": Counter(
                "mark42_loop_runs_total",
                "Loop 执行次数",
                ["loop_type", "status"],
            ),
            "loop_duration": Histogram(
                "mark42_loop_duration_seconds",
                "Loop 单次执行耗时",
                ["loop_type"],
            ),
            # 上下文压缩
            "compress_runs": Counter(
                "mark42_context_compression_total",
                "上下文压缩执行次数",
                ["strategy", "status"],
            ),
            "compress_duration": Histogram(
                "mark42_context_compression_duration_seconds",
                "上下文压缩耗时",
                ["strategy"],
            ),
            "compress_ratio": Gauge(
                "mark42_context_compression_ratio",
                "最近一次压缩比（压缩后/压缩前）",
                ["strategy"],
            ),
            # 上下文水位
            "context_usage": Gauge(
                "mark42_context_usage_percent",
                "当前上下文使用率百分比",
            ),
            # 审计
            "audit_violations": Counter(
                "mark42_audit_violations_total",
                "审计发现的问题数",
                ["category"],
            ),
            # 构建信息
            "build_info": Info("mark42_build", "Mark42 构建信息"),
        }
        m["build_info"].info(
            {"version": _get_version_safe(), "service_name": SERVICE_NAME}
        )

        if not _prom_started:
            start_http_server(METRICS_PORT)
            _prom_started = True
            logger.info("Mark42 Prometheus 指标已启用 (端口 %s)", METRICS_PORT)
        return m
    except ImportError:
        logger.debug("prometheus_client 未安装，指标采集降级为空操作")
        return {}
    except Exception as e:
        logger.warning("指标初始化失败，降级为空操作: %s", e)
        return {}


def init_telemetry() -> None:
    """初始化可观测性。daemon 启动时调用一次即可，重复调用安全。"""
    global _tracer, _metrics
    if _tracer is None:
        _tracer = _init_tracing()
    if not _metrics:
        _metrics = _init_metrics()


def is_enabled() -> bool:
    """是否有任一采集通道真正生效（供 status 面板展示）。"""
    return _tracer is not None or bool(_metrics)


def telemetry_status() -> dict[str, Any]:
    """返回可观测性当前状态，供 mark42 status 展示。"""
    tracing_lib = _probe_import("opentelemetry")
    metrics_lib = _probe_import("prometheus_client")
    return {
        "tracingEnabled": TRACING_ENABLED,
        "tracingActive": _tracer is not None,
        "tracingLibInstalled": tracing_lib,
        "metricsEnabled": METRICS_ENABLED,
        "metricsActive": bool(_metrics),
        "metricsLibInstalled": metrics_lib,
        "metricsPort": METRICS_PORT if _metrics else None,
        "serviceName": SERVICE_NAME,
    }


def _probe_import(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


# ── 采集 API（全部保证不抛异常） ──────────────────────────


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[None]:
    """创建一个 span。未启用时是零开销的空上下文。

    用法：
        with span("armor.compress", strategy="llm"):
            ...

    约定：telemetry 自身失败只降级并记 debug 日志，
    但业务异常必须原样向外传播，绝不能被吞掉或替换。
    """
    if _tracer is None:
        yield
        return

    # 阶段 1：创建 span。失败则退化为无追踪，但业务照常执行。
    cm = None
    span_obj = None
    try:
        cm = _tracer.start_as_current_span(name)
        span_obj = cm.__enter__()
    except Exception as e:
        logger.debug("span %s 创建失败: %s", name, e)
        cm = None
        span_obj = None

    if cm is None:
        yield
        return

    # 阶段 2：设置属性，失败不影响业务。
    if span_obj is not None:
        for k, v in attributes.items():
            try:
                span_obj.set_attribute(k, v)
            except Exception as e:
                logger.debug("span %s 属性 %s 设置失败: %s", name, k, e)

    # 阶段 3：执行业务。业务异常必须原样抛出。
    try:
        yield
    except BaseException as exc:
        try:
            suppressed = cm.__exit__(type(exc), exc, exc.__traceback__)
        except Exception as e:
            # span 关闭失败不得替换业务异常
            logger.debug("span %s 关闭失败: %s", name, e)
            suppressed = False
        if not suppressed:
            raise
        return

    # 阶段 4：正常结束时关闭 span，关闭失败只降级。
    try:
        cm.__exit__(None, None, None)
    except Exception as e:
        logger.debug("span %s 关闭失败: %s", name, e)


def record_loop_run(loop_type: str, status: str, duration_s: float | None = None) -> None:
    """记录一次 Loop 执行。"""
    if not _metrics:
        return
    try:
        _metrics["loop_runs"].labels(loop_type=loop_type, status=status).inc()
        if duration_s is not None:
            _metrics["loop_duration"].labels(loop_type=loop_type).observe(duration_s)
    except Exception as e:
        logger.debug("记录 loop 指标失败: %s", e)


def record_compression(
    strategy: str,
    status: str,
    duration_s: float | None = None,
    ratio: float | None = None,
) -> None:
    """记录一次上下文压缩。"""
    if not _metrics:
        return
    try:
        _metrics["compress_runs"].labels(strategy=strategy, status=status).inc()
        if duration_s is not None:
            _metrics["compress_duration"].labels(strategy=strategy).observe(duration_s)
        if ratio is not None:
            _metrics["compress_ratio"].labels(strategy=strategy).set(ratio)
    except Exception as e:
        logger.debug("记录压缩指标失败: %s", e)


def record_context_usage(percent: float) -> None:
    """记录当前上下文使用率。"""
    if not _metrics:
        return
    try:
        _metrics["context_usage"].set(percent)
    except Exception as e:
        logger.debug("记录上下文水位失败: %s", e)


def record_audit_violation(category: str, count: int = 1) -> None:
    """记录审计发现的问题。"""
    if not _metrics:
        return
    try:
        _metrics["audit_violations"].labels(category=category).inc(count)
    except Exception as e:
        logger.debug("记录审计指标失败: %s", e)


def timed(metric_fn: Callable[..., None], **labels: Any) -> Callable[[F], F]:
    """装饰器：自动记录函数耗时。

    用法：
        @timed(record_loop_run, loop_type="health-watch")
        def run_health_watch(): ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            status = "ok"
            try:
                return func(*args, **kwargs)
            except Exception:
                status = "error"
                raise
            finally:
                try:
                    metric_fn(
                        status=status, duration_s=time.monotonic() - start, **labels
                    )
                except Exception as e:
                    # 指标记录失败绝不能影响业务函数的返回/异常传递
                    logger.debug("记录耗时指标失败 (%s): %s", func.__name__, e)

        return wrapper  # type: ignore[return-value]

    return decorator
