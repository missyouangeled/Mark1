#!/usr/bin/env python3
"""
会话文件大小监测与自动修复 (Session Size Watcher)

监测会话目录总大小，在超过阈值时自动分层清理旧数据，
减少会话压缩竞态和 I/O 争抢的发生概率。

触发方式：
  - 事件驱动：每次收到用户消息时后台运行（--gate-seconds 60 门控去重）
  - 手动：python3 scripts/openclaw-session-size-watcher.py --print-human

阈值（只看总目录大小）：
  - INFO:   记录当前大小（始终执行），低于 CRITICAL 不做清理
  - CRITICAL: 总目录 > 25MB，清理旧 checkpoint/trajectory/bak/reset
  - FORCE_CLEAN: 总目录 > 40MB，额外清理死会话完整 jsonl（≥4h、不在 sessions.json 索引中）

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
ALERT_FILE = STATE_DIR / "alerts.json"  # 异常告警，启动时检查

# 阈值 (MB) — 只看总目录大小，不管单个文件
# WARN 已取消（不告警，只记录）
CRITICAL_MB = 25   # 总目录到此开始清理旧数据（降低以更早介入）
FORCE_CLEAN_DIR_MB = 40  # 总目录到此强制大扫除

# 可安全清理的文件类型（非当前活跃会话的）
CLEANABLE_PATTERNS = [
    "*.checkpoint.*.jsonl",   # 旧 checkpoint
    "*.trajectory.jsonl",     # 旧 trajectory
    "*.trajectory-path.json", # 旧 trajectory 路径引用
    "*.bak",                  # 备份
    "*.checkpoint.*.jsonl.bak",
    "*.reset.*",              # 重置残留
]

# FORCE_CLEAN 时额外清理：死会话的完整 jsonl（需交叉验证 sessions.json）
DEAD_SESSION_CLEANUP_MIN_AGE_HOURS = 4  # 会话结束后至少 4 小时才清理


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


def raise_alert(level: str, message: str, detail: dict | None = None):
    """写入告警文件，供启动时（BOOT.md）和手动检查时读取。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    alerts = {}
    if ALERT_FILE.exists():
        try:
            alerts = json.loads(ALERT_FILE.read_text())
        except Exception:
            pass
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
    }
    if detail:
        entry["detail"] = detail
    # 按时间倒序，保留最近 20 条
    items = alerts.get("items", [])
    items.insert(0, entry)
    if len(items) > 20:
        items = items[:20]
    alerts["items"] = items
    alerts["unread"] = True
    ALERT_FILE.write_text(json.dumps(alerts, ensure_ascii=False, indent=2))


def mark_alerts_read():
    """标记告警已读。"""
    if ALERT_FILE.exists():
        try:
            alerts = json.loads(ALERT_FILE.read_text())
            alerts["unread"] = False
            ALERT_FILE.write_text(json.dumps(alerts, ensure_ascii=False, indent=2))
        except Exception:
            pass


def get_unread_alerts() -> list[dict]:
    """获取未读告警列表。"""
    if not ALERT_FILE.exists():
        return []
    try:
        alerts = json.loads(ALERT_FILE.read_text())
        if alerts.get("unread"):
            return alerts.get("items", [])
    except Exception:
        pass
    return []


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


def get_alive_session_keys() -> set[str]:
    """从 sessions.json 读取 OpenClaw 知道的活跃/历史会话 key，
    用于判断磁盘上哪些 jsonl 是彻底被遗忘的死会话。
    """
    sessions_json = SESSIONS_DIR / "sessions.json"
    if not sessions_json.exists():
        return set()
    try:
        data = json.loads(sessions_json.read_text())
        keys: set[str] = set()
        for entry in data.values():
            sid = entry.get("sessionId")
            if sid:
                keys.add(sid)
        return keys
    except Exception:
        return set()


def cleanup_dead_sessions(session_key: str) -> dict:
    """清理死会话的完整 jsonl 文件。

    判定死会话：
    1. 不属于当前活跃会话
    2. 不在 sessions.json 索引中（彻底被遗忘）
    3. 且至少 DEAD_SESSION_CLEANUP_MIN_AGE_HOURS 小时未修改
    """
    result = {"files_removed": 0, "mb_freed": 0, "errors": []}
    if not SESSIONS_DIR.exists():
        return result

    alive_keys = get_alive_session_keys()
    now = time.time()
    min_age_s = DEAD_SESSION_CLEANUP_MIN_AGE_HOURS * 3600

    for f in sorted(SESSIONS_DIR.glob("*.jsonl")):
        name = f.name
        if session_key and name.startswith(session_key):
            continue
        if name == "sessions.json":
            continue
        if ".checkpoint." in name or ".trajectory" in name:
            continue

        file_session_key = name.replace(".jsonl", "")
        if file_session_key not in alive_keys:
            try:
                age_h = (now - f.stat().st_mtime) / 3600
                if age_h >= DEAD_SESSION_CLEANUP_MIN_AGE_HOURS:
                    size = f.stat().st_size
                    f.unlink()
                    result["files_removed"] += 1
                    result["mb_freed"] += size / (1024 * 1024)
            except Exception as e:
                result["errors"].append(f"{name}: {e}")

    # 同时清理死会话的 trajectory-path.json
    for f in sorted(SESSIONS_DIR.glob("*.trajectory-path.json")):
        name = f.name
        if session_key and name.startswith(session_key):
            continue
        file_session_key = name.replace(".trajectory-path.json", "")
        if file_session_key not in alive_keys:
            try:
                f.unlink()
            except Exception:
                pass

    result["mb_freed"] = round(result["mb_freed"], 2)
    return result


def cleanup_old_session_data(session_key: str) -> dict:
    """清理旧的会话数据。

    层数：
    1. 其他会话的 checkpoint/trajectory/bak/reset — 全清
    2. 当前会话的旧 checkpoint — 只保留最新 1 个
    3. 当前会话的旧 trajectory — 仅当陈旧时清理
    （死会话完整 jsonl 由 cleanup_dead_sessions() 在 FORCE_CLEAN 时单独处理）
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

        # 当前会话的 trajectory — 仅当明显陈旧时才清理
        # 条件：trajectory 的 mtime 比主 jsonl 早 10 分钟以上（说明是旧压缩的残留，不是当前活跃的）
        traj_f = SESSIONS_DIR / f"{session_key}.trajectory.jsonl"
        main_f = SESSIONS_DIR / f"{session_key}.jsonl"
        if traj_f.exists() and main_f.exists():
            try:
                traj_mtime = traj_f.stat().st_mtime
                main_mtime = main_f.stat().st_mtime
                stale_seconds = main_mtime - traj_mtime
                if stale_seconds > 600:  # 10 分钟以上未更新 = 旧残留
                    size = traj_f.stat().st_size
                    traj_f.unlink()
                    files_removed += 1
                    bytes_freed += size
                # 否则 trajectory 仍在活跃使用，跳过
            except Exception as e:
                result["errors"].append(str(e))

    result["files_removed"] = files_removed
    result["mb_freed"] = round(bytes_freed / (1024 * 1024), 2)

    # 如果有错误，写入告警
    if result["errors"]:
        raise_alert("ERROR", f"清理过程中有 {len(result['errors'])} 个错误",
                     {"errors": result["errors"], "files_removed": files_removed})

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
        is_force = force_clean or file_info.get("level") == "FORCE_CLEAN"
        ck = cleanup_old_session_data(session_key or "")
        if is_force:
            dead = cleanup_dead_sessions(session_key or "")
            if dead["files_removed"] > 0:
                ck["files_removed"] += dead["files_removed"]
                ck["mb_freed"] += dead["mb_freed"]
                ck["mb_freed"] = round(ck["mb_freed"], 2)
                if dead.get("errors"):
                    ck.setdefault("errors", []).extend(dead["errors"])
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

        # 告警触发
        level = file_info.get("level", "INFO")
        if level == "FORCE_CLEAN":
            raise_alert("WARN",
                f"总目录 {file_info['total_dir_mb']:.1f}MB 触发 FORCE_CLEAN，已清理 {ck.get('mb_freed', 0):.2f}MB",
                {"total_mb": file_info["total_dir_mb"], "mb_freed": ck.get("mb_freed", 0)})
        elif level == "CRITICAL" and ck.get("files_removed", 0) == 0:
            # CRITICAL 但无可清理文件 — 可能是当前会话自身膨胀
            if file_info.get("cleanable_old_mb", 0) == 0:
                raise_alert("WARN",
                    f"CRITICAL 但无可清理项（总目录 {file_info['total_dir_mb']:.1f}MB），当前会话自身膨胀，需关注",
                    {"total_mb": file_info["total_dir_mb"], "main_mb": file_info["main_jsonl_mb"]})

    # 检测失败告警
    if file_info.get("error") == "no-session":
        # 统计连续失败次数
        failures = state.get("consecutive_failures", 0) + 1
        state["consecutive_failures"] = failures
        if failures >= 3:
            raise_alert("ERROR", f"连续 {failures} 次无法找到活跃会话，检测链路可能失效")
    else:
        state["consecutive_failures"] = 0

    # 记录最后一次成功运行的来源（用于跨模型可靠性审计）
    state["last_success_run"] = datetime.now(timezone.utc).isoformat()

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
    if not gated:
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

    # 未读告警
    unread = get_unread_alerts()
    if unread:
        print(f"\n🚨 未读告警 ({len(unread)} 条):")
        for a in unread[:5]:
            print(f"   [{a.get('level', '?')}] {a.get('time', '?')[:19]}")
            print(f"   {a.get('message', '')}")
        if len(unread) > 5:
            print(f"   ... 还有 {len(unread) - 5} 条")
        print(f"\n   运行 --mark-read 标记已读")

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
    parser.add_argument("--mark-read", action="store_true", help="标记所有告警已读")
    parser.add_argument("--check-alerts", action="store_true", help="仅检查未读告警（启动时快速检查用）")
    args = parser.parse_args()

    if args.init_state:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"状态目录已就绪: {STATE_DIR}")
        return

    if args.mark_read:
        mark_alerts_read()
        print("✅ 所有告警已标记为已读")
        return

    if args.check_alerts:
        unread = get_unread_alerts()
        if unread:
            print(f"🚨 有 {len(unread)} 条未读告警:")
            for a in unread[:10]:
                print(f"  [{a.get('level', '?')}] {a.get('time', '')[:19]}")
                print(f"  {a.get('message', '')}")
            sys.exit(2)
        else:
            print("✅ 无未读告警，检测链路正常")
            sys.exit(0)
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
