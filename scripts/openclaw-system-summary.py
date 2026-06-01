#!/usr/bin/env python3
"""
openclaw-system-summary.py — OpenClaw 系统一眼总览

低侵入聚合现有验收入口，不新增 daemon/timer，不替代更细的诊断脚本。

用法：
  python3 scripts/openclaw-system-summary.py --print-human
  python3 scripts/openclaw-system-summary.py --print-json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def run(cmd: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, timeout=timeout, check=False)
        return {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exitCode": -1, "stdout": "", "stderr": f"TIMEOUT({timeout}s)", "cmd": cmd}
    except Exception as exc:
        return {"ok": False, "exitCode": -2, "stdout": "", "stderr": str(exc), "cmd": cmd}


def first_matching_line(text: str, needles: list[str]) -> str:
    for line in text.splitlines():
        if any(needle in line for needle in needles):
            return line.strip()
    return ""


def parse_verify_today(text: str) -> dict[str, Any]:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if "passed" in stripped and "failed" in stripped:
            return {"summary": stripped, "ok": "0 failed" in stripped}
    return {"summary": text.splitlines()[-1].strip() if text.splitlines() else "no output", "ok": False}


def count_openclaw_timers(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip() and "openclaw-" in line])


def git_dirty_summary() -> dict[str, Any]:
    res = run(["git", "status", "--short", "--untracked-files=all"], timeout=10)
    lines = [line for line in res["stdout"].splitlines() if line.strip()] if res["ok"] else []
    system_like_prefixes = (
        " M scripts/", "M  scripts/", "?? scripts/",
        " M docs/", "M  docs/", "?? docs/",
        " M TOOLS.md", "M  TOOLS.md", " M AGENTS.md", "M  AGENTS.md",
        " M HOST_CONTEXT.md", "M  HOST_CONTEXT.md", " M SKILL_CATALOG.md", "M  SKILL_CATALOG.md",
        " M .gitignore", "M  .gitignore", "?? .gitignore",
    )
    system_like = [line for line in lines if line.startswith(system_like_prefixes)]
    memory_like = [line for line in lines if "memory/" in line or ".learnings/" in line]
    return {
        "ok": res["ok"],
        "dirtyCount": len(lines),
        "systemLikeCount": len(system_like),
        "memoryLikeCount": len(memory_like),
        "sample": lines[:12],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw 系统一眼总览")
    parser.add_argument("--print-human", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    checks: dict[str, Any] = {}

    gateway_status = run(["openclaw", "gateway", "status"], timeout=35)
    gateway_lines = gateway_status["stdout"].splitlines()
    runtime_line = first_matching_line(gateway_status["stdout"], ["Runtime:"])
    probe_line = first_matching_line(gateway_status["stdout"], ["Connectivity probe:"])
    checks["gateway"] = {
        "ok": gateway_status["ok"] and "Runtime: running" in gateway_status["stdout"] and "Connectivity probe: ok" in gateway_status["stdout"],
        "summary": "; ".join([line for line in [runtime_line, probe_line] if line]) or (gateway_status["stderr"][:160] if gateway_status["stderr"] else gateway_status["stdout"][:160]),
    }

    security = run(["openclaw", "security", "audit"], timeout=40)
    checks["security"] = {
        "ok": security["ok"] and "0 critical" in security["stdout"] and "0 warn" in security["stdout"],
        "summary": first_matching_line(security["stdout"], ["Summary:"]) or security["stderr"][:160],
    }

    tasks = run(["openclaw", "tasks", "audit"], timeout=40)
    checks["tasks"] = {
        "ok": tasks["ok"] and "0 findings" in tasks["stdout"] and "0 warnings" in tasks["stdout"],
        "summary": first_matching_line(tasks["stdout"], ["Tasks audit:"]) or tasks["stderr"][:160],
    }

    timers = run(["systemctl", "--user", "list-timers", "openclaw-*", "--no-pager", "--no-legend"], timeout=15)
    timer_count = count_openclaw_timers(timers["stdout"]) if timers["ok"] else 0
    checks["watchers"] = {
        "ok": timers["ok"] and timer_count == 5,
        "summary": f"{timer_count}/5 openclaw timers",
    }

    verify = run([sys.executable, str(SCRIPTS / "verify-today-patches.py"), "--print"], timeout=90)
    parsed_verify = parse_verify_today(verify["stdout"])
    checks["patches"] = {
        "ok": verify["ok"] and parsed_verify["ok"],
        "summary": parsed_verify["summary"],
    }

    local_health = run([sys.executable, str(SCRIPTS / "openclaw-local-health-diagnose.py"), "--print-human"], timeout=90)
    local_health_first_line = local_health["stdout"].splitlines()[0].strip() if local_health["stdout"].splitlines() else ""
    checks["localHealth"] = {
        "ok": local_health["ok"] and "OK" in local_health_first_line,
        "summary": local_health_first_line or local_health["stderr"][:160],
    }

    daily_dir = WORKSPACE / "memory" / "daily"
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    daily = daily_dir / f"{today}.md"
    transcript = daily_dir / f"{today}-transcript.md"
    checks["daily"] = {
        "ok": daily.exists() and transcript.exists() and transcript.stat().st_size > 0,
        "summary": f"daily={'yes' if daily.exists() else 'no'} transcript={'yes' if transcript.exists() else 'no'}",
    }

    git_summary = git_dirty_summary()
    checks["git"] = {
        "ok": git_summary["ok"],
        "summary": f"dirty={git_summary['dirtyCount']} systemLike={git_summary['systemLikeCount']} memoryLike={git_summary['memoryLikeCount']}",
        "sample": git_summary["sample"],
    }

    overall_ok = all(item.get("ok") for item in checks.values() if isinstance(item, dict))
    report = {"checkedAt": now_iso(), "ok": overall_ok, "checks": checks}

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        icon = "✅" if overall_ok else "⚠️"
        print(f"{icon} OpenClaw 系统总览 — {'OK' if overall_ok else '需要关注'}")
        for key, item in checks.items():
            cicon = "✅" if item.get("ok") else "⚠️"
            print(f"{cicon} {key:<12} {item.get('summary', '')}")
        if checks.get("git", {}).get("sample"):
            print("\nGit 工作区样例：")
            for line in checks["git"]["sample"]:
                print(f"  {line}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
