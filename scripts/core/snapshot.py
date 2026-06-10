#!/usr/bin/env python3
"""Infos-handle snapshot: broker data loading, parsing, event building, source/panel summaries."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from .catalog import ARTIFACT_NOTICE_CONTRACT_VERSION, DELIVERY_NOTICE_CONTRACT_VERSION, DEFAULT_QUERY_LIMIT


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, dict) else {}


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def slugify(value: str, *, fallback: str = "item", max_length: int = 48) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip().lower())
    lowered = lowered.strip("-._")
    if not lowered:
        lowered = fallback
    if len(lowered) > max_length:
        lowered = lowered[:max_length].rstrip("-._") or fallback
    return lowered


def trim_line(value: Any, max_chars: int = 44) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return text[:max_chars]
    return text[: max_chars - 1].rstrip() + "…"


def output_artifact_stem(kind: str, text: str, suffix: str) -> str:
    digest = hashlib.sha1(f"{kind}|{text}|{suffix}".encode("utf-8")).hexdigest()[:10]
    return f"{slugify(kind, fallback='query')}-{digest}"


def file_size_bytes(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None
    except OSError:
        return None


def guess_media_type(path: Path, fallback: str) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or fallback


def cleanup_stale_artifacts(output_root: Path, *, hours: float) -> dict[str, Any]:
    """Remove image/audio artifacts older than `hours`."""
    if hours <= 0:
        return {"action": "cleanup", "cleaned": 0, "formats": {}}
    import time

    cutoff = time.time() - hours * 3600
    cleaned: dict[str, int] = {}
    for format_name in ("image", "audio"):
        fmt_dir = (output_root / format_name)
        if not fmt_dir.is_dir():
            continue
        fmt_cleaned = 0
        for child in fmt_dir.iterdir():
            if not child.is_file():
                continue
            try:
                if child.stat().st_mtime < cutoff:
                    child.unlink()
                    fmt_cleaned += 1
            except OSError:
                pass
        cleaned[format_name] = fmt_cleaned
    total = sum(cleaned.values())
    return {"action": "cleanup", "cleaned": total, "formats": cleaned, "cutoffHours": hours}


def extract_last_nonempty_line(text: str) -> str | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return lines[-1] if lines else None


def normalize_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return DEFAULT_QUERY_LIMIT
    return max(1, parsed)


def first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_output_artifact_ref(output: dict[str, Any]) -> str:
    existing = first_text(output.get("artifactRef"))
    if existing:
        return existing
    format_name = slugify(str(output.get("format") or "artifact"), fallback="artifact", max_length=24)
    file_name = first_text(output.get("fileName"))
    if file_name:
        stem = Path(file_name).stem
    else:
        stem = slugify(first_text(output.get("path"), output.get("handler"), output.get("format")) or "artifact", fallback="artifact", max_length=72)
    return f"infos-handle:{format_name}:{slugify(stem, fallback='artifact', max_length=72)}"


def build_output_artifact_payload(output: dict[str, Any]) -> dict[str, Any]:
    return {
        "ref": build_output_artifact_ref(output),
        "format": output.get("format"),
        "handler": output.get("handler"),
        "mediaType": output.get("mediaType"),
        "path": output.get("path"),
        "fileName": output.get("fileName"),
        "sizeBytes": output.get("sizeBytes"),
        "preset": output.get("preset"),
        "summary": first_text(output.get("summary"), output.get("spokenText")),
        "renderer": output.get("renderer"),
    }


def build_frontstage_delivery_target(
    output: dict[str, Any],
    query_payload: dict[str, Any],
    request: dict[str, Any],
    *,
    notice_kind: str | None = None,
    artifact_ref: str | None = None,
    display_text: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": "frontstage",
        "channel": "frontstage_message",
        "requestedSessionKey": request.get("sessionKey") or DEFAULT_SESSION_KEY,
        "targetSessionKey": None,
        "messageId": None,
        "frontstageSource": request.get("frontstageSource"),
        "frontstageEventKey": request.get("frontstageEventKey"),
        "queryKind": query_payload.get("kind"),
        "handler": output.get("handler"),
        "noticeKind": notice_kind,
        "artifactRef": artifact_ref,
        "displayText": display_text,
    }


def hydrate_frontstage_delivery_target(target: dict[str, Any], notify_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target, dict):
        return {}
    target["targetSessionKey"] = notify_payload.get("targetSessionKey")
    notify_response = notify_payload.get("response") if isinstance(notify_payload.get("response"), dict) else {}
    target["messageId"] = notify_response.get("messageId")
    return target


def build_frontstage_delivery_notice(
    output: dict[str, Any],
    query_payload: dict[str, Any],
    request: dict[str, Any],
    *,
    delivery_kind: str,
    display_text: str,
    fallback_text: str,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = first_text(
        (artifact or {}).get("summary") if isinstance(artifact, dict) else None,
        output.get("summary"),
        output.get("spokenText"),
        (query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {}).get("summary"),
        query_payload.get("kind"),
        display_text,
    )
    artifact_ref = first_text((artifact or {}).get("ref") if isinstance(artifact, dict) else None)
    return {
        "contractVersion": DELIVERY_NOTICE_CONTRACT_VERSION,
        "kind": delivery_kind,
        "displayText": display_text,
        "fallbackText": fallback_text,
        "summary": summary,
        "queryKind": query_payload.get("kind"),
        "artifactRef": artifact_ref,
        "artifact": artifact,
        "frontstage": build_frontstage_delivery_target(
            output,
            query_payload,
            request,
            notice_kind=delivery_kind,
            artifact_ref=artifact_ref,
            display_text=display_text,
        ),
    }


def build_frontstage_artifact_notice_payload(
    output: dict[str, Any],
    query_payload: dict[str, Any],
    request: dict[str, Any],
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    format_name = str(output.get("format") or "artifact")
    label = {"image": "图片", "audio": "音频"}.get(format_name, "artifact")
    summary = first_text(
        output.get("summary"),
        output.get("spokenText"),
        (query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {}).get("summary"),
        query_payload.get("kind"),
    )
    file_name = first_text(output.get("fileName")) or "unknown"
    display_text = f"[infos-handle] 已生成{label} artifact：{file_name}｜{trim_line(summary or label, 34)}"
    fallback_text = f"[infos-handle] {label} artifact 已生成。"
    artifact_payload = artifact if isinstance(artifact, dict) else build_output_artifact_payload(output)
    return {
        "contractVersion": ARTIFACT_NOTICE_CONTRACT_VERSION,
        "kind": "artifact_notice",
        "artifactRef": artifact_payload["ref"],
        "label": label,
        "displayText": display_text,
        "fallbackText": fallback_text,
        "summary": summary,
        "artifact": artifact_payload,
        "delivery": build_frontstage_delivery_target(
            output,
            query_payload,
            request,
            notice_kind="artifact_notice",
            artifact_ref=artifact_payload["ref"],
            display_text=display_text,
        ),
    }


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


def list_panel_names(snapshot: dict[str, Any]) -> list[str]:
    panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    return sorted(name for name, payload in panels.items() if isinstance(payload, dict))


def record_data(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("data") if isinstance(record.get("data"), dict) else {}


def summarize_source_state(record: dict[str, Any]) -> str | None:
    if not record:
        return None
    payload = record_data(record)
    return first_text(record.get("summary"), payload.get("summary"), record.get("message"), record.get("eventKey"))


def summarize_source_delivery(record: dict[str, Any]) -> str | None:
    if not record:
        return None
    return first_text(record.get("message"), record.get("summary"), record.get("eventKey"))


def summarize_source_event(record: dict[str, Any]) -> str | None:
    if not record:
        return None
    payload = record_data(record)
    record_type = str(record.get("recordType") or "")
    if record_type in {"broker.source.event", "broker.source.latest"} or (payload.get("summary") and not record.get("sentAt")):
        return first_text(payload.get("summary"), record.get("summary"), record.get("message"), payload.get("detail"), record.get("eventKey"))
    return first_text(record.get("message"), record.get("summary"), payload.get("summary"), payload.get("detail"), record.get("eventKey"))


def build_source_event_item(record: dict[str, Any]) -> dict[str, Any]:
    payload = record_data(record)
    record_type = first_text(record.get("recordType"))
    return {
        "recordType": record_type,
        "source": first_text(record.get("source")),
        "sourceEventType": first_text(record.get("sourceEventType")),
        "sourceView": first_text(record.get("sourceView")),
        "eventAt": first_text(record.get("recordedAt"), record.get("sentAt")),
        "recordedAt": first_text(record.get("recordedAt")),
        "sentAt": first_text(record.get("sentAt")),
        "checkedAt": first_text(record.get("checkedAt"), payload.get("checkedAt"), payload.get("updatedAt")),
        "eventKey": first_text(record.get("eventKey")),
        "summary": summarize_source_event(record),
        "message": first_text(record.get("message")),
        "detail": first_text(record.get("detail"), payload.get("detail"), payload.get("issueOverview")),
        "severity": first_text(record.get("severity"), payload.get("severity")),
        "reportStatus": first_text(payload.get("status")),
        "deliveryStatus": first_text(record.get("deliveryStatus")),
        "ingestStatus": first_text(record.get("ingestStatus")),
        "isDelivery": record_type in {"frontstage.delivery.sent", "frontstage.delivery.latest"},
    }


def build_source_event_items(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        return []
    return [build_source_event_item(item) for item in records if isinstance(item, dict)]


def build_record_type_counts(event_items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in event_items:
        record_type = first_text(item.get("recordType")) or "unknown"
        counts[record_type] = counts.get(record_type, 0) + 1
    return counts


def build_latest_by_source(event_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest_by_source: dict[str, dict[str, Any]] = {}
    for item in event_items:
        source = first_text(item.get("source"))
        if not source:
            continue
        summary = latest_by_source.get(source)
        if summary is None:
            latest_by_source[source] = {
                "source": source,
                "eventCount": 1,
                "deliveryCount": 1 if bool(item.get("isDelivery")) else 0,
                "latestEventAt": item.get("eventAt"),
                "latestRecordType": item.get("recordType"),
                "latestEventSummary": item.get("summary") or item.get("message") or item.get("eventKey"),
                "latestEventKey": item.get("eventKey"),
                "sourceEventType": item.get("sourceEventType"),
                "sourceView": item.get("sourceView"),
                "isDelivery": bool(item.get("isDelivery")),
            }
            continue
        summary["eventCount"] = int(summary.get("eventCount") or 0) + 1
        if bool(item.get("isDelivery")):
            summary["deliveryCount"] = int(summary.get("deliveryCount") or 0) + 1
        if not summary.get("sourceEventType") and item.get("sourceEventType"):
            summary["sourceEventType"] = item.get("sourceEventType")
        if not summary.get("sourceView") and item.get("sourceView"):
            summary["sourceView"] = item.get("sourceView")
    return latest_by_source


def build_latest_by_source_items(latest_by_source: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    items = [dict(summary) for summary in latest_by_source.values() if isinstance(summary, dict)]
    items.sort(key=lambda item: str(item.get("source") or ""))
    items.sort(key=lambda item: str(item.get("latestEventAt") or ""), reverse=True)
    return items


def build_recent_events_result(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_items = build_source_event_items(events)
    available_sources = sorted(
        {
            source
            for item in event_items
            for source in [first_text(item.get("source"))]
            if source
        }
    )
    delivery_count = sum(1 for item in event_items if bool(item.get("isDelivery")))
    latest_by_source = build_latest_by_source(event_items)
    return {
        "count": len(event_items),
        "latestEventAt": event_items[0].get("eventAt") if event_items else None,
        "availableSources": available_sources,
        "sourceEventCount": len(event_items) - delivery_count,
        "deliveryCount": delivery_count,
        "recordTypeCounts": build_record_type_counts(event_items),
        "latestBySource": latest_by_source,
        "latestBySourceItems": build_latest_by_source_items(latest_by_source),
        "eventItems": event_items,
        "events": events,
    }


def build_source_overview(
    source_name: str,
    contract: dict[str, Any],
    latest_source_state: dict[str, Any],
    latest_delivery: dict[str, Any],
    recent_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    current_events = recent_events if isinstance(recent_events, list) else []
    source_event_type = (
        contract.get("sourceEventType")
        or latest_source_state.get("sourceEventType")
        or latest_delivery.get("sourceEventType")
        or (current_events[0].get("sourceEventType") if current_events else None)
    )
    source_view = (
        contract.get("sourceView")
        or latest_source_state.get("sourceView")
        or latest_delivery.get("sourceView")
        or (current_events[0].get("sourceView") if current_events else None)
    )
    latest_summary = build_latest_source_summary(current_events, latest_source_state, latest_delivery)
    return {
        "source": source_name,
        "sourceEventType": source_event_type,
        "sourceView": source_view,
        "hasContract": bool(contract),
        "hasSourceState": bool(latest_source_state),
        "hasDelivery": bool(latest_delivery),
        "latestEventAt": latest_summary.get("latestEventAt"),
        "latestRecordType": latest_summary.get("latestRecordType"),
        "latestEventSummary": latest_summary.get("latestEventSummary"),
        "latestEventKey": latest_summary.get("latestEventKey"),
        "latestEventItem": latest_summary.get("latestEventItem"),
        "latestSourceStateSummary": summarize_source_state(latest_source_state),
        "latestSourceStateRecordedAt": latest_source_state.get("recordedAt") or latest_source_state.get("sentAt"),
        "latestDeliveryMessage": summarize_source_delivery(latest_delivery),
        "latestDeliveryEventKey": latest_delivery.get("eventKey"),
        "latestDeliveryRecordType": (latest_delivery.get("recordType") or "frontstage.delivery.latest") if latest_delivery else None,
        "latestDeliverySentAt": latest_delivery.get("sentAt") or latest_delivery.get("recordedAt"),
        "latestDeliveryItem": build_source_event_item(latest_delivery) if latest_delivery else {},
    }


def build_source_latest_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
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
                **build_source_overview(source_name, contract, latest_state, latest_delivery),
                "contract": contract,
                "latestSourceState": latest_state,
                "latestDelivery": latest_delivery,
            }
        )
    return items


def build_source_catalog(snapshot: dict[str, Any]) -> dict[str, Any]:
    items = build_source_latest_items(snapshot)
    return {
        "count": len(items),
        "sources": items,
    }


def build_sources_latest(snapshot: dict[str, Any]) -> dict[str, Any]:
    items = build_source_latest_items(snapshot)
    return {
        "count": len(items),
        "availableSources": [item.get("source") for item in items if isinstance(item.get("source"), str)],
        "sourceItems": items,
        "sourceStateSnapshots": snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {},
        "sources": snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {},
        "latestSource": snapshot.get("latestSource"),
        "latestSourceState": snapshot.get("latestSourceState") if isinstance(snapshot.get("latestSourceState"), dict) else {},
        "latestDelivery": snapshot.get("latestDelivery") if isinstance(snapshot.get("latestDelivery"), dict) else {},
    }


def build_panel_catalog(snapshot: dict[str, Any]) -> dict[str, Any]:
    panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    items = []
    for panel_name in list_panel_names(snapshot):
        panel = panels.get(panel_name) if isinstance(panels.get(panel_name), dict) else {}
        items.append(
            {
                "panelName": panel_name,
                "available": bool(panel),
                "summary": panel.get("summary"),
                "detail": panel.get("detail"),
                "severity": panel.get("severity"),
                "checkedAt": panel.get("checkedAt"),
                "panel": panel,
            }
        )
    return {
        "count": len(items),
        "panels": items,
    }


def build_latest_source_summary(
    recent_events: list[dict[str, Any]],
    latest_source_state: dict[str, Any],
    latest_delivery: dict[str, Any],
) -> dict[str, Any]:
    if recent_events:
        latest_event = recent_events[0] if isinstance(recent_events[0], dict) else {}
        return {
            "latestEventAt": latest_event.get("recordedAt") or latest_event.get("sentAt"),
            "latestRecordType": latest_event.get("recordType"),
            "latestEventSummary": summarize_source_event(latest_event),
            "latestEventKey": latest_event.get("eventKey"),
            "latestEventItem": build_source_event_item(latest_event),
        }
    if latest_delivery:
        return {
            "latestEventAt": latest_delivery.get("recordedAt") or latest_delivery.get("sentAt"),
            "latestRecordType": latest_delivery.get("recordType") or "frontstage.delivery.latest",
            "latestEventSummary": summarize_source_delivery(latest_delivery),
            "latestEventKey": latest_delivery.get("eventKey"),
            "latestEventItem": build_source_event_item(latest_delivery),
        }
    if latest_source_state:
        return {
            "latestEventAt": latest_source_state.get("recordedAt") or latest_source_state.get("sentAt"),
            "latestRecordType": latest_source_state.get("recordType") or "broker.source.latest",
            "latestEventSummary": summarize_source_state(latest_source_state),
            "latestEventKey": latest_source_state.get("eventKey"),
            "latestEventItem": build_source_event_item(latest_source_state),
        }
    return {
        "latestEventAt": None,
        "latestRecordType": None,
        "latestEventSummary": None,
        "latestEventKey": None,
        "latestEventItem": {},
    }


def build_source_detail(snapshot: dict[str, Any], events: list[dict[str, Any]], source_name: str | None) -> dict[str, Any]:
    if not source_name:
        raise ValueError("source.inspect requires source_name")
    source_states = snapshot.get("sourceStateSnapshots") if isinstance(snapshot.get("sourceStateSnapshots"), dict) else {}
    deliveries = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
    contract_sources = contracts.get("sources") if isinstance(contracts.get("sources"), dict) else {}
    contract = contract_sources.get(source_name) if isinstance(contract_sources.get(source_name), dict) else {}
    latest_source_state = source_states.get(source_name) if isinstance(source_states.get(source_name), dict) else {}
    latest_delivery = deliveries.get(source_name) if isinstance(deliveries.get(source_name), dict) else {}
    recent_events = [item for item in events if str(item.get("source") or "") == source_name]
    recent_event_items = build_source_event_items(recent_events)
    recent_delivery_items = [item for item in recent_event_items if bool(item.get("isDelivery"))]
    recent_delivery_count = len(recent_delivery_items)
    return {
        **build_source_overview(source_name, contract, latest_source_state, latest_delivery, recent_events),
        "exists": bool(contract or latest_source_state or latest_delivery or recent_events),
        "availableSources": list_source_names(snapshot),
        "recentEventCount": len(recent_events),
        "recentDeliveryCount": recent_delivery_count,
        "contract": contract,
        "latestSourceState": latest_source_state,
        "latestDelivery": latest_delivery,
        "recentEventItems": recent_event_items,
        "recentDeliveryItems": recent_delivery_items,
        "recentEvents": recent_events,
    }


def build_panel_detail(snapshot: dict[str, Any], panel_name: str | None) -> dict[str, Any]:
    if not panel_name:
        raise ValueError("panel.inspect requires panel_name")
    panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    panel = panels.get(panel_name) if isinstance(panels.get(panel_name), dict) else {}
    return {
        "panelName": panel_name,
        "exists": bool(panel),
        "availablePanels": list_panel_names(snapshot),
        "summary": panel.get("summary") if isinstance(panel, dict) else None,
        "detail": panel.get("detail") if isinstance(panel, dict) else None,
        "severity": panel.get("severity") if isinstance(panel, dict) else None,
        "checkedAt": panel.get("checkedAt") if isinstance(panel, dict) else None,
        "panel": panel,
    }
