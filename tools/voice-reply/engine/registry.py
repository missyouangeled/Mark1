"""引擎注册表 + 60s 健康检查缓存"""

from __future__ import annotations

import time
import logging
from typing import Optional

from .base import BaseEngine, HealthCacheEntry

logger = logging.getLogger(__name__)


class EngineRegistry:
    """管理所有引擎实例，按优先级选最佳可用引擎。"""

    HEALTH_CACHE_S = 60
    HEALTH_CHECK_TIMEOUT_S = 3

    def __init__(self):
        self.engines: list[BaseEngine] = []
        self._health_cache: dict[str, HealthCacheEntry] = {}

    def register(self, engine: BaseEngine) -> None:
        self.engines.append(engine)
        # 按优先级排序（0 最高）
        self.engines.sort(key=lambda e: e.priority)

    def pick_best(
        self, prefer_local: bool = False, need_cloning: bool = False
    ) -> BaseEngine:
        """
        按优先级遍历引擎，选第一个健康的。

        - prefer_local: True → 跳过云端引擎
        - need_cloning: 保留给未来（XTTS/CosyVoice 优先）
        """
        *primary, fallback = self.engines  # 最后一个永远是兜底
        ordered = primary[::-1] if fallback else []

        for engine in self.engines:
            if prefer_local and engine.is_cloud:
                logger.debug(f"跳过云端引擎 {engine.name}（prefer_local）")
                continue

            if self._check_cached(engine):
                logger.info(f"选定引擎: {engine.name} (priority={engine.priority})")
                return engine

        msg = "所有引擎均不可用"
        logger.error(msg)
        for e in self.engines:
            cached = self._health_cache.get(e.name)
            if cached:
                logger.error(f"  {e.name}: {cached.reason}")
        raise RuntimeError(msg)

    def _check_cached(self, engine: BaseEngine) -> bool:
        """检查缓存。有效则直接返回；过期则重新检测并更新缓存。"""
        cached = self._health_cache.get(engine.name)
        now_s = time.monotonic()

        if cached and (now_s - cached.checked_at_s) < self.HEALTH_CACHE_S:
            return cached.healthy

        healthy = False
        reason = "not installed"
        try:
            if not engine.is_installed():
                reason = "not installed"
            else:
                healthy = engine.health_check()
                reason = "ok" if healthy else "health check failed"
        except Exception as e:
            reason = f"error: {e}"

        self._health_cache[engine.name] = HealthCacheEntry(
            healthy=healthy, checked_at_s=now_s, reason=reason
        )
        return healthy

    def invalidate(self, engine_name: str) -> None:
        """强制使缓存失效（引擎恢复后调用）。"""
        self._health_cache.pop(engine_name, None)
