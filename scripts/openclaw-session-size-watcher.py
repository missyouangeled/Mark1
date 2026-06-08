#!/usr/bin/env python3
"""
会话文件大小监测与自动修复 (Session Size Watcher)

监测当前活跃会话的 JSONL 文件大小，记录增长趋势，
在超过阈值时自动清理旧 checkpoint / trajectory 文件，
减少会话压缩竞态的发生概率。

触发方式：
  - systemd timer（默认每 2 分钟）
  - 手动：python3 scripts/openclaw-session-size-watcher.py --print-human

阈值：
  - INFO:   记录当前大小（始终执行）
  - WARN:   会话 > 2.5MB，记录警告但不触发清理
  - CRITICAL: 会话 > 3.0MB，自动清理旧数据 + 发出 broker 通知
  - FORCE_CLEAN: 总 session 目录 > 50MB，强制清理所有非活跃旧数据

状态目录：
  ~/.local/state/openclaw/session-size-watcher/

用法：
  python3 scripts/openclaw-session-size-watcher.py
  python3 scripts/openclaw-session-size-watcher.py --print-human
  python3 scripts/openclaw-session-size-watcher.py --print-json
  python3 scripts/openclaw-session-size-watcher.py --force-clean
  python3 scripts/openclaw-session-size-watcher.py --init-state
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


# ── 配置 ──────────────────────────────────────────────────

SESSIONS_DIR = Path.home() / ".openclaw/agents/main/sessions"
STATE_DIR = Path.home() / ".local/state/openclaw/session-size-watcher"
STATE_FILE = STATE_DIR / "state.json"

# 阈值 (MB) — 只看总目录大小，不管单个文件
# WARN 已取消（不告警，只记录）
CRITICAL_MB = 40   # 总目录到此开始清理旧数据
FORCE_CLEAN_DIR_MB = 60  # 总目录到此强制大扫除

# 可安全清理的文件类型（非当前活跃会话的）
CLEANABLE_PATTERNS = [
    "*.checkpoint.*.jsonl",   # 旧 checkpoint
    "*.trajectory.jsonl",     # 旧 trajectory
    "*.bak",                  # 备份
    "*.checkpoint.*.jsonl.bak",
]


# ── 核心逻辑 ──────────────────────────────────────────────

def get_current_session_key() -> str | None:
    """找到当前活跃主会话的 key。
    
    策略：
    1. 先查哪個 .jsonl 有对应的 .lock 文件（活会话持有锁）
    2. 若有多个锁，取最近修改的
    3. 若无锁文件，取最近修改的非 checkpoint/trajectory .jsonl
    """
    if not SESSIONS_DIR.exists():
        return None

    # 策略1: 查有锁文件的会话
    lock_files = sorted(
        SESSIONS_DIR.glob("*.jsonl.lock"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for lock_f in lock_files:
        # 去掉 .lock 后缀得到会话 key
        session_key = lock_f.name.replace(".jsonl.lock", "")
        main_f = SESSIONS_DIR / f"{session_key}.jsonl"
        if main_f.exists():
            return session_key

    # 策略2: 找最近修改的主 .jsonl（排除 checkpoint/trajectory）
    candidates = []
    for f in SESSIONS_DIR.glob("*.jsonl"):
        name = f.name
        if ".checkpoint." in name or ".trajectory" in name:
            continue
        if ".reset." in name:
            continue
        candidates.append((f.stat().st_mtime, name))

    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1].replace(".jsonl", "")

    return None


def get_session_files(session_key: str | None) -> dict:
    """获取会话相关文件的大小信息。"""
    if not session_key or not SESSIONS_DIR.exists():
        return {"error": "no-session", "session_key": session_key}

    result = {
        "session_key": session_key,
        "main_jsonl_mb": 0,
        "main_jsonl_bytes": 0,
        "checkpoint_count": 0,
        "checkpoint_mb": 0,
        "trajectory_mb": 0,
        "other_sessions_mb": 0,
        "total_dir_mb": 0,
        "total_dir_bytes": 0,
        "level": "INFO",
        "cleanable_old_mb": 0,
    }

    # 主会话文件
    main_f = SESSIONS_DIR / f"{session_key}.jsonl"
    if main_f.exists():
        size = main_f.stat().st_size
        result["main_jsonl_bytes"] = size
        result["main_jsonl_mb"] = round(size / (1024 * 1024), 2)

    # 本会话的 checkpoint 文件
    checkpoint_total = 0
    for cp in SESSIONS_DIR.glob(f"{session_key}.checkpoint.*.jsonl"):
        checkpoint_total += cp.stat().st_size
        result["checkpoint_count"] += 1
    result["checkpoint_mb"] = round(checkpoint_total / (1024 * 1024), 2)

    # 本会话的 trajectory 文件
    traj_f = SESSIONS_DIR / f"{session_key}.trajectory.jsonl"
    if traj_f.exists():
        result["trajectory_mb"] = round(traj_f.stat().st_size / (1024 * 1024), 2)

    # 其他会话文件大小（非当前 session_key 的）
    other_total = 0
    cleanable_total = 0
    for f in SESSIONS_DIR.iterdir():
        if f.is_file():
            fname = f.name
            if not fname.startswith(session_key):
                other_total += f.stat().st_size
                # 统计可清理的
                if any(f.match(p) for p in CLEANABLE_PATTERNS):
                    cleanable_total += f.stat().st_size

    result["other_sessions_mb"] = round(other_total / (1024 * 1024), 2)
    result["cleanable_old_mb"] = round(cleanable_total / (1024 * 1024), 2)

    # 总目录大小
    total = other_total
    for f in SESSIONS_DIR.glob(f"{session_key}*"):
        if f.is_file():
            total += f.stat().st_size
    result["total_dir_bytes"] = total
    result["total_dir_mb"] = round(total / (1024 * 1024), 2)

    # 判定级别 — 只看总目录大小
    if total > FORCE_CLEAN_DIR_MB * 1024 * 1024:
        result["level"] = "FORCE_CLEAN"
    elif total >= CRITICAL_MB * 1024 * 1024:
        result["level"] = "CRITICAL"
    else:
        result["level"] = "INFO"

    return result


def load_state() -> dict:
    """加载历史状态。"""
    if not STATE_FILE.exists():
        return {"history": [], "cleanups": []}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"history": [], "cleanups": []}


def save_state(state: dict):
    """保存状态。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def append_history(state: dict, file_info: dict):
    """追加一条大小记录。"""
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "time": now,
        "session_key": file_info.get("session_key", "unknown"),
        "main_mb": file_info.get("main_jsonl_mb", 0),
        "total_mb": file_info.get("total_dir_mb", 0),
        "level": file_info.get("level", "INFO"),
    }
    history = state.get("history", [])
    history.append(entry)
    # 只保留最近 200 条
    if len(history) > 200:
        history = history[-200:]
    state["history"] = history


def cleanup_old_session_data(session_key: str) -> dict:
    """清理旧的会话数据。

    三层：
    1. 其他会话的 checkpoint/trajectory/bak — 全清
    2. 当前会话的旧 checkpoint — 只保留最新 1 个
    3. 当前会话的旧 trajectory — OpenClaw 压缩后会重建，旧的可安全删除
    """
    result = {
        "action": "cleanup",
        "files_removed": 0,
        "mb_freed": 0,
        "errors": [],
    }
    if not SESSIONS_DIR.exists():
        return result

    files_removed = 0
    bytes_freed = 0

    for pattern in CLEANABLE_PATTERNS:
        for f in SESSIONS_DIR.glob(pattern):
            if session_key and f.name.startswith(session_key):
                continue
            try:
                size = f.stat().st_size
                f.unlink()
                files_removed += 1
                bytes_freed += size
            except Exception as e:
                result["errors"].append(str(e))

    # 当前会话的旧 checkpoint — 只保留最新 1 个
    if session_key:
        current_checkpoints = sorted(
            SESSIONS_DIR.glob(f"{session_key}.checkpoint.*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for cp in current_checkpoints[1:]:
            try:
                size = cp.stat().st_size
                cp.unlink()
                files_removed += 1
                bytes_freed += size
            except Exception as e:
                result["errors"].append(str(e))

        # 当前会话的 trajectory
        traj_f = SESSIONS_DIR / f"{session_key}.trajectory.jsonl"
        if traj_f.exists():
            try:
                size = traj_f.stat().st_size
                traj_f.unlink()
                files_removed += 1
                bytes_freed += size
            except Exception as e:
                result["errors"].append(str(e))

    result["files_removed"] = files_removed
    result["mb_freed"] = round(bytes_freed / (1024 * 1024), 2)
    return result


def run_check(force_clean: bool = False, gate_seconds: int = 0) -> dict:
    """执行一次完整检测。
    
    gate_seconds: 若 > 0 且上次检测在此秒数内，则只做轻量心跳不扫文件系统。
    """
    state = load_state()

    # 时间门：上次检测太近，跳过完整扫描
    if gate_seconds > 0 and state.get("history"):
        last_entry = state["history"][-1]
        last_time_str = last_entry.get("time", "")
        if last_time_str:
            try:
                last_time = datetime.fromisoformat(last_time_str)
                now = datetime.now(timezone.utc)
                delta = (now - last_time).total_seconds()
                if delta < gate_seconds:
                    # 快速心跳：只更新时间戳，不扫文件
                    state["last_heartbeat"] = now.isoformat()
                    save_state(state)
                    return {
                        "file_info": {
                            "session_key": last_entry.get("session_key", "unknown"),
                            "main_jsonl_mb": last_entry.get("main_mb", 0),
                            "level": last_entry.get("level", "INFO"),
                            "gated": True,
                            "gate_delta_s": round(delta, 1),
                        },
                        "cleanup": None,
                        "state_summary": {
                            "history_count": len(state.get("history", [])),
                            "cleanup_count": len(state.get("cleanups", [])),
                        },
                    }
            except Exception:
                pass

    session_key = get_current_session_key()
    file_info = get_session_files(session_key)
    state = load_state()

    result = {
        "file_info": file_info,
        "cleanup": None,
        "state_summary": {},
    }

    if force_clean or file_info.get("level") in ("CRITICAL", "FORCE_CLEAN"):
        ck = cleanup_old_session_data(session_key or "")
        result["cleanup"] = ck
        if ck["files_removed"] > 0:
            cleanup_record = {
                "time": datetime.now(timezone.utc).isoformat(),
                "trigger": "force_clean" if force_clean else file_info["level"],
                "total_mb": file_info["total_dir_mb"],
                "main_mb": file_info["main_jsonl_mb"],
                "files_removed": ck["files_removed"],
                "mb_freed": ck["mb_freed"],
            }
            state.setdefault("cleanups", []).append(cleanup_record)
            if len(state["cleanups"]) > 100:
                state["cleanups"] = state["cleanups"][-100:]

    append_history(state, file_info)
    save_state(state)

    history = state.get("history", [])
    cleanups = state.get("cleanups", [])
    result["state_summary"] = {
        "history_count": len(history),
        "cleanup_count": len(cleanups),
        "last_cleanup": cleanups[-1] if cleanups else None,
    }

    return result


# ── 输出格式化 ────────────────────────────────────────────

def format_human(result: dict):
    """人类可读输出。"""
    fi = result["file_info"]
    cl = result.get("cleanup")
    ss = result["state_summary"]
    level = fi.get("level", "INFO")

    level_icon = {"INFO": "✅", "WARN": "⚠️", "CRITICAL": "🔴", "FORCE_CLEAN": "🧹"}.get(level, "❓")
    gated = fi.get("gated", False)
    label = f"📋 门控（缓存，{fi.get('gate_delta_s', 0):.0f}s 前刚查过）" if gated else level
    print(f"{level_icon} 会话大小监测 [{label}]")
    print(f"   当前会话 : {fi.get('session_key', 'unknown')}")
    print(f"   主文件   : {fi.get('main_jsonl_mb', 0):.2f} MB")
    print(f"   本会话 checkpoint: {fi.get('checkpoint_count', 0)} 个 ({fi.get('checkpoint_mb', 0):.2f} MB)")
    print(f"   本会话 trajectory: {fi.get('trajectory_mb', 0):.2f} MB")
    print(f"   其他会话 : {fi.get('other_sessions_mb', 0):.2f} MB（其中可清理 {fi.get('cleanable_old_mb', 0):.2f} MB）")
    print(f"   总目录   : {fi.get('total_dir_mb', 0):.2f} MB")

    if cl and cl.get("files_removed", 0) > 0:
        print(f"\n🧹 自动清理完成:")
        print(f"   删除文件 : {cl['files_removed']} 个")
        print(f"   释放空间 : {cl['mb_freed']:.2f} MB")
        if cl.get("errors"):
            for e in cl["errors"]:
                print(f"   ⚠️ 错误: {e}")

    print(f"\n📊 趋势: 共 {ss.get('history_count', 0)} 条记录, {ss.get('cleanup_count', 0)} 次清理")
    if ss.get("last_cleanup"):
        lc = ss["last_cleanup"]
        print(f"   上次清理: {lc.get('time', '?')} — 释放 {lc.get('mb_freed', 0):.2f} MB")
    print(f"\n   阈值: CRITICAL={CRITICAL_MB}MB（总目录）  FORCE_CLEAN={FORCE_CLEAN_DIR_MB}MB  WARN=已关闭")


def format_json(result: dict):
    """JSON 输出。"""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="会话文件大小监测与自动修复")
    parser.add_argument("--print-human", action="store_true", help="人类可读格式")
    parser.add_argument("--print-json", action="store_true", help="JSON 格式")
    parser.add_argument("--force-clean", action="store_true", help="强制清理（无视阈值）")
    parser.add_argument("--init-state", action="store_true", help="初始化状态目录")
    parser.add_argument("--systemd", action="store_true", help="以 systemd 模式运行（总是返回 0）")
    parser.add_argument("--gate-seconds", type=int, default=0, help="时间门：若上次检测在此秒数内则跳过完整扫描（0=不设门）")
    args = parser.parse_args()

    if args.init_state:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"状态目录已就绪: {STATE_DIR}")
        return

    try:
        result = run_check(force_clean=args.force_clean, gate_seconds=args.gate_seconds)

        if args.print_json:
            format_json(result)
        else:
            format_human(result)

        # 退出码：CRITICAL / FORCE_CLEAN 时返回 2；WARN 返回 1（手动模式）
        # systemd 模式或门控命中时总是返回 0
        if args.systemd or result["file_info"].get("gated"):
            sys.exit(0)
        level = result["file_info"].get("level", "INFO")
        if level in ("CRITICAL", "FORCE_CLEAN"):
            sys.exit(2)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"❌ 执行失败: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
