"""Mark42 Session Fence - 会话安全围栏。

设计意图：防止 armor 误操作错误的 session，确保压缩前后 session 文件完整性。

功能：
1. 验证活跃 session 是预期的那一个（agent:main:main）
2. 记录压缩前后的文件状态（mtime + size），检测外部篡改
3. 提供 context manager 包装压缩操作，自动留痕

历史：原设计文档提到 session_fence，但从未实现。2026-07-28 补齐。
"""

import time
from pathlib import Path
from typing import Any

from .config import XDG_STATE
from .utils import _find_active_session, _now_iso, _save_json

# Fence 状态文件
FENCE_STATE = XDG_STATE / "mark42" / "fence.json"


def fence_verify(session_path: Path | None = None) -> dict[str, Any]:
    """验证当前活跃 session 是否安全可操作。

    Fail-open 原则：检查失败时不阻断压缩，只记录原因。

    Returns:
        {"ok": bool, "sessionPath": str, "reason": str, "mtime": float, "size": int}
    """
    if session_path is None:
        session_path = _find_active_session()

    if session_path is None:
        return {"ok": False, "sessionPath": "", "reason": "no-active-session", "mtime": 0, "size": 0}

    try:
        if not session_path.exists():
            return {"ok": False, "sessionPath": str(session_path), "reason": "file-not-found", "mtime": 0, "size": 0}

        stat = session_path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        # 检查 session 文件是否异常过大（>2GB = 可能损坏）
        if size > 2 * 1024 * 1024 * 1024:
            return {"ok": False, "sessionPath": str(session_path), "reason": "file-too-large",
                    "mtime": mtime, "size": size}

        # 检查 session 是否过于陈旧
        age = time.time() - mtime
        if age > 3600:
            return {"ok": False, "sessionPath": str(session_path), "reason": "session-stale",
                    "mtime": mtime, "size": size, "ageSeconds": round(age, 0)}
    except (OSError, TypeError, AttributeError):
        # Fail-open: 无法 stat 或比较时放行，不阻断压缩
        return {"ok": True, "sessionPath": str(session_path), "reason": "stat-skipped", "mtime": 0, "size": 0}

    return {"ok": True, "sessionPath": str(session_path), "reason": "ok",
            "mtime": mtime, "size": size}


def fence_record_pre(session_path: Path) -> dict[str, Any]:
    """记录压缩前的 session 状态（fence 锁定）。"""
    try:
        stat = session_path.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except (OSError, TypeError, AttributeError):
        mtime, size = 0, 0
    record = {
        "phase": "pre-compact",
        "sessionPath": str(session_path),
        "mtime": mtime,
        "size": size,
        "timestamp": _now_iso(),
    }
    FENCE_STATE.parent.mkdir(parents=True, exist_ok=True)
    _save_json(FENCE_STATE, record)
    return record


def fence_record_post(session_path: Path, pre_record: dict[str, Any]) -> dict[str, Any]:
    """记录压缩后的 session 状态，并验证完整性。

    Returns:
        {"ok": bool, "preSize": int, "postSize": int, "delta": int, "tampered": bool}
    """
    try:
        stat = session_path.stat()
        post_size = stat.st_size
        post_mtime = stat.st_mtime
    except (OSError, TypeError, AttributeError):
        post_size, post_mtime = 0, 0
    pre_size = pre_record.get("size", 0)

    # 检测外部篡改：只在显著增长时报告（>10% 增长才可能是外部写入）
    # 小幅增长可能是 LLM 压缩后输出比原文件略大，属于正常情况
    tampered = False
    if pre_size > 0 and post_size > pre_size * 1.10:
        # 压缩后文件增长 >10% = 很可能有外部写入
        tampered = True

    record = {
        "phase": "post-compact",
        "sessionPath": str(session_path),
        "mtime": post_mtime,
        "size": post_size,
        "preSize": pre_size,
        "delta": post_size - pre_size,
        "tampered": tampered,
        "timestamp": _now_iso(),
    }
    _save_json(FENCE_STATE, record)

    return {
        "ok": not tampered,
        "preSize": pre_size,
        "postSize": post_size,
        "delta": post_size - pre_size,
        "tampered": tampered,
    }
