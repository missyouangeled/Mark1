#!/usr/bin/env python3
"""Infos-handle query: text rendering, query result building, request normalization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .catalog import (
    QUERY_CONTRACT_VERSION,
    REQUEST_CONTRACT_VERSION,
    QUERY_KINDS,
    SUPPORTED_OUTPUT_FORMATS,
    READY_OUTPUT_FORMATS,
    PREVIEW_OUTPUT_FORMATS,
    READY_DELIVERY_MODES,
    DEFAULT_QUERY_LIMIT,
    DEFAULT_IMAGE_PRESET,
    RESERVED_OUTPUT_FORMATS,
    build_output_format_catalog,
    build_output_handler_catalog,
    build_request_catalog,
    build_query_catalog,
)
from .snapshot import (
    load_json,
    load_recent_events,
    load_recent_source_events,
    first_text,
    normalize_limit,
    summarize_panel,
    build_panel_detail,
    build_panel_catalog,
    build_sources_latest,
    build_source_catalog,
    build_source_detail,
    build_recent_events_result,
)


def render_text(kind: str, snapshot: dict[str, Any], events: list[dict[str, Any]], source_name: str | None = None, panel_name: str | None = None) -> str:
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

    if kind == "health.detail":
        panel = snapshot.get("panels", {}).get("health") if isinstance(snapshot.get("panels"), dict) else {}
        raw = panel.get("raw") if isinstance(panel.get("raw"), dict) else {}
        gateway = raw.get("gateway") if isinstance(raw.get("gateway"), dict) else {}
        generic = raw.get("genericProbes") if isinstance(raw.get("genericProbes"), list) else []
        providers = raw.get("providerProbes") if isinstance(raw.get("providerProbes"), list) else []
        lines = [
            f"主机: {raw.get('host', 'unknown')}",
            f"检查时间: {raw.get('checkedAt', '-')}",
            f"严重程度: {raw.get('severity', 'unknown')}",
            f"概述: {raw.get('summary', '未知')}",
        ]
        if gateway:
            gw_status = gateway.get("status", "unknown")
            gw_latency = gateway.get("latencyMs", "?")
            gw_pid = gateway.get("pid", "?")
            lines.append(f"\nGateway: {gw_status} (延迟 {gw_latency}ms, PID {gw_pid})")
        if raw.get("statusError"):
            lines.append(f"Gateway 错误: {raw.get('statusError')}")
        if generic:
            lines.append("\n外部连通性:")
            for probe in generic:
                ok_mark = "✓" if probe.get("ok") else "✗"
                lines.append(f"  {ok_mark} {probe.get('name', '?')}: {probe.get('detail', '-')} ({probe.get('latencyMs', '?')}ms)")
        if providers:
            lines.append("\n模型 Provider:")
            for probe in providers:
                ok_mark = "✓" if probe.get("ok") else "✗"
                lines.append(f"  {ok_mark} {probe.get('name', '?')}: {probe.get('detail', '-')}")
        if raw.get("reasons"):
            lines.append(f"\n判定理由: {', '.join(str(r) for r in raw['reasons'])}")
        return "\n".join(lines)

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

    if kind == "panel.inspect":
        detail = build_panel_detail(snapshot, panel_name)
        resolved_panel_name = str(detail.get("panelName") or panel_name or "unknown")
        available_panels = detail.get("availablePanels") if isinstance(detail.get("availablePanels"), list) else []
        if not detail.get("exists"):
            available = ", ".join(str(item) for item in available_panels) or "none"
            return f"panel={resolved_panel_name}\nexists=false\navailablePanels: {available}"
        lines = [
            f"panel={resolved_panel_name}",
            "exists=true",
            f"summary: {detail.get('summary') or detail.get('detail') or detail.get('severity') or 'unknown'}",
        ]
        if detail.get("detail"):
            lines.append(f"detail: {detail.get('detail')}")
        if detail.get("severity"):
            lines.append(f"severity: {detail.get('severity')}")
        if detail.get("checkedAt"):
            lines.append(f"checkedAt: {detail.get('checkedAt')}")
        return "\n".join(lines)

    if kind == "panels.catalog":
        panel_catalog = build_panel_catalog(snapshot)
        items = panel_catalog.get("panels") if isinstance(panel_catalog.get("panels"), list) else []
        if not items:
            return "当前还没有 panel 快照。"
        lines = []
        for item in items:
            panel_name_str = str(item.get("panelName") or "unknown")
            summary = str(item.get("summary") or item.get("detail") or item.get("severity") or "unknown")
            severity = str(item.get("severity") or "unknown")
            checked_at = str(item.get("checkedAt") or "-")
            lines.append(f"- {panel_name_str}｜available=true｜severity={severity}｜summary={summary}｜checkedAt={checked_at}")
        return "\n".join(lines)

    if kind == "sources.latest":
        sources_latest = build_sources_latest(snapshot)
        items = sources_latest.get("sourceItems") if isinstance(sources_latest.get("sourceItems"), list) else []
        if not items:
            return "当前还没有来源快照。"
        lines = []
        for item in items:
            source = str(item.get("source") or "unknown")
            state_part = str(item.get("latestSourceStateSummary") or "无 ingest")
            delivery_part = str(item.get("latestDeliveryMessage") or "无 delivery")
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
        recent_event_items = detail.get("recentEventItems") if isinstance(detail.get("recentEventItems"), list) else []
        available_sources = detail.get("availableSources") if isinstance(detail.get("availableSources"), list) else []
        if not detail.get("exists"):
            available = ", ".join(str(item) for item in available_sources) or "none"
            return f"source={source}\nexists=false\navailableSources: {available}"
        state_text = str(detail.get("latestSourceStateSummary") or "无 ingest")
        delivery_text = str(detail.get("latestDeliveryMessage") or "无 delivery")
        event_type = str(detail.get("sourceEventType") or "unknown")
        source_view = str(detail.get("sourceView") or "unknown")
        lines = [
            f"source={source}",
            "exists=true",
            f"contract: eventType={event_type}｜view={source_view}",
            f"hasContract={str(bool(detail.get('hasContract'))).lower()}｜hasState={str(bool(detail.get('hasSourceState'))).lower()}｜hasDelivery={str(bool(detail.get('hasDelivery'))).lower()}｜recentEvents={detail.get('recentEventCount') or 0}｜recentDeliveries={detail.get('recentDeliveryCount') or 0}",
        ]
        if detail.get("latestEventAt") or detail.get("latestRecordType"):
            lines.append(f"latestRecord: {detail.get('latestRecordType') or 'unknown'} @ {detail.get('latestEventAt') or '-'}")
        lines.extend([
            f"latestState: {state_text}",
            f"latestDelivery: {delivery_text}",
        ])
        if recent_event_items:
            for item in recent_event_items[:3]:
                summary = str(item.get("summary") or item.get("message") or item.get("eventKey") or "")
                detail_text = str(item.get("detail") or "").strip()
                suffix = f"｜{detail_text}" if detail_text and detail_text != summary else ""
                lines.append(
                    f"- [{item.get('recordType') or 'unknown'}] {item.get('eventAt') or ''}｜{summary}{suffix}"
                )
        else:
            lines.append("- 最近没有这个 source 的事件记录。")
        return "\n".join(lines)

    if kind == "events.recent":
        recent_events = build_recent_events_result(events)
        event_items = recent_events.get("eventItems") if isinstance(recent_events.get("eventItems"), list) else []
        if not event_items:
            return "最近没有 broker 事件。"
        record_type_counts = recent_events.get("recordTypeCounts") if isinstance(recent_events.get("recordTypeCounts"), dict) else {}
        latest_by_source_items = recent_events.get("latestBySourceItems") if isinstance(recent_events.get("latestBySourceItems"), list) else []
        count_parts = [f"{record_type}:{count}" for record_type, count in record_type_counts.items()]
        latest_parts = [
            f"{item.get('source') or 'unknown'}={item.get('latestRecordType') or 'unknown'}"
            for item in latest_by_source_items
            if isinstance(item, dict)
        ]
        sources = ", ".join(str(item) for item in recent_events.get("availableSources") or []) or "none"
        lines = [
            f"count={recent_events.get('count') or 0}｜sources={sources}｜recordTypes={', '.join(count_parts) or 'none'}"
        ]
        if latest_parts:
            lines.append(f"latestBySource: {', '.join(latest_parts)}")
        for item in event_items:
            record_type = str(item.get("recordType") or "unknown")
            source = str(item.get("source") or "unknown")
            source_view = str(item.get("sourceView") or "unknown")
            source_event_type = str(item.get("sourceEventType") or "unknown")
            stamp = str(item.get("eventAt") or "")
            summary = str(item.get("summary") or item.get("message") or item.get("eventKey") or "")
            lines.append(f"- [{record_type}] {source}｜view={source_view}｜eventType={source_event_type}｜{stamp}｜{summary}")
        return "\n".join(lines)

    if kind == "events.timeline":
        recent_events = build_recent_events_result(events)
        event_items = recent_events.get("eventItems") if isinstance(recent_events.get("eventItems"), list) else []
        if not event_items:
            return "最近没有 broker 事件，无法生成时间线。"
        sources = ", ".join(str(s) for s in (recent_events.get("availableSources") or [])) or "none"
        lines = [f"Broker 事件时间线（共 {recent_events.get('count') or 0} 条，来源：{sources}）"]
        for idx, item in enumerate(event_items):
            record_type = str(item.get("recordType") or "unknown")
            source = str(item.get("source") or "unknown")
            stamp = str(item.get("eventAt") or "-")
            summary = str(item.get("summary") or item.get("message") or item.get("eventKey") or "")
            marker = "├─" if idx < len(event_items) - 1 else "└─"
            lines.append(f"  {marker} [{stamp}] {source} ({record_type})")
            if summary:
                lines.append(f"  │  {str(summary)[:80]}")
        return "\n".join(lines)

    if kind == "healthz":
        return "infos-handle healthz ok"
    if kind == "contract.catalog":
        contracts = snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {}
        snapshot_contract = snapshot.get("snapshotContract") if isinstance(snapshot.get("snapshotContract"), dict) else {}
        broker_contract_version = contracts.get("version")
        primary_view = snapshot_contract.get("primaryView") or "unknown"
        primary_published = snapshot_contract.get("primaryPublishedJsonKey") or "unknown"
        source_count = len(contracts.get("sources")) if isinstance(contracts.get("sources"), dict) else 0
        record_type_count = len(contracts.get("recordTypes")) if isinstance(contracts.get("recordTypes"), dict) else 0
        query_catalog = build_query_catalog(
            DEFAULT_QUERY_LIMIT,
            READY_OUTPUT_FORMATS,
            PREVIEW_OUTPUT_FORMATS,
            RESERVED_OUTPUT_FORMATS,
            build_output_format_catalog(),
            build_output_handler_catalog(),
            build_request_catalog(SUPPORTED_OUTPUT_FORMATS, READY_DELIVERY_MODES, PREVIEW_OUTPUT_FORMATS, READY_OUTPUT_FORMATS),
        )
        query_count = len(query_catalog.get("queries") or {})
        request_catalog = query_catalog.get("requestCatalog") if isinstance(query_catalog.get("requestCatalog"), dict) else {}
        request_action_count = len(request_catalog.get("actions") or {})
        format_catalog = query_catalog.get("outputFormatCatalog") if isinstance(query_catalog.get("outputFormatCatalog"), dict) else {}
        ready_formats = ",".join(name for name, meta in format_catalog.items() if isinstance(meta, dict) and meta.get("status") == "ready")
        preview_formats = ",".join(name for name, meta in format_catalog.items() if isinstance(meta, dict) and meta.get("status") == "preview")
        reserved_formats = ",".join(name for name, meta in format_catalog.items() if isinstance(meta, dict) and meta.get("status") == "reserved")
        return (
            f"infos-handle queryContractVersion={QUERY_CONTRACT_VERSION}｜"
            f"requestContractVersion={REQUEST_CONTRACT_VERSION}｜"
            f"broker contractVersion={broker_contract_version}｜"
            f"primaryView={primary_view}｜primaryPublishedJsonKey={primary_published}｜"
            f"sources={source_count}｜eventRecordTypes={record_type_count}｜queries={query_count}｜requestActions={request_action_count}｜"
            f"readyFormats={ready_formats or '-'}｜previewFormats={preview_formats or '-'}｜reservedFormats={reserved_formats or '-'}"
        )

    raise ValueError(f"unsupported kind: {kind}")


def build_query_result(
    kind: str,
    snapshot: dict[str, Any],
    events: list[dict[str, Any]],
    source_name: str | None = None,
    panel_name: str | None = None,
) -> dict[str, Any]:
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
    if kind == "health.detail":
        panel = panels.get("health") if isinstance(panels.get("health"), dict) else {}
        raw = panel.get("raw") if isinstance(panel.get("raw"), dict) else {}
        return {
            "severity": raw.get("severity"),
            "summary": raw.get("summary"),
            "host": raw.get("host"),
            "checkedAt": raw.get("checkedAt"),
            "gateway": raw.get("gateway") if isinstance(raw.get("gateway"), dict) else None,
            "statusError": raw.get("statusError"),
            "genericProbes": [
                {
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "ok": p.get("ok"),
                    "detail": p.get("detail"),
                    "latencyMs": p.get("latencyMs"),
                    "url": p.get("url"),
                }
                for p in (raw.get("genericProbes") if isinstance(raw.get("genericProbes"), list) else [])
            ],
            "providerProbes": [
                {
                    "name": p.get("name"),
                    "category": p.get("category"),
                    "ok": p.get("ok"),
                    "detail": p.get("detail"),
                    "url": p.get("url"),
                }
                for p in (raw.get("providerProbes") if isinstance(raw.get("providerProbes"), list) else [])
            ],
            "reasons": raw.get("reasons") if isinstance(raw.get("reasons"), list) else [],
            "issues": raw.get("issues") if isinstance(raw.get("issues"), list) else [],
        }
    if kind == "tasks.summary":
        return {
            "supervisor": panels.get("supervisor") if isinstance(panels.get("supervisor"), dict) else {},
            "recovery": panels.get("recovery") if isinstance(panels.get("recovery"), dict) else {},
            "latestDelivery": snapshot.get("latestDelivery") if isinstance(snapshot.get("latestDelivery"), dict) else {},
        }
    if kind == "recovery.summary":
        return panels.get("recovery") if isinstance(panels.get("recovery"), dict) else {}
    if kind == "panel.inspect":
        return build_panel_detail(snapshot, panel_name)
    if kind == "panels.catalog":
        return build_panel_catalog(snapshot)
    if kind == "sources.latest":
        return build_sources_latest(snapshot)
    if kind == "sources.catalog":
        return build_source_catalog(snapshot)
    if kind == "source.inspect":
        return build_source_detail(snapshot, events, source_name)
    if kind == "events.recent":
        return build_recent_events_result(events)
    if kind == "events.timeline":
        recent = build_recent_events_result(events)
        event_items = recent.get("eventItems") if isinstance(recent.get("eventItems"), list) else []
        timeline_items: list[dict[str, Any]] = []
        for item in event_items:
            timeline_items.append({
                "time": item.get("eventAt"),
                "source": item.get("source"),
                "recordType": item.get("recordType"),
                "sourceView": item.get("sourceView"),
                "sourceEventType": item.get("sourceEventType"),
                "summary": item.get("summary") or item.get("message") or item.get("eventKey"),
            })
        return {
            "count": recent.get("count"),
            "availableSources": recent.get("availableSources"),
            "recordTypeCounts": recent.get("recordTypeCounts"),
            "timelineItems": timeline_items,
        }
    if kind == "healthz":
        return {"ok": True, "kind": "healthz", "service": "infos-handle", "checkedAt": snapshot.get("checkedAt")}
    if kind == "contract.catalog":
        query_catalog = build_query_catalog(
            DEFAULT_QUERY_LIMIT,
            READY_OUTPUT_FORMATS,
            PREVIEW_OUTPUT_FORMATS,
            RESERVED_OUTPUT_FORMATS,
            build_output_format_catalog(),
            build_output_handler_catalog(),
            build_request_catalog(SUPPORTED_OUTPUT_FORMATS, READY_DELIVERY_MODES, PREVIEW_OUTPUT_FORMATS, READY_OUTPUT_FORMATS),
        )
        return {
            "queryContractVersion": QUERY_CONTRACT_VERSION,
            "requestContractVersion": REQUEST_CONTRACT_VERSION,
            "brokerContractVersion": snapshot.get("contractVersion"),
            "contracts": snapshot.get("contracts") if isinstance(snapshot.get("contracts"), dict) else {},
            "snapshotContract": snapshot.get("snapshotContract") if isinstance(snapshot.get("snapshotContract"), dict) else {},
            "queryCatalog": query_catalog,
            "requestCatalog": query_catalog.get("requestCatalog") if isinstance(query_catalog.get("requestCatalog"), dict) else {},
            "handlerCatalog": query_catalog.get("outputHandlerCatalog") if isinstance(query_catalog.get("outputHandlerCatalog"), dict) else {},
        }
    raise ValueError(f"unsupported kind: {kind}")


def build_query_payload(
    kind: str,
    snapshot_path: Path,
    events_path: Path,
    limit: int,
    output_format: str,
    source_name: str | None = None,
    panel_name: str | None = None,
) -> dict[str, Any]:
    if kind not in QUERY_KINDS:
        raise ValueError(f"unsupported kind: {kind}")
    snapshot = load_json(snapshot_path)
    events = load_recent_source_events(events_path, source_name, limit) if kind == "source.inspect" and source_name else load_recent_events(events_path, limit)
    text = render_text(kind, snapshot, events, source_name=source_name, panel_name=panel_name)
    result = build_query_result(kind, snapshot, events, source_name=source_name, panel_name=panel_name)
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
        "format": output_format,
        "queryContractVersion": QUERY_CONTRACT_VERSION,
        "snapshotPath": str(snapshot_path),
        "eventsPath": str(events_path),
        "result": result,
        "sourceName": source_name,
        "panelName": panel_name,
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "events": events,
        "text": text,
    }


def build_direct_message_payload(message: str, snapshot_path: Path, events_path: Path, output_format: str) -> dict[str, Any]:
    snapshot = load_json(snapshot_path)
    return {
        "ok": True,
        "kind": "direct.message",
        "format": output_format,
        "queryContractVersion": QUERY_CONTRACT_VERSION,
        "snapshotPath": str(snapshot_path),
        "eventsPath": str(events_path),
        "result": {
            "message": message,
            "messageSource": "direct",
        },
        "sourceName": None,
        "panelName": None,
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "events": [],
        "text": message,
    }


def normalize_handle_request(
    request: dict[str, Any],
    *,
    snapshot_path: Path,
    events_path: Path,
    output_root: Path,
    session_key: str,
    audio_renderer: str | None,
    audio_preset: str,
) -> dict[str, Any]:
    kind = first_text(request.get("kind"))
    message = first_text(request.get("message"))
    if not kind and not message:
        raise ValueError("handle requires kind or message")
    if kind and kind not in QUERY_KINDS:
        raise ValueError(f"unsupported kind: {kind}")

    output_format = first_text(request.get("format")) or "json"
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(f"unsupported format: {output_format}")

    delivery_mode = first_text(request.get("deliveryMode")) or "none"
    if delivery_mode not in READY_DELIVERY_MODES:
        raise ValueError(f"unsupported delivery mode: {delivery_mode}")

    data_payload = request.get("data") if isinstance(request.get("data"), dict) else None
    normalized_output_root = Path(first_text(request.get("outputRoot")) or str(output_root)).expanduser().resolve()

    return {
        "requestId": first_text(request.get("requestId")),
        "kind": kind,
        "message": message,
        "format": output_format,
        "limit": normalize_limit(request.get("limit")),
        "sourceName": first_text(request.get("sourceName")),
        "panelName": first_text(request.get("panelName")),
        "sessionKey": first_text(request.get("sessionKey")) or session_key,
        "deliveryMode": delivery_mode,
        "frontstageSource": first_text(request.get("frontstageSource")),
        "frontstageEventKey": first_text(request.get("frontstageEventKey")),
        "data": data_payload,
        "snapshotPath": str(Path(first_text(request.get("snapshotPath")) or str(snapshot_path)).expanduser().resolve()),
        "eventsPath": str(Path(first_text(request.get("eventsPath")) or str(events_path)).expanduser().resolve()),
        "outputRoot": str(normalized_output_root),
        "audioRenderer": first_text(request.get("audioRenderer")) or audio_renderer,
        "audioPreset": first_text(request.get("audioPreset")) or audio_preset,
        "imagePreset": first_text(request.get("imagePreset")) or DEFAULT_IMAGE_PRESET,
        "brokerStateDir": str(Path(first_text(request.get("brokerStateDir"))).expanduser().resolve()) if first_text(request.get("brokerStateDir")) else None,
        "brokerDataDir": str(Path(first_text(request.get("brokerDataDir"))).expanduser().resolve()) if first_text(request.get("brokerDataDir")) else None,
    }


def output_descriptor_for_stdout(query_payload: dict[str, Any], output_format: str) -> dict[str, Any]:
    if output_format == "text":
        return {
            "format": "text",
            "status": "ready",
            "handler": "text.stdout.v1",
            "delivery": "stdout",
            "mediaType": "text/plain; charset=utf-8",
            "text": query_payload.get("text") or "",
        }
    return {
        "format": "json",
        "status": "ready",
        "handler": "json.stdout.v1",
        "delivery": "stdout",
        "mediaType": "application/json",
        "result": query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {},
    }


def pick_response_severity(query_payload: dict[str, Any]) -> str | None:
    result = query_payload.get("result") if isinstance(query_payload.get("result"), dict) else {}
    snapshot = query_payload.get("snapshot") if isinstance(query_payload.get("snapshot"), dict) else {}
    panels = snapshot.get("panels") if isinstance(snapshot.get("panels"), dict) else {}
    return first_text(
        result.get("severity"),
        snapshot.get("severity"),
        (result.get("panel") if isinstance(result.get("panel"), dict) else {}).get("severity"),
        (panels.get("health") if isinstance(panels.get("health"), dict) else {}).get("severity"),
    )


def normalize_render_lines(values: list[Any], *, max_items: int = 8, split_pipes: bool = True) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        raw_parts = [str(value)]
        if split_pipes:
            raw_parts = []
            for part in str(value).splitlines() or [str(value)]:
                raw_parts.extend(part.split("｜"))
        for part in raw_parts:
            text = re.sub(r"\s+", " ", str(part or "").strip())
            text = text.strip("｜")
            if not text:
                continue
            if text in seen:
                continue
            seen.add(text)
            lines.append(text)
            if len(lines) >= max_items:
                return lines
    return lines



