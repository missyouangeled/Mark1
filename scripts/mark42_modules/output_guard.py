"""Mark42 输出 token 优化：统一摘要/详情/预览截断策略。"""

from __future__ import annotations

from typing import Any


def _normalize_text(text: object) -> str:
    if text is None:
        return ""
    raw = str(text).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in raw.split("\n")]
    collapsed = " ".join(line for line in lines if line)
    return " ".join(collapsed.split())


def _trim(text: object, limit: int) -> str:
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    if limit <= 1:
        return normalized[:limit]
    return normalized[: limit - 1].rstrip() + "…"


def trim_summary(text: object, limit: int = 120) -> str:
    return _trim(text, limit)


def trim_detail(text: object, limit: int = 280) -> str:
    return _trim(text, limit)


def compact_preview(text: object, limit: int = 160) -> str:
    return _trim(text, limit)


def should_spill_to_file(text: object, limit: int = 300) -> bool:
    return len(_normalize_text(text)) > limit


def trim_json_short(value: Any, limit: int = 160) -> Any:
    if isinstance(value, dict):
        return {k: trim_json_short(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [trim_json_short(v, limit) for v in value]
    if isinstance(value, tuple):
        return tuple(trim_json_short(v, limit) for v in value)
    if isinstance(value, str):
        return _trim(value, limit)
    return value
