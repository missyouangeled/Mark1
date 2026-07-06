#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openclaw_infos_handle_contract import build_handle_request_payload, extract_frontstage_notify_payload, invoke_handle_request

DEFAULT_TASKS_DB_PATH = Path.home() / ".openclaw" / "state" / "openclaw.sqlite"
LEGACY_TASKS_DB_PATH = Path.home() / ".openclaw" / "tasks" / "runs.sqlite"
DEFAULT_AGENTS_ROOT = Path.home() / ".openclaw" / "agents"
DEFAULT_STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "supervisor"
STATUS_PATH_NAME = "supervisor-status.json"
CONTROL_PATH_NAME = "service-control.json"
EVENT_LOG_PATH_NAME = "supervisor-events.log"
NOTIFY_STATE_PATH_NAME = "notify-state.json"
DEFAULT_STALLED_AFTER_SECONDS = 180
DEFAULT_TERMINAL_DISPLAY_SECONDS = 180
DEFAULT_FOLLOWUP_WAIT_SECONDS = 600
DEFAULT_SESSION_TAIL_LINES = 16
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "canceled", "timed_out", "lost"}
FAILURE_STATUSES = {"failed", "cancelled", "canceled", "timed_out", "lost"}
NOTIFYABLE_STATUSES = {"stalled", "failed", "done", "waiting"}
ALLOWED_DESIRED_STATES = {"disabled", "armed"}
ALLOWED_POLICY_MODES = {"auto", "force_on", "force_off"}
UNSET = object()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def iso_from_ms(value: int | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def epoch_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


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
        fh.write(line + "\n")


def normalize_desired_state(value: Any) -> str:
    if value in ALLOWED_DESIRED_STATES:
        return str(value)
    return "disabled"


def normalize_policy_mode(value: Any) -> str:
    if value in ALLOWED_POLICY_MODES:
        return str(value)
    return "auto"


def compute_desired_state(policy_mode: str, task_active: bool) -> str:
    normalized_policy = normalize_policy_mode(policy_mode)
    if normalized_policy == "force_on":
        return "armed"
    if normalized_policy == "force_off":
        return "disabled"
    return "armed" if task_active else "disabled"


def normalize_followup_window(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    expires_at_ms = value.get("expiresAtMs")
    if not isinstance(expires_at_ms, int) or expires_at_ms <= 0:
        return None
    started_at_ms = value.get("startedAtMs")
    if not isinstance(started_at_ms, int) or started_at_ms <= 0:
        started_at_ms = max(0, expires_at_ms - DEFAULT_FOLLOWUP_WAIT_SECONDS * 1000)
    return {
        "startedAtMs": started_at_ms,
        "startedAt": value.get("startedAt") or iso_from_ms(started_at_ms),
        "expiresAtMs": expires_at_ms,
        "expiresAt": value.get("expiresAt") or iso_from_ms(expires_at_ms),
        "taskId": value.get("taskId"),
        "taskLabel": value.get("taskLabel"),
        "ownerKey": value.get("ownerKey"),
        "completedAt": value.get("completedAt"),
        "waitSeconds": value.get("waitSeconds") if isinstance(value.get("waitSeconds"), int) else max(0, int((expires_at_ms - started_at_ms) / 1000)),
    }


def is_followup_window_active(window: dict[str, Any] | None, now_ms: int) -> bool:
    if not isinstance(window, dict):
        return False
    expires_at_ms = window.get("expiresAtMs")
    return isinstance(expires_at_ms, int) and expires_at_ms > now_ms


def build_followup_window(task: dict[str, Any], now_ms: int, wait_seconds: int) -> dict[str, Any]:
    expires_at_ms = now_ms + max(0, wait_seconds) * 1000
    return {
        "startedAtMs": now_ms,
        "startedAt": iso_from_ms(now_ms),
        "expiresAtMs": expires_at_ms,
        "expiresAt": iso_from_ms(expires_at_ms),
        "taskId": task.get("taskId"),
        "taskLabel": task.get("label"),
        "ownerKey": task.get("ownerKey"),
        "completedAt": task.get("terminalAt") or task.get("endedAt") or task.get("lastEventAt"),
        "waitSeconds": max(0, wait_seconds),
    }


def followup_window_matches_task(window: dict[str, Any] | None, task: dict[str, Any] | None) -> bool:
    if not isinstance(window, dict) or not isinstance(task, dict):
        return False
    return window.get("taskId") == task.get("taskId") and window.get("completedAt") == (task.get("terminalAt") or task.get("endedAt") or task.get("lastEventAt"))


def load_service_control(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    legacy_desired_state = normalize_desired_state(raw.get("desiredState"))
    policy_mode = normalize_policy_mode(raw.get("policyMode"))
    if "policyMode" in raw:
        task_active = bool(raw.get("taskActive"))
    else:
        task_active = legacy_desired_state == "armed"
    desired_state = compute_desired_state(policy_mode, task_active)
    return {
        "policyMode": policy_mode,
        "taskActive": task_active,
        "desiredState": desired_state,
        "updatedAt": raw.get("updatedAt"),
        "updatedBy": raw.get("updatedBy"),
        "host": raw.get("host"),
        "reason": raw.get("reason"),
        "followupWindow": normalize_followup_window(raw.get("followupWindow")),
    }


def save_service_control(
    path: Path,
    *,
    policy_mode: str | None = None,
    task_active: bool | None = None,
    updated_by: str,
    reason: str | None,
    followup_window: Any = UNSET,
) -> dict[str, Any]:
    current = load_service_control(path)
    next_policy_mode = normalize_policy_mode(policy_mode if policy_mode is not None else current.get("policyMode"))
    next_task_active = bool(task_active if task_active is not None else current.get("taskActive"))
    next_followup_window = current.get("followupWindow") if followup_window is UNSET else normalize_followup_window(followup_window)
    payload = {
        "policyMode": next_policy_mode,
        "taskActive": next_task_active,
        "desiredState": compute_desired_state(next_policy_mode, next_task_active),
        "updatedAt": now_iso(),
        "updatedBy": updated_by,
        "host": socket.gethostname(),
        "reason": reason or None,
        "followupWindow": next_followup_window,
    }
    save_json(path, payload)
    return payload


def _connect_db(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _has_task_runs_table(conn: sqlite3.Connection | None) -> bool:
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='task_runs' LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return False
    return row is not None


def open_db(tasks_db_path: Path) -> tuple[sqlite3.Connection | None, Path | None]:
    candidates: list[Path] = []
    for candidate in (tasks_db_path, DEFAULT_TASKS_DB_PATH, LEGACY_TASKS_DB_PATH):
        resolved = candidate.expanduser().resolve()
        if resolved not in candidates:
            candidates.append(resolved)

    fallback: tuple[sqlite3.Connection | None, Path | None] = (None, None)
    for candidate in candidates:
        conn = _connect_db(candidate)
        if conn is None:
            continue
        if _has_task_runs_table(conn):
            return conn, candidate
        if fallback[0] is None:
            fallback = (conn, candidate)
        else:
            conn.close()
    return fallback


def parse_iso_ms(value: Any) -> int | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def session_key_agent_id(session_key: Any, fallback: str | None = None) -> str:
    if isinstance(session_key, str):
        parts = session_key.split(":")
        if len(parts) >= 2 and parts[0] == "agent" and parts[1]:
            return parts[1]
    return fallback or "main"


def sessions_index_path(agent_id: str | None) -> Path:
    return DEFAULT_AGENTS_ROOT / session_key_agent_id(None, agent_id) / "sessions" / "sessions.json"


def load_sessions_index(agent_id: str | None) -> dict[str, Any]:
    raw = load_json(sessions_index_path(agent_id))
    return raw if isinstance(raw, dict) else {}


def read_jsonl_tail(path: Path, max_lines: int = DEFAULT_SESSION_TAIL_LINES) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def message_has_visible_text(message: dict[str, Any]) -> bool:
    content = message.get("content")
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str) and item.get("text").strip():
            return True
    return False


def entry_timestamp_ms(entry: dict[str, Any]) -> int | None:
    message = entry.get("message")
    if isinstance(message, dict):
        timestamp = message.get("timestamp")
        if isinstance(timestamp, int):
            return timestamp
    timestamp = entry.get("timestamp")
    if isinstance(timestamp, int):
        return timestamp
    return parse_iso_ms(timestamp)


def detect_orphaned_running_task(row: Any) -> tuple[bool, str | None]:
    if not isinstance(row, (dict, sqlite3.Row)):
        return False, None
    status = row["status"] if isinstance(row, sqlite3.Row) else row.get("status")
    if status in TERMINAL_STATUSES:
        return False, None
    child_session_key = row["child_session_key"] if isinstance(row, sqlite3.Row) else row.get("child_session_key")
    if not isinstance(child_session_key, str) or not child_session_key:
        return False, None
    agent_id = row["agent_id"] if isinstance(row, sqlite3.Row) else row.get("agent_id")
    session_index = load_sessions_index(session_key_agent_id(child_session_key, agent_id))
    session_meta = session_index.get(child_session_key)
    if not isinstance(session_meta, dict):
        return False, None
    session_file = session_meta.get("sessionFile")
    if not isinstance(session_file, str) or not session_file:
        return False, None
    entries = read_jsonl_tail(Path(session_file).expanduser())
    if not entries:
        return False, None

    task_started_ms = 0
    for candidate in (
        row["started_at"] if isinstance(row, sqlite3.Row) else row.get("started_at"),
        row["created_at"] if isinstance(row, sqlite3.Row) else row.get("created_at"),
    ):
        if isinstance(candidate, int) and candidate > task_started_ms:
            task_started_ms = candidate

    relevant_entries = [entry for entry in entries if (entry_timestamp_ms(entry) or task_started_ms) >= task_started_ms]
    if not relevant_entries:
        return False, None

    for entry in reversed(relevant_entries):
        entry_type = entry.get("type")
        if entry_type == "message":
            message = entry.get("message")
            if not isinstance(message, dict):
                continue
            role = message.get("role")
            if role == "assistant":
                error_message = entry.get("errorMessage") or message.get("errorMessage")
                stop_reason = entry.get("stopReason") or message.get("stopReason")
                if (isinstance(error_message, str) and error_message.strip()) or stop_reason == "error":
                    if not message_has_visible_text(message):
                        return True, (error_message or stop_reason or "assistant_error")
                return False, None
            if role in {"toolResult", "user"}:
                return False, None
        if entry_type == "custom" and entry.get("customType") == "openclaw:prompt-error":
            data = entry.get("data")
            if isinstance(data, dict):
                error_message = data.get("error")
                if isinstance(error_message, str) and error_message.strip():
                    return True, error_message
            return True, "prompt_error"
    return False, None


def fetch_active_tasks(conn: sqlite3.Connection | None, now_ms: int, stalled_after_seconds: int) -> tuple[list[dict[str, Any]], str | None]:
    if conn is None:
        return [], "tasks_db_missing"
    try:
        rows = conn.execute(
            """
            SELECT task_id, label, status, runtime, owner_key, child_session_key,
                   agent_id, created_at, started_at, ended_at, last_event_at,
                   error, progress_summary, terminal_summary, terminal_outcome
            FROM task_runs
            WHERE status NOT IN ('succeeded', 'failed', 'cancelled', 'canceled', 'timed_out', 'lost')
            ORDER BY COALESCE(last_event_at, started_at, created_at) DESC
            """
        ).fetchall()
    except sqlite3.Error as exc:
        return [], f"tasks_db_query_failed:{exc}"

    tasks: list[dict[str, Any]] = []
    for row in rows:
        orphaned, _orphan_reason = detect_orphaned_running_task(row)
        if orphaned:
            continue
        created_at = row["created_at"]
        started_at = row["started_at"]
        last_event_at = row["last_event_at"]
        last_activity_ms = max([value for value in [last_event_at, started_at, created_at] if isinstance(value, int)], default=0)
        silent_seconds = max(0, int((now_ms - last_activity_ms) / 1000)) if last_activity_ms else None
        derived_status = "stalled" if silent_seconds is not None and silent_seconds >= stalled_after_seconds else "running"
        tasks.append(
            {
                "taskId": row["task_id"],
                "label": row["label"],
                "runtime": row["runtime"],
                "status": row["status"],
                "derivedStatus": derived_status,
                "ownerKey": row["owner_key"],
                "childSessionKey": row["child_session_key"],
                "createdAt": iso_from_ms(created_at),
                "startedAt": iso_from_ms(started_at),
                "endedAt": iso_from_ms(row["ended_at"]),
                "lastEventAt": iso_from_ms(last_event_at),
                "lastActivityAt": iso_from_ms(last_activity_ms),
                "silentSeconds": silent_seconds,
                "progressSummary": row["progress_summary"],
                "terminalSummary": row["terminal_summary"],
                "terminalOutcome": row["terminal_outcome"],
                "error": row["error"],
            }
        )
    return tasks, None


def is_frontstage_owner_key(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("agent:") and ":subagent:" not in value


def pick_user_facing_task(tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tasks:
        return None
    preferred = [task for task in tasks if is_frontstage_owner_key(task.get("ownerKey"))]
    pool = preferred or tasks
    stalled = [task for task in pool if task.get("derivedStatus") == "stalled"]
    if stalled:
        return max(stalled, key=lambda item: item.get("silentSeconds") or 0)
    return max(pool, key=lambda item: item.get("silentSeconds") or 0)


def fetch_recent_terminal_task(conn: sqlite3.Connection | None, now_ms: int, terminal_display_seconds: int) -> tuple[dict[str, Any] | None, str | None]:
    if conn is None:
        return None, "tasks_db_missing"
    try:
        rows = conn.execute(
            """
            SELECT task_id, label, status, runtime, owner_key, child_session_key,
                   created_at, started_at, ended_at, last_event_at,
                   error, progress_summary, terminal_summary, terminal_outcome
            FROM task_runs
            WHERE status IN ('succeeded', 'failed', 'cancelled', 'canceled', 'timed_out', 'lost')
            ORDER BY COALESCE(ended_at, last_event_at, started_at, created_at) DESC
            LIMIT 12
            """
        ).fetchall()
    except sqlite3.Error as exc:
        return None, f"tasks_db_query_failed:{exc}"

    candidates: list[dict[str, Any]] = []
    for row in rows:
        terminal_at_ms = max([value for value in [row["ended_at"], row["last_event_at"], row["started_at"], row["created_at"]] if isinstance(value, int)], default=0)
        age_seconds = max(0, int((now_ms - terminal_at_ms) / 1000)) if terminal_at_ms else None
        if age_seconds is None or age_seconds > terminal_display_seconds:
            continue
        candidates.append(
            {
                "taskId": row["task_id"],
                "label": row["label"],
                "runtime": row["runtime"],
                "status": row["status"],
                "ownerKey": row["owner_key"],
                "childSessionKey": row["child_session_key"],
                "createdAt": iso_from_ms(row["created_at"]),
                "startedAt": iso_from_ms(row["started_at"]),
                "endedAt": iso_from_ms(row["ended_at"]),
                "lastEventAt": iso_from_ms(row["last_event_at"]),
                "terminalAt": iso_from_ms(terminal_at_ms),
                "ageSeconds": age_seconds,
                "progressSummary": row["progress_summary"],
                "terminalSummary": row["terminal_summary"],
                "terminalOutcome": row["terminal_outcome"],
                "error": row["error"],
            }
        )

    if not candidates:
        return None, None
    preferred = [task for task in candidates if is_frontstage_owner_key(task.get("ownerKey"))]
    return (preferred or candidates)[0], None


def pick_focus_task(active_tasks: list[dict[str, Any]]) -> dict[str, Any] | None:
    return pick_user_facing_task(active_tasks)


def derive_service_state(desired_state: str, active_tasks: list[dict[str, Any]]) -> str:
    if desired_state == "disabled":
        return "stopping" if active_tasks else "disabled"
    return "active" if active_tasks else "armed"


def derive_monitor_status(
    active_tasks: list[dict[str, Any]],
    recent_terminal_task: dict[str, Any] | None,
    followup_window: dict[str, Any] | None,
    now_ms: int,
) -> str:
    if active_tasks:
        if any(task.get("derivedStatus") == "stalled" for task in active_tasks):
            return "stalled"
        return "running"
    if is_followup_window_active(followup_window, now_ms):
        return "waiting"
    if recent_terminal_task:
        return "failed" if recent_terminal_task.get("status") in FAILURE_STATUSES else "done"
    return "idle"


def build_summary(
    control: dict[str, Any],
    service_state: str,
    monitor_status: str,
    active_tasks: list[dict[str, Any]],
    focus_task: dict[str, Any] | None,
    recent_terminal_task: dict[str, Any] | None,
    followup_window: dict[str, Any] | None,
) -> tuple[str, str]:
    policy_mode = str(control.get("policyMode") or "auto")
    task_active = bool(control.get("taskActive"))

    if service_state == "disabled":
        if policy_mode == "force_off":
            return "监工服务已关闭", "当前处于手动关闭状态。"
        return "监工服务自动待机", "当前处于自动模式；这轮未标记为复杂任务，所以暂不启用监工。"
    if service_state == "armed" and monitor_status == "idle":
        likely_idle_reason = "当前没有 active run 可监工；这通常表示工作仍在前台进行，或上一轮后台任务刚结束。"
        if policy_mode == "force_on":
            return "监工服务常开待命中", f"{likely_idle_reason} 若这轮准备按“后台推进 + 监工盯着”执行，应立即真卸到后台任务。"
        if policy_mode == "auto" and task_active:
            return "监工服务待命中", f"{likely_idle_reason} 当前已标记为复杂任务；若还要继续后台推进，应立即补一个真实后台任务。"
        return "监工服务待命中", "监工服务已开启，但当前没有后台任务。"
    if service_state == "stopping":
        count = len(active_tasks)
        if policy_mode == "force_off":
            return "监工服务收尾中", f"监工服务已被手动关闭，但还有 {count} 个后台任务未结束。"
        return "监工服务收尾中", f"当前轮已退出监工，但还有 {count} 个后台任务未结束。"
    if monitor_status == "running":
        count = len(active_tasks)
        label = focus_task.get("label") if focus_task else None
        if label:
            return f"后台任务运行中（{count}）", f"最近关注任务：{label}。"
        return f"后台任务运行中（{count}）", "至少有一个后台任务仍在运行。"
    if monitor_status == "waiting" and followup_window:
        label = followup_window.get("taskLabel") or followup_window.get("taskId") or "上一轮后台任务"
        remaining_seconds = max(0, int((int(followup_window.get("expiresAtMs") or 0) - epoch_ms() + 999) / 1000))
        return "后台任务已完成，等待接续中", f"{label} 刚完成。监工会在接下来 {remaining_seconds} 秒内等待新的后台任务；若没有新的后台任务或继续信号，将自动关闭。"
    if monitor_status == "stalled":
        count = len(active_tasks)
        silent_seconds = focus_task.get("silentSeconds") if focus_task else None
        label = focus_task.get("label") if focus_task else None
        if label and silent_seconds is not None:
            return "后台任务可能卡住", f"任务 {label} 已有 {silent_seconds} 秒无新进展；当前活跃任务 {count} 个。"
        if silent_seconds is not None:
            return "后台任务可能卡住", f"至少一个后台任务已有 {silent_seconds} 秒无新进展。"
        return "后台任务可能卡住", "至少一个后台任务超过静默阈值仍无新进展。"
    if monitor_status == "failed" and recent_terminal_task:
        label = recent_terminal_task.get("label") or recent_terminal_task.get("taskId")
        return "后台任务异常结束", f"最近一个后台任务异常结束：{label}。"
    if monitor_status == "done" and recent_terminal_task:
        label = recent_terminal_task.get("label") or recent_terminal_task.get("taskId")
        return "后台任务已完成", f"最近一个后台任务刚完成：{label}。"
    return "当前空闲", "没有检测到需要监工的后台任务。"


def build_human_summary(report: dict[str, Any]) -> str:
    service = report.get("service", {})
    detail = report.get("detail") or "-"
    focus = report.get("focusTask") or {}
    recent_terminal = report.get("recentTerminalTask") or {}
    lines = [
        report.get("summary") or "-",
        f"- 服务状态：{service.get('state') or '-'}（策略：{service.get('policyMode') or '-'} / 有效意图：{service.get('desiredState') or '-'}）",
        f"- 任务激活：{service.get('taskActive')}",
        f"- 监工状态：{report.get('status') or '-'}",
        f"- 活跃任务数：{report.get('activeTaskCount') or 0}",
        f"- 更新时间：{report.get('checkedAt') or '-'}",
        f"- 说明：{detail}",
    ]
    if focus:
        lines.append(
            f"- 关注任务：{focus.get('label') or focus.get('taskId') or '-'} / silent={focus.get('silentSeconds') if focus.get('silentSeconds') is not None else '-'}s"
        )
    if recent_terminal:
        lines.append(
            f"- 最近结束：{recent_terminal.get('status') or '-'} / {recent_terminal.get('label') or recent_terminal.get('taskId') or '-'}"
        )
    if report.get("statusError"):
        lines.append(f"- 状态错误：{report['statusError']}")
    return "\n".join(lines)


def maybe_log_transition(previous: dict[str, Any], current: dict[str, Any], event_log_path: Path) -> None:
    prev_service = (previous.get("service") or {}).get("state")
    curr_service = (current.get("service") or {}).get("state")
    prev_status = previous.get("status")
    curr_status = current.get("status")
    prev_summary = previous.get("summary")
    curr_summary = current.get("summary")
    if prev_service == curr_service and prev_status == curr_status and prev_summary == curr_summary:
        return
    append_log(
        event_log_path,
        f"[{current.get('checkedAt')}] service={curr_service} policy={(current.get('service') or {}).get('policyMode')} desired={(current.get('service') or {}).get('desiredState')} taskActive={(current.get('service') or {}).get('taskActive')} status={curr_status} summary={curr_summary}",
    )


def should_open_followup_window(report: dict[str, Any]) -> bool:
    service = report.get("service") or {}
    task = report.get("recentTerminalTask") or {}
    if report.get("status") != "done":
        return False
    if service.get("desiredState") != "armed":
        return False
    if not (service.get("taskActive") or service.get("policyMode") == "force_on"):
        return False
    if not isinstance(task, dict) or not is_frontstage_owner_key(task.get("ownerKey")):
        return False
    return True


def reconcile_followup_window(report: dict[str, Any], control_path: Path, wait_seconds: int) -> bool:
    control = load_service_control(control_path)
    followup_window = control.get("followupWindow")
    now_ms = epoch_ms()

    if report.get("hasActiveTask"):
        if followup_window is not None:
            save_service_control(
                control_path,
                updated_by="supervisor-auto",
                reason="followup-window-cleared-active-task",
                followup_window=None,
            )
            return True
        return False

    if followup_window and not is_followup_window_active(followup_window, now_ms):
        save_service_control(
            control_path,
            policy_mode="auto",
            task_active=False,
            updated_by="supervisor-auto",
            reason="followup-window-expired",
            followup_window=None,
        )
        return True

    if should_open_followup_window(report):
        task = report.get("recentTerminalTask") or {}
        if not followup_window_matches_task(followup_window, task):
            save_service_control(
                control_path,
                updated_by="supervisor-auto",
                reason="await-next-task",
                followup_window=build_followup_window(task, now_ms, wait_seconds),
            )
            return True
        return False

    if followup_window is not None:
        save_service_control(
            control_path,
            updated_by="supervisor-auto",
            reason="followup-window-cleared",
            followup_window=None,
        )
        return True
    return False


def build_report(tasks_db_path: Path, state_dir: Path, stalled_after_seconds: int, terminal_display_seconds: int) -> dict[str, Any]:
    now_ms = epoch_ms()
    control_path = state_dir / CONTROL_PATH_NAME
    status_path = state_dir / STATUS_PATH_NAME
    desired = load_service_control(control_path)

    conn, resolved_tasks_db_path = open_db(tasks_db_path)
    status_errors: list[str] = []
    try:
        active_tasks, active_error = fetch_active_tasks(conn, now_ms, stalled_after_seconds)
        if active_error:
            status_errors.append(active_error)
        recent_terminal_task, terminal_error = fetch_recent_terminal_task(conn, now_ms, terminal_display_seconds)
        if terminal_error and terminal_error != active_error:
            status_errors.append(terminal_error)
    finally:
        if conn is not None:
            conn.close()

    followup_window = desired.get("followupWindow")
    focus_task = pick_focus_task(active_tasks)
    service_state = derive_service_state(desired["desiredState"], active_tasks)
    monitor_status = derive_monitor_status(active_tasks, recent_terminal_task, followup_window, now_ms)
    summary, detail = build_summary(desired, service_state, monitor_status, active_tasks, focus_task, recent_terminal_task, followup_window)
    host = socket.gethostname()

    report = {
        "checkedAt": now_iso(),
        "host": host,
        "status": monitor_status,
        "summary": summary,
        "detail": detail,
        "hasActiveTask": bool(active_tasks),
        "activeTaskCount": len(active_tasks),
        "stalledAfterSeconds": stalled_after_seconds,
        "terminalDisplaySeconds": terminal_display_seconds,
        "service": {
            "state": service_state,
            "policyMode": desired["policyMode"],
            "taskActive": desired["taskActive"],
            "desiredState": desired["desiredState"],
            "updatedAt": desired.get("updatedAt"),
            "updatedBy": desired.get("updatedBy"),
            "host": desired.get("host"),
            "reason": desired.get("reason"),
        },
        "followupWindow": followup_window,
        "focusTask": focus_task,
        "activeTasks": active_tasks,
        "recentTerminalTask": recent_terminal_task,
        "statusError": "; ".join(status_errors) if status_errors else None,
        "paths": {
            "tasksDb": str(resolved_tasks_db_path or tasks_db_path),
            "stateDir": str(state_dir),
            "serviceControl": str(control_path),
            "statusFile": str(status_path),
            "notifyState": str(state_dir / NOTIFY_STATE_PATH_NAME),
        },
    }
    return report


def build_notification_candidate(report: dict[str, Any]) -> dict[str, Any] | None:
    service = report.get("service") or {}
    if service.get("policyMode") == "force_off":
        return None
    if report.get("status") not in NOTIFYABLE_STATUSES:
        return None
    if service.get("state") == "disabled":
        return None

    status = str(report.get("status") or "")
    task: dict[str, Any] | None
    marker: str | None
    owner_key: str | None
    if status == "stalled":
        task = report.get("focusTask") or None
        marker = (task or {}).get("lastActivityAt") or (task or {}).get("taskId")
        owner_key = (task or {}).get("ownerKey")
    elif status == "waiting":
        task = report.get("recentTerminalTask") or None
        followup_window = report.get("followupWindow") or {}
        marker = followup_window.get("expiresAt") or (task or {}).get("terminalAt") or (task or {}).get("taskId")
        owner_key = followup_window.get("ownerKey") or (task or {}).get("ownerKey")
    else:
        task = report.get("recentTerminalTask") or None
        marker = (task or {}).get("terminalAt") or (task or {}).get("endedAt") or (task or {}).get("taskId")
        owner_key = (task or {}).get("ownerKey")

    if not isinstance(task, dict):
        return None
    if not is_frontstage_owner_key(owner_key):
        return None

    label = task.get("label") or task.get("taskId") or "后台任务"
    if status == "stalled":
        silent_seconds = task.get("silentSeconds")
        tail = f"{label} 已有 {silent_seconds} 秒无新进展。" if silent_seconds is not None else f"{label} 可能卡住了。"
    elif status == "failed":
        tail = f"{label} 异常结束，我正在接手检查。"
    elif status == "waiting":
        wait_seconds = ((report.get("followupWindow") or {}).get("waitSeconds") or DEFAULT_FOLLOWUP_WAIT_SECONDS)
        tail = f"{label} 已完成。我会再等 {wait_seconds} 秒看是否接续新任务；若没有新的后台任务或继续信号，就自动关闭监工。"
    else:
        tail = f"{label} 已完成。"

    message = f"[监工] {tail}"
    return {
        "eventKey": f"{status}|{task.get('taskId')}|{marker}|{owner_key}",
        "sessionKey": owner_key,
        "message": message,
        "status": status,
        "taskId": task.get("taskId"),
    }

def maybe_send_transition_notification(report: dict[str, Any], state_dir: Path, event_log_path: Path) -> None:
    candidate = build_notification_candidate(report)
    if not candidate:
        return

    notify_state_path = state_dir / NOTIFY_STATE_PATH_NAME
    previous = load_json(notify_state_path)
    if previous.get("eventKey") == candidate["eventKey"]:
        return

    helper_path = Path(__file__).with_name("openclaw-infos-handle.py")
    request_payload = build_handle_request_payload(
        request_id=f"supervisor:{candidate['eventKey']}",
        message=str(candidate["message"]),
        output_format="text",
        delivery_mode="frontstage",
        frontstage_source="supervisor",
        frontstage_event_key=str(candidate["eventKey"]),
        session_key=str(candidate["sessionKey"]),
        data={
            "status": candidate.get("status"),
            "taskId": candidate.get("taskId"),
            "checkedAt": report.get("checkedAt"),
        },
    )
    try:
        payload = invoke_handle_request(
            helper_path,
            request_payload,
            python_executable=sys.executable,
            run=subprocess.run,
        )
    except RuntimeError as exc:
        append_log(event_log_path, f"[{report.get('checkedAt')}] notify_failed session={candidate['sessionKey']} error={exc}")
        return

    notify_payload = extract_frontstage_notify_payload(payload)
    response = notify_payload.get("response") if isinstance(notify_payload.get("response"), dict) else {}
    message_id = response.get("messageId") or notify_payload.get("messageId")
    notify_state = {
        "sentAt": report.get("checkedAt"),
        "eventKey": candidate["eventKey"],
        "status": candidate["status"],
        "taskId": candidate["taskId"],
        "sessionKey": candidate["sessionKey"],
        "targetSessionKey": notify_payload.get("targetSessionKey"),
        "messageId": message_id,
        "message": candidate["message"],
    }
    save_json(notify_state_path, notify_state)
    append_log(event_log_path, f"[{report.get('checkedAt')}] notify_sent session={notify_state['sessionKey']} target={notify_state.get('targetSessionKey')} status={notify_state['status']} task={notify_state['taskId']} messageId={message_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw supervisor status snapshot")
    parser.add_argument("--tasks-db-path", default=str(DEFAULT_TASKS_DB_PATH), help="Path to tasks database (默认 ~/.openclaw/state/openclaw.sqlite)")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="Directory for supervisor state files")
    parser.add_argument("--stalled-after-seconds", type=int, default=DEFAULT_STALLED_AFTER_SECONDS, help="Silent threshold for stalled tasks")
    parser.add_argument("--terminal-display-seconds", type=int, default=DEFAULT_TERMINAL_DISPLAY_SECONDS, help="Keep done/failed visible for this long")
    parser.add_argument("--followup-wait-seconds", type=int, default=DEFAULT_FOLLOWUP_WAIT_SECONDS, help="After a task finishes, wait this long for the next background task before auto-closing supervisor")
    parser.add_argument("--set-service-state", choices=sorted(ALLOWED_DESIRED_STATES), help="Legacy shortcut: armed=auto+taskActive=true, disabled=auto+taskActive=false")
    parser.add_argument("--set-policy-mode", choices=sorted(ALLOWED_POLICY_MODES), help="Persist supervisor policy mode")
    parser.add_argument("--activate-task", action="store_true", help="Mark current work as complex/active under auto mode")
    parser.add_argument("--deactivate-task", action="store_true", help="Mark current work as no longer needing auto supervisor activation")
    parser.add_argument("--reason", help="Optional reason recorded when changing service control")
    parser.add_argument("--notify-transitions", action="store_true", help="Send frontstage notifications for stalled/failed/done transitions")
    parser.add_argument("--print-json", action="store_true", help="Print JSON report")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    tasks_db_path = Path(args.tasks_db_path).expanduser().resolve()
    state_dir = Path(args.state_dir).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    control_path = state_dir / CONTROL_PATH_NAME
    status_path = state_dir / STATUS_PATH_NAME
    event_log_path = state_dir / EVENT_LOG_PATH_NAME

    if args.activate_task and args.deactivate_task:
        raise SystemExit("--activate-task and --deactivate-task cannot be used together")

    if args.set_service_state:
        save_service_control(
            control_path,
            policy_mode="auto",
            task_active=args.set_service_state == "armed",
            updated_by="legacy-manual",
            reason=args.reason,
            followup_window=None,
        )

    if args.set_policy_mode or args.activate_task or args.deactivate_task:
        save_service_control(
            control_path,
            policy_mode=args.set_policy_mode,
            task_active=True if args.activate_task else False if args.deactivate_task else None,
            updated_by="manual",
            reason=args.reason,
            followup_window=None,
        )

    previous = load_json(status_path)
    report = build_report(tasks_db_path, state_dir, args.stalled_after_seconds, args.terminal_display_seconds)
    if reconcile_followup_window(report, control_path, args.followup_wait_seconds):
        report = build_report(tasks_db_path, state_dir, args.stalled_after_seconds, args.terminal_display_seconds)
    save_json(status_path, report)
    maybe_log_transition(previous, report, event_log_path)
    if args.notify_transitions:
        maybe_send_transition_notification(report, state_dir, event_log_path)

    if args.print_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.print_human or not args.print_json:
        print(build_human_summary(report))

    if report["status"] == "failed":
        return 2
    if report["status"] == "stalled":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
