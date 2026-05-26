#!/usr/bin/env python3
"""
系统健康采集器 (Health Collector)

合并了原先三个独立 watcher，按分层节奏执行：
  - 每次运行（~60s）：刷新 supervisor 状态 + 重建 broker 视图
  - 每 5 次运行（~5min）：追加完整 local-health 诊断

上游：supervisor 状态文件、broker 视图
下游：broker events → frontstage 前台回报
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        ok = result.returncode == 0
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        first_line = stdout.split("\n")[0] if stdout else ""
        return {
            "label": label,
            "ok": ok,
            "exitCode": result.returncode,
            "summary": first_line[:200] if first_line else ("error" if not ok else "ok"),
            "stderr": stderr[:300] if stderr else None,
        }
    except subprocess.TimeoutExpired:
        append_log(f"{label}: TIMEOUT ({timeout}s)")
        return {"label": label, "ok": False, "exitCode": -1, "summary": f"TIMEOUT({timeout}s)", "stderr": f"subprocess timed out after {timeout}s"}
    except Exception as exc:
        append_log(f"{label}: EXCEPTION {exc}")
        return {"label": label, "ok": False, "exitCode": -2, "summary": f"EXCEPTION: {exc}", "stderr": str(exc)[:300]}


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

    # 2. 重建 broker 视图
    checks.append(run_sub_check(
        "broker-rebuild",
        [sys.executable, str(SCRIPTS / "openclaw-frontstage-broker.py"),
         "rebuild-views", "--print-json"],
        timeout=30,
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
        append_log(f"run #{new_count}: lightweight (supervisor + broker only, next full at #{FULL_CHECK_EVERY_N})")

    # ── 汇总 ──
    all_ok = all(c.get("ok") for c in checks)
    summary = "；".join(c.get("summary", "?") for c in checks)
    overall = "OK" if all_ok else "⚠"

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

    if not all_ok:
        failed = [c["label"] for c in checks if not c.get("ok")]
        append_log(f"ANOMALY overall={overall} failed={','.join(failed)}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human:
        print(f"{overall} - {summary}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
