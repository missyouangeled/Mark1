#!/usr/bin/env python3
"""
Jarvis IO Watchdog - 自动检测 + 自动恢复 (H3)

设计目标：
- 监控 OpenClaw gateway 日志中的"工具/IO 失效"征兆
- 阈值触发时自动清缓存（不重启 gateway）
- 写告警到 /tmp/jarvis-alert.txt（不直接发消息，避免自激）
- 接入 Mark42 engine loop，每 5 分钟跑一次

监控关键字（基于 H2 抓到的根因）：
  - "incomplete turn" → MiniMax-M3 stopReason=length
  - "stream ended"    → Ollama fallback 死路（即使现在已清 ollama，留作防御）
  - "DrainingError"   → gateway 重启打断（崩案例 CASE-20260706-003 同型）
  - "context overflow" / "prompt too large" → 7/2 那种假报

阈值：
  - 单 5 分钟 ≥ 3 次 incomplete → 写 L1 告警（"清缓存"）
  - 单 5 分钟 ≥ 5 次 incomplete → 写 L2 告警（"建议 reset session"）
  - 任何 DrainingError → 立即 L1（gateway 刚被打断过）
  - 任何 stream ended → 立即 L2（fallback 链有死路）

参考：
  - 崩坏案例 CASE-20260706-003（不要在 main session 里跑 restart）
  - 崩坏案例 CASE-20260616-002（不要直接写 openclaw.json）
  - 应急恢复手册 memory/daily/2026-07-06-emergency-recovery.md

用法：
  python3 scripts/jarvis-io-watchdog.py --once           # 单次跑
  python3 scripts/jarvis-io-watchdog.py --once --verbose # 单次 + 详细输出
  python3 scripts/jarvis-io-watchdog.py --dry-run        # 只看检测结果不动
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

# ── 路径 ──────────────────────────────────────────────────────────────
WORKSPACE = Path("/home/missyouangeled/.openclaw/workspace")
GATEWAY_LOG_DIR = Path("/tmp/openclaw")
ALERT_FILE = Path("/tmp/jarvis-alert.txt")
STATE_FILE = Path("/tmp/jarvis-io-watchdog.state.json")

# ── 监控关键字（正则）────────────────────────────────────────────
PATTERNS = {
    "incomplete": re.compile(r"incomplete turn", re.IGNORECASE),
    "stream_ended": re.compile(r"stream ended", re.IGNORECASE),
    "draining": re.compile(r"DrainingError", re.IGNORECASE),
    "context_overflow": re.compile(r"context overflow|prompt too large", re.IGNORECASE),
    "tool_failed": re.compile(r"tool.*(?:failed|hang)|exec.*hang|\(see attached image\)", re.IGNORECASE),
}

# ── 阈值 ──────────────────────────────────────────────────────────
THRESHOLDS = {
    "L1_count": 3,     # 5 分钟内 3 次 incomplete → L1
    "L2_count": 5,     # 5 分钟内 5 次 incomplete → L2
    "window_minutes": 5,
}

# ── 严重度排序 ───────────────────────────────────────────────────
SEVERITY_ORDER = {"INFO": 0, "L1": 1, "L2": 2, "CRIT": 3}


def _latest_log() -> Path | None:
    """找最新的 gateway 日志文件。"""
    if not GATEWAY_LOG_DIR.exists():
        return None
    logs = sorted(GATEWAY_LOG_DIR.glob("openclaw-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def _parse_log_window(log_path: Path, window: timedelta) -> Counter:
    """扫日志最近 window 时间内的关键字命中数。"""
    cutoff_ts = (datetime.now() - window).timestamp() * 1000  # ms
    hits: Counter = Counter()
    if not log_path.exists():
        return hits

    # JSONL 格式：每行一个 JSON event
    # 时间字段在 _meta.date (ISO string) 或 _meta.ts (epoch ms)
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 提取时间戳
            ts_ms = None
            if "_meta" in obj and "date" in obj["_meta"]:
                # ISO 8601 — OpenClaw 用 UTC 'Z' 后缀
                try:
                    s = obj["_meta"]["date"]
                    # fromisoformat 3.11+ 直接接受 'Z'
                    try:
                        dt = datetime.fromisoformat(s)
                    except ValueError:
                        # 3.11- 手动处理
                        if s.endswith("Z"):
                            s = s[:-1] + "+00:00"
                        dt = datetime.fromisoformat(s)
                    ts_ms = dt.timestamp() * 1000
                except (ValueError, AttributeError):
                    pass
            if ts_ms is None:
                continue

            if ts_ms < cutoff_ts:
                continue

            # 提取 message 字段
            message = obj.get("message", "") or ""
            if isinstance(message, list):
                message = " ".join(str(m) for m in message)

            # 检查每个 pattern
            for name, pat in PATTERNS.items():
                if pat.search(message):
                    hits[name] += 1
    return hits


def _severity(hits: Counter) -> str:
    """根据命中数判断告警级别。"""
    if hits.get("draining", 0) > 0:
        return "L1"
    if hits.get("stream_ended", 0) > 0:
        return "L2"
    if hits.get("context_overflow", 0) >= 2:
        return "L1"
    incomplete = hits.get("incomplete", 0)
    if incomplete >= THRESHOLDS["L2_count"]:
        return "L2"
    if incomplete >= THRESHOLDS["L1_count"]:
        return "L1"
    if hits.get("tool_failed", 0) >= 2:
        return "L1"
    return "INFO"


def _write_alert(severity: str, hits: Counter, dry_run: bool = False) -> None:
    """写告警到 /tmp/jarvis-alert.txt。"""
    if dry_run:
        print(f"  [DRY-RUN] alert severity={severity} hits={dict(hits)}", file=sys.stderr)
        return

    ts = datetime.now().isoformat(timespec="seconds")
    alert = {
        "ts": ts,
        "severity": severity,
        "hits": dict(hits),
        "window_min": THRESHOLDS["window_minutes"],
        "actions": {
            "L1": [
                "sync && echo 3 | sudo tee /proc/sys/vm/drop_caches",
                "find ~/.openclaw/workspace -name __pycache__ -type d -exec rm -rf {} +",
                "openclaw tasks audit  # 看残留任务",
            ],
            "L2": [
                "见 memory/daily/2026-07-06-emergency-recovery.md 第 3 节",
                "考虑 reset 当前 session jsonl（保留 gateway）",
            ],
        },
    }
    ALERT_FILE.write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✉️  告警 {severity} 已写入 {ALERT_FILE}", file=sys.stderr)


def _should_send_alert(new_sev: str) -> bool:
    """避免重复告警——同一级别 30 分钟内只发一次。"""
    if not STATE_FILE.exists():
        return True
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True
    last_ts = state.get("last_alert_ts")
    last_sev = state.get("last_severity")
    if not last_ts:
        return True
    if last_sev != new_sev:
        return True
    try:
        last_dt = datetime.fromisoformat(last_ts)
        if datetime.now() - last_dt > timedelta(minutes=30):
            return True
    except ValueError:
        return True
    return False


def _save_state(severity: str) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {"last_alert_ts": datetime.now().isoformat(timespec="seconds"), "last_severity": severity},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def run_once(verbose: bool = False, dry_run: bool = False) -> int:
    """单次检测，返回严重度码（0=INFO, 1=L1, 2=L2）。"""
    log = _latest_log()
    if log is None:
        if verbose:
            print(f"  ⚠️  没找到 gateway 日志（{GATEWAY_LOG_DIR}）", file=sys.stderr)
        return 0

    window = timedelta(minutes=THRESHOLDS["window_minutes"])
    hits = _parse_log_window(log, window)
    severity = _severity(hits)

    if verbose:
        print(f"  📄 日志: {log}", file=sys.stderr)
        print(f"  🕒 窗口: 最近 {int(window.total_seconds())}s", file=sys.stderr)
        print(f"  🔍 命中: {dict(hits)}", file=sys.stderr)
        print(f"  📊 严重度: {severity}", file=sys.stderr)

    if severity != "INFO" and _should_send_alert(severity):
        _write_alert(severity, hits, dry_run=dry_run)
        _save_state(severity)
    elif verbose and severity != "INFO":
        print(f"  ⏸  告警 {severity} 在 30 分钟冷却内，跳过", file=sys.stderr)

    return SEVERITY_ORDER.get(severity, 0)


def main() -> int:
    p = argparse.ArgumentParser(description="Jarvis IO Watchdog (H3)")
    p.add_argument("--once", action="store_true", help="单次检测后退出（给 Mark42 engine 调度用）")
    p.add_argument("--dry-run", action="store_true", help="只看检测，不写告警")
    p.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    p.add_argument("--loop", type=int, default=0, help="循环模式，间隔秒数（0=不循环）")
    args = p.parse_args()

    if args.loop > 0:
        if args.verbose:
            print(f"  🔁 循环模式，每 {args.loop}s 检测一次", file=sys.stderr)
        try:
            while True:
                run_once(verbose=args.verbose, dry_run=args.dry_run)
                time.sleep(args.loop)
        except KeyboardInterrupt:
            return 0
    else:
        return run_once(verbose=args.verbose, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
