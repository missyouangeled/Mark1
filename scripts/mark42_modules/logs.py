"""Mark42 日志轮替模块：自动清理旧日志、broker 事件、历史索引。"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .config import (
    ARMOR_STATE, BROKER_DIR, LOG_DIR, MARK42_BROKER_EVENTS,
    MAX_ACTIONS_LINES, MAX_BROKER_EVENTS_MB, MAX_DAEMON_LOG_MB,
    MAX_DAEMON_LOG_LINES, MAX_HISTORY_FILES, MAX_LOG_AGE_DAYS,
)

LOG_ROTATION_STATE = ARMOR_STATE.parent / "log-rotation.json"


def _load_state() -> dict:
    if LOG_ROTATION_STATE.exists():
        try:
            with open(LOG_ROTATION_STATE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"lastRotation": None, "rotationCount": 0}


def _save_state(state: dict) -> None:
    LOG_ROTATION_STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_ROTATION_STATE, "w") as f:
        json.dump(state, f, indent=2)


def _age_days(path: Path) -> float:
    try:
        mtime = path.stat().st_mtime
        return (time.time() - mtime) / 86400
    except OSError:
        return 999


def rotate_history_files() -> dict:
    """清理旧的历史索引文件（超过 MAX_HISTORY_FILES 个或 MAX_LOG_AGE_DAYS 天）。"""
    history_dir = ARMOR_STATE / "history"
    if not history_dir.exists():
        return {"cleaned": 0, "note": "无历史目录"}
    files = sorted(history_dir.glob("memory-index-*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    cleaned = 0
    # 按数量裁剪：保留最近 MAX_HISTORY_FILES 个
    if len(files) > MAX_HISTORY_FILES:
        for f in files[MAX_HISTORY_FILES:]:
            f.unlink()
            cleaned += 1
    # 按时间裁剪：删除超过 MAX_LOG_AGE_DAYS 天的
    for f in list(history_dir.glob("memory-index-*.json")):
        if _age_days(f) > MAX_LOG_AGE_DAYS:
            f.unlink()
            cleaned += 1
    return {"cleaned": cleaned, "remaining": max(0, len(files) - cleaned)}


def rotate_actions_log() -> dict:
    """裁剪 actions.jsonl 尾部保留最近 MAX_ACTIONS_LINES 行。"""
    log_path = ARMOR_STATE / "actions.jsonl"
    if not log_path.exists():
        return {"trimmed": 0, "note": "无 actions 日志"}
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
        if len(lines) <= MAX_ACTIONS_LINES:
            return {"trimmed": 0, "lines": len(lines)}
        kept = lines[-MAX_ACTIONS_LINES:]
        with open(log_path, "w") as f:
            f.writelines(kept)
        return {"trimmed": len(lines) - len(kept), "lines": len(kept)}
    except OSError:
        return {"trimmed": 0, "error": "IO 错误"}


def rotate_broker_events() -> dict:
    """若 broker events.jsonl 超过 MAX_BROKER_EVENTS_MB 则裁剪尾部。"""
    if not MARK42_BROKER_EVENTS.exists():
        return {"trimmed": 0, "note": "无 broker 事件"}
    try:
        size_mb = MARK42_BROKER_EVENTS.stat().st_size / (1024 * 1024)
        if size_mb <= MAX_BROKER_EVENTS_MB:
            return {"sizeMB": round(size_mb, 2), "trimmed": 0}
        # 保留尾部的量 = 总行数 * (MAX_BROKER_EVENTS_MB / size_mb)
        with open(MARK42_BROKER_EVENTS, "r") as f:
            lines = f.readlines()
        keep_count = max(100, int(len(lines) * MAX_BROKER_EVENTS_MB / size_mb))
        kept = lines[-keep_count:]
        with open(MARK42_BROKER_EVENTS, "w") as f:
            f.writelines(kept)
        return {"sizeMB": round(size_mb, 2), "trimmed": len(lines) - len(kept),
                "kept": len(kept)}
    except OSError:
        return {"trimmed": 0, "error": "IO 错误"}


def rotate_daemon_logs() -> dict:
    """检查 daemon 日志大小：单个文件超 MAX_DAEMON_LOG_MB 则截尾。"""
    if not LOG_DIR.exists():
        return {"trimmed": 0, "note": "无日志目录"}
    max_bytes = MAX_DAEMON_LOG_MB * 1024 * 1024
    trimmed_files = 0
    trimmed_lines = 0
    for fpath in sorted(LOG_DIR.glob("*.log")):
        try:
            size = fpath.stat().st_size
            if size <= max_bytes:
                continue
            with open(fpath) as f:
                lines = f.readlines()
            keep = min(MAX_DAEMON_LOG_LINES // 2, len(lines) // 2)
            with open(fpath, "w") as f:
                f.writelines(lines[-keep:])
            trimmed_files += 1
            trimmed_lines += len(lines) - keep
        except OSError:
            pass
    return {"trimmed_files": trimmed_files, "trimmed_lines": trimmed_lines}


def rotate_scratch_old() -> dict:
    """清理超过 MAX_LOG_AGE_DAYS 天且无 .keep 标记的 scratch 目录。"""
    from .config import SCRATCH
    if not SCRATCH.exists():
        return {"cleaned": 0, "note": "无 scratch 目录"}
    cleaned = 0
    for d in SCRATCH.iterdir():
        if not d.is_dir():
            continue
        if (d / ".keep").exists():
            continue
        if _age_days(d) > MAX_LOG_AGE_DAYS:
            import shutil
            shutil.rmtree(d)
            cleaned += 1
    return {"cleaned": cleaned}


def log_rotate(target: str = "all") -> dict:
    """执行日志轮替。target: all / history / actions / broker / scratch"""
    targets = ["daemon", "history", "actions", "broker", "scratch"] if target == "all" else [target]
    results = {}
    now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    if "daemon" in targets:
        results["daemon"] = rotate_daemon_logs()
    if "history" in targets:
        results["history"] = rotate_history_files()
    if "actions" in targets:
        results["actions"] = rotate_actions_log()
    if "broker" in targets:
        results["broker"] = rotate_broker_events()
    if "scratch" in targets:
        results["scratch"] = rotate_scratch_old()
    total = sum(r.get("cleaned", 0) + r.get("trimmed", 0) + r.get("trimmed_files", 0) + r.get("trimmed_lines", 0) for r in results.values())
    state = _load_state()
    state["lastRotation"] = now_str
    state["rotationCount"] = state.get("rotationCount", 0) + 1
    _save_state(state)
    print(f"🧹 日志轮替完成 ({now_str})")
    for k, v in results.items():
        if v.get("cleaned", 0) > 0:
            print(f"   {k}: 删除 {v['cleaned']} 个文件")
        if v.get("trimmed", 0) > 0:
            print(f"   {k}: 裁剪 {v['trimmed']} 行")
        if v.get("trimmed_files", 0) > 0:
            print(f"   {k}: 截尾 {v['trimmed_files']} 个日志 ({v.get('trimmed_lines', 0)} 行)")
    if total == 0:
        print(f"   ℹ️ 无需清理")
    return {"status": "ok", "results": results, "totalItems": total}


def log_rotate_status() -> None:
    """查看日志轮替状态。"""
    state = _load_state()
    print("🧹 日志轮替状态:\n")
    print(f"   上次轮替: {state.get('lastRotation', '从未')}")
    print(f"   累计次数: {state.get('rotationCount', 0)}")
    print(f"\n   阈值:")
    print(f"     历史文件: ≤{MAX_HISTORY_FILES} 个")
    print(f"     actions.jsonl: ≤{MAX_ACTIONS_LINES} 行")
    print(f"     broker events: ≤{MAX_BROKER_EVENTS_MB}MB")
    print(f"     老化天数: {MAX_LOG_AGE_DAYS} 天")
    print(f"\n   当前状态:")
    # armor history
    history_dir = ARMOR_STATE / "history"
    if history_dir.exists():
        count = len(list(history_dir.glob("memory-index-*.json")))
        print(f"     历史索引: {count} 个文件")
    # actions.jsonl
    actions_log = ARMOR_STATE / "actions.jsonl"
    if actions_log.exists():
        lines = sum(1 for _ in open(actions_log))
        print(f"     actions.jsonl: {lines} 行")
    # broker
    if MARK42_BROKER_EVENTS.exists():
        size_mb = MARK42_BROKER_EVENTS.stat().st_size / (1024 * 1024)
        lines = sum(1 for _ in open(MARK42_BROKER_EVENTS))
        print(f"     broker events: {size_mb:.1f}MB ({lines} 行)")
    # scratch
    from .config import SCRATCH
    if SCRATCH.exists():
        dirs = [d for d in SCRATCH.iterdir() if d.is_dir()]
        kept = sum(1 for d in dirs if (d / ".keep").exists())
        print(f"     scratch: {len(dirs)} 个目录 ({kept} 受保护)")
