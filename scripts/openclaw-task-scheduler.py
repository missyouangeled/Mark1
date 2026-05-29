#!/usr/bin/env python3
"""
任务调度器 (Task Scheduler)

Watcher 体系第 5 个成员：自动管理后台任务的生命周期。
取代之前的"手动判断→手动开监工→手动关监工→手动清理"流程。

每 60s 运行一次：
  1. 扫描 runs.sqlite → 僵尸/静默/并发检测
  2. 任务静默 > 3min → broker 回报前台
  3. 僵尸任务（无活动 > 30min）→ 自动 kill
  4. 终端任务过期 → 标记可清理
  5. 旧会话清理
  （监工自动管理已内迁到 health-collector）

依赖：
  - supervisor-status.py  (开关监工)
  - supervisor-subagent.py (kill 僵尸)
  - frontstage-broker.py   (emit → 前台回报)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"
TASKS_DB = Path.home() / ".openclaw" / "tasks" / "runs.sqlite"
STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "task-scheduler"
STATUS_PATH = STATE_DIR / "status.json"
LOG_PATH = STATE_DIR / "scheduler.log"
TRANSITION_PATH = STATE_DIR / "transition.json"
SUPERVISOR_STATUS_PATH = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "supervisor" / "supervisor-status.json"

# ── 阈值 ──
STALLED_AFTER_S = 180       # 3min 无产出 → 触发前台回报
ZOMBIE_AFTER_S = 1800       # 30min 无活动 → 自动 kill
COOLDOWN_AFTER_DONE_S = 600  # 任务完成后 10min → 自动关监工
TERMINAL_CLEANUP_AFTER_S = 3600  # 1h 后清理终端任务
LOG_ROTATE_MAX_BYTES = 256 * 1024
LOG_ROTATE_KEEP_BYTES = 64 * 1024

# ── 阶段 2 阈值 ──
MAINTENANCE_EVERY_N_CYCLES = 10   # 每 10 次（5min）做一次 tasks maintenance
SESSION_EXPIRY_S = 3600            # 1h 未活动的 old subagent/dashboard 会话清理
SESSION_CLEANUP_EVERY_N_CYCLES = 10  # 每 10 次 扫描并清理旧会话

# ── 阶段 3 阈值 ──
MAX_CONCURRENT_TASKS = 4  # 超过此数视为并发过高
RECENT_FAILURE_WINDOW_S = 600  # 10min 内的失败任务视为"近期"
RETRY_CANDIDATE_DELAY_S = 120  # 失败后等待 2min 再考虑重试

# ── Run count 持久化 ──
RUN_COUNT_PATH = STATE_DIR / "run-count.json"

# ── owner_key 过滤 ──
# 只管理属于当前用户的会话任务
USER_OWNER_PREFIX = "agent:main:"
# 排除的系统标签
EXCLUDE_LABEL_PREFIXES = ["system:cron:", "[noschedule]", "[heartbeat]"]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def now_ms() -> int:
    return int(time.time() * 1000)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    save_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def append_log(line: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_ROTATE_MAX_BYTES:
        try:
            raw = LOG_PATH.read_bytes()
            tail = raw[-LOG_ROTATE_KEEP_BYTES:]
            idx = tail.find(b"\n")
            if idx != -1:
                tail = tail[idx + 1:]
            LOG_PATH.write_bytes(b"[scheduler-log-rotated]\n" + tail)
        except Exception:
            pass
    ts = now_iso()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")


def is_user_task(label: str | None, owner_key: str | None) -> bool:
    """判断任务是否属于当前用户（需要调度器管理）。"""
    if not owner_key or not owner_key.startswith(USER_OWNER_PREFIX):
        return False
    # 排除主会话的持久 running 任务（不是可调度的工作任务）
    if owner_key == "agent:main:main" and not label:
        return False
    if label:
        for prefix in EXCLUDE_LABEL_PREFIXES:
            if label.startswith(prefix):
                return False
    return True


def get_db() -> sqlite3.Connection | None:
    if not TASKS_DB.exists():
        return None
    conn = sqlite3.connect(str(TASKS_DB))
    conn.row_factory = sqlite3.Row
    return conn


def scan_active_tasks(conn: sqlite3.Connection | None, now_ms_val: int) -> list[dict[str, Any]]:
    """扫描所有 running 状态的用户任务。"""
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT task_id, label, status, owner_key, child_session_key,
                   created_at, started_at, last_event_at,
                   progress_summary
            FROM task_runs
            WHERE status = 'running'
            ORDER BY COALESCE(last_event_at, started_at, created_at) DESC
            """
        ).fetchall()
    except sqlite3.Error as exc:
        append_log(f"DB_ERROR: {exc}")
        return []

    tasks = []
    for row in rows:
        d = dict(row)
        if not is_user_task(d.get("label"), d.get("owner_key")):
            continue
        created = d.get("created_at") or 0
        started = d.get("started_at") or 0
        last_event = d.get("last_event_at") or 0
        last_activity = max(created, started, last_event)
        silent_s = max(0, int((now_ms_val - last_activity) / 1000)) if last_activity else None
        tasks.append({
            "taskId": d["task_id"],
            "label": d.get("label"),
            "ownerKey": d.get("owner_key"),
            "childSessionKey": d.get("child_session_key"),
            "createdAt": created,
            "lastEventAt": last_event,
            "lastActivityAt": last_activity,
            "silentSeconds": silent_s,
            "stalled": silent_s is not None and silent_s >= STALLED_AFTER_S,
            "zombie": silent_s is not None and silent_s >= ZOMBIE_AFTER_S,
            "progressSummary": d.get("progress_summary"),
        })
    return tasks


def scan_terminal_tasks(conn: sqlite3.Connection | None, now_ms_val: int) -> list[dict[str, Any]]:
    """扫描已完成的用户任务，用于清理判定。"""
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT task_id, label, status, owner_key,
                   created_at, ended_at, last_event_at, error
            FROM task_runs
            WHERE status IN ('succeeded', 'failed', 'cancelled', 'timed_out', 'lost')
            ORDER BY COALESCE(ended_at, last_event_at, created_at) DESC
            LIMIT 50
            """
        ).fetchall()
    except sqlite3.Error:
        return []

    tasks = []
    for row in rows:
        d = dict(row)
        if not is_user_task(d.get("label"), d.get("owner_key")):
            continue
        ended = d.get("ended_at") or d.get("last_event_at") or d.get("created_at") or 0
        age_s = max(0, int((now_ms_val - ended) / 1000)) if ended else None
        tasks.append({
            "taskId": d["task_id"],
            "label": d.get("label"),
            "status": d.get("status"),
            "endedAt": ended,
            "ageSeconds": age_s,
            "readyForCleanup": age_s is not None and age_s >= TERMINAL_CLEANUP_AFTER_S,
            "error": d.get("error"),
        })
    return tasks


def _quick_count_tasks(conn: sqlite3.Connection | None) -> int:
    """快速预检：统计活跃+终端任务数，避免全量扫描。"""
    if conn is None:
        return 0
    try:
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM runs WHERE status IN ('running','pending')"
        ).fetchall()
        return int(rows[0]["cnt"]) if rows else 0
    except (sqlite3.Error, KeyError, TypeError):
        return 0


def read_supervisor_state() -> dict[str, Any]:
    """读取当前监工状态。"""
    data = load_json(SUPERVISOR_STATUS_PATH)
    if not data:
        return {"serviceState": "unavailable", "taskActive": False, "policyMode": "unknown"}
    svc = data.get("service", {}) if isinstance(data.get("service"), dict) else {}
    return {
        "serviceState": svc.get("state", "unknown"),
        "taskActive": bool(svc.get("taskActive")),
        "policyMode": svc.get("policyMode", "unknown"),
        "lastTaskEndedAt": data.get("lastTaskEndedAt"),
        "checkedAt": data.get("checkedAt"),
    }


def call_supervisor_enable() -> tuple[bool, str]:
    """自动开启监工。"""
    cmd = [
        sys.executable, str(SCRIPTS / "openclaw-supervisor-status.py"),
        "--set-policy-mode", "auto",
        "--activate-task",
        "--reason", "scheduler-auto-enable",
        "--print-human",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.returncode == 0, (result.stdout or result.stderr or "").strip()[:200]
    except Exception as exc:
        return False, str(exc)[:200]


def call_supervisor_disable() -> tuple[bool, str]:
    """自动关闭监工。"""
    cmd = [
        sys.executable, str(SCRIPTS / "openclaw-supervisor-status.py"),
        "--set-policy-mode", "auto",
        "--deactivate-task",
        "--reason", "scheduler-cooldown",
        "--print-human",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.returncode == 0, (result.stdout or result.stderr or "").strip()[:200]
    except Exception as exc:
        return False, str(exc)[:200]


def call_kill_zombie(child_session_key: str, task_label: str | None) -> tuple[bool, str]:
    """通过 supervisor-subagent kill 僵尸任务。"""
    cmd = [
        sys.executable, str(SCRIPTS / "openclaw-supervisor-subagent.py"),
        "kill",
        "--session-key", "agent:main:main",
        "--target", child_session_key,
        "--print-json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        ok = result.returncode == 0
        summary = (result.stdout or result.stderr or "").strip()[:200]
        return ok, summary
    except Exception as exc:
        return False, str(exc)[:200]


def call_frontstage_notify(message: str) -> tuple[bool, str]:
    """通过 broker → infos-handle → chat.inject 回报前台。"""
    cmd = [
        sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"),
        "emit",
        "--source", "task-scheduler",
        "--event-key", f"scheduler|notify|{int(time.time())}",
        "--session-key", "agent:main:main",
        "--message", message,
        "--print-json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        ok = result.returncode == 0
        summary = (result.stdout or "").strip()[:200]
        return ok, summary
    except Exception as exc:
        return False, str(exc)[:200]


def notify_stalled(tasks: list[dict[str, Any]]) -> str | None:
    """对静默超过阈值的任务生成回报消息。"""
    stalled = [t for t in tasks if t.get("stalled") and not t.get("zombie")]
    if not stalled:
        return None
    parts = []
    for t in stalled[:3]:  # 最多报 3 个
        label = (t.get("label") or "未命名任务")[:40]
        silent = t.get("silentSeconds", 0)
        parts.append(f"「{label}」已静默 {int(silent)}s")
    return "调度器提醒：" + "；".join(parts) + "。仍在运行中，请稍候。"


# ═══════════════════════════════════════════════════════
#  阶段 2：清理自动化
# ═══════════════════════════════════════════════════════

def get_openclaw_bin() -> str:
    """找到 openclaw CLI 路径。"""
    candidates = [
        os.path.expanduser("~/.nvm/versions/node/v22.22.2/bin/openclaw"),
        "/usr/local/bin/openclaw",
        "/usr/bin/openclaw",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # fallback: try PATH via node
    try:
        result = subprocess.run(["which", "openclaw"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "openclaw"  # last resort


def maybe_run_maintenance(run_count: int, dry_run: bool) -> list[str]:
    """每 N 个周期执行一次 OpenClaw tasks maintenance。"""
    if run_count % MAINTENANCE_EVERY_N_CYCLES != 0:
        return []

    actions = []
    bin_path = get_openclaw_bin()
    cmd = [bin_path, "tasks", "maintenance", "--apply", "--json"]
    try:
        if dry_run:
            actions.append("would-run-maintenance")
            return actions
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout) if result.stdout.strip() else {}
                maint = data.get("maintenance", {}) if isinstance(data, dict) else {}
                tasks_data = maint.get("tasks", {}) if isinstance(maint, dict) else {}
                sessions_data = maint.get("sessions", {}) if isinstance(maint, dict) else {}
                cleaned = tasks_data.get("pruned", 0) + sessions_data.get("pruned", 0)
                actions.append(f"maintenance-applied:cleaned={cleaned}")
                append_log(f"MAINTENANCE OK (cycle={run_count}): cleaned={cleaned}")
            except (json.JSONDecodeError, TypeError):
                actions.append("maintenance-applied")
                append_log(f"MAINTENANCE OK (cycle={run_count})")
        else:
            actions.append(f"maintenance-failed:{result.returncode}")
            append_log(f"MAINTENANCE FAIL: {result.stderr[:120] if result.stderr else 'unknown'}")
    except Exception as exc:
        actions.append(f"maintenance-error:{exc}")
        append_log(f"MAINTENANCE ERROR: {exc}")
    return actions


def maybe_audit_tasks(run_count: int, dry_run: bool) -> list[str]:
    """定期审计任务，发现严重问题回报前台。"""
    if run_count % MAINTENANCE_EVERY_N_CYCLES != 0:
        return []

    actions = []
    bin_path = get_openclaw_bin()
    cmd = [bin_path, "tasks", "audit", "--severity", "error", "--json"]
    try:
        if dry_run:
            actions.append("would-audit-tasks")
            return actions
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            findings = data.get("findings", []) if isinstance(data, dict) else []
            if findings:
                codes = {}
                for f in findings:
                    c = f.get("code", "?")
                    codes[c] = codes.get(c, 0) + 1
                summary = ", ".join(f"{c}x{n}" for c, n in codes.items())
                actions.append(f"audit-findings:{summary}")
                # 有严重问题时回报前台
                severity_codes = ["lost", "cancel_stuck", "stale_running"]
                critical = [c for c in severity_codes if c in codes]
                if critical:
                    msg = f"调度器审计：发现 {len(findings)} 个任务问题（{'，'.join(critical)}），已自动执行维护清理。"
                    call_frontstage_notify(msg)
                    append_log(f"AUDIT notify: {msg[:120]}")
    except Exception as exc:
        actions.append(f"audit-error:{exc}")
    return actions


def maybe_cleanup_sessions(run_count: int, dry_run: bool) -> list[str]:
    """每 N 个周期扫描一次旧 subagent/dashboard 会话并清理。"""
    if run_count % SESSION_CLEANUP_EVERY_N_CYCLES != 0:
        return []

    actions = []
    try:
        if dry_run:
            actions.append("would-scan-sessions")
            return actions

        # 用 supervisor-subagent list 获取子代理
        cmd = [
            sys.executable, str(SCRIPTS / "openclaw-supervisor-subagent.py"),
            "list",
            "--session-key", "agent:main:main",
            "--print-json",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return actions

        data = json.loads(result.stdout) if result.stdout.strip() else {}
        subs = data.get("subagents", []) if isinstance(data, dict) else []
        cleaned = 0
        for s in subs:
            sid = s.get("id", "")
            status = s.get("status", "")
            # 跳过当前活跃的
            if status in ("running", "spawning"):
                continue
            # 跳过监工分身
            label = s.get("label", "") or ""
            if "supervisor" in label.lower() or "guard" in label.lower():
                continue
            # 检查是否是旧会话（通过 status 判断）
            if status in ("done", "failed", "killed", "timed_out", "cancelled"):
                # Attempt kill for cleanup
                kill_cmd = [
                    sys.executable, str(SCRIPTS / "openclaw-supervisor-subagent.py"),
                    "kill",
                    "--session-key", "agent:main:main",
                    "--target", sid,
                    "--print-json",
                ]
                try:
                    kill_result = subprocess.run(kill_cmd, capture_output=True, text=True, timeout=15)
                    if kill_result.returncode == 0:
                        cleaned += 1
                        append_log(f"SESSION CLEANUP: killed old subagent {sid[:20]} status={status}")
                except Exception:
                    pass

        if cleaned > 0:
            actions.append(f"sessions-cleaned:{cleaned}")
    except Exception as exc:
        append_log(f"SESSION SCAN ERROR: {exc}")

    return actions


# ═══════════════════════════════════════════════════════
#  阶段 3：智能调度
# ═══════════════════════════════════════════════════════

def check_concurrency(active_tasks: list[dict[str, Any]], sup_enabled: bool) -> list[str]:
    """并发控制：active 任务超过阈值时告警。"""
    actions = []
    active_count = len(active_tasks)
    if active_count > MAX_CONCURRENT_TASKS:
        labels = [t.get("label", "?")[:30] for t in active_tasks[:6]]
        actions.append(f"high-concurrency:{active_count}/{MAX_CONCURRENT_TASKS}")
        # 只在并发数首次超过阈值时或每 5min 提醒一次
        append_log(f"HIGH CONCURRENCY: {active_count} active tasks ({'; '.join(labels)})")
    return actions


def scan_recent_failures(conn: sqlite3.Connection | None, now_ms_val: int) -> list[dict[str, Any]]:
    """扫描近期（10min 内）失败的用户任务。"""
    if conn is None:
        return []
    cutoff_ms = now_ms_val - (RECENT_FAILURE_WINDOW_S * 1000)
    try:
        rows = conn.execute(
            """
            SELECT task_id, label, status, owner_key, run_id,
                   ended_at, error, task
            FROM task_runs
            WHERE status = 'failed'
              AND COALESCE(ended_at, 0) > ?
            ORDER BY ended_at DESC
            LIMIT 10
            """,
            (cutoff_ms,),
        ).fetchall()
    except sqlite3.Error:
        return []

    failures = []
    for row in rows:
        d = dict(row)
        if not is_user_task(d.get("label"), d.get("owner_key")):
            continue
        # 排除 cron 任务失败（这些不会重试）
        label = d.get("label") or ""
        if any(label.startswith(p) for p in EXCLUDE_LABEL_PREFIXES):
            continue
        failures.append({
            "taskId": d["task_id"],
            "label": label,
            "error": (d.get("error") or "")[:200],
            "task": (d.get("task") or "")[:200],
            "endedAt": d.get("ended_at"),
        })
    return failures


def maybe_notify_failures(failures: list[dict[str, Any]]) -> list[str]:
    """对近期失败任务生成通知。"""
    actions = []
    if not failures:
        return actions

    # 去重：检查 transition 里的 lastFailureNotify
    prev = load_json(TRANSITION_PATH)
    prev_key = prev.get("lastFailureKey", "") if isinstance(prev, dict) else ""
    # 用失败任务 ID 拼接唯一 key
    current_key = "|".join(f["taskId"][:8] for f in failures[:3])
    if current_key == prev_key:
        return actions  # 同一批失败，不重复通知

    parts = []
    for f in failures[:3]:
        label = (f["label"] or "未命名任务")[:30]
        err = f["error"][:60] if f["error"] else "未知错误"
        parts.append(f"「{label}」失败：{err}")
    msg = "调度器提醒：近期任务失败——" + "；".join(parts)
    ok, _ = call_frontstage_notify(msg)
    if ok:
        actions.append(f"notify-failures:{len(failures)}")
        append_log(f"NOTIFY failures: {msg[:150]}")
        # 保存去重 key
        data = prev if isinstance(prev, dict) else {}
        data["lastFailureKey"] = current_key
        data["lastFailureAt"] = now_iso()
        save_json(TRANSITION_PATH, data)
    return actions


# ═══════════════════════════════════════════════════════
#  Run count 持久化
# ═══════════════════════════════════════════════════════

def _load_run_count() -> int:
    data = load_json(RUN_COUNT_PATH)
    return (data.get("count", 0) if isinstance(data, dict) else 0)


def _save_run_count(count: int) -> None:
    save_json(RUN_COUNT_PATH, {"count": count, "lastUpdated": now_iso()})


def main():
    parser = argparse.ArgumentParser(description="Task Scheduler — 任务调度器")
    parser.add_argument("--print-human", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只检测，不执行动作")
    args = parser.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    now_val = now_ms()
    conn = get_db()

    # ── 快速预检（闲时跳过全量扫描）──
    active_tasks = []
    terminal_tasks = []
    sup = read_supervisor_state()
    sup_enabled = sup.get("serviceState") in ("armed", "running") or sup.get("taskActive")

    # ── Run count ──
    raw_count = _load_run_count()
    run_count = raw_count + 1
    _save_run_count(run_count)

    # 维护/清理周期强制全扫，其他周期利用快速预检跳过
    is_maintenance_cycle = run_count % MAINTENANCE_EVERY_N_CYCLES == 0
    is_cleanup_cycle = run_count % SESSION_CLEANUP_EVERY_N_CYCLES == 0

    if not is_maintenance_cycle and not is_cleanup_cycle:
        # 快速预检：无活跃/终端任务则跳过全量扫描
        quick_count = _quick_count_tasks(conn)
        if quick_count == 0:
            append_log(f"run #{run_count}: idle, skipping full scan (quick pre-check passed)")
            status_line = "idle (fast skip)"
            report = {
                "checkedAt": now_iso(),
                "ok": True,
                "overall": "idle",
                "summary": status_line,
                "activeTaskCount": 0,
                "stalledCount": 0,
                "zombieCount": 0,
                "terminalCount": 0,
                "supervisorEnabled": sup_enabled,
                "actions": [],
                "skipped": True,
            }
            save_text(STATUS_PATH, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            if args.print_json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            elif args.print_human:
                print("idle - fast skip")
            conn.close()
            return 0

    # ── 全量扫描 ──
    active_tasks = scan_active_tasks(conn, now_val)
    terminal_tasks = scan_terminal_tasks(conn, now_val)

    # ── 判定 ──
    actions: list[str] = []
    stalled_count = sum(1 for t in active_tasks if t.get("stalled"))
    zombie_count = sum(1 for t in active_tasks if t.get("zombie"))
    ready_cleanup_count = sum(1 for t in terminal_tasks if t.get("readyForCleanup"))
    active_count = len(active_tasks)

    # 1. 监工自动开关已内迁到 health-collector（2026-05-29）
    # task-scheduler 不再管理 supervisor，只做僵尸检测 + 会话清理 + 维护
    # (原 enable/disable 逻辑保留作参考，已禁用)

    # 3. 僵尸任务 → kill
    zombies = [t for t in active_tasks if t.get("zombie")]
    for z in zombies:
        child_key = z.get("childSessionKey")
        label = z.get("label")
        if child_key:
            if not args.dry_run:
                ok, msg = call_kill_zombie(child_key, label)
                action = f"kill-zombie:{label[:20]}" if ok else f"kill-failed:{label[:20]}"
                actions.append(action)
                append_log(f"KILL zombie {label}: {'OK' if ok else msg[:100]}")
            else:
                actions.append(f"would-kill-zombie:{label[:20]}")

    # 4. 静默任务 → 回报前台
    if stalled_count > 0:
        msg = notify_stalled(active_tasks)
        if msg:
            prev = load_json(TRANSITION_PATH)
            prev_msg = prev.get("lastStallMessage") if isinstance(prev, dict) else None
            if prev_msg != msg:
                if not args.dry_run:
                    ok, _ = call_frontstage_notify(msg)
                    append_log(f"NOTIFY stalled: {msg[:120]} {'OK' if ok else 'FAIL'}")
                actions.append(f"notify-stalled:{stalled_count}tasks")
                save_json(TRANSITION_PATH, {"lastStallMessage": msg, "lastStallAt": now_iso()})

    # ══════════════════════════════════════════════════
    #  阶段 2：清理自动化
    # ══════════════════════════════════════════════════

    # 5a. 终端任务 → 执行 gateway 维护清理
    actions.extend(maybe_run_maintenance(run_count, args.dry_run))

    # 5b. 任务审计 → 发现严重问题通知前台
    actions.extend(maybe_audit_tasks(run_count, args.dry_run))

    # 5c. 旧会话清理
    actions.extend(maybe_cleanup_sessions(run_count, args.dry_run))

    # 5d. 终端任务计数（从 runs.sqlite 视角）
    if ready_cleanup_count > 0:
        actions.append(f"terminal-ready-cleanup:{ready_cleanup_count}")

    # ══════════════════════════════════════════════════
    #  阶段 3：智能调度
    # ══════════════════════════════════════════════════

    # 6a. 并发控制
    actions.extend(check_concurrency(active_tasks, sup_enabled))

    # 6b. 失败检测
    recent_failures = scan_recent_failures(conn, now_val)
    actions.extend(maybe_notify_failures(recent_failures))

    # ── 汇总 ──
    overall = "idle" if active_count == 0 else ("active" if zombie_count == 0 else "warning")
    active_summary = "；".join(
        f"{(t.get('label') or '?')[:30]} st={int(t.get('silentSeconds',0))}s"
        for t in sorted(active_tasks, key=lambda x: x.get("stalled", False), reverse=True)[:5]
    ) if active_tasks else "无"

    report = {
        "checkedAt": now_iso(),
        "runCount": run_count,
        "activeTaskCount": active_count,
        "stalledTaskCount": stalled_count,
        "zombieTaskCount": zombie_count,
        "terminalReadyCleanupCount": ready_cleanup_count,
        "recentFailureCount": len(recent_failures),
        "supervisorEnabled": sup_enabled,
        "overall": overall,
        "activeSummary": active_summary,
        "actions": actions,
        "activeTasks": [
            {
                "taskId": t["taskId"],
                "label": (t.get("label") or "")[:60],
                "silentSeconds": t.get("silentSeconds"),
                "stalled": t.get("stalled"),
                "zombie": t.get("zombie"),
            }
            for t in active_tasks
        ],
        "recentFailures": [
            {
                "taskId": f["taskId"],
                "label": f["label"],
                "error": f["error"][:100],
            }
            for f in recent_failures[:5]
        ],
    }

    save_json(STATUS_PATH, report)

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human:
        status_line = f"active={active_count} stalled={stalled_count} zombie={zombie_count} sup={'on' if sup_enabled else 'off'}"
        action_line = f"actions: {', '.join(actions) if actions else 'none'}"
        print(f"{overall} - {status_line}")
        print(action_line)

    return 0


if __name__ == "__main__":
    sys.exit(main())
