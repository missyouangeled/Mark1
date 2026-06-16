"""Mark42 工具函数模块。"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 活跃 session 的 .lock 文件最大年龄（秒），超过视为死 session
LOCK_MAX_AGE = 120

# 从 config 导入常量
from .config import (
    ARMOR_STATE, BROKER_DIR, BROKER_DIRTY, BROKER_SOURCE, BYTES_PER_KTOKEN,
    CONFIG_PATH, DEFAULT_CONTEXT_WINDOW, HEAVY_STATE, MARK42_STATE,
    MARK42_BROKER_EVENTS, MAX_ACTIONS_LINES, MAX_BROKER_EVENTS_MB, MAX_HISTORY_FILES,
    MAX_LOG_AGE_DAYS, SCRATCH, THRESHOLD_ALERT, THRESHOLD_CRIT,
    THRESHOLD_WARN, WORKSPACE, XDG_STATE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()

def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _append_broker(source_view: str, event_type: str, label: str, level: str,
                   summary: str, metadata: dict[str, Any] | None = None) -> None:
    BROKER_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": _now_iso(),
        "source": BROKER_SOURCE,
        "sourceView": source_view,
        "sourceEventType": event_type,
        "label": label,
        "level": level,
        "summary": summary,
        "metadata": metadata or {},
    }
    with open(str(MARK42_BROKER_EVENTS), "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def _run_script(name: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(WORKSPACE / "scripts" / name), *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)

def _find_active_session() -> Path | None:
    """找当前活跃 session：优先用 .lock 文件，按 mtime 取最新。
    
    选择策略：
    1. 找所有 .jsonl.lock 文件，按修改时间排序
    2. 过滤掉 LOCK_MAX_AGE 秒内未更新的死 session
    3. 取最新的活跃 session，回退到对应 JSONL 文件
    4. 无 .lock 文件时回退到按 mtime 取最新 .jsonl
    """
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    now = time.time()
    # 策略 A：.lock 文件
    lock_files = sorted(sessions_dir.glob("*.jsonl.lock"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    for lock in lock_files:
        age = now - lock.stat().st_mtime
        if age > LOCK_MAX_AGE:
            continue  # 死 session
        jsonl_path = Path(str(lock).replace(".lock", ""))
        if jsonl_path.exists():
            return jsonl_path
    # 策略 B：回退——按 mtime 取最新 JSONL
    best = None
    best_mtime = 0
    for candidate in sessions_dir.glob("*.jsonl"):
        if ".meta" in candidate.suffixes or "snapshot" in candidate.name:
            continue
        try:
            mtime = candidate.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = candidate
        except OSError:
            continue
    return best

def _estimate_tokens(session_path: Path) -> dict[str, Any]:
    try:
        size_bytes = session_path.stat().st_size
        tokens = size_bytes // BYTES_PER_KTOKEN * 1000
        file_mb = size_bytes / (1024 * 1024)
        return {"estimatedTokens": tokens, "fileSizeMB": round(file_mb, 2)}
    except OSError:
        return {"estimatedTokens": 0, "fileSizeMB": 0}

def _get_context_window() -> int:
    try:
        cfg = _load_json(CONFIG_PATH)
        return cfg.get("contextWindow", DEFAULT_CONTEXT_WINDOW)
    except Exception:
        return DEFAULT_CONTEXT_WINDOW
