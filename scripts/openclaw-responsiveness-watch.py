#!/usr/bin/env python3
"""
主会话响应性看门狗 (Main Session Responsiveness Watchdog)

探测模型层无响应：用户发了消息，但超过阈值时间后仍无 assistant 回复。
独立于模型运行（systemd timer），不依赖模型自身响应能力。

检测逻辑：
1. 找当前最活跃的 dashboard 会话
2. 读其 transcript 最后一条消息
3. 若为 user 角色且距今 > 阈值 → 模型无响应
4. 通过 broker → chat.inject 向主会话注入提醒
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

# ---- config ----

DEFAULT_STATE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "responsiveness-watch"
NOTIFY_STATE_PATH_NAME = "notify-state.json"
EVENT_LOG_PATH_NAME = "responsiveness-watch-events.log"
SESSIONS_INDEX_PATH = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"

# 阈值（秒）
WARN_THRESHOLD_S = 30   # 第一次提醒
CRIT_THRESHOLD_S = 60   # 第二次提醒（更紧急）
MAX_BACKOFF_S = 300      # 同一条消息最多提醒间隔

# 心跳（系统在线信号）
HEARTBEAT_IDLE_S = 120   # 上次 assistant 回复后静默超过此时间 → 发心跳
HEARTBEAT_COOLDOWN_S = 600  # 两次心跳最小间隔（10 分钟）

# ---- helpers ----

def now_epoch_s() -> int:
    return int(time.time())


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    tmp.replace(path)


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def timestamp_to_epoch_s(value: Any) -> int | None:
    """Convert various timestamp formats to epoch seconds."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                dt = datetime.strptime(value.replace("Z", "+00:00"), fmt if fmt.endswith("%z") else fmt.replace("Z", "+00:00").replace("z", "+00:00"))
                return int(dt.timestamp())
            except ValueError:
                continue
        # Try ISO
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except (ValueError, TypeError):
            pass
    return None


# ---- core detection ----

def find_active_dashboard_session() -> dict[str, Any] | None:
    """Find the most recently active dashboard session from sessions.json."""
    if not SESSIONS_INDEX_PATH.exists():
        return None

    index = load_json(SESSIONS_INDEX_PATH)
    if not isinstance(index, dict):
        return None

    candidates: list[dict[str, Any]] = []
    for key, info in index.items():
        if not isinstance(info, dict):
            continue
        if "dashboard" in str(key).lower():
            candidates.append({**info, "key": key})

    if not candidates:
        return None

    candidates.sort(key=lambda s: s.get("updatedAt", 0) or 0, reverse=True)
    return candidates[0]


def get_session_transcript_path(session_info: dict[str, Any]) -> Path | None:
    """Resolve the transcript JSONL path for a session."""
    sid = session_info.get("sessionId")
    if not sid:
        return None

    sessions_dir = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
    for pattern in (f"{sid}.jsonl", f"{sid}*.jsonl"):
        matches = sorted(sessions_dir.glob(pattern))
        # Prefer the plain .jsonl (not .trajectory.jsonl)
        for m in matches:
            if ".trajectory." not in m.name:
                return m
        if matches:
            return matches[0]

    return None


def read_transcript_last_message(transcript_path: Path, max_lines: int = 20) -> dict[str, Any] | None:
    """Read the last user/assistant message from a transcript JSONL file.

    Handles both plain format ({"role":"user",...}) and nested format
    ({"type":"message","message":"{\"role\":\"assistant\",...}"} used by dashboard sessions.
    """
    if not transcript_path.exists():
        return None

    try:
        with transcript_path.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return None

    # Look backwards for the last user or assistant message
    for line in reversed(lines[-max_lines:]):
        line = line.strip()
        if not line:
            continue
        try:
            outer = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Handle nested format: {"type":"message","message":"{...}",...}
        role = None
        content = None
        msg_id = None
        msg_ts = None

        if isinstance(outer.get("message"), str):
            try:
                inner = json.loads(outer["message"])
            except (json.JSONDecodeError, TypeError):
                inner = None
            if isinstance(inner, dict):
                role = inner.get("role")
                content = inner.get("content")
                msg_id = outer.get("id") or inner.get("id")
                # Nested format: timestamp is on outer
                msg_ts = outer.get("timestamp")
        else:
            # Plain format: {"role":"user","content":"...","timestamp":"..."}
            role = outer.get("role")
            content = outer.get("content")
            msg_id = outer.get("id")
            msg_ts = outer.get("timestamp")

        if role in ("user", "assistant"):
            return {
                "role": role,
                "content": content,
                "id": msg_id,
                "timestamp": msg_ts,
            }

    return None


def detect_idle_heartbeat() -> dict[str, Any] | None:
    """
    Check if the system is alive but the frontstage has been silent too long.
    Returns a heartbeat result dict, or None if not needed.
    """
    dash = find_active_dashboard_session()
    if not dash:
        return None

    tp = get_session_transcript_path(dash)
    if not tp:
        return None

    last_msg = read_transcript_last_message(tp)
    if not last_msg:
        return None

    # Only heartbeat after assistant replied and system is idle
    role = last_msg.get("role", "")
    if role != "assistant":
        return None

    # Get assistant message timestamp
    ts = last_msg.get("timestamp")
    msg_epoch = timestamp_to_epoch_s(ts)
    if msg_epoch is None:
        msg_epoch = dash.get("updatedAt", 0)
        if isinstance(msg_epoch, (int, float)):
            msg_epoch = int(msg_epoch / 1000)
        else:
            return None

    now = now_epoch_s()
    elapsed = now - msg_epoch

    if elapsed < HEARTBEAT_IDLE_S:
        return None  # Too soon since last message

    return {
        "detectedAt": now_iso(),
        "detectedAtEpoch": now,
        "sessionKey": dash.get("key", "unknown"),
        "sessionId": dash.get("sessionId", "unknown"),
        "lastMessageEpoch": msg_epoch,
        "elapsedSeconds": elapsed,
        "kind": "heartbeat",
        "fingerprint": "heartbeat",
    }


def maybe_heartbeat(hb: dict[str, Any], state_dir: Path, log_path: Path, enabled: bool) -> None:
    """Send a subtle 'I'm alive' heartbeat if cooldown has passed."""
    hb_state_path = state_dir / "heartbeat-state.json"
    prev = load_json(hb_state_path)
    now = hb["detectedAtEpoch"]
    prev_time = prev.get("notifiedAtEpoch", 0)

    if (now - prev_time) < HEARTBEAT_COOLDOWN_S:
        return  # Cooldown not expired

    message = "🫀 系统在线，等待中"

    if enabled:
        success = _inject_via_broker(hb["sessionKey"], message)
    else:
        success = False

    save_json(hb_state_path, {
        "notifiedAt": hb["detectedAt"],
        "notifiedAtEpoch": now,
        "sessionKey": hb["sessionKey"],
        "elapsedSeconds": hb["elapsedSeconds"],
        "injected": success,
    })

    append_log(log_path, f"[{hb['detectedAt']}] 🫀 HEARTBEAT idle={hb['elapsedSeconds']}s injected={success}")


def detect_no_response() -> dict[str, Any] | None:
    """
    Detect if the current dashboard session has a pending user message
    without an assistant response.

    Returns a detection result dict, or None if nothing to report.
    """
    dash = find_active_dashboard_session()
    if not dash:
        return None

    tp = get_session_transcript_path(dash)
    if not tp:
        return None

    last_msg = read_transcript_last_message(tp)
    if not last_msg:
        return None

    role = last_msg.get("role", "")
    if role != "user":
        # Last message is from assistant → model is responding normally
        return None

    # Get message timestamp
    ts = last_msg.get("timestamp")
    msg_epoch = timestamp_to_epoch_s(ts)
    if msg_epoch is None:
        # Fall back to session updatedAt
        msg_epoch = dash.get("updatedAt", 0)
        if isinstance(msg_epoch, (int, float)):
            msg_epoch = int(msg_epoch / 1000)  # ms → s
        else:
            return None

    now = now_epoch_s()
    elapsed = now - msg_epoch

    if elapsed < WARN_THRESHOLD_S:
        return None  # Too soon to worry

    # Build a unique fingerprint for this user message (for dedup)
    content_raw = last_msg.get("content", "")
    # Handle list-type content (e.g., thinking blocks)
    if isinstance(content_raw, list):
        content_preview = " ".join(
            str(item.get("text", item.get("thinking", ""))) if isinstance(item, dict) else str(item)
            for item in content_raw
        )[:80]
    else:
        content_preview = str(content_raw)[:80]
    msg_id = str(last_msg.get("id", "")) or str(last_msg.get("__openclaw", {}).get("id", ""))
    fingerprint = msg_id or content_preview

    severity = "critical" if elapsed >= CRIT_THRESHOLD_S else "warn"

    return {
        "detectedAt": now_iso(),
        "detectedAtEpoch": now,
        "sessionKey": dash.get("key", "unknown"),
        "sessionId": dash.get("sessionId", "unknown"),
        "messageTimestamp": ts,
        "messageEpoch": msg_epoch,
        "elapsedSeconds": elapsed,
        "severity": severity,
        "fingerprint": fingerprint,
        "contentPreview": content_preview,
    }


# ---- notification ----

def maybe_notify(detection: dict[str, Any], state_dir: Path, log_path: Path, enabled: bool) -> None:
    """Decide whether to send a notification, with dedup logic."""
    notify_state_path = state_dir / NOTIFY_STATE_PATH_NAME
    prev = load_json(notify_state_path)

    fingerprint = detection["fingerprint"]
    severity = detection["severity"]
    elapsed = detection["elapsedSeconds"]

    # Dedup: same fingerprint, same severity → already alerted
    prev_fp = prev.get("fingerprint", "")
    prev_severity = prev.get("severity", "")
    prev_time = prev.get("notifiedAtEpoch", 0)
    now = detection["detectedAtEpoch"]

    if prev_fp == fingerprint:
        if prev_severity == severity:
            # Same message, same severity → already sent, don't repeat
            return
        if prev_severity == "critical" and severity == "warn":
            # Already escalated to critical, don't go back to warn
            return
        if prev_severity == "warn" and severity == "critical" and (now - prev_time) < MAX_BACKOFF_S:
            # Allow escalation: warn → critical after threshold
            pass
        else:
            return

    message = build_notification_message(detection)

    # Send via broker → infos-handle → chat.inject
    if enabled:
        success = _inject_via_broker(detection["sessionKey"], message)
    else:
        success = False

    # Update state
    notify_state = {
        "fingerprint": fingerprint,
        "severity": severity,
        "notifiedAt": detection["detectedAt"],
        "notifiedAtEpoch": now,
        "sessionKey": detection["sessionKey"],
        "elapsedSeconds": elapsed,
        "injected": success,
    }
    save_json(notify_state_path, notify_state)

    # Log
    icon = {"warn": "⚠️", "critical": "🚨"}.get(severity, "❓")
    append_log(log_path, f"[{detection['detectedAt']}] {icon} {severity.upper()} elapsed={elapsed}s injected={success} fp={fingerprint[:40]}")


def build_notification_message(detection: dict[str, Any]) -> str:
    elapsed = detection["elapsedSeconds"]
    severity = detection["severity"]

    if severity == "warn":
        return (
            f"⏳ 模型响应可能延迟——你上一条消息已发出 {elapsed} 秒，暂未收到回复。"
            f"可能是网络波动或模型限流，请稍候。若超过 60 秒仍未回复，我会再提醒。"
        )
    else:
        return (
            f"🚨 模型已 {elapsed} 秒无响应，可能被限流/卡死。"
            f"建议：检查网络连接，或尝试切换到备用模型。"
        )


def _inject_via_broker(session_key: str, message: str) -> bool:
    """Inject a message into the target session via the infos-handle contract path."""
    try:
        # Ensure scripts dir is in path for contract module import
        script_dir = str(Path(__file__).resolve().parent)
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)

        from openclaw_infos_handle_contract import (
            build_handle_request_payload,
            invoke_handle_request,
        )

        handle_script = Path(script_dir) / "openclaw-infos-handle.py"
        if not handle_script.exists():
            return False

        event_key = f"responsiveness-watch|{int(time.time() // 15)}"
        payload = build_handle_request_payload(
            request_id=f"responsiveness-watch:{event_key}",
            message=message,
            output_format="text",
            delivery_mode="frontstage",
            frontstage_source="responsiveness-watch",
            frontstage_event_key=event_key,
            session_key=session_key,
        )

        result = invoke_handle_request(
            handle_script=handle_script,
            request_payload=payload,
        )

        # Check if handle was successful (ok=true in response)
        if isinstance(result, dict):
            return result.get("ok", False) is True
        return False
    except Exception:
        return False


# ---- main ----

def main() -> None:
    parser = argparse.ArgumentParser(description="主会话响应性看门狗")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="状态目录")
    parser.add_argument("--dry-run", action="store_true", help="仅检测，不发送提醒")
    parser.add_argument("--print-human", action="store_true", help="输出人类可读结果")
    parser.add_argument("--print-json", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    log_path = state_dir / EVENT_LOG_PATH_NAME
    enabled = not args.dry_run

    detection = detect_no_response()

    if args.print_human:
        if detection is None:
            print("✅ 主会话响应正常（最近一次回复是 assistant，或用户消息未超阈值）")
        else:
            icon = {"warn": "⚠️", "critical": "🚨"}.get(detection["severity"], "❓")
            print(f"{icon} 检测到无响应：已等待 {detection['elapsedSeconds']}s")
            print(f"   会话: {detection['sessionKey']}")
            print(f"   最后用户消息: {detection['contentPreview'][:60]}")
            print(f"   严重程度: {detection['severity']}")
        # Also check heartbeat
        hb = detect_idle_heartbeat()
        if hb:
            print(f"🫀 系统已静默 {hb['elapsedSeconds']}s（会话: {hb['sessionKey']}）")
        else:
            print("🫀 心跳无需发送（静默时间未达阈值）")
        return

    if args.print_json:
        print(json.dumps(detection, ensure_ascii=False, indent=2))
        return

    if detection is not None:
        maybe_notify(detection, state_dir, log_path, enabled)
    else:
        # Clear notify state if model has recovered
        notify_path = state_dir / NOTIFY_STATE_PATH_NAME
        prev = load_json(notify_path)
        if prev:
            append_log(log_path, f"[{now_iso()}] ✅ 模型已恢复响应")
            notify_path.unlink(missing_ok=True)

        # Heartbeat check: system alive but frontstage silent too long?
        if enabled:
            hb = detect_idle_heartbeat()
            if hb:
                maybe_heartbeat(hb, state_dir, log_path, enabled)


if __name__ == "__main__":
    main()
