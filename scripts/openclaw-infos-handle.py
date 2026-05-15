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
QUERY_CONTRACT_VERSION = 2
DEFAULT_QUERY_LIMIT = 6

QUERY_KINDS = {
    "snapshot.summary",
    "health.summary",
    "tasks.summary",
    "recovery.summary",
    "sources.latest",
    "sources.catalog",
    "source.inspect",
    "events.recent",
    "contract.catalog",
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


def load_recent_source_events(path: Path, source_name: str, limit: int) -> list[dict[str, Any]]:
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
            if not isinstance(payload, dict):
                continue
            if str(payload.get("source") or "") != source_name:
                continue
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


def list_source_names(snapshot: dict[str, Any]) -> list[str]:
    source_states = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}
    deliveries = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
    contract_sources = contracts.get("sources") if isinstance(contracts.get("sources"), dict) else {}
    return sorted({*contract_sources.keys(), *source_states.keys(), *deliveries.keys()})


def build_source_catalog(snapshot: dict[str, Any]) -> dict[str, Any]:
    source_states = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}
    deliveries = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
    contract_sources = contracts.get("sources") if isinstance(contracts.get("sources"), dict) else {}
    items = []
    for source_name in list_source_names(snapshot):
        contract = contract_sources.get(source_name) if isinstance(contract_sources.get(source_name), dict) else {}
        latest_state = source_states.get(source_name) if isinstance(source_states.get(source_name), dict) else {}
        latest_delivery = deliveries.get(source_name) if isinstance(deliveries.get(source_name), dict) else {}
        items.append(
            {
                "source": source_name,
                "sourceEventType": contract.get("sourceEventType"),
                "sourceView": contract.get("sourceView"),
                "hasContract": bool(contract),
                "hasSourceState": bool(latest_state),
                "hasDelivery": bool(latest_delivery),
                "latestSourceState": latest_state,
                "latestDelivery": latest_delivery,
            }
        )
    return {
        "count": len(items),
        "sources": items,
    }


def build_query_catalog() -> dict[str, Any]:
    query_catalog: dict[str, Any] = {
        "snapshot.summary": {
            "description": "Top-level snapshot summary for lightweight consumers.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "health.summary": {
            "description": "Health panel summary.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "tasks.summary": {
            "description": "Supervisor and recovery panel summary with latest delivery.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "recovery.summary": {
            "description": "Recovery panel summary.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "sources.latest": {
            "description": "Raw latest source-state and delivery snapshots keyed by source.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "sources.catalog": {
            "description": "Machine-readable source inventory with contract presence and latest availability.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
        "source.inspect": {
            "description": "Inspect one source contract, latest snapshots, and recent events.",
            "formats": ["text", "json"],
            "requiredArgs": ["source_name"],
            "optionalArgs": ["limit"],
        },
        "events.recent": {
            "description": "Recent broker events sorted by recorded time descending.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": ["limit"],
        },
        "contract.catalog": {
            "description": "Infos-handle and broker contract catalog, including query metadata.",
            "formats": ["text", "json"],
            "requiredArgs": [],
            "optionalArgs": [],
        },
    }
    return {
        "defaultLimit": DEFAULT_QUERY_LIMIT,
        "responseEnvelope": {
            "ok": "bool",
            "kind": "str",
            "queryContractVersion": "int",
            "snapshotPath": "str",
            "eventsPath": "str",
            "result": "object",
            "sourceName": "str|null",
            "snapshot": "object",
            "events": "array",
            "text": "str",
        },
        "queries": query_catalog,
    }


def build_source_detail(snapshot: dict[str, Any], events: list[dict[str, Any]], source_name: str | None) -> dict[str, Any]:
    if not source_name:
        raise ValueError("source.inspect requires source_name")
    source_states = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}
    deliveries = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
    contract_sources = contracts.get("sources") if isinstance(contracts.get("sources"), dict) else {}
    return {
        "source": source_name,
        "contract": contract_sources.get(source_name) if isinstance(contract_sources.get(source_name), dict) else {},
        "latestSourceState": source_states.get(source_name) if isinstance(source_states.get(source_name), dict) else {},
        "latestDelivery": deliveries.get(source_name) if isinstance(deliveries.get(source_name), dict) else {},
        "recentEvents": [item for item in events if str(item.get("source") or "") == source_name],
    }


def render_text(kind: str, snapshot: dict[str, Any], events: list[dict[str, Any]], source_name: str | None = None) -> str:
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

    if kind == "sources.catalog":
        source_catalog = build_source_catalog(snapshot)
        items = source_catalog.get("sources") if isinstance(source_catalog.get("sources"), list) else []
        if not items:
            return "当前还没有来源契约或快照。"
        lines = []
        for item in items:
            source = str(item.get("source") or "unknown")
            source_view = str(item.get("sourceView") or "unknown")
            event_type = str(item.get("sourceEventType") or "unknown")
            lines.append(
                f"- {source}｜view={source_view}｜eventType={event_type}｜hasState={str(bool(item.get('hasSourceState'))).lower()}｜hasDelivery={str(bool(item.get('hasDelivery'))).lower()}"
            )
        return "\n".join(lines)

    if kind == "source.inspect":
        detail = build_source_detail(snapshot, events, source_name)
        source = str(detail.get("source") or source_name or "unknown")
        contract = detail.get("contract") if isinstance(detail.get("contract"), dict) else {}
        latest_state = detail.get("latestSourceState") if isinstance(detail.get("latestSourceState"), dict) else {}
        latest_delivery = detail.get("latestDelivery") if isinstance(detail.get("latestDelivery"), dict) else {}
        recent_events = detail.get("recentEvents") if isinstance(detail.get("recentEvents"), list) else []
        state_text = str(latest_state.get("message") or latest_state.get("summary") or latest_state.get("eventKey") or "无 ingest")
        delivery_text = str(latest_delivery.get("message") or latest_delivery.get("eventKey") or "无 delivery")
        event_type = str(contract.get("sourceEventType") or "unknown")
        source_view = str(contract.get("sourceView") or "unknown")
        lines = [
            f"source={source}",
            f"contract: eventType={event_type}｜view={source_view}",
            f"latestState: {state_text}",
            f"latestDelivery: {delivery_text}",
        ]
        if recent_events:
            for item in recent_events[:3]:
                lines.append(
                    f"- [{item.get('recordType') or 'unknown'}] {item.get('recordedAt') or item.get('sentAt') or ''}｜{item.get('message') or item.get('eventKey') or ''}"
                )
        else:
            lines.append("- 最近没有这个 source 的事件记录。")
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

    if kind == "contract.catalog":
        contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
        snapshot_contract = snapshot.get("snapshotContract") if isinstance(snapshot.get("snapshotContract"), dict) else {}
        broker_contract_version = contracts.get("version")
        primary_view = snapshot_contract.get("primaryView") or "unknown"
        primary_published = snapshot_contract.get("primaryPublishedJsonKey") or "unknown"
        source_count = len(contracts.get("sources")) if isinstance(contracts.get("sources"), dict) else 0
        query_count = len(build_query_catalog().get("queries") or {})
        return (
            f"infos-handle queryContractVersion={QUERY_CONTRACT_VERSION}｜"
            f"broker contractVersion={broker_contract_version}｜"
            f"primaryView={primary_view}｜primaryPublishedJsonKey={primary_published}｜sources={source_count}｜queries={query_count}"
        )

    raise ValueError(f"unsupported kind: {kind}")


def build_query_result(kind: str, snapshot: dict[str, Any], events: list[dict[str, Any]], source_name: str | None = None) -> dict[str, Any]:
    panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    if kind == "snapshot.summary":
        return {
            "summary": snapshot.get("summary"),
            "issueOverview": snapshot.get("issueOverview"),
            "severity": snapshot.get("severity"),
            "selfHelpActions": snapshot.get("selfHelpActions") if isinstance(snapshot.get("selfHelpActions"), list) else [],
            "checkedAt": snapshot.get("checkedAt"),
        }
    if kind == "health.summary":
        return panels.get("health") if isinstance(panels.get("health"), dict) else {}
    if kind == "tasks.summary":
        return {
            "supervisor": panels.get("supervisor") if isinstance(panels.get("supervisor"), dict) else {},
            "recovery": panels.get("recovery") if isinstance(panels.get("recovery"), dict) else {},
            "latestDelivery": snapshot.get("latestDelivery") if isinstance(snapshot.get("latestDelivery"), dict) else {},
        }
    if kind == "recovery.summary":
        return panels.get("recovery") if isinstance(panels.get("recovery"), dict) else {}
    if kind == "sources.latest":
        return {
            "sourceStateSnapshots": snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {},
            "sources": snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {},
            "latestSource": snapshot.get("latestSource"),
            "latestSourceState": snapshot.get("latestSourceState") if isinstance(snapshot.get("latestSourceState"), dict) else {},
            "latestDelivery": snapshot.get("latestDelivery") if isinstance(snapshot.get("latestDelivery"), dict) else {},
        }
    if kind == "sources.catalog":
        return build_source_catalog(snapshot)
    if kind == "source.inspect":
        return build_source_detail(snapshot, events, source_name)
    if kind == "events.recent":
        return {"events": events}
    if kind == "contract.catalog":
        return {
            "queryContractVersion": QUERY_CONTRACT_VERSION,
            "brokerContractVersion": snapshot.get("contractVersion"),
            "contracts": snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {},
            "snapshotContract": snapshot.get("snapshotContract") if isinstance(snapshot.get("snapshotContract"), dict) else {},
            "queryCatalog": build_query_catalog(),
        }
    raise ValueError(f"unsupported kind: {kind}")


def build_query_payload(kind: str, snapshot_path: Path, events_path: Path, limit: int, source_name: str | None = None) -> dict[str, Any]:
    if kind not in QUERY_KINDS:
        raise ValueError(f"unsupported kind: {kind}")
    snapshot = load_json(snapshot_path)
    events = load_recent_source_events(events_path, source_name, limit) if kind == "source.inspect" and source_name else load_recent_events(events_path, limit)
    text = render_text(kind, snapshot, events, source_name=source_name)
    result = build_query_result(kind, snapshot, events, source_name=source_name)
    if kind == "contract.catalog":
        result = {
            **result,
            "paths": {
                "snapshotPath": str(snapshot_path),
                "eventsPath": str(events_path),
            },
        }
    return {
        "ok": True,
        "kind": kind,
        "queryContractVersion": QUERY_CONTRACT_VERSION,
        "snapshotPath": str(snapshot_path),
        "eventsPath": str(events_path),
        "result": result,
        "sourceName": source_name,
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
    parser.add_argument("--source-name", help="Source name for source.inspect")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format for query")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="Broker snapshot.json path")
    parser.add_argument("--events-path", default=str(DEFAULT_EVENTS_PATH), help="Broker events.jsonl path")
    parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_LIMIT, help="Max recent events for events.recent or source.inspect")
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
        payload = build_query_payload(args.kind, snapshot_path, events_path, args.limit, source_name=args.source_name)
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
        query_payload = build_query_payload(args.kind, snapshot_path, events_path, args.limit, source_name=args.source_name)
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
