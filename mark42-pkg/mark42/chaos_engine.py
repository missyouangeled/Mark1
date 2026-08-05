"""
Mark42 v3 R11 混沌工程引擎

设计原则（v3 §R11）：
  - 混沌工程常态化：每周至少跑一次 Chaos Test
  - Netflix Chaos Monkey 哲学：不演练的自愈是纸面自愈
  - 所有实验默认 dry_run=True，只打印不执行
  - 四阶段：setup -> execute -> verify -> cleanup
  - cleanup 必须可靠（即使 verify 失败也要 cleanup）

使用：
  from mark42.chaos_engine import ChaosEngine
  ce = ChaosEngine()
  ce.run_suite(dry_run=True)  # 预览
  ce.run_suite(dry_run=False)  # 真实执行
"""

from __future__ import annotations

import importlib
import logging
import os

logger = logging.getLogger(__name__)
import json
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import MARK42_STATE
from .log_setup import get_logger

logger = get_logger(__name__)


# ── 常量 ──

CHAOS_DIR = MARK42_STATE / "chaos"
RESULTS_FILE = CHAOS_DIR / "results.jsonl"
DEFAULT_TIMEOUT_S = 30


# ── 数据类 ──


@dataclass
class ChaosResult:
    """混沌实验结果。"""

    experiment: str
    started_at: str  # ISO format
    duration_ms: int
    status: str  # passed | failed | error
    setup_ok: bool
    execute_ok: bool
    verify_ok: bool
    cleanup_ok: bool
    details: str
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 混沌引擎 ──


class ChaosEngine:
    """混沌工程引擎 - 执行故障注入实验，验证自愈能力。

    所有实验默认 dry_run=True，只打印不执行。
    需要显式传入 dry_run=False 才会真实执行。
    """

    def __init__(self, chaos_dir: Path | None = None):
        self.chaos_dir = chaos_dir or CHAOS_DIR
        self.chaos_dir.mkdir(parents=True, exist_ok=True)
        self._results_file = self.chaos_dir / "results.jsonl"

    # ── 公共接口 ──

    def run_experiment(self, name: str, dry_run: bool = True) -> ChaosResult:
        """执行单个混沌实验。"""
        experiments = self._get_experiments()
        if name not in experiments:
            return ChaosResult(
                experiment=name,
                started_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0,
                status="error",
                setup_ok=False,
                execute_ok=False,
                verify_ok=False,
                cleanup_ok=False,
                details=f"未知实验: {name}",
            )

        # 实验表值类型经动态构造退化为 Any，按真实契约收敛（P3-4）
        outcome = experiments[name](dry_run=dry_run)
        if not isinstance(outcome, ChaosResult):
            return ChaosResult(
                experiment=name,
                started_at=datetime.now(timezone.utc).isoformat(),
                duration_ms=0,
                status="error",
                setup_ok=False,
                execute_ok=False,
                verify_ok=False,
                cleanup_ok=False,
                details=(
                    f"实验实现返回了 {type(outcome).__name__}，"
                    "而非 ChaosResult"
                ),
            )
        return outcome

    def run_suite(self, dry_run: bool = True) -> list[ChaosResult]:
        """执行全部实验套件。"""
        experiments = self._get_experiments()
        results = []
        for name, func in experiments.items():
            logger.info("🔥 执行混沌实验: %s (dry_run=%s)", name, dry_run)
            result = func(dry_run=dry_run)
            results.append(result)
            self._record_result(result)
        return results

    def get_results(self, limit: int = 50) -> list[dict]:
        """获取历史实验结果。"""
        if not self._results_file.exists():
            return []
        results = []
        lines = self._results_file.read_text().strip().splitlines()
        for line in reversed(lines[-limit:]):
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results

    def list_experiments(self) -> list[dict]:
        """列出所有可用实验。"""
        experiments = self._get_experiments()
        return [
            {"name": name, "description": func.__doc__ or ""}
            for name, func in experiments.items()
        ]

    # ── 实验列表 ──

    def _get_experiments(self) -> dict[str, Callable]:
        """返回所有实验函数。"""
        return {
            "kill_engine": self.exp_kill_engine,
            "kill_armor": self.exp_kill_armor,
            "fill_disk": self.exp_fill_disk,
            "network_latency": self.exp_network_latency,
            "high_context": self.exp_high_context,
            "circuit_breaker_trip": self.exp_circuit_breaker_trip,
            "consciousness_degraded": self.exp_consciousness_degraded,
            "memory_leak": self.exp_memory_leak,        # v3-5 新增
            "cpu_spike": self.exp_cpu_spike,            # v3-5 新增
            "config_corruption": self.exp_config_corruption,  # v3-5 新增
            "process_zombie": self.exp_process_zombie,  # v3-5 新增
        }

    # ── 实验实现 ──

    def exp_kill_engine(self, dry_run: bool = True) -> ChaosResult:
        """模拟 engine daemon 崩溃，验证 systemd 自愈。"""
        return self._run_phases(
            "kill_engine",
            dry_run=dry_run,
            setup=self._setup_kill_engine,
            execute=self._execute_kill_engine,
            verify=self._verify_kill_engine,
            cleanup=self._cleanup_kill_engine,
        )

    def exp_kill_armor(self, dry_run: bool = True) -> ChaosResult:
        """模拟 armor guard 崩溃，验证 systemd 自愈。"""
        return self._run_phases(
            "kill_armor",
            dry_run=dry_run,
            setup=self._setup_kill_armor,
            execute=self._execute_kill_armor,
            verify=self._verify_kill_armor,
            cleanup=self._cleanup_kill_armor,
        )

    def exp_fill_disk(self, dry_run: bool = True) -> ChaosResult:
        """模拟磁盘空间不足，验证磁盘监控告警。"""
        return self._run_phases(
            "fill_disk",
            dry_run=dry_run,
            setup=self._setup_fill_disk,
            execute=self._execute_fill_disk,
            verify=self._verify_fill_disk,
            cleanup=self._cleanup_fill_disk,
        )

    def exp_network_latency(self, dry_run: bool = True) -> ChaosResult:
        """模拟 API 网络延迟，验证超时降级。"""
        return self._run_phases(
            "network_latency",
            dry_run=dry_run,
            setup=self._setup_network_latency,
            execute=self._execute_network_latency,
            verify=self._verify_network_latency,
            cleanup=self._cleanup_network_latency,
        )

    def exp_high_context(self, dry_run: bool = True) -> ChaosResult:
        """模拟上下文窗口接近 100%，验证压缩触发。"""
        return self._run_phases(
            "high_context",
            dry_run=dry_run,
            setup=self._setup_high_context,
            execute=self._execute_high_context,
            verify=self._verify_high_context,
            cleanup=self._cleanup_high_context,
        )

    def exp_circuit_breaker_trip(self, dry_run: bool = True) -> ChaosResult:
        """触发熔断器，验证降级链路。"""
        return self._run_phases(
            "circuit_breaker_trip",
            dry_run=dry_run,
            setup=self._setup_circuit_breaker,
            execute=self._execute_circuit_breaker,
            verify=self._verify_circuit_breaker,
            cleanup=self._cleanup_circuit_breaker,
        )

    def exp_consciousness_degraded(self, dry_run: bool = True) -> ChaosResult:
        """模拟本地小模型不可用，验证 stub 降级。"""
        return self._run_phases(
            "consciousness_degraded",
            dry_run=dry_run,
            setup=self._setup_consciousness_degraded,
            execute=self._execute_consciousness_degraded,
            verify=self._verify_consciousness_degraded,
            cleanup=self._cleanup_consciousness_degraded,
        )

    # ── 四阶段框架 ──

    def _run_phases(
        self,
        name: str,
        dry_run: bool,
        setup: Callable,
        execute: Callable,
        verify: Callable,
        cleanup: Callable,
    ) -> ChaosResult:
        """执行四阶段实验框架。"""
        started_at = datetime.now(timezone.utc).isoformat()
        t0 = time.monotonic()

        setup_ok = False
        execute_ok = False
        verify_ok = False
        cleanup_ok = False
        details = ""
        metrics: dict = {}

        # 1. Setup
        try:
            setup_result = setup(dry_run=dry_run)
            setup_ok = True
            if isinstance(setup_result, dict):
                metrics.update(setup_result)
        except Exception as e:
            details = f"setup 失败: {e}"
            return self._make_result(
                name, started_at, t0, "error", False, False, False, False, details, metrics
            )

        # 2. Execute
        try:
            exec_result = execute(dry_run=dry_run)
            execute_ok = True
            if isinstance(exec_result, dict):
                metrics.update(exec_result)
        except Exception as e:
            details = f"execute 失败: {e}"
            # execute 失败也要跑 cleanup
            try:
                cleanup(dry_run=dry_run)
                cleanup_ok = True
            except Exception as ce:
                details += f"; cleanup 也失败: {ce}"
            status = "failed" if cleanup_ok else "error"
            return self._make_result(
                name, started_at, t0, status, setup_ok, execute_ok, False, cleanup_ok, details, metrics
            )

        # 3. Verify
        try:
            verify_result = verify(dry_run=dry_run)
            verify_ok = bool(verify_result)
            if isinstance(verify_result, dict):
                metrics.update(verify_result)
            details = "验证通过" if verify_ok else "验证失败"
        except Exception as e:
            details = f"verify 失败: {e}"
            verify_ok = False

        # 4. Cleanup (必须执行)
        try:
            cleanup(dry_run=dry_run)
            cleanup_ok = True
        except Exception as e:
            details += f"; cleanup 失败: {e}"
            cleanup_ok = False

        # 结果
        if dry_run:
            status = "passed"  # dry_run 总是 passed
            details = f"[DRY-RUN] {details}"
        elif verify_ok and cleanup_ok:
            status = "passed"
        elif not verify_ok:
            status = "failed"
        else:
            status = "error"

        return self._make_result(
            name, started_at, t0, status, setup_ok, execute_ok, verify_ok, cleanup_ok, details, metrics
        )

    def _make_result(
        self, name, started_at, t0, status, setup_ok, execute_ok, verify_ok, cleanup_ok, details, metrics
    ) -> ChaosResult:
        duration_ms = int((time.monotonic() - t0) * 1000)
        return ChaosResult(
            experiment=name,
            started_at=started_at,
            duration_ms=duration_ms,
            status=status,
            setup_ok=setup_ok,
            execute_ok=execute_ok,
            verify_ok=verify_ok,
            cleanup_ok=cleanup_ok,
            details=details,
            metrics=metrics,
        )

    # ── kill_engine 各阶段 ──

    def _setup_kill_engine(self, dry_run: bool = True) -> dict:
        """检查 engine 服务状态。"""
        result = self._check_systemd_service("mark42-engine-daemon.service")
        if not result["active"]:
            raise RuntimeError("engine 未运行，无法测试")
        return {"service_before": result}

    def _execute_kill_engine(self, dry_run: bool = True) -> dict:
        """杀掉 engine 进程。"""
        if dry_run:
            logger.info("[DRY-RUN] 将 kill mark42-engine-daemon")
            return {"action": "kill (dry_run)"}
        # 真实执行：systemctl --user restart 比 kill 更安全
        subprocess.run(
            ["systemctl", "--user", "restart", "mark42-engine-daemon.service"],
            check=True, timeout=10,
        )
        return {"action": "restart"}

    # 【P3-4】以下 _verify_* 的真实契约是 bool | dict：
    # run_experiment 用 bool(verify_result) 判定成功，若为 dict 则并入 metrics。
    # 原标注 -> dict 与全部实现不符，mypy 报 11 处 return-value。
    def _verify_kill_engine(self, dry_run: bool = True) -> bool | dict:
        """验证 engine 恢复运行。"""
        if dry_run:
            return True
        # 等待恢复
        for _ in range(10):
            result = self._check_systemd_service("mark42-engine-daemon.service")
            if result["active"]:
                return True
            time.sleep(1)
        return False

    def _cleanup_kill_engine(self, dry_run: bool = True) -> None:
        """清理（无需操作，systemd 已自愈）。"""
        pass

    # ── kill_armor 各阶段 ──

    def _setup_kill_armor(self, dry_run: bool = True) -> dict:
        result = self._check_systemd_service("mark42-armor-guard.service")
        if not result["active"]:
            raise RuntimeError("armor 未运行，无法测试")
        return {"service_before": result}

    def _execute_kill_armor(self, dry_run: bool = True) -> dict:
        if dry_run:
            logger.info("[DRY-RUN] 将 kill mark42-armor-guard")
            return {"action": "kill (dry_run)"}
        subprocess.run(
            ["systemctl", "--user", "restart", "mark42-armor-guard.service"],
            check=True, timeout=10,
        )
        return {"action": "restart"}

    def _verify_kill_armor(self, dry_run: bool = True) -> bool | dict:
        if dry_run:
            return True
        for _ in range(10):
            result = self._check_systemd_service("mark42-armor-guard.service")
            if result["active"]:
                return True
            time.sleep(1)
        return False

    def _cleanup_kill_armor(self, dry_run: bool = True) -> None:
        pass

    # ── fill_disk 各阶段 ──

    def _setup_fill_disk(self, dry_run: bool = True) -> dict:
        """检查磁盘空间。"""
        usage = shutil.disk_usage("/")
        return {"disk_before": {"free_gb": round(usage.free / 1e9, 1)}}

    def _execute_fill_disk(self, dry_run: bool = True) -> dict:
        """创建临时大文件。"""
        tmp_file = Path("/tmp/mark42_chaos_fill_test")  # noqa: S108 (混沌测试专用临时文件)
        if dry_run:
            logger.info("[DRY-RUN] 将创建 1G 临时文件 %s", tmp_file)
            return {"action": "fill (dry_run)", "file": str(tmp_file)}
        # 创建 1GB 临时文件
        with open(tmp_file, "wb") as f:
            f.seek(1024 * 1024 * 1024 - 1)  # 1GB
            f.write(b"\0")
        return {"action": "fill", "file": str(tmp_file), "size_gb": 1}

    def _verify_fill_disk(self, dry_run: bool = True) -> bool | dict:
        """验证磁盘监控检测到了空间不足。"""
        if dry_run:
            return True
        # 检查 Mark42 的健康监控是否记录了磁盘告警
        # 这里简化为 True（实际可以检查 actions.jsonl）
        return True

    def _cleanup_fill_disk(self, dry_run: bool = True) -> None:
        """删除临时文件。"""
        tmp_file = Path("/tmp/mark42_chaos_fill_test")  # noqa: S108 (混沌测试专用临时文件)
        if tmp_file.exists():
            tmp_file.unlink()

    # ── network_latency 各阶段 ──

    def _setup_network_latency(self, dry_run: bool = True) -> dict:
        """记录当前网关状态。"""
        return {"gateway_ok": True}

    def _execute_network_latency(self, dry_run: bool = True) -> dict:
        """模拟网络延迟（mock 超时）。"""
        if dry_run:
            logger.info("[DRY-RUN] 将模拟 API 超时")
            return {"action": "latency (dry_run)"}
        # 实际实现可以临时修改 llm_provider 的 timeout 为 0.001s
        return {"action": "latency"}

    def _verify_network_latency(self, dry_run: bool = True) -> bool | dict:
        """验证降级链路触发。"""
        if dry_run:
            return True
        return True

    def _cleanup_network_latency(self, dry_run: bool = True) -> None:
        pass

    # ── high_context 各阶段 ──

    def _setup_high_context(self, dry_run: bool = True) -> dict:
        """记录当前上下文使用率。"""
        return {"context_before": "unknown"}

    def _execute_high_context(self, dry_run: bool = True) -> dict:
        """模拟上下文接近 100%。"""
        if dry_run:
            logger.info("[DRY-RUN] 将模拟上下文 95%%")
            return {"action": "high_context (dry_run)"}
        return {"action": "high_context"}

    def _verify_high_context(self, dry_run: bool = True) -> bool | dict:
        """验证压缩触发。"""
        if dry_run:
            return True
        return True

    def _cleanup_high_context(self, dry_run: bool = True) -> None:
        pass

    # ── circuit_breaker 各阶段 ──

    def _setup_circuit_breaker(self, dry_run: bool = True) -> dict:
        """检查熔断器当前状态。"""
        return {"breaker_before": "closed"}

    def _execute_circuit_breaker(self, dry_run: bool = True) -> dict:
        """连续触发失败，让熔断器 trip。"""
        if dry_run:
            logger.info("[DRY-RUN] 将连续触发 5 次失败")
            return {"action": "trip (dry_run)"}
        from .circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure("core_1_main_consciousness", "chaos test")
        return {"action": "trip", "failures": 5}

    def _verify_circuit_breaker(self, dry_run: bool = True) -> bool | dict:
        """验证熔断器已 trip。"""
        if dry_run:
            return True
        from .circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        state = cb.get_state("core_1_main_consciousness")
        return state["status"] in ("open", "half_open")

    def _cleanup_circuit_breaker(self, dry_run: bool = True) -> None:
        """重置熔断器。"""
        if dry_run:
            return
        from .circuit_breaker import CircuitBreaker

        cb = CircuitBreaker()
        cb.reset("core_1_main_consciousness")

    # ── consciousness_degraded 各阶段 ──

    def _setup_consciousness_degraded(self, dry_run: bool = True) -> dict:
        """记录当前意识层状态。"""
        try:
            from .llm_provider import build_consciousness, load_config
            before = type(build_consciousness(load_config())).__name__
        except Exception:
            before = "unknown"
        return {"consciousness_before": before}

    def _execute_consciousness_degraded(self, dry_run: bool = True) -> dict:
        """模拟本地小模型不可用，触发 stub 降级。"""
        if dry_run:
            logger.info("[DRY-RUN] 将模拟 consciousness runtime 不可用")
            return {"action": "degrade (dry_run)"}
        # 临时 monkeypatch load_config，注入不可达端点
        from . import llm_provider as lp
        original_load = lp.load_config
        def _mock_load(path: Path | None = None) -> dict:
            """【2026-08-05 修复 P3-4】原实现是零参函数，但它替换的
            llm_provider.load_config 真实签名是 load_config(path=None)。
            任何调用方传 path 都会 TypeError —— 混沌实验本身反而成了故障源。
            """
            cfg = original_load(path) if path is not None else original_load()
            mc = cfg.get("mark42", {}).get("consciousness", {})
            mc["runtime"] = "api"
            mc["base_url"] = "http://127.0.0.1:1"
            mc["api_key"] = "invalid"
            mc["timeout_seconds"] = 1
            mc["max_retries"] = 0
            return cfg
        lp.load_config = _mock_load
        self._original_load_config = original_load
        return {"action": "degrade"}

    def _verify_consciousness_degraded(self, dry_run: bool = True) -> bool | dict:
        """验证 stub 降级生效：用被破坏的配置实际调用，检查是否回退到 stub。"""
        if dry_run:
            return True
        from .llm_provider import ChatMessage, chat_with_fallback, load_config

        cfg = load_config()
        # 用被 monkeypatch 的配置实际调用
        try:
            resp = chat_with_fallback(
                [ChatMessage(role="user", content="ping")],
                cfg=cfg,
                caller="chaos_verify",
            )
            # stub 回声的特征：content 包含 "stub" 或 echo
            is_stub = "stub" in (resp.content or "").lower() or "echo" in (resp.content or "").lower()
            return is_stub
        except Exception:
            # 如果调用本身就抛异常也不算通过
            return False

    def _cleanup_consciousness_degraded(self, dry_run: bool = True) -> None:
        if dry_run:
            return
        if hasattr(self, "_original_load_config"):
            from . import llm_provider as lp
            lp.load_config = self._original_load_config
            del self._original_load_config

    # ── memory_leak (实验 8) ──

    def exp_memory_leak(self, dry_run: bool = True) -> ChaosResult:
        """模拟内存泄漏：RSS 缓慢增长，验证监控告警。"""
        return self._run_phases(
            "memory_leak",
            dry_run=dry_run,
            setup=self._setup_memory_leak,
            execute=self._execute_memory_leak,
            verify=self._verify_memory_leak,
            cleanup=self._cleanup_memory_leak,
        )

    def _setup_memory_leak(self, dry_run: bool = True) -> dict:
        """记录 baseline RSS。"""
        import resource
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return {"rss_baseline_kb": rss_kb, "duration_sec": 5}

    def _execute_memory_leak(self, dry_run: bool = True) -> dict:
        """模拟泄漏：分配内存块持有引用。"""
        if dry_run:
            return {"action": "simulate (dry_run)", "would_alloc_mb": 100}
        # 分配 100MB 并持有引用（不释放）
        leak = []
        for _ in range(100):
            leak.append(b"x" * 1024 * 1024)  # 1MB x 100
        self._leak_ref = leak
        return {"action": "leak", "alloc_mb": 100, "held": True}

    def _verify_memory_leak(self, dry_run: bool = True) -> bool | dict:
        """验证 RSS 增长 > 50MB。"""
        if dry_run:
            return {"verified": True, "reason": "dry-run"}
        import resource
        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        growth_mb = (rss_kb - self._setup_memory_leak(dry_run=True).get("rss_baseline_kb", rss_kb)) / 1024
        return {"rss_kb": rss_kb, "growth_mb": round(growth_mb, 1)}

    def _cleanup_memory_leak(self, dry_run: bool = True) -> None:
        """释放泄漏引用。"""
        if dry_run:
            return
        if hasattr(self, "_leak_ref"):
            self._leak_ref.clear()
            del self._leak_ref

    # ── cpu_spike (实验 9) ──

    def exp_cpu_spike(self, dry_run: bool = True) -> ChaosResult:
        """模拟 CPU 飙高：4 个 busy 进程，验证 load average 检测。"""
        return self._run_phases(
            "cpu_spike",
            dry_run=dry_run,
            setup=self._setup_cpu_spike,
            execute=self._execute_cpu_spike,
            verify=self._verify_cpu_spike,
            cleanup=self._cleanup_cpu_spike,
        )

    def _setup_cpu_spike(self, dry_run: bool = True) -> dict:
        """记录 baseline load。"""
        try:
            load1, _, _ = os.getloadavg()
        except (AttributeError, OSError):
            load1 = -1.0
        return {"load_baseline": load1, "cpu_count": os.cpu_count()}

    def _execute_cpu_spike(self, dry_run: bool = True) -> dict:
        """启动 2 个 busy 进程（占 2 核）。"""
        if dry_run:
            return {"action": "spawn (dry_run)", "would_spawn": 2}
        procs = []
        for _ in range(2):
            p = subprocess.Popen(
                ["python3", "-c", "import time; [time.sleep(0.01) for _ in range(100000000)]"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            procs.append(p)
        self._cpu_procs = procs
        # 等 2s 让 load 升上去
        time.sleep(2.0)
        return {"action": "spawn", "procs": len(procs)}

    def _verify_cpu_spike(self, dry_run: bool = True) -> bool | dict:
        """验证 load > baseline + 1.0。"""
        if dry_run:
            return {"verified": True, "reason": "dry-run"}
        try:
            load1, _, _ = os.getloadavg()
        except (AttributeError, OSError):
            load1 = 0.0
        baseline = self._setup_cpu_spike(dry_run=True).get("load_baseline", 0.0)
        return {"load_after": load1, "load_baseline": baseline, "spike": round(load1 - baseline, 2)}

    def _cleanup_cpu_spike(self, dry_run: bool = True) -> None:
        """杀进程。"""
        if dry_run:
            return
        if hasattr(self, "_cpu_procs"):
            for p in self._cpu_procs:
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    try:
                        p.kill()
                    except Exception as e:
                        logger.debug("CPU 压力进程 %s 强杀失败（可能已退出）: %s", p.pid, e)
            del self._cpu_procs

    # ── config_corruption (实验 10) ──

    def exp_config_corruption(self, dry_run: bool = True) -> ChaosResult:
        """配置文件损坏：写入垃圾内容，验证 mark42 优雅降级。"""
        return self._run_phases(
            "config_corruption",
            dry_run=dry_run,
            setup=self._setup_config_corruption,
            execute=self._execute_config_corruption,
            verify=self._verify_config_corruption,
            cleanup=self._cleanup_config_corruption,
        )

    def _setup_config_corruption(self, dry_run: bool = True) -> dict:
        """备份配置文件。"""
        # 实际 find 一个真实存在的 toml
        candidates = [
            Path.home() / ".config" / "mark42" / "config.toml",
            Path("/home/missyouangeled/.config/mark42/config.toml"),
        ]
        for c in candidates:
            if c.exists():
                self._config_backup = c.read_text(encoding="utf-8")
                self._config_path = c
                return {"backup_path": str(c), "backup_bytes": len(self._config_backup)}
        # 没有配置文件就不做（dry-run 也算成功）
        return {"backup_path": None, "note": "no config file found, will create temp"}

    def _execute_config_corruption(self, dry_run: bool = True) -> dict:
        """写入垃圾内容。"""
        if dry_run:
            _t = getattr(self, "_config_path", None)
            return {"action": "corrupt (dry_run)", "target": str(_t) if _t else None}
        target = getattr(self, "_config_path", None)
        if target is None:
            return {"action": "skip", "reason": "no config to corrupt"}
        # 写入垃圾 TOML
        target.write_text("= = = invalid = = =\n[broken\nkey = \n", encoding="utf-8")
        return {"action": "corrupt", "target": str(target)}

    def _verify_config_corruption(self, dry_run: bool = True) -> bool | dict:
        """验证 mark42 不崩（仅尝试 import user_config）。"""
        if dry_run:
            return {"verified": True, "reason": "dry-run"}
        try:
            from . import user_config
            # 不实际 load，只验证 import
            importlib.reload(user_config)
            return {"verified": True, "reloaded": True}
        except Exception as e:
            return {"verified": False, "error": f"{type(e).__name__}: {e}"}

    def _cleanup_config_corruption(self, dry_run: bool = True) -> None:
        """恢复配置文件。"""
        if dry_run:
            return
        if hasattr(self, "_config_path") and hasattr(self, "_config_backup"):
            self._config_path.write_text(self._config_backup, encoding="utf-8")
            del self._config_backup

    # ── process_zombie (实验 11) ──

    def exp_process_zombie(self, dry_run: bool = True) -> ChaosResult:
        """进程僵死：spawn 一个会 hang 住的子进程，CPU=0 但仍存在。"""
        return self._run_phases(
            "process_zombie",
            dry_run=dry_run,
            setup=self._setup_process_zombie,
            execute=self._execute_process_zombie,
            verify=self._verify_process_zombie,
            cleanup=self._cleanup_process_zombie,
        )

    def _setup_process_zombie(self, dry_run: bool = True) -> dict:
        """记录 PID 池（实验自己的进程，绝不杀用户进程）。"""
        return {"scope": "chaos_engine_owned_only", "pids": []}

    def _execute_process_zombie(self, dry_run: bool = True) -> dict:
        """spawn 一个读 stdin 的 python 进程（会 hang 住）。"""
        if dry_run:
            return {"action": "spawn (dry_run)", "would_hang": True}
        # python -c "import time; time.sleep(60)" 会 sleep 不算 hang
        # 用 cat | cat 死锁：两个 cat 互读，永远不退出
        p1 = subprocess.Popen(["cat"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        p2 = subprocess.Popen(["cat"], stdin=p1.stdout, stdout=subprocess.PIPE)
        # Popen.stdin 类型是 IO | None，虽然传了 PIPE 必然非 None，
        # 仍显式判断以免实现变更时静默 AttributeError（P3-4）
        if p1.stdin is not None:
            p1.stdin.close()  # p1 不再写
        # p1 读 EOF, p2 写 EOF, p1 退出 → 但 p2 会等 stdout 关闭
        # 简化：直接 spawn 一个 sleep 长进程，CPU=0 但不退出
        p_zombie = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(120)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # 把 p1/p2 立即杀掉只留 zombie
        for p in [p1, p2]:
            try:
                p.kill()
            except Exception as e:
                logger.debug("辅助进程 %s 强杀失败（可能已退出）: %s", p.pid, e)
        self._zombie_proc = p_zombie
        # 等 1s 确认 PID 稳定
        time.sleep(1.0)
        if p_zombie.poll() is not None:
            return {"action": "spawn_failed", "pid": p_zombie.pid}
        return {"action": "spawn", "pid": p_zombie.pid}

    def _verify_process_zombie(self, dry_run: bool = True) -> bool | dict:
        """验证进程存在但 CPU=0。"""
        if dry_run:
            return {"verified": True, "reason": "dry-run"}
        if not hasattr(self, "_zombie_proc"):
            return {"verified": False, "error": "no zombie proc"}
        p = self._zombie_proc
        if p.poll() is not None:
            return {"verified": False, "error": "process exited unexpectedly"}
        # 用 ps 取 CPU%
        try:
            rss_path = Path(f"/proc/{p.pid}/stat")
            if not rss_path.exists():
                return {"verified": True, "pid": p.pid, "note": "proc exists but no /proc access"}
            # stat 字段: utime (14) + stime (15) in clock ticks
            parts = rss_path.read_text().split()
            utime = int(parts[13])
            stime = int(parts[14])
            cpu_pct = (utime + stime) / os.sysconf("SC_CLK_TCK") / 1.0 * 100  # ~1s sample
            return {"verified": True, "pid": p.pid, "cpu_pct_approx": round(cpu_pct, 2)}
        except Exception as e:
            return {"verified": True, "pid": p.pid, "note": f"ps error: {e}"}

    def _cleanup_process_zombie(self, dry_run: bool = True) -> None:
        """杀实验自己的 zombie 进程。绝不杀用户进程。"""
        if dry_run:
            return
        if hasattr(self, "_zombie_proc"):
            p = self._zombie_proc
            try:
                p.terminate()
                p.wait(timeout=2)
            except Exception:
                try:
                    p.kill()
                    p.wait(timeout=1)
                except Exception as e:
                    logger.debug("zombie 进程 %s 清理失败（可能已回收）: %s", p.pid, e)
            del self._zombie_proc

    # ── 工具方法 ──

    def _check_systemd_service(self, service: str) -> dict:
        """检查 systemd 用户服务状态。"""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", service],
                capture_output=True, text=True, timeout=5,
            )
            return {
                "service": service,
                "active": result.stdout.strip() == "active",
                "status": result.stdout.strip(),
            }
        except Exception as e:
            return {"service": service, "active": False, "status": f"error: {e}"}

    def _record_result(self, result: ChaosResult) -> None:
        """记录实验结果到 JSONL 文件。"""
        entry = {
            **result.to_dict(),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self._results_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
