"""可观测性模块（telemetry）测试。

【2026-08-03 新增】核心验证目标不是"指标数字对不对"，而是三条铁律：
1. 依赖缺失时必须降级为空操作，绝不让 Mark42 起不来
2. 默认关闭，不显式开启就不采集
3. 采集失败绝不抛异常，不能影响压缩/Loop 等主业务
"""

import os
import site
import subprocess
import sys
from pathlib import Path

import pytest

from mark42 import telemetry as t

PKG_ROOT = str(Path(__file__).resolve().parent.parent)


def _subprocess_env():
    """构造子进程环境。

    conftest 的隔离 fixture 会把 HOME 改到 tmp 目录，导致子进程丢失
    ~/.local/lib/.../site-packages，进而误报"prometheus_client 未安装"并跳过测试。
    这里把真实的 site-packages 显式注入 PYTHONPATH，保证子进程能看到已装的可选依赖。
    """
    env = dict(os.environ)
    paths = [p for p in site.getsitepackages() if p]
    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        paths.append(user_site)
    else:  # pragma: no cover
        paths.extend(user_site)
    paths.append(PKG_ROOT)
    existing = env.get("PYTHONPATH", "")
    if existing:
        paths.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


# ── 铁律 1：默认关闭 ──────────────────────────────────────


class TestDefaultOff:
    def test_disabled_by_default(self):
        """不设环境变量时不得启用采集。"""
        assert t._env_flag("MARK42_TRACING_ENABLED") is False
        assert t._env_flag("MARK42_METRICS_ENABLED") is False

    def test_env_flag_parsing(self):
        for truthy in ("1", "true", "TRUE", "yes", "on"):
            os.environ["_M42_TEST_FLAG"] = truthy
            assert t._env_flag("_M42_TEST_FLAG") is True
        for falsy in ("0", "false", "no", "off", ""):
            os.environ["_M42_TEST_FLAG"] = falsy
            assert t._env_flag("_M42_TEST_FLAG") is False
        del os.environ["_M42_TEST_FLAG"]

    def test_status_reports_disabled(self):
        st = t.telemetry_status()
        assert st["tracingEnabled"] is False
        assert st["metricsEnabled"] is False
        assert st["metricsPort"] is None


# ── 铁律 2 + 3：所有 API 在未启用时安全可调 ────────────────


class TestNoOpSafety:
    def test_span_is_safe_when_disabled(self):
        with t.span("test.operation", attr1="v", attr2=42):
            pass  # 不抛异常即通过

    def test_span_yields_even_on_internal_error(self):
        """span 内部出错也必须把控制权交回业务代码。"""
        executed = []
        with t.span("test.op"):
            executed.append(True)
        assert executed == [True]

    def test_span_does_not_swallow_business_exception(self):
        """监控不能吞掉业务异常——那会掩盖真问题。"""
        with pytest.raises(ValueError, match="业务错误"):
            with t.span("test.op"):
                raise ValueError("业务错误")

    @pytest.mark.parametrize(
        "call",
        [
            lambda: t.record_loop_run("health-watch", "ok", 1.0),
            lambda: t.record_loop_run("x", "error"),
            lambda: t.record_compression("llm", "ok", 2.0, 0.5),
            lambda: t.record_compression("fallback", "error"),
            lambda: t.record_context_usage(9.4),
            lambda: t.record_context_usage(0),
            lambda: t.record_audit_violation("identity"),
            lambda: t.record_audit_violation("projects", 5),
        ],
    )
    def test_all_record_apis_safe_when_disabled(self, call):
        call()  # 不抛异常即通过

    def test_record_with_garbage_input_does_not_raise(self):
        """脏输入也不能炸——监控代码不该成为新的故障源。"""
        t.record_loop_run(None, None, None)  # type: ignore[arg-type]
        t.record_context_usage("not-a-number")  # type: ignore[arg-type]
        t.record_audit_violation(None)  # type: ignore[arg-type]


# ── 铁律 1：依赖缺失时降级 ────────────────────────────────


class TestGracefulDegradation:
    def test_import_works_without_otel_installed(self):
        """模拟 opentelemetry / prometheus_client 完全不存在。

        这是最关键的一条：Mark42 声称零依赖，装不装监控库都必须能跑。
        """
        code = f"""
import sys
sys.path.insert(0, {PKG_ROOT!r})

# 屏蔽两个可选依赖，模拟未安装环境
import builtins
_real_import = builtins.__import__
def _blocked(name, *a, **kw):
    if name.split('.')[0] in ('opentelemetry', 'prometheus_client'):
        raise ImportError(f'模拟未安装: {{name}}')
    return _real_import(name, *a, **kw)
builtins.__import__ = _blocked

import os
os.environ['MARK42_TRACING_ENABLED'] = '1'
os.environ['MARK42_METRICS_ENABLED'] = '1'

from mark42 import telemetry as t
t.init_telemetry()
assert t.is_enabled() is False, '依赖缺失时不该报告为已启用'

# 即使显式开启，所有 API 也必须安全
with t.span('x', a=1):
    pass
t.record_loop_run('l', 'ok', 1.0)
t.record_compression('s', 'ok', 1.0, 0.5)
t.record_context_usage(50.0)
t.record_audit_violation('c')
st = t.telemetry_status()
assert st['tracingLibInstalled'] is False
assert st['metricsLibInstalled'] is False
print('DEGRADE_OK')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=90
        )
        assert "DEGRADE_OK" in proc.stdout, f"stdout={proc.stdout} stderr={proc.stderr}"

    def test_mark42_core_imports_without_monitoring_libs(self):
        """核心模块导入链不能因为缺监控库而断。"""
        code = f"""
import sys
sys.path.insert(0, {PKG_ROOT!r})
import builtins
_real = builtins.__import__
def _blocked(name, *a, **kw):
    if name.split('.')[0] in ('opentelemetry', 'prometheus_client'):
        raise ImportError('blocked')
    return _real(name, *a, **kw)
builtins.__import__ = _blocked

import mark42.config, mark42.utils, mark42.telemetry, mark42.cli.status
print('CORE_IMPORT_OK')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=90
        )
        assert "CORE_IMPORT_OK" in proc.stdout, f"stderr={proc.stderr}"


# ── 真实采集验证 ──────────────────────────────────────────


class TestRealCollection:
    def test_prometheus_metrics_actually_exposed(self):
        """启用后必须真的能在 HTTP 端点抓到 mark42_ 指标。"""
        code = f"""
import sys, os, time, urllib.request
sys.path.insert(0, {PKG_ROOT!r})
os.environ['MARK42_METRICS_ENABLED'] = '1'
os.environ['MARK42_METRICS_PORT'] = '9473'
from mark42 import telemetry as t
t.init_telemetry()
if not t.is_enabled():
    print('SKIP_NO_LIB')
    sys.exit(0)
t.record_loop_run('health-watch', 'ok', 1.5)
t.record_compression('llm-analyze', 'ok', 2.4, 0.37)
t.record_context_usage(9.4)
t.record_audit_violation('identity')
time.sleep(0.5)
body = urllib.request.urlopen('http://127.0.0.1:9473/metrics', timeout=5).read().decode()
required = [
    'mark42_loop_runs_total',
    'mark42_loop_duration_seconds',
    'mark42_context_compression_total',
    'mark42_context_compression_ratio',
    'mark42_context_usage_percent',
    'mark42_audit_violations_total',
    'mark42_build_info',
]
missing = [m for m in required if m not in body]
assert not missing, f'缺少指标: {{missing}}'
print('METRICS_OK')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        out = proc.stdout
        if "SKIP_NO_LIB" in out:
            pytest.skip("prometheus_client 未安装")
        assert "METRICS_OK" in out, f"stdout={out} stderr={proc.stderr}"

    def test_metric_names_follow_prometheus_convention(self):
        """指标命名必须符合 Prometheus 官方规范。"""
        code = f"""
import sys, os, time, urllib.request
sys.path.insert(0, {PKG_ROOT!r})
os.environ['MARK42_METRICS_ENABLED'] = '1'
os.environ['MARK42_METRICS_PORT'] = '9474'
from mark42 import telemetry as t
t.init_telemetry()
if not t.is_enabled():
    print('SKIP_NO_LIB')
    sys.exit(0)
t.record_loop_run('l', 'ok', 1.0)
time.sleep(0.4)
body = urllib.request.urlopen('http://127.0.0.1:9474/metrics', timeout=5).read().decode()
names = set()
for line in body.splitlines():
    if line.startswith('mark42_') :
        names.add(line.split('{{')[0].split(' ')[0])
# 所有指标必须带 mark42_ 前缀
assert all(n.startswith('mark42_') for n in names), names
# 计数器必须以 _total 结尾（Prometheus 规范）
counters = [n for n in names if 'runs' in n or 'violations' in n or 'compression_total' in n]
bad = [c for c in counters if not (c.endswith('_total') or c.endswith('_created'))]
assert not bad, f'计数器命名不规范: {{bad}}'
# 耗时必须以 _seconds 结尾
durations = [n for n in names if 'duration' in n]
bad_d = [d for d in durations if '_seconds' not in d]
assert not bad_d, f'耗时指标命名不规范: {{bad_d}}'
print('NAMING_OK')
"""
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=120,
            env=_subprocess_env(),
        )
        if "SKIP_NO_LIB" in proc.stdout:
            pytest.skip("prometheus_client 未安装")
        assert "NAMING_OK" in proc.stdout, f"stderr={proc.stderr}"

    def test_no_high_cardinality_labels(self):
        """禁止把 session_id / task_id 等高基数值做标签（会打爆时序库）。"""
        src = Path(t.__file__).read_text(encoding="utf-8")
        for banned in ('"session_id"', '"task_id"', '"user_id"', '"session"'):
            assert banned not in src, f"发现高基数标签: {banned}"


# ── 装饰器 ────────────────────────────────────────────────


class TestTimedDecorator:
    def test_timed_preserves_return_value(self):
        @t.timed(t.record_loop_run, loop_type="test-loop")
        def compute():
            return 42

        assert compute() == 42

    def test_timed_preserves_function_metadata(self):
        @t.timed(t.record_loop_run, loop_type="test-loop")
        def documented():
            """原始文档字符串。"""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "原始文档字符串。"

    def test_timed_reraises_business_exception(self):
        @t.timed(t.record_loop_run, loop_type="test-loop")
        def failing():
            raise RuntimeError("业务失败")

        with pytest.raises(RuntimeError, match="业务失败"):
            failing()

    def test_timed_records_error_status(self):
        recorded = []

        def fake_metric(**kw):
            recorded.append(kw)

        @t.timed(fake_metric, loop_type="x")
        def boom():
            raise ValueError("err")

        with pytest.raises(ValueError):
            boom()
        assert recorded and recorded[0]["status"] == "error"
        assert recorded[0]["duration_s"] >= 0

    def test_timed_metric_failure_does_not_break_business(self):
        """指标记录本身炸了，业务函数的返回值也必须正常送出。"""

        def broken_metric(**kw):
            raise RuntimeError("指标系统故障")

        @t.timed(broken_metric, loop_type="x")
        def business():
            return "业务结果"

        assert business() == "业务结果"


# ── status 面板集成 ───────────────────────────────────────


class TestStatusIntegration:
    def test_status_includes_telemetry_section(self):
        from mark42.cli.status import _collect_status_data

        d = _collect_status_data()
        assert "telemetry" in d
        assert "tracingEnabled" in d["telemetry"]
        assert "metricsEnabled" in d["telemetry"]

    def test_status_telemetry_keys_complete(self):
        st = t.telemetry_status()
        for k in (
            "tracingEnabled",
            "tracingActive",
            "tracingLibInstalled",
            "metricsEnabled",
            "metricsActive",
            "metricsLibInstalled",
            "metricsPort",
            "serviceName",
        ):
            assert k in st, f"缺少字段: {k}"
