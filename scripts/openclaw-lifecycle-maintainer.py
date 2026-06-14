#!/usr/bin/env python3
"""
生命周期维护器 (Lifecycle Maintainer)

合并了原先两个独立维护任务：
  - daily-transcript-aggregator: 聚合当日所有转录
  - cleanup-temp:                清理过期临时文件
  - chattts-on-demand:           清理过期 ChatTTS 音频（原独立 cron 已并入）

每 15min 运行一次：
  - 每次都做转录聚合
  - 每 2 次（=30min）做一次文件清理
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"
VENV_PYTHON = str(Path.home() / ".local" / "share" / "openclaw-voice-venv311" / "bin" / "python3")
STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "lifecycle-maintainer"
EMBED_PYTHON = Path.home() / ".local/share/openclaw-voice-venv311/bin/python3"
COUNTER_PATH = STATE_DIR / "run-counter.json"
REPORT_PATH = STATE_DIR / "last-report.json"
LOG_PATH = STATE_DIR / "maintainer.log"
LOG_ROTATE_MAX_BYTES = 256 * 1024
LOG_ROTATE_KEEP_BYTES = 64 * 1024
CLEANUP_EVERY_N = 2  # 15min × 2 = 30min (timer changed from 5min to 15min)
DAILY_DATE_KEY = "lastDailyCleanupDate"  # 用于记录上次 daily 清理日期


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
            LOG_PATH.write_bytes(b"[maintainer-log-rotated]\n" + tail)
        except Exception:
            pass
    ts = now_iso()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {line}\n")


def run_sub_check(label: str, cmd: list[str], timeout: int = 120) -> dict[str, Any]:
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
        append_log(f"{label}: TIMEOUT")
        return {"label": label, "ok": False, "exitCode": -1, "summary": "TIMEOUT", "stderr": f"subprocess timed out after {timeout}s"}
    except Exception as exc:
        append_log(f"{label}: EXCEPTION {exc}")
        return {"label": label, "ok": False, "exitCode": -2, "summary": f"EXCEPTION: {exc}", "stderr": str(exc)[:300]}



def ensure_daily_skeleton() -> dict[str, Any]:
    """Ensure today/yesterday daily summary files exist.

    The transcript aggregator writes `YYYY-MM-DD-transcript.md`, while startup
    rules read `YYYY-MM-DD.md` for curated daily notes.  Creating a light
    skeleton avoids ENOENT without invoking a model or doing expensive summary
    work.
    """
    daily_dir = WORKSPACE / "memory" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().astimezone().date()
    created: list[str] = []
    existing: list[str] = []
    for day in (today, today - timedelta(days=1)):
        label = day.isoformat()
        path = daily_dir / f"{label}.md"
        if path.exists():
            existing.append(str(path.relative_to(WORKSPACE)))
            continue
        content = (
            f"# {label} 日常记录\n\n"
            "## 今日摘要\n\n"
            "待整理。\n\n"
            "## 重要事项\n\n"
            "- 暂无。\n\n"
            "## 后续待办\n\n"
            "- 暂无。\n"
        )
        save_text(path, content)
        created.append(str(path.relative_to(WORKSPACE)))
    summary = "created " + ",".join(created) if created else "daily skeletons present"
    return {
        "label": "daily-skeleton",
        "ok": True,
        "exitCode": 0,
        "summary": summary,
        "created": created,
        "existing": existing,
        "stderr": None,
    }

def main():
    parser = argparse.ArgumentParser(description="Lifecycle Maintainer — 生命周期维护器")
    parser.add_argument("--print-human", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    args = parser.parse_args()

    new_count = 1
    old_counter = load_json(COUNTER_PATH)
    if isinstance(old_counter, dict) and "count" in old_counter:
        new_count = int(old_counter.get("count", 0)) + 1
        if new_count > CLEANUP_EVERY_N:
            new_count = 1

    counter_payload = {"count": new_count, "cleanupEvery": CLEANUP_EVERY_N}
    do_cleanup = (new_count == CLEANUP_EVERY_N)

    checks = []

    # 0.5 向量索引增量检查（每次都做，hash 对比，有变化才重建）
    checks.append(run_sub_check(
        "embed-index",
        [VENV_PYTHON, str(SCRIPTS / "memory-embed-index.py"), "--incremental-view"],
        timeout=180,
    ))

    # 1. 每日转录聚合（每次都做）
    checks.append(run_sub_check(
        "transcript-aggregate",
        [sys.executable, str(SCRIPTS / "aggregate-daily-transcript.py")]
    ))

    # 1.5 memory flush 同步（每次都做，汇入 daily 归档）
    checks.append(run_sub_check(
        "flush-memory-sync",
        ["/bin/bash", str(SCRIPTS / "flush-memory-sync.sh")],
        timeout=10,
    ))

    # 1.6 daily 摘要骨架（每次轻量确认，避免启动读取 ENOENT）
    checks.append(ensure_daily_skeleton())

    # 1.8 每日备份清理 + scratch 清理（每天一次，不依赖计数器）
    today_str = str(datetime.now().astimezone().date())
    do_daily = old_counter.get(DAILY_DATE_KEY) != today_str if isinstance(old_counter, dict) else True
    if do_daily:
        counter_payload[DAILY_DATE_KEY] = today_str
        checks.append(run_sub_check(
            "backup-cleanup",
            [sys.executable, str(SCRIPTS / "openclaw-session-backup.py"), "--clean", "7"],
            timeout=30,
        ))
        checks.append(run_sub_check(
            "scratch-cleanup",
            [sys.executable, str(SCRIPTS / "openclaw-scratch-cleanup.py"), "--days", "7"],
            timeout=60,
        ))
        # 每日重建记忆关键词索引 + QMD BM25 reindex（Bug6修复：防止索引变僵尸）
        checks.append(run_sub_check(
            "memory-index-rebuild",
            [sys.executable, str(SCRIPTS / "memory-index-builder.py")],
            timeout=30,
        ))
        # qmd reindex removed upstream (v2026.6.5+); qmd auto-indexes on queries
        append_log(f"daily backup & scratch cleanup triggered (date={today_str})")

    # 2. 临时文件清理 + ChatTTS 过期音频清理（统一入口，每 2 次一次 = 30min）
    if do_cleanup:
        checks.append(run_sub_check(
            "temp-cleanup",
            ["/bin/bash", str(SCRIPTS / "openclaw-cleanup-temp.sh")]
        ))
        # 并入原独立 cron 的 ChatTTS 过期音频清理
        checks.append(run_sub_check(
            "chattts-cleanup",
            ["/bin/bash", str(WORKSPACE / "tools" / "chattts-on-demand" / "cleanup-old-audio.sh"), "--quiet"],
            timeout=120,
        ))
        # 清理 flat memory 文件（压缩 flush 产生的扁平 2026-0X-XX.md，内容已在 daily/）
        checks.append(run_sub_check(
            "flat-memory-cleanup",
            ["/bin/bash", "-c", "find /home/missyouangeled/.openclaw/workspace/memory -maxdepth 1 -name '202?-??-??*.md' -not -name 'MEMORY.md' -delete && echo ok || true"],
            timeout=10,
        ))
        append_log(f"run #{new_count}: triggering cleanup (temp + chattts + flat-memory)")
    else:
        append_log(f"run #{new_count}: skip cleanup (next at #{CLEANUP_EVERY_N})")

    all_ok = all(c.get("ok") for c in checks if c.get("label") != "embed-index")
    summary = "；".join(c.get("summary", "?") for c in checks)
    overall = "OK" if all_ok else "⚠"

    # 统一保存计数器（包含 daily 日期标记和 run count）
    save_json(COUNTER_PATH, counter_payload)

    report = {
        "checkedAt": now_iso(),
        "ok": all_ok,
        "overall": overall,
        "summary": summary,
        "runCount": new_count,
        "cleanupRun": do_cleanup,
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
