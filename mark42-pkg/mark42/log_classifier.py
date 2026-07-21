"""
Mark42 v3 · 核心 6 · 日志/事件分类器

按 v3 §3.6 钉死的核心 6 实现：
- 对 broker 事件按类型自动分类
- 关键词规则 + 可选 LLM 辅助
- 输出结构化分类结果

分类维度：
  - source 分类：health / tasks / engine / security / user / system / unknown
  - 级别分类：info / warning / error / critical
  - 动作建议：monitor / alert / auto_fix / ask_user
"""

from __future__ import annotations

from .log_setup import get_logger

logger = get_logger(__name__)

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── 分类规则 ─────────────────────────────────────────

# source 关键词映射
SOURCE_RULES: list[dict[str, Any]] = [
    {
        "id": "R-HEALTH",
        "match_fields": ["source", "sourceView", "sourceEventType"],
        "keywords": ["health", "compaction", "context_monitor", "armor", "memory"],
        "category": "health",
        "default_level": "warning",
        "action": "monitor",
    },
    {
        "id": "R-TASKS",
        "match_fields": ["source", "sourceView", "sourceEventType"],
        "keywords": ["task", "heavy", "subtask", "supervisor"],
        "category": "tasks",
        "default_level": "info",
        "action": "monitor",
    },
    {
        "id": "R-ENGINE",
        "match_fields": ["source", "sourceView", "sourceEventType"],
        "keywords": ["engine", "loop", "daemon"],
        "category": "engine",
        "default_level": "info",
        "action": "monitor",
    },
    {
        "id": "R-SECURITY",
        "match_fields": ["source", "sourceView", "sourceEventType"],
        "keywords": ["security", "auth", "denied", "unauthorized", "pi i", "breach"],
        "category": "security",
        "default_level": "error",
        "action": "alert",
    },
    {
        "id": "R-SYSTEM",
        "match_fields": ["source", "sourceView", "sourceEventType"],
        "keywords": ["system", "systemd", "service", "process", "disk", "mem", "cpu"],
        "category": "system",
        "default_level": "warning",
        "action": "auto_fix",
    },
    {
        "id": "R-USER",
        "match_fields": ["source", "sourceView"],
        "keywords": ["user", "webchat", "telegram", "signal", "feishu"],
        "category": "user",
        "default_level": "info",
        "action": "monitor",
    },
]

# 级别关键词映射
LEVEL_RULES: dict[str, list[str]] = {
    "critical": ["crash", "panic", "oom", "killed", "fatal", "corruption"],
    "error": ["error", "failed", "failure", "denied", "unauthorized", "timeout"],
    "warning": ["warn", "alert", "stale", "degraded", "slow", "retry"],
    "info": ["completed", "started", "registered", "ok", "success"],
}


# ── 数据类 ───────────────────────────────────────────


@dataclass
class ClassificationResult:
    """单条事件的分类结果。"""

    category: str = "unknown"
    level: str = "info"
    action: str = "monitor"
    matched_rule: str | None = None
    matched_keyword: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 分类器 ───────────────────────────────────────────


class LogClassifier:
    """核心 6 · 日志/事件分类器。

    轻量关键词分类器，不依赖 LLM。
    对于关键词匹配不到的事件，返回 category=unknown + action=monitor。
    """

    def __init__(self):
        self.rules = SOURCE_RULES
        self.level_rules = LEVEL_RULES
        self._stats = {"total": 0, "classified": 0, "unknown": 0}

    def classify(self, event: dict[str, Any]) -> ClassificationResult:
        """分类单条 broker 事件。

        Args:
            event: broker 事件字典（含 source, sourceEventType, sourceView 等字段）

        Returns:
            ClassificationResult
        """
        self._stats["total"] += 1

        # 提取所有文本字段拼成搜索串
        text_fields = []
        for field_name in ["source", "sourceEventType", "sourceView", "recordType", "message"]:
            val = event.get(field_name, "")
            if val and isinstance(val, str):
                text_fields.append(val.lower())
        search_text = " ".join(text_fields)

        # source 分类
        best_match = None
        best_keyword = None
        for rule in self.rules:
            for kw in rule["keywords"]:
                if kw in search_text:
                    best_match = rule
                    best_keyword = kw
                    break
            if best_match:
                break

        if best_match:
            self._stats["classified"] += 1
            category = best_match["category"]
            action = best_match["action"]
            matched_rule = best_match["id"]
            confidence = 0.8  # 关键词匹配，中高置信度
        else:
            self._stats["unknown"] += 1
            category = "unknown"
            action = "monitor"
            matched_rule = None
            best_keyword = None
            confidence = 0.3  # 低置信度

        # 级别分类（覆盖默认级别）
        level = self._classify_level(search_text, best_match)

        return ClassificationResult(
            category=category,
            level=level,
            action=action,
            matched_rule=matched_rule,
            matched_keyword=best_keyword,
            confidence=confidence,
        )

    def _classify_level(self, text: str, source_rule: dict | None) -> str:
        """根据关键词判断级别。"""
        for level, keywords in self.level_rules.items():
            for kw in keywords:
                if kw in text:
                    return level
        # 没匹配到关键词，用 source 规则的默认级别
        if source_rule:
            return source_rule.get("default_level", "info")
        return "info"

    def classify_batch(self, events: list[dict[str, Any]]) -> list[ClassificationResult]:
        """批量分类。"""
        return [self.classify(e) for e in events]

    def stats(self) -> dict[str, Any]:
        """分类统计。"""
        return dict(self._stats)

    def health_check(self) -> bool:
        """健康检查（能否正常实例化 + 分类）。"""
        try:
            test_event = {"source": "engine", "sourceEventType": "loop.completed"}
            r = self.classify(test_event)
            return r.category == "engine"
        except Exception:
            return False


# ── CLI 接口 ────────────────────────────────────────


def cli_classify_test(event_str: str) -> dict[str, Any]:
    """CLI: 测试分类单条事件。"""
    clf = LogClassifier()
    try:
        event = json.loads(event_str)
    except Exception:
        event = {"source": event_str, "sourceEventType": "unknown"}
    result = clf.classify(event)
    return result.to_dict()


def cli_classify_stats() -> dict[str, Any]:
    """CLI: 分类统计。"""
    clf = LogClassifier()
    return clf.stats()


def cli_classify_recent(limit: int = 20) -> list[dict[str, Any]]:
    """CLI: 分类最近的 broker 事件。"""
    broker_file = Path.home() / ".local" / "state" / "openclaw" / "broker" / "events.jsonl"
    if not broker_file.exists():
        return []

    events = []
    with open(broker_file) as f:
        lines = f.readlines()
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line.strip()))
        except Exception:
            logger.debug("跳过无法解析的日志事件行", exc_info=True)
            continue

    clf = LogClassifier()
    results = []
    for e in events:
        r = clf.classify(e)
        results.append(
            {
                "source": e.get("source", ""),
                "type": e.get("sourceEventType", ""),
                **r.to_dict(),
            }
        )
    return results
