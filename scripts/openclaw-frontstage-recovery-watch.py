#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "frontstage-recovery"
REPORT_PATH_NAME = "last-report.json"
NOTIFY_STATE_PATH_NAME = "notify-state.json"
EVENT_LOG_PATH_NAME = "frontstage-recovery-events.log"
DEFAULT_SESSION_KEY = "agent:main:main"
MAX_TRANSCRIPT_MESSAGES = 400
PENDING_CATCHUP_SECONDS = 30
RECENT_END_PENDING_SECONDS = 20
TOOL_XML_PATTERNS = [
    re.compile(r"<tool_call>.*?</tool_call>", re.S | re.I),
    re.compile(r"<function_call>.*?</function_call>", re.S | re.I),
    re.compile(r"<tool_calls>.*?</tool_calls>", re.S | re.I),
    re.compile(r"<function_calls>.*?</function_calls>", re.S | re.I),
]
INLINE_TAG_PATTERN = re.compile(r"\[\[\s*(reply_to_current|reply_to:[^\]]+|audio_as_voice)\s*\]\]", re.I)
OVERSIZED_PLACEHOLDER = "[chat.history omitted: message too large]"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def timestamp_to_ms(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None
    return None


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


def append_log(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line.rstrip() + "\n")


def run_json_command(cmd: list[str]) -> dict[str, Any]:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "command failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid json output: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def resolve_frontstage(session_key: str) -> dict[str, Any]:
    helper_path = Path(__file__).with_name("openclaw-supervisor-subagent.py")
    return run_json_command([
        sys.executable,
        str(helper_path),
        "resolve-frontstage",
        "--session-key",
        session_key,
        "--print-json",
    ])


def fetch_chat_history(session_key: str, limit: int) -> dict[str, Any]:
    return run_json_command([
        "openclaw",
        "gateway",
        "call",
        "chat.history",
        "--params",
        json.dumps({"sessionKey": session_key, "limit": limit}, ensure_ascii=False),
        "--json",
    ])


def fetch_session_snapshot(session_key: str) -> dict[str, Any]:
    payload = run_json_command([
        "openclaw",
        "gateway",
        "call",
        "sessions.list",
        "--params",
        json.dumps({"includeGlobal": True, "includeUnknown": True}, ensure_ascii=False),
        "--json",
    ])
    sessions = payload.get("sessions") if isinstance(payload.get("sessions"), list) else []
    for row in sessions:
        if isinstance(row, dict) and str(row.get("key") or "") == session_key:
            return row
    return {}


def session_file_for_key(session_key: str) -> Path:
    store_path = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
    store = json.loads(store_path.read_text(encoding="utf-8"))
    row = store.get(session_key)
    if not isinstance(row, dict):
        raise RuntimeError(f"unknown session key: {session_key}")
    session_file = row.get("sessionFile")
    if not isinstance(session_file, str) or not session_file.strip():
        raise RuntimeError(f"sessionFile missing for: {session_key}")
    return Path(session_file)


def load_recent_transcript_messages(path: Path) -> list[dict[str, Any]]:
    items: deque[dict[str, Any]] = deque(maxlen=MAX_TRANSCRIPT_MESSAGES)
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("type") != "message":
                continue
            message = payload.get("message")
            if isinstance(message, dict):
                items.append(message)
    return list(items)


def strip_projection_artifacts(text: str) -> str:
    value = text
    for pattern in TOOL_XML_PATTERNS:
        value = pattern.sub(" ", value)
    value = INLINE_TAG_PATTERN.sub(" ", value)
    value = value.replace("NO_REPLY", " ").replace("no_reply", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def extract_text_blocks(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "\n".join(parts)


def summarize_attachment_block(block: dict[str, Any]) -> str:
    attachment = block.get("attachment") if isinstance(block.get("attachment"), dict) else {}
    kind = attachment.get("kind") or block.get("kind") or attachment.get("mimeType") or block.get("mimeType") or "attachment"
    kind_text = str(kind).strip().lower() or "attachment"
    return f"[attachment:{kind_text}]"


def summarize_canvas_block(block: dict[str, Any]) -> str:
    view_id = block.get("viewId") if isinstance(block.get("viewId"), str) else ""
    title = block.get("title") if isinstance(block.get("title"), str) else ""
    surface = block.get("surface") if isinstance(block.get("surface"), str) else ""
    label = view_id.strip() or title.strip() or surface.strip()
    return f"[canvas:{label}]" if label else "[canvas]"


def extract_visible_assistant_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        if block_type == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif block_type == "attachment":
            parts.append(summarize_attachment_block(block))
        elif block_type == "canvas":
            parts.append(summarize_canvas_block(block))
    return "\n".join(parts)


def is_gateway_injected_assistant(message: dict[str, Any]) -> bool:
    return str(message.get("provider") or "") == "openclaw" and str(message.get("model") or "") == "gateway-injected"


def assistant_turn_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "") != "assistant":
            continue
        if is_gateway_injected_assistant(message):
            continue
        raw_text = extract_visible_assistant_content(message.get("content", message.get("text")))
        visible = strip_projection_artifacts(raw_text)
        result.append(
            {
                "text": visible,
                "rawText": raw_text,
                "timestamp": message.get("timestamp"),
                "provider": message.get("provider"),
                "model": message.get("model"),
            }
        )
    return result


def visible_assistant_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "text": item["text"],
            "timestamp": item.get("timestamp"),
            "provider": item.get("provider"),
            "model": item.get("model"),
        }
        for item in assistant_turn_messages(messages)
        if isinstance(item.get("text"), str) and item["text"]
    ]


def parse_tool_result_payload(message: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(message, dict) or str(message.get("role") or "") != "toolResult":
        return {}
    raw_text = extract_text_blocks(message.get("content", message.get("text")))
    if not raw_text.strip():
        return {}
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def yielded_tool_result_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        payload = parse_tool_result_payload(message)
        if str(payload.get("status") or "") != "yielded":
            continue
        raw_text = payload.get("message")
        if not isinstance(raw_text, str):
            continue
        visible = strip_projection_artifacts(raw_text)
        if not visible:
            continue
        result.append(
            {
                "text": visible,
                "rawText": raw_text,
                "timestamp": message.get("timestamp"),
            }
        )
    return result


def latest_user_timestamp(messages: list[dict[str, Any]]) -> Any:
    for message in reversed(messages):
        if isinstance(message, dict) and str(message.get("role") or "") == "user":
            return message.get("timestamp")
    return None


def pick_after_user(messages: list[dict[str, Any]], user_timestamp: Any) -> dict[str, Any] | None:
    if user_timestamp is None:
        return messages[-1] if messages else None
    filtered = [item for item in messages if item.get("timestamp") is None or item.get("timestamp") >= user_timestamp]
    return filtered[-1] if filtered else None


def analyze_projection(transcript_messages: list[dict[str, Any]], history_messages: list[dict[str, Any]], session_snapshot: dict[str, Any]) -> dict[str, Any]:
    transcript_user_ts = latest_user_timestamp(transcript_messages)
    history_user_ts = latest_user_timestamp(history_messages)
    transcript_assistant_turns = assistant_turn_messages(transcript_messages)
    history_assistant_turns = assistant_turn_messages(history_messages)
    transcript_assistants = [
        {
            "text": item["text"],
            "timestamp": item.get("timestamp"),
            "provider": item.get("provider"),
            "model": item.get("model"),
        }
        for item in transcript_assistant_turns
        if isinstance(item.get("text"), str) and item["text"]
    ]
    history_assistants = [
        {
            "text": item["text"],
            "timestamp": item.get("timestamp"),
            "provider": item.get("provider"),
            "model": item.get("model"),
        }
        for item in history_assistant_turns
        if isinstance(item.get("text"), str) and item["text"]
    ]
    transcript_latest = pick_after_user(transcript_assistants, transcript_user_ts)
    history_latest = pick_after_user(history_assistants, history_user_ts)
    transcript_latest_turn = pick_after_user(transcript_assistant_turns, transcript_user_ts)
    history_latest_turn = pick_after_user(history_assistant_turns, history_user_ts)
    transcript_latest_yielded = pick_after_user(yielded_tool_result_messages(transcript_messages), transcript_user_ts)
    history_latest_yielded = pick_after_user(yielded_tool_result_messages(history_messages), history_user_ts)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    transcript_latest_ms = timestamp_to_ms((transcript_latest or {}).get("timestamp"))
    history_latest_ms = timestamp_to_ms((history_latest or {}).get("timestamp"))
    session_has_active_run = bool(session_snapshot.get("hasActiveRun"))
    session_status = str(session_snapshot.get("status") or "")
    session_ended_ms = timestamp_to_ms(session_snapshot.get("endedAt"))
    session_recently_ended = session_ended_ms is not None and now_ms - session_ended_ms <= RECENT_END_PENDING_SECONDS * 1000
    history_behind_transcript = transcript_latest_ms is not None and (history_latest_ms is None or history_latest_ms < transcript_latest_ms)
    recent_catchup_window = transcript_latest_ms is not None and now_ms - transcript_latest_ms <= PENDING_CATCHUP_SECONDS * 1000
    latest_empty_turn = transcript_latest_turn or history_latest_turn
    latest_empty_turn_ms = timestamp_to_ms((latest_empty_turn or {}).get("timestamp"))
    empty_assistant_turn = bool(latest_empty_turn) and not transcript_latest and not history_latest and not (transcript_latest_yielded or history_latest_yielded)
    recent_empty_turn_window = latest_empty_turn_ms is not None and now_ms - latest_empty_turn_ms <= PENDING_CATCHUP_SECONDS * 1000

    pending_projection = False
    pending_reason = None
    if history_behind_transcript and session_has_active_run and session_status == "running":
        pending_projection = True
        pending_reason = "session-active-run"
    elif history_behind_transcript and session_status == "running":
        pending_projection = True
        pending_reason = "session-running"
    elif history_behind_transcript and session_recently_ended:
        pending_projection = True
        pending_reason = "session-recently-ended"
    elif recent_catchup_window and history_behind_transcript:
        pending_projection = True
        pending_reason = "recent-transcript-ahead-of-history"
    elif empty_assistant_turn and session_status == "running":
        pending_projection = True
        pending_reason = "empty-assistant-turn-running"
    elif empty_assistant_turn and session_has_active_run and session_ended_ms is None:
        pending_projection = True
        pending_reason = "empty-assistant-turn-active-run"
    elif empty_assistant_turn and session_recently_ended:
        pending_projection = True
        pending_reason = "empty-assistant-turn-recently-ended"
    elif empty_assistant_turn and recent_empty_turn_window:
        pending_projection = True
        pending_reason = "empty-assistant-turn-recent"

    anomaly_code = None
    detail = "未发现明显异常。"
    if pending_projection:
        if pending_reason == "session-active-run":
            detail = "当前 session 仍有 active run；chat.history 暂时没追上最新 transcript，这轮先按进行中处理。"
        elif pending_reason == "session-running":
            detail = "当前 session 仍处于 running；chat.history 可能还在追赶 transcript，暂不把这轮视为异常。"
        elif pending_reason == "session-recently-ended":
            detail = "当前 session 刚结束不久；chat.history 可能仍在做最终追赶，这轮先按恢复中的短窗口处理。"
        elif pending_reason == "empty-assistant-turn-running":
            detail = "当前 session 仍处于 running；latest assistant turn 还只有空文本/工具阶段，这轮先按进行中处理。"
        elif pending_reason == "empty-assistant-turn-active-run":
            detail = "当前 session 仍有 active run；latest assistant turn 还只有空文本/工具阶段，这轮先按进行中处理。"
        elif pending_reason == "empty-assistant-turn-recently-ended":
            detail = "当前 session 刚结束不久；latest assistant turn 还只有空文本/工具阶段，这轮先按恢复中的短窗口处理。"
        elif pending_reason == "empty-assistant-turn-recent":
            detail = "latest assistant turn 还只有空文本/工具阶段，先给前台一个短暂追赶窗口。"
        else:
            detail = "chat.history 可能还在追赶最新 transcript，暂不把这轮视为异常。"
    elif transcript_latest and not history_latest:
        anomaly_code = "assistant_missing_in_history"
        detail = "transcript 里有可见 assistant 回复，但 chat.history 投影里没有对应稳定结果。"
    elif history_latest and history_latest.get("text") == OVERSIZED_PLACEHOLDER:
        anomaly_code = "history_oversized_placeholder"
        detail = "chat.history 返回了 oversized placeholder，当前前台可能看不到完整稳定文本。"
    elif transcript_latest and history_latest and transcript_latest.get("text") != history_latest.get("text"):
        anomaly_code = "assistant_text_mismatch"
        detail = "transcript 与 chat.history 的最新可见 assistant 文本不一致，可能存在投影/渲染层差异。"
    elif (transcript_latest_yielded or history_latest_yielded) and not transcript_latest and not history_latest and not session_has_active_run and session_status != "running":
        anomaly_code = "yielded_tool_result_missing_visible_reply"
        detail = "主会话已经收到带 message 的 yielded 结果，但它没有投影成可见 assistant 回复；前台会表现成“三个点消失了，但没回字”。"
    elif (transcript_latest_turn or history_latest_turn) and not transcript_latest and not history_latest:
        anomaly_code = "assistant_turn_missing_visible_text"
        detail = "latest assistant turn 已经发生，但稳定可见文本为空（例如 silent NO_REPLY 或只剩工具阶段内容）；前台可能会出现“边回边消失”。"

    return {
        "ok": anomaly_code is None,
        "pendingProjection": pending_projection,
        "pendingReason": pending_reason,
        "anomalyCode": anomaly_code,
        "detail": detail,
        "transcriptLatestAssistant": transcript_latest,
        "historyLatestAssistant": history_latest,
        "transcriptLatestAssistantTurn": transcript_latest_turn,
        "historyLatestAssistantTurn": history_latest_turn,
        "transcriptLatestYielded": transcript_latest_yielded,
        "historyLatestYielded": history_latest_yielded,
        "transcriptAssistantCount": len(transcript_assistants),
        "historyAssistantCount": len(history_assistants),
        "transcriptAssistantTurnCount": len(transcript_assistant_turns),
        "historyAssistantTurnCount": len(history_assistant_turns),
    }


def anomaly_anchor(report: dict[str, Any]) -> str:
    anomaly_code = str(report.get("anomalyCode") or "")
    transcript_latest = report.get("transcriptLatestAssistant") if isinstance(report.get("transcriptLatestAssistant"), dict) else {}
    history_latest = report.get("historyLatestAssistant") if isinstance(report.get("historyLatestAssistant"), dict) else {}
    transcript_latest_turn = report.get("transcriptLatestAssistantTurn") if isinstance(report.get("transcriptLatestAssistantTurn"), dict) else {}
    history_latest_turn = report.get("historyLatestAssistantTurn") if isinstance(report.get("historyLatestAssistantTurn"), dict) else {}
    transcript_latest_yielded = report.get("transcriptLatestYielded") if isinstance(report.get("transcriptLatestYielded"), dict) else {}
    history_latest_yielded = report.get("historyLatestYielded") if isinstance(report.get("historyLatestYielded"), dict) else {}
    if anomaly_code == "assistant_missing_in_history":
        return str(transcript_latest.get("timestamp") or transcript_latest.get("text") or "unknown")
    if anomaly_code == "history_oversized_placeholder":
        return str(history_latest.get("timestamp") or report.get("chatHistorySessionId") or "unknown")
    if anomaly_code == "assistant_text_mismatch":
        return f"{transcript_latest.get('timestamp') or transcript_latest.get('text') or 'unknown'}|{history_latest.get('timestamp') or history_latest.get('text') or 'unknown'}"
    if anomaly_code == "assistant_turn_missing_visible_text":
        return f"{transcript_latest_turn.get('timestamp') or transcript_latest_turn.get('rawText') or 'unknown'}|{history_latest_turn.get('timestamp') or history_latest_turn.get('rawText') or 'unknown'}"
    if anomaly_code == "yielded_tool_result_missing_visible_reply":
        yielded = transcript_latest_yielded or history_latest_yielded
        return str(yielded.get("timestamp") or yielded.get("text") or "unknown")
    return str(report.get("checkedAt") or "unknown")


def is_real_anomaly(report: dict[str, Any]) -> bool:
    return not bool(report.get("ok")) and not bool(report.get("pendingProjection")) and bool(report.get("anomalyCode"))


def build_notification_candidate(previous_report: dict[str, Any], previous_notify: dict[str, Any], current_report: dict[str, Any]) -> dict[str, Any] | None:
    previous_anomaly = is_real_anomaly(previous_report)
    current_anomaly = is_real_anomaly(current_report)
    current_pending = bool(current_report.get("pendingProjection"))
    previous_notify_status = str(previous_notify.get("status") or "")
    previous_notify_event_key = str(previous_notify.get("eventKey") or "")
    previous_notify_anomaly_code = previous_notify.get("anomalyCode")
    session_key = str(current_report.get("requestedSessionKey") or DEFAULT_SESSION_KEY)
    target_session_key = str(current_report.get("targetSessionKey") or session_key)

    if current_anomaly:
        current_anchor = anomaly_anchor(current_report)
        previous_anchor = anomaly_anchor(previous_report) if previous_anomaly else None
        if (
            previous_anomaly
            and previous_report.get("anomalyCode") == current_report.get("anomalyCode")
            and previous_report.get("targetSessionKey") == target_session_key
            and previous_anchor == current_anchor
        ):
            return None
        anomaly_code = current_report.get("anomalyCode")
        yielded_current = current_report.get("transcriptLatestYielded") if isinstance(current_report.get("transcriptLatestYielded"), dict) else {}
        yielded_history = current_report.get("historyLatestYielded") if isinstance(current_report.get("historyLatestYielded"), dict) else {}
        yielded_message = (yielded_current or yielded_history).get("text") if anomaly_code == "yielded_tool_result_missing_visible_reply" else None
        return {
            "eventKey": f"{current_report.get('anomalyCode')}|{target_session_key}|{current_anchor}",
            "sessionKey": session_key,
            "status": "replayed" if isinstance(yielded_message, str) and yielded_message.strip() else "anomaly",
            "anomalyCode": anomaly_code,
            "message": yielded_message if isinstance(yielded_message, str) and yielded_message.strip() else f"[前台恢复观察] 检测到主回复在前台投影里可能不稳定：{current_report.get('detail')}",
        }

    if not current_pending:
        if previous_notify_anomaly_code == "yielded_tool_result_missing_visible_reply":
            return None
        if previous_notify_status == "anomaly" and previous_notify_event_key:
            return {
                "eventKey": f"recovered|{previous_notify_event_key}",
                "sessionKey": session_key,
                "status": "recovered",
                "anomalyCode": previous_notify_anomaly_code,
                "message": "[前台恢复观察] 当前前台投影看起来已恢复稳定。",
            }
        if previous_anomaly and previous_report.get("anomalyCode") != "yielded_tool_result_missing_visible_reply":
            previous_anchor = anomaly_anchor(previous_report)
            return {
                "eventKey": f"recovered|{previous_report.get('anomalyCode')}|{target_session_key}|{previous_anchor}",
                "sessionKey": session_key,
                "status": "recovered",
                "anomalyCode": previous_report.get("anomalyCode"),
                "message": "[前台恢复观察] 当前前台投影看起来已恢复稳定。",
            }

    return None


def maybe_send_frontstage(previous_report: dict[str, Any], current_report: dict[str, Any], state_dir: Path, event_log_path: Path, enabled: bool) -> None:
    if not enabled:
        return

    notify_state_path = state_dir / NOTIFY_STATE_PATH_NAME
    previous_notify = load_json(notify_state_path)
    candidate = build_notification_candidate(previous_report, previous_notify, current_report)
    if not candidate:
        return
    if previous_notify.get("eventKey") == candidate["eventKey"]:
        return

    helper_path = Path(__file__).with_name("openclaw-frontstage-broker.py")
    cmd = [
        sys.executable,
        str(helper_path),
        "emit",
        "--source",
        "frontstage-recovery",
        "--event-key",
        str(candidate["eventKey"]),
        "--session-key",
        str(candidate["sessionKey"]),
        "--message",
        str(candidate["message"]),
        "--print-json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        append_log(event_log_path, f"[{current_report.get('checkedAt')}] notify_failed session={candidate['sessionKey']} error={(result.stderr or result.stdout).strip()}")
        return
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        append_log(event_log_path, f"[{current_report.get('checkedAt')}] notify_failed session={candidate['sessionKey']} error=invalid_json")
        return

    notify_state = {
        "sentAt": current_report.get("checkedAt"),
        "eventKey": candidate["eventKey"],
        "status": candidate["status"],
        "anomalyCode": candidate.get("anomalyCode"),
        "sessionKey": candidate["sessionKey"],
        "targetSessionKey": payload.get("targetSessionKey") if isinstance(payload, dict) else None,
        "messageId": payload.get("messageId") if isinstance(payload, dict) else None,
        "message": candidate["message"],
    }
    save_json(notify_state_path, notify_state)
    append_log(event_log_path, f"[{current_report.get('checkedAt')}] notify_sent session={notify_state['sessionKey']} target={notify_state.get('targetSessionKey')} status={notify_state['status']} anomaly={notify_state.get('anomalyCode')} messageId={notify_state.get('messageId')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Watch for frontstage history/transcript projection anomalies")
    parser.add_argument("--session-key", default=DEFAULT_SESSION_KEY, help="Owner/current session key to inspect")
    parser.add_argument("--limit", type=int, default=80, help="chat.history message limit")
    parser.add_argument("--notify-frontstage", action="store_true", help="Send brokered frontstage updates on anomaly/recovery transitions")
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    state_dir = DEFAULT_STATE_DIR
    state_dir.mkdir(parents=True, exist_ok=True)
    report_path = state_dir / REPORT_PATH_NAME
    event_log_path = state_dir / EVENT_LOG_PATH_NAME
    previous_report = load_json(report_path)

    binding = resolve_frontstage(args.session_key)
    target_session_key = str(binding.get("targetSessionKey") or args.session_key)
    session_file = session_file_for_key(target_session_key)
    transcript_messages = load_recent_transcript_messages(session_file)
    history_payload = fetch_chat_history(target_session_key, args.limit)
    history_messages = history_payload.get("messages") if isinstance(history_payload.get("messages"), list) else []
    session_snapshot = fetch_session_snapshot(target_session_key)
    analysis = analyze_projection(transcript_messages, history_messages, session_snapshot)

    report = {
        "checkedAt": now_iso(),
        "requestedSessionKey": args.session_key,
        "targetSessionKey": target_session_key,
        "sessionFile": str(session_file),
        "chatHistorySessionId": history_payload.get("sessionId"),
        "sessionSnapshot": {
            "key": session_snapshot.get("key"),
            "status": session_snapshot.get("status"),
            "hasActiveRun": session_snapshot.get("hasActiveRun"),
            "updatedAt": session_snapshot.get("updatedAt"),
            "startedAt": session_snapshot.get("startedAt"),
            "endedAt": session_snapshot.get("endedAt"),
            "sessionId": session_snapshot.get("sessionId"),
        },
        "paths": {
            "stateDir": str(state_dir),
            "reportFile": str(report_path),
            "notifyState": str(state_dir / NOTIFY_STATE_PATH_NAME),
            "eventLog": str(event_log_path),
        },
        **analysis,
    }
    save_json(report_path, report)
    maybe_send_frontstage(previous_report, report, state_dir, event_log_path, args.notify_frontstage)

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report.get("pendingProjection"):
            print(f"PENDING - {report.get('detail')}")
        else:
            status = "OK" if report.get("ok") else f"ANOMALY:{report.get('anomalyCode')}"
            print(f"{status} - {report.get('detail')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
