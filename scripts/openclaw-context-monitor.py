#!/usr/bin/env python3
"""
上下文溢出主动防御监控器 (Context Overflow Monitor)

Mark1 (公司 Linux) / Mark2 通用。

每 5 分钟检查当前活跃 session 的上下文使用率，三级阈值告警：
  - 70%: 静默记录 + broker 事件
  - 85%: broker 告警 + frontstage 推送（建议 /compact）
  - 95%: 紧急告警，写入紧急事件（建议立即 /reset 或 /compact）

数据来源：
  - 当前活跃 session JSONL（带 .lock 文件）
  - 文件大小 → 校准后 token 估算（14 KB ≈ 1K tokens）
  - 模型上下文窗口从配置读取，默认 131072

集成方式：
  - 独立 timer：每 5 分钟运行一次（推荐）
  - 可选接入 health-collector（修改 collector 添加调用）

用法:
  python3 scripts/openclaw-context-monitor.py --print-human    # 人类可读输出
  python3 scripts/openclaw-context-monitor.py --check           # 写入状态文件 + broker
  python3 scripts/openclaw-context-monitor.py --check --force-notify  # 强制推送到前台
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 常量 ──────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parent.parent
SCRIPTS = WORKSPACE / "scripts"

XDG_STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
STATE_DIR = XDG_STATE / "openclaw" / "context-monitor"
STATUS_PATH = STATE_DIR / "status.json"

# 三级阈值（百分比，可环境变量覆盖）
THRESHOLD_WARN = int(os.environ.get("CONTEXT_MONITOR_WARN_PCT", "70"))   # 提醒
THRESHOLD_ALERT = int(os.environ.get("CONTEXT_MONITOR_ALERT_PCT", "85")) # 告警
THRESHOLD_CRIT = int(os.environ.get("CONTEXT_MONITOR_CRIT_PCT", "95"))   # 紧急

# 校准因子：14 KB JSONL ≈ 1K tokens（来自 2026-06-15 实测校准）
BYTES_PER_KTOKEN = int(os.environ.get("CONTEXT_MONITOR_BYTES_PER_KTOKEN", str(14 * 1024)))

# 活跃 lock 文件最大年龄（秒）：超过此时间视为死 session
ACTIVE_LOCK_MAX_AGE = int(os.environ.get("CONTEXT_MONITOR_LOCK_MAX_AGE", str(120)))

# 默认上下文窗口
DEFAULT_CONTEXT_WINDOW = 131072

# Broker 事件路径
BROKER_EVENTS_PATH = XDG_STATE / "openclaw" / "broker" / "events.jsonl"
BROKER_DIRTY_PATH = XDG_STATE / "openclaw" / "broker" / ".dirty"

# Broker source name（在 snapshot 面板中显示的名字）
BROKER_SOURCE = "context-monitor"

# 去重冷却：同级别事件 10 分钟内不重复发
DEDUP_COOLDOWN_S = 600


# ── 工具函数 ──────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ts() -> float:
    return time.time()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _append_broker_event(event: dict[str, Any]) -> None:
    """追加 broker 事件并标记 dirty。"""
    BROKER_EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BROKER_EVENTS_PATH, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    BROKER_DIRTY_PATH.touch()


# ── 核心逻辑 ──────────────────────────────────────────

def find_active_session(sessions_dir: Path) -> Path | None:
    """找到当前有 .lock 文件的活跃 session JSONL。
    
    选择策略：按修改时间取最新的 .lock 文件，并验证 lock 文件在
    ACTIVE_LOCK_MAX_AGE 秒内被更新过（否则视为死 session）。
    """
    if not sessions_dir.exists():
        return None
    now = time.time()
    lock_files = sorted(sessions_dir.glob("*.jsonl.lock"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    for lock in lock_files:
        age = now - lock.stat().st_mtime
        if age > ACTIVE_LOCK_MAX_AGE:
            continue  # 死 session，跳过
        jsonl_path = Path(str(lock).replace(".lock", ""))
        if jsonl_path.exists():
            return jsonl_path
    return None


def estimate_tokens(session_path: Path) -> dict[str, Any]:
    """估算当前 session 的 token 使用量。"""
    file_size = session_path.stat().st_size
    est_tokens = int(file_size / BYTES_PER_KTOKEN * 1000)
    return {
        "sessionPath": str(session_path),
        "fileSizeBytes": file_size,
        "estimatedTokens": est_tokens,
        "calibrationBytesPerKToken": BYTES_PER_KTOKEN,
    }


def get_context_window() -> int:
    """从 Gateway 配置读取模型上下文窗口，失败时用默认值。"""
    # 尝试从 CLI profile 配置读取
    config_paths = [
        Path.home() / ".openclaw" / "openclaw.json",
        WORKSPACE / "openclaw.json",
    ]
    for cp in config_paths:
        if cp.exists():
            try:
                data = _load_json(cp)
                agents = data.get("agents", {})
                defaults = agents.get("defaults", {})
                models = defaults.get("models", {})
                # 尝试匹配 deepseek
                if models:
                    for model_id, model_cfg in models.items():
                        if "deepseek" in model_id.lower():
                            ctx = model_cfg.get("contextWindow")
                            if ctx:
                                return int(ctx)
            except Exception:
                pass
    return DEFAULT_CONTEXT_WINDOW


def check_context() -> dict[str, Any]:
    """主检查逻辑，返回状态字典。"""
    result = {
        "checkedAt": _now_iso(),
        "host": os.uname().nodename,
        "status": "ok",
        "severity": "ok",
        "summary": "上下文使用率正常",
        "usagePercent": 0,
        "estimatedTokens": 0,
        "contextWindow": DEFAULT_CONTEXT_WINDOW,
        "thresholds": {
            "warn": THRESHOLD_WARN,
            "alert": THRESHOLD_ALERT,
            "crit": THRESHOLD_CRIT,
        },
        "sessionInfo": {},
        "error": None,
    }

    # 找活跃 session
    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    active = find_active_session(sessions_dir)
    if not active:
        result["status"] = "unknown"
        result["severity"] = "warn"
        result["summary"] = "找不到活跃 session（无 .lock 文件）"
        result["error"] = "no_active_session"
        return result

    # 估算 token
    token_info = estimate_tokens(active)
    result["sessionInfo"] = token_info

    est_tokens = token_info["estimatedTokens"]
    result["estimatedTokens"] = est_tokens

    context_window = get_context_window()
    result["contextWindow"] = context_window

    if context_window <= 0:
        result["status"] = "unknown"
        result["severity"] = "warn"
        result["summary"] = "无法确定模型上下文窗口大小"
        result["error"] = "unknown_context_window"
        return result

    usage_pct = round(est_tokens / context_window * 100, 1)
    result["usagePercent"] = usage_pct

    # 三级判定
    if usage_pct >= THRESHOLD_CRIT:
        result["status"] = "critical"
        result["severity"] = "critical"
        result["summary"] = f"🔥 上下文使用率 {usage_pct}%（≥{THRESHOLD_CRIT}%），建议立即 /reset 或 /compact"
    elif usage_pct >= THRESHOLD_ALERT:
        result["status"] = "alert"
        result["severity"] = "error"
        result["summary"] = f"⚠️ 上下文使用率 {usage_pct}%（≥{THRESHOLD_ALERT}%），建议 /compact"
    elif usage_pct >= THRESHOLD_WARN:
        result["status"] = "warn"
        result["severity"] = "warn"
        result["summary"] = f"上下文使用率 {usage_pct}%（≥{THRESHOLD_WARN}%），注意监控"
    else:
        result["status"] = "ok"
        result["severity"] = "ok"
        result["summary"] = f"上下文使用率 {usage_pct}%，正常"

    return result


def write_broker_event(result: dict[str, Any], prev_state: dict[str, Any] | None = None) -> None:
    """
    当 severity ≥ warn 时写入 broker 事件。
    去重：同级别事件 10 分钟内不重复。
    """
    severity = result.get("severity", "ok")
    if severity == "ok":
        return  # 不需要发事件

    # 用传入的旧状态做去重
    prev = prev_state or {}
    prev_severity = prev.get("severity", "ok")
    prev_at = prev.get("checkedAt", "")

    # 如果级别没变且在冷却期内，跳过
    if prev_severity == severity and prev_at:
        try:
            prev_ts = datetime.fromisoformat(prev_at).timestamp()
            if _now_ts() - prev_ts < DEDUP_COOLDOWN_S:
                return
        except Exception:
            pass

    # 级别变化或冷却过期 → 发事件
    usage_pct = result.get("usagePercent", 0)
    event = {
        "recordType": "broker.source.event",
        "source": BROKER_SOURCE,
        "sourceEventType": f"context_monitor.{severity}",
        "sourceEventLabel": f"上下文使用率 {usage_pct}%",
        "sourceView": "health",
        "eventKey": f"context-{severity}-{datetime.now().strftime('%Y%m%d-%H%M')}",
        "sessionKey": "agent:main:main",
        "message": result.get("summary", ""),
        "recordedAt": _now_iso(),
        "metadata": {
            "usagePercent": usage_pct,
            "estimatedTokens": result.get("estimatedTokens", 0),
            "contextWindow": result.get("contextWindow", 0),
            "thresholdAlert": THRESHOLD_ALERT,
            "thresholdCrit": THRESHOLD_CRIT,
        },
    }
    _append_broker_event(event)


# ── 入口 ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="上下文溢出主动防御监控器")
    parser.add_argument("--print-human", action="store_true", help="人类可读输出")
    parser.add_argument("--check", action="store_true", help="执行检查并写入状态文件")
    parser.add_argument("--force-notify", action="store_true", help="强制推送 broker 事件（忽略去重）")
    args = parser.parse_args()

    if not args.print_human and not args.check:
        # 默认 check 模式
        args.check = True

    # 先读旧状态（用于去重），再做检查
    prev_state = _load_json(STATUS_PATH)
    result = check_context()

    # 写入新状态文件
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _save_json(STATUS_PATH, result)

    if args.check:
        write_broker_event(result, prev_state)

    if args.print_human:
        print(f"📊 上下文监控器")
        print(f"   检查时间: {result['checkedAt']}")
        print(f"   状态: {result['status'].upper()} ({result['severity']})")
        print(f"   {result['summary']}")
        si = result.get("sessionInfo", {})
        if si:
            print(f"   Session 文件: {Path(si.get('sessionPath','')).name}")
            print(f"   文件大小: {si.get('fileSizeBytes', 0)/1024:.0f} KB")
            print(f"   估算 Tokens: ~{result.get('estimatedTokens', 0)/1000:.0f}K / {result.get('contextWindow', 0)/1000:.0f}K")
        print(f"   使用率: {result.get('usagePercent', 0)}%")
        print(f"   阈值: WARN={THRESHOLD_WARN}% ALERT={THRESHOLD_ALERT}% CRIT={THRESHOLD_CRIT}%")
        if result.get("error"):
            print(f"   错误: {result['error']}")


if __name__ == "__main__":
    main()
