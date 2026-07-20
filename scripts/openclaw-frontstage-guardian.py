#!/usr/bin/env python3
"""
前台体验保护器 (Frontstage Guardian)

合并了原先两个独立 watcher：
  - frontstage-recovery-watch: 检测 transcript/history 投影异常
  - responsiveness-watch:      检测主会话响应性

作为 wrapper 调用两者的 CLI 入口，共享同一个调度节拍（每 20s）。
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
RECOVERY_SCRIPT = str(SCRIPTS / "openclaw-frontstage-recovery-watch.py")
RESPONSIVENESS_SCRIPT = str(SCRIPTS / "openclaw-responsiveness-watch.py")
STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "frontstage-guardian"
REPORT_PATH = STATE_DIR / "last-report.json"
LOG_PATH = STATE_DIR / "guardian.log"
BACKOFF_PATH = STATE_DIR / "backoff.json"
LOG_ROTATE_MAX_BYTES = 512 * 1024
LOG_ROTATE_KEEP_BYTES = 128 * 1024

# 退避参数
BACKOFF_ERROR_THRESHOLD = 3   # 连续 ≥3 次 ERROR 进入降频
BACKOFF_SKIP_COUNT = 4        # 降频后每 4 次跳过 1 次（60s→300s）

# broker dirty flag — 发现异常时置脏，触发 health-collector 下一次立即重建
BROKER_DIRTY_PATH = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "broker" / ".dirty"


def _mark_broker_dirty(reason: str = "") -> None:
    """设置 broker dirty flag。"""
    try:
        BROKER_DIRTY_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            "source": "frontstage-guardian",
            "reason": reason,
            "at": now_iso(),
        }, ensure_ascii=False)
        tmp = BROKER_DIRTY_PATH.with_suffix(".dirty.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(BROKER_DIRTY_PATH)
    except Exception:
        pass


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def load_backoff_state() -> dict[str, Any]:
    """读取退避状态文件。"""
    if not BACKOFF_PATH.exists():
        return {"consecutiveErrors": 0, "skipsRemaining": 0}
    try:
        return json.loads(BACKOFF_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"consecutiveErrors": 0, "skipsRemaining": 0}


def save_backoff_state(state: dict[str, Any]) -> None:
    """写入退避状态文件。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state["updatedAt"] = now_iso()
    tmp = BACKOFF_PATH.with_suffix(".backoff.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(BACKOFF_PATH)


def append_log(line: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_ROTATE_MAX_BYTES:
        try:
            raw = LOG_PATH.read_bytes()
            tail = raw[-LOG_ROTATE_KEEP_BYTES:]
            idx = tail.find(b"\n")
            if idx != -1:
                tail = tail[idx + 1:]
            LOG_PATH.write_bytes(b"[guardian-log-rotated]\n" + tail)
        except Exception:
            pass
    ts = now_iso()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")


def run_sub_check(label: str, script: str, args: list[str]) -> dict[str, Any]:
    """Run a sub-check script and return structured result."""
    cmd = [sys.executable, script, *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25, check=False)
        ok = result.returncode == 0
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        # Try to extract a one-line summary from stdout
        first_line = stdout.split("\n")[0] if stdout else ""
        return {
            "label": label,
            "ok": ok,
            "exitCode": result.returncode,
            "summary": first_line[:200] if first_line else ("error" if not ok else "ok"),
            "stderr": stderr[:300] if stderr else None,
        }
    except subprocess.TimeoutExpired:
        append_log(f"{label}: TIMEOUT")
        return {"label": label, "ok": False, "exitCode": -1, "summary": "TIMEOUT", "stderr": "subprocess timed out after 25s"}
    except Exception as exc:
        append_log(f"{label}: EXCEPTION {exc}")
        return {"label": label, "ok": False, "exitCode": -2, "summary": f"EXCEPTION: {exc}", "stderr": str(exc)[:300]}


def main():
    parser = argparse.ArgumentParser(description="Frontstage Guardian — 前台体验保护器")
    parser.add_argument("--print-human", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    parser.add_argument("--no-notify", action="store_true", help="Skip frontstage notification")
    args = parser.parse_args()

    # ── 退避逻辑 ──
    # 若上次连续错误 ≥ 3 次，则降频：每 BACKOFF_SKIP_COUNT 次检查跳过 1 次（60s → 300s 等效）
    bo = load_backoff_state()
    if bo.get("skipsRemaining", 0) > 0:
        bo["skipsRemaining"] -= 1
        save_backoff_state(bo)
        msg = f"SKIPPED (backoff after {bo.get('consecutiveErrors', '?')} consecutive errors, {bo['skipsRemaining']} skips remaining)"
        append_log(msg)
        if args.print_human:
            print(msg)
        elif args.print_json:
            print(json.dumps({"checkedAt": now_iso(), "ok": True, "overall": "SKIPPED", "summary": msg, "checks": []}, ensure_ascii=False))
        return 0

    checks = []

    # 1. 前台恢复观察
    recovery_flags = ["--limit", "500", "--notify-frontstage", "--print-human"]
    if args.no_notify:
        recovery_flags.remove("--notify-frontstage")
    checks.append(run_sub_check("frontstage-recovery", RECOVERY_SCRIPT, recovery_flags))

    # 2. 主会话响应性
    checks.append(run_sub_check("responsiveness", RESPONSIVENESS_SCRIPT, ["--print-human"]))

    # Aggregate
    all_ok = all(c.get("ok") for c in checks)
    summary = "；".join(c.get("summary", "?") for c in checks)
    overall = "OK" if all_ok else "⚠"

    report = {
        "checkedAt": now_iso(),
        "ok": all_ok,
        "overall": overall,
        "summary": summary,
        "checks": checks,
    }
    save_text(REPORT_PATH, json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    # ── 退避状态更新 ──
    if all_ok:
        # 健康恢复 → 重置退避
        bo = {"consecutiveErrors": 0, "skipsRemaining": 0}
        save_backoff_state(bo)
    else:
        bo["consecutiveErrors"] = bo.get("consecutiveErrors", 0) + 1
        if bo["consecutiveErrors"] >= BACKOFF_ERROR_THRESHOLD:
            bo["skipsRemaining"] = BACKOFF_SKIP_COUNT
        save_backoff_state(bo)
        failed = [c["label"] for c in checks if not c.get("ok")]
        append_log(f"ANOMALY overall={overall} failed={','.join(failed)}")
        _mark_broker_dirty(reason=f"guardian detection: {','.join(failed)}")

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human:
        print(f"{overall} - {summary}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
