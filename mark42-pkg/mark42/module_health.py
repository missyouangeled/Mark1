"""
Mark42 v3 §3.7 · 模块级协议健康监控

三态自检（green/yellow/red）+ 4 Golden Signals（延迟/错误率/饱和度/流量）
+ 契约测试（contract_passed）

从 governance.py 拆出，修复 embed 健康检查（不再探测 18792 端口）。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from .config import MARK42_STATE
from .log_setup import get_logger

logger = get_logger(__name__)

MODULE_HEALTH_DIR = MARK42_STATE / "module-health"


@dataclass
class ModuleHealth:
    """模块三态健康度（§3.7.1）。"""

    module_id: str
    module_name: str
    status: str = "green"  # green | yellow | red
    latency_ms: int | None = None
    error_rate: float = 0.0  # 0.0-1.0
    saturation: float = 0.0  # 0.0-1.0
    traffic_per_min: int = 0
    contract_passed: bool = True
    fallback_active: str | None = None
    last_check: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def golden_signals_ok(self) -> bool:
        """4 Golden Signals 是否全达标。"""
        if self.latency_ms and self.latency_ms > 2000:
            return False
        if self.error_rate > 0.05:
            return False
        if self.saturation > 0.8:
            return False
        return True

    @property
    def is_degraded(self) -> bool:
        return self.status == "yellow"

    @property
    def is_down(self) -> bool:
        return self.status == "red"


class ModuleHealthMonitor:
    """§3.7 模块级协议：三态 + 契约测试 + 4 Golden Signals。"""

    MODULES = [
        {"id": "armor", "name": "上下文铠甲", "check": "armor_check"},
        {"id": "engine", "name": "循环引擎", "check": "engine_status"},
        {"id": "consciousness", "name": "战甲意识层", "check": "consciousness_check"},
        {"id": "advisor", "name": "主动交流", "check": "advisor_ping"},
        {"id": "memory_vector", "name": "向量引擎", "check": "qmd_check"},
        {"id": "error_archive", "name": "错误档案", "check": "archive_list"},
    ]

    def __init__(self):
        MODULE_HEALTH_DIR.mkdir(parents=True, exist_ok=True)

    def check_all(self) -> list[ModuleHealth]:
        """检查所有模块三态 + 4 Golden Signals。"""
        results = []
        for mod in self.MODULES:
            health = self._check_module(mod)
            results.append(health)
        return results

    def _check_module(self, mod: dict[str, Any]) -> ModuleHealth:
        """检查单个模块。"""
        mid = mod["id"]
        name = mod["name"]
        check = mod["check"]
        t0 = time.monotonic()

        health = ModuleHealth(
            module_id=mid, module_name=name,
            last_check=datetime.now().isoformat(),
        )

        try:
            if check == "armor_check":
                from .armor import armor_check
                r = armor_check()
                health.latency_ms = int((time.monotonic() - t0) * 1000)
                usage = r.get("usagePercent", 0)
                health.saturation = usage / 100.0
                health.status = "green" if usage < 85 else "yellow"

            elif check == "engine_status":
                from .engine import _load_loops
                loops = _load_loops()
                active = sum(1 for lp in loops.values()
                             if lp.get("status") in ("registered", "running"))
                total = len(loops)
                health.latency_ms = int((time.monotonic() - t0) * 1000)
                health.traffic_per_min = active
                if active > 0:
                    health.status = "green"
                elif total > 0:
                    health.status = "red"
                else:
                    health.status = "yellow"

            elif check == "consciousness_check":
                from .consciousness import Consciousness
                cs = Consciousness()
                # 【P3-4】不复用变量名 r —— 上文 r 是 armor_check() 返回的 dict,
                # 这里是 SelfCheckResult(dataclass), 同名不同类型
                self_check = cs.self_check()
                health.latency_ms = int((time.monotonic() - t0) * 1000)
                health.status = "green" if self_check.healthy else "yellow"
                health.error_rate = len(self_check.issues) / 10.0

            elif check == "advisor_ping":
                from .advisor_client import AdvisorClient
                client = AdvisorClient()
                if not client.enabled:
                    health.status = "yellow"
                    health.fallback_active = "advisor_not_enabled"
                else:
                    result = client.ping()
                    health.latency_ms = result.verdict.elapsed_ms if result.verdict else 0
                    health.status = "green" if result.success else "red"
                    if not result.success:
                        health.fallback_active = result.fallback_reason

            elif check == "qmd_check":
                # 不再探测 HTTP 端口，直接检查 qmd 命令 + 索引
                import shutil
                qmd_bin = shutil.which("qmd") or os.path.expanduser("~/.npm-global/bin/qmd")
                index_path = os.path.expanduser("~/.cache/qmd/index.sqlite")
                health.latency_ms = int((time.monotonic() - t0) * 1000)
                if os.path.isfile(qmd_bin) and os.path.isfile(index_path):
                    health.status = "green"
                else:
                    health.status = "red"
                    health.fallback_active = "L1_keyword_only"

            elif check == "archive_list":
                from .error_archive import ErrorArchive
                ea = ErrorArchive()
                ea.list_entries()  # 63a26d4b526f4f5c7528Ff1a9a8c8bc1 error_archive 53ef7528
                health.status = "green"
                health.latency_ms = int((time.monotonic() - t0) * 1000)

            health.contract_passed = True

        except Exception as e:
            health.status = "red"
            health.fallback_active = f"error: {e}"
            health.contract_passed = False
            health.latency_ms = int((time.monotonic() - t0) * 1000)

        # 4 Golden Signals 触线降级
        if health.status == "green" and not health.golden_signals_ok:
            health.status = "yellow"

        return health

    def summary(self) -> dict[str, Any]:
        """摘要。"""
        results = self.check_all()
        green = sum(1 for r in results if r.status == "green")
        yellow = sum(1 for r in results if r.status == "yellow")
        red = sum(1 for r in results if r.status == "red")
        return {
            "total": len(results),
            "green": green,
            "yellow": yellow,
            "red": red,
            "modules": [r.to_dict() for r in results],
        }
