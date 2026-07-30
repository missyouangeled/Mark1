"""内置健康监控锁扣实现：包装 engine.py health-watch 逻辑。"""

from __future__ import annotations

from typing import Any


class BuiltinHealth:
    """将 engine.py 的健康监控包装为 HealthLock 接口。"""

    def check_health(self) -> dict[str, Any]:

        import psutil

        try:
            vm = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu = psutil.cpu_percent(interval=0.5)

            alerts = []
            if vm.percent > 85:
                alerts.append({"type": "memory", "level": "critical",
                               "msg": f"内存使用 {vm.percent}%"})
            if disk.percent > 90:
                alerts.append({"type": "disk", "level": "critical",
                               "msg": f"磁盘使用 {disk.percent}%"})
            if cpu > 90:
                alerts.append({"type": "cpu", "level": "warning",
                               "msg": f"CPU 使用 {cpu}%"})

            return {
                "status": "healthy" if not alerts else "degraded",
                "memory": {"percent": vm.percent, "available_mb": vm.available // (1024*1024)},
                "disk": {"percent": disk.percent, "free_gb": disk.free // (1024**3)},
                "cpu": {"percent": cpu},
                "alerts": alerts,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "alerts": []}
