#!/usr/bin/env python3
"""
系统健康采集器 (Health Collector)

合并了原先三个独立 watcher，按分层节奏执行：
  - 每次运行（~60s）：刷新 supervisor 状态 + 条件重建 broker 视图（事件驱动，dirty 标记）
  - 每 5 次运行（~5min）：追加完整 local-health 诊断 + 强制重建 broker（安全网）

上游：supervisor 状态文件、broker 事件流 + dirty flag
下游：broker events → frontstage 前台回报
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
STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "health-collector"
COUNTER_PATH = STATE_DIR / "run-counter.json"
REPORT_PATH = STATE_DIR / "last-report.json"
LOG_PATH = STATE_DIR / "collector.log"
LOG_ROTATE_MAX_BYTES = 256 * 1024
LOG_ROTATE_KEEP_BYTES = 64 * 1024
FULL_CHECK_EVERY_N = 5  # 60s × 5 ≈ 5min

# broker 事件驱动：dirty flag 路径（由 watcher 写入事件后被置脏）
BROKER_EVENTS_PATH = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "broker" / "events.jsonl"
BROKER_DIRTY_PATH = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "broker" / ".dirty"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


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
            LOG_PATH.write_bytes(b"[collector-log-rotated]\n" + tail)
        except Exception:
            pass
    ts = now_iso()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")


def run_sub_check(label: str, cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    start = time.monotonic()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        elapsed = round(time.monotonic() - start, 3)
        ok = result.returncode == 0
        degraded = result.returncode == 2  # exit 2 = warning/degraded, not a crash
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        first_line = stdout.split("\n")[0] if stdout else ""
        return {
            "label": label,
            "ok": ok,
            "degraded": degraded,
            "exitCode": result.returncode,
            "elapsedMs": int(elapsed * 1000),
            "summary": first_line[:200] if first_line else ("degraded" if degraded else "error" if not ok else "ok"),
            "stderr": stderr[:300] if stderr else None,
        }
    except subprocess.TimeoutExpired:
        elapsed = round(time.monotonic() - start, 3)
        append_log(f"{label}: TIMEOUT ({timeout}s)")
        return {"label": label, "ok": False, "exitCode": -1, "elapsedMs": int(elapsed * 1000), "summary": f"TIMEOUT({timeout}s)", "stderr": f"subprocess timed out after {timeout}s"}
    except Exception as exc:
        elapsed = round(time.monotonic() - start, 3)
        append_log(f"{label}: EXCEPTION {exc}")
        return {"label": label, "ok": False, "exitCode": -2, "elapsedMs": int(elapsed * 1000), "summary": f"EXCEPTION: {exc}", "stderr": str(exc)[:300]}


# ── 耗时基线：每个子检查的最大预期耗时（ms），超过则标 degraded ──
# 基线取正常情况下的 P95 估测值，有 50% 余量
DURATION_BASELINE_MS: dict[str, float] = {
    "supervisor-refresh":    8000,   # ~5s P95 → 8s
    "broker-rebuild":        15000,  # ~10s P95 → 15s
    "stuck-session-detect":  6000,   # ~3s P95 → 6s
    "local-health":          30000,  # ~20s P95 → 30s
}


# ── 监工自动管理（从 task-scheduler 内迁）──

SUPERVISOR_STATUS_PATH = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "supervisor" / "supervisor-status.json"


def _read_supervisor_state() -> dict[str, Any]:
    data = load_json(SUPERVISOR_STATUS_PATH)
    if not data:
        return {"policyMode": "unknown", "taskActive": False}
    svc = data.get("service", {}) if isinstance(data.get("service"), dict) else {}
    return {
        "taskActive": bool(svc.get("taskActive")),
        "policyMode": svc.get("policyMode", "unknown"),
        "lastTaskEndedAt": data.get("lastTaskEndedAt"),
    }


def _count_active_tasks() -> int:
    """扫描 runs.sqlite 统计活跃任务数。"""
    runs_db = Path.home() / ".openclaw" / "tasks" / "runs.sqlite"
    if not runs_db.exists():
        return 0
    try:
        conn = sqlite3.connect(str(runs_db))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM runs WHERE status IN ('running','pending')"
        ).fetchall()
        conn.close()
        return rows[0]["cnt"] if rows else 0
    except Exception:
        return 0


def _call_supervisor_cmd(action: str, task_count: int = 0) -> None:
    if action == "enable":
        args_list = ["--activate-task", "--reason", f"collector-auto-enable({task_count} tasks)"]
    else:
        args_list = ["--deactivate-task", "--reason", "collector-cooldown"]
    try:
        subprocess.run(
            [sys.executable, str(SCRIPTS / "openclaw-supervisor-status.py"),
             "--set-policy-mode", "auto", *args_list, "--print-human"],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except Exception:
        pass


def _auto_manage_supervisor() -> None:
    """自动管理监工：有活跃任务时开启，冷却到期后关闭。"""
    try:
        svc_state = _read_supervisor_state()
        if svc_state.get("policyMode") != "auto":
            return  # force_on/force_off 不干预
        active_tasks = _count_active_tasks()
        if active_tasks > 0 and not svc_state.get("taskActive"):
            _call_supervisor_cmd("enable", active_tasks)
            append_log(f"supervisor auto-enabled ({active_tasks} active tasks)")
        elif active_tasks == 0 and svc_state.get("taskActive"):
            last_ended = svc_state.get("lastTaskEndedAt")
            if last_ended:
                try:
                    ended_ts = datetime.fromisoformat(str(last_ended).replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - ended_ts).total_seconds() > 600:
                        _call_supervisor_cmd("disable")
                        append_log("supervisor auto-disabled (cooldown expired)")
                except Exception:
                    pass
    except Exception:
        pass  # 不影响主健康检查


def main():
    parser = argparse.ArgumentParser(description="Health Collector — 系统健康采集器")
    parser.add_argument("--print-human", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    # ── 计数器：每 N 次做一次完整诊断 ──
    new_count = 1
    old_counter = load_json(COUNTER_PATH)
    if isinstance(old_counter, dict) and "count" in old_counter:
        new_count = int(old_counter.get("count", 0)) + 1
        if new_count > FULL_CHECK_EVERY_N:
            new_count = 1
    do_full = (new_count == FULL_CHECK_EVERY_N)
    save_json(COUNTER_PATH, {"count": new_count, "fullCheckEvery": FULL_CHECK_EVERY_N})

    checks = []

    # ── 轻量层（每次都做）──

    # 1. 刷新 supervisor 状态
    checks.append(run_sub_check(
        "supervisor-refresh",
        [sys.executable, str(SCRIPTS / "openclaw-supervisor-status.py"),
         "--notify-transitions", "--print-human"],
        timeout=30,
    ))

    # 1.5 监工自动管理（从 task-scheduler 内迁；只在 auto 模式干预）
    _auto_manage_supervisor()

    # 2. 重建 broker 视图（事件驱动：只在 dirty 或完整层时才重建）
    broker_should_rebuild = do_full
    dirty_reason = ""
    if BROKER_DIRTY_PATH.exists():
        try:
            dirty_data = load_json(BROKER_DIRTY_PATH)
            dirty_reason = dirty_data.get("reason", "unknown")
            broker_should_rebuild = True
        except Exception:
            broker_should_rebuild = True
            dirty_reason = "parse error"
    if broker_should_rebuild:
        checks.append(run_sub_check(
            "broker-rebuild",
            [sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"),
             "rebuild-views", "--print-json"],
            timeout=30,
        ))
        # 重建后清除 dirty flag
        try:
            BROKER_DIRTY_PATH.unlink(missing_ok=True)
        except Exception:
            pass
        if dirty_reason:
            append_log(f"broker rebuild triggered by dirty flag: {dirty_reason}")
    else:
        append_log("broker rebuild skipped (no new events, not full cycle)")

    # 3. 卡住会话检测（每次轻量层都做，截获主会话阻塞等严重问题）
    checks.append(run_sub_check(
        "stuck-session-detect",
        [sys.executable, str(SCRIPTS / "openclaw-stuck-session-detector.py"),
         "--print-json", "--report"],
        timeout=20,
    ))

    # ── 完整层（每 N 次一次）──
    if do_full:
        checks.append(run_sub_check(
            "local-health",
            [sys.executable, str(SCRIPTS / "openclaw-local-health-diagnose.py"),
             "--notify-frontstage", "--print-human"],
            timeout=60,
        ))
        append_log(f"run #{new_count}: full check triggered (supervisor + broker + local-health)")
    else:
        append_log(f"run #{new_count}: lightweight (supervisor + broker-on-dirty, next full at #{FULL_CHECK_EVERY_N})")

    # ── 耗时基线检查：超过基线标 degraded ──
    latency_flags: list[str] = []
    for c in checks:
        label = c.get("label", "")
        baseline = DURATION_BASELINE_MS.get(label)
        elapsed = c.get("elapsedMs", 0)
        if baseline and elapsed > baseline:
            # 未标记为退化但超时了，追加 degraded 标记
            if not c.get("degraded") and c.get("ok"):
                c["degraded"] = True
                c["degradedReason"] = f"latency {elapsed}ms > baseline {baseline}ms"
                latency_flags.append(f"{label}:{elapsed}ms>{baseline}ms")
    if latency_flags:
        append_log(f"LATENCY_DEGRADED: {', '.join(latency_flags)}")

    # ── 汇总 ──
    # ok: exit 0 only  |  degraded: exit 2 (warning, not a crash)  |  failed: exit 1/exception/timeout
    all_ok = all(c.get("ok") for c in checks)
    any_degraded = any(c.get("degraded") for c in checks)
    any_failed = any((not c.get("ok") and not c.get("degraded")) for c in checks)
    summary = "；".join(c.get("summary", "?") for c in checks)
    if any_failed:
        overall = "❌"
    elif any_degraded or not all_ok:
        overall = "⚠"
    else:
        overall = "OK"

    report = {
        "checkedAt": now_iso(),
        "ok": all_ok,
        "overall": overall,
        "summary": summary,
        "runCount": new_count,
        "fullCheck": do_full,
        "checks": checks,
    }
    save_text(REPORT_PATH, json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    if any_failed:
        failed = [c["label"] for c in checks if not c.get("ok") and not c.get("degraded")]
        append_log(f"ANOMALY overall={overall} failed={','.join(failed)}")
    elif any_degraded:
        degraded_list = [c["label"] for c in checks if c.get("degraded")]
        append_log(f"DEGRADED overall={overall} degraded={','.join(degraded_list)}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human:
        print(f"{overall} - {summary}")
    # exit 0 = all fine or degraded (warning), exit 1 = real failures only
    return 0 if not any_failed else 1


if __name__ == "__main__":
    sys.exit(main())
