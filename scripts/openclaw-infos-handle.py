#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）设计并验证最小入口）
# 系统 / OS：通用
# 用途：作为 broker 与具体消费方之间的最小信息处理层；先支持 text/json 查询与前台通知。

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_BROKER_ROOT = Path.home() / ".local" / "state" / "openclaw" / "broker"
DEFAULT_VIEWS_DIR = DEFAULT_BROKER_ROOT / "views"
DEFAULT_SNAPSHOT_PATH = DEFAULT_VIEWS_DIR / "snapshot.json"
DEFAULT_EVENTS_PATH = DEFAULT_BROKER_ROOT / "events.jsonl"
DEFAULT_SESSION_KEY = "agent:main:main"
WORKSPACE = Path(__file__).resolve().parents[1]
BROKER_SCRIPT = WORKSPACE / "scripts" / "openclaw-frontstage-broker.py"
FRONTSTAGE_HELPER = WORKSPACE / "scripts" / "openclaw-supervisor-subagent.py"

QUERY_KINDS = {
    "snapshot.summary",
    "health.summary",
    "tasks.summary",
    "recovery.summary",
    "sources.latest",
    "events.recent",
}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def load_recent_events(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    rows.sort(key=lambda item: str(item.get("recordedAt") or item.get("sentAt") or ""), reverse=True)
    return rows[: max(1, limit)]


def summarize_panel(panel: dict[str, Any], fallback_title: str) -> str:
    summary = str(panel.get("summary") or fallback_title)
    detail = str(panel.get("detail") or "").strip()
    checked_at = str(panel.get("checkedAt") or "").strip()
    parts = [summary]
    if detail and detail != summary:
        parts.append(detail)
    if checked_at:
        parts.append(f"checkedAt={checked_at}")
    return "｜".join(parts)


def render_text(kind: str, snapshot: dict[str, Any], events: list[dict[str, Any]]) -> str:
    if kind == "snapshot.summary":
        summary = str(snapshot.get("summary") or "前台状态未知")
        issue_overview = str(snapshot.get("issueOverview") or summary)
        severity = str(snapshot.get("severity") or "unknown")
        actions = snapshot.get("selfHelpActions") if isinstance(snapshot.get("selfHelpActions"), list) else []
        action_lines = [f"- {item}" for item in actions[:3] if isinstance(item, str) and item.strip()]
        lines = [f"[{severity}] {summary}", issue_overview]
        if action_lines:
            lines.append("建议：")
            lines.extend(action_lines)
        return "\n".join(lines)

    if kind == "health.summary":
        panel = snapshot.get("panels", {}).get("health") if isinstance(snapshot.get("panels"), dict) else {}
        return summarize_panel(panel if isinstance(panel, dict) else {}, "本地健康状态未知")

    if kind == "tasks.summary":
        panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
        supervisor = panels.get("supervisor") if isinstance(panels.get("supervisor"), dict) else {}
        recovery = panels.get("recovery") if isinstance(panels.get("recovery"), dict) else {}
        lines = [
            f"监工：{summarize_panel(supervisor, '监工状态未知')}",
            f"恢复观察：{summarize_panel(recovery, '恢复状态未知')}",
        ]
        latest_delivery = snapshot.get("latestDelivery") if isinstance(snapshot.get("latestDelivery"), dict) else {}
        if latest_delivery:
            lines.append(
                f"最近辅助投递：{latest_delivery.get('source') or 'unknown'} / {latest_delivery.get('message') or latest_delivery.get('eventKey') or ''}"
            )
        return "\n".join(lines)

    if kind == "recovery.summary":
        panel = snapshot.get("panels", {}).get("recovery") if isinstance(snapshot.get("panels"), dict) else {}
        return summarize_panel(panel if isinstance(panel, dict) else {}, "前台恢复状态未知")

    if kind == "sources.latest":
        source_states = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}
        deliveries = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
        source_names = sorted({*source_states.keys(), *deliveries.keys()})
        if not source_names:
            return "当前还没有来源快照。"
        lines = []
        for source in source_names:
            state_payload = source_states.get(source) if isinstance(source_states.get(source), dict) else {}
            delivery_payload = deliveries.get(source) if isinstance(deliveries.get(source), dict) else {}
            state_part = str(state_payload.get("summary") or state_payload.get("message") or state_payload.get("eventKey") or "无 ingest")
            delivery_part = str(delivery_payload.get("message") or delivery_payload.get("eventKey") or "无 delivery")
            lines.append(f"- {source}｜state={state_part}｜delivery={delivery_part}")
        return "\n".join(lines)

    if kind == "events.recent":
        if not events:
            return "最近没有 broker 事件。"
        lines = []
        for item in events:
            record_type = str(item.get("recordType") or "unknown")
            source = str(item.get("source") or "unknown")
            stamp = str(item.get("recordedAt") or item.get("sentAt") or "")
            message = str(item.get("message") or item.get("eventKey") or "")
            lines.append(f"- [{record_type}] {source} @ {stamp}｜{message}")
        return "\n".join(lines)

    raise ValueError(f"unsupported kind: {kind}")


def build_query_payload(kind: str, snapshot_path: Path, events_path: Path, limit: int) -> dict[str, Any]:
    if kind not in QUERY_KINDS:
        raise ValueError(f"unsupported kind: {kind}")
    snapshot = load_json(snapshot_path)
    events = load_recent_events(events_path, limit)
    text = render_text(kind, snapshot, events)
    return {
        "ok": True,
        "kind": kind,
        "snapshotPath": str(snapshot_path),
        "eventsPath": str(events_path),
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "events": events,
        "text": text,
    }


def run_broker_action(action: str, **kwargs: Any) -> dict[str, Any]:
    cmd = [sys.executable, str(BROKER_SCRIPT), action]
    for key, value in kwargs.items():
        if value is None:
            continue
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, dict):
            cmd.extend([flag, json.dumps(value, ensure_ascii=False)])
        else:
            cmd.extend([flag, str(value)])
    cmd.append("--print-json")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"broker {action} failed").strip())
    payload = json.loads(result.stdout)
    return payload if isinstance(payload, dict) else {}


def notify_frontstage(
    session_key: str,
    message: str,
    source: str | None = None,
    event_key: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if source and event_key:
        run_broker_action(
            "ingest",
            source=source,
            event_key=event_key,
            session_key=session_key,
            message=message,
            data_json=data,
        )

    cmd = [
        sys.executable,
        str(FRONTSTAGE_HELPER),
        "send-frontstage",
        "--session-key",
        session_key,
        "--message",
        message,
        "--print-json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "send-frontstage failed").strip())
    payload = json.loads(result.stdout)
    response = payload.get("response") if isinstance(payload.get("response"), dict) else {}

    if source and event_key:
        run_broker_action(
            "record-delivery",
            source=source,
            event_key=event_key,
            session_key=session_key,
            target_session_key=payload.get("targetSessionKey"),
            message_id=response.get("messageId"),
            message=message,
        )
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal infos-handle layer for broker-backed text/json queries")
    parser.add_argument("action", choices=["query", "notify-frontstage"], help="Operation to run")
    parser.add_argument("--kind", choices=sorted(QUERY_KINDS), help="What info to query")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format for query")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="Broker snapshot.json path")
    parser.add_argument("--events-path", default=str(DEFAULT_EVENTS_PATH), help="Broker events.jsonl path")
    parser.add_argument("--limit", type=int, default=6, help="Max recent events for events.recent")
    parser.add_argument("--session-key", default=DEFAULT_SESSION_KEY, help="Target session key for frontstage notify")
    parser.add_argument("--source", help="Optional source name when notify-frontstage should also ingest/record delivery")
    parser.add_argument("--event-key", help="Optional event key when notify-frontstage should also ingest/record delivery")
    parser.add_argument("--data-json", help="Optional JSON object payload to ingest before notify-frontstage")
    parser.add_argument("--message", help="Direct message for notify-frontstage; when omitted, query text is used")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot_path).expanduser().resolve()
    events_path = Path(args.events_path).expanduser().resolve()

    if args.action == "query":
        if not args.kind:
            raise SystemExit("query requires --kind")
        payload = build_query_payload(args.kind, snapshot_path, events_path, args.limit)
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload["text"])
        return 0

    data_payload = None
    if args.data_json:
        try:
            parsed = json.loads(args.data_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--data-json must be a JSON object: {exc}") from exc
        if not isinstance(parsed, dict):
            raise SystemExit("--data-json must be a JSON object")
        data_payload = parsed

    query_text = args.message
    if not query_text:
        if not args.kind:
            raise SystemExit("notify-frontstage requires --message or --kind")
        query_payload = build_query_payload(args.kind, snapshot_path, events_path, args.limit)
        query_text = str(query_payload.get("text") or "").strip()
    if not query_text:
        raise SystemExit("notify-frontstage resolved to empty message")

    payload = notify_frontstage(
        args.session_key,
        query_text,
        source=args.source,
        event_key=args.event_key,
        data=data_payload,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        raise SystemExit(0)
