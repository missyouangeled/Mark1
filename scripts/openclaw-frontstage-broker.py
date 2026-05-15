#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

DEFAULT_STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "frontstage"
STATE_PATH_NAME = "broker-state.json"
DEFAULT_BROKER_DATA_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "openclaw" / "broker"
EVENTS_PATH_NAME = "events.jsonl"
VIEWS_DIR_NAME = "views"
DEFAULT_SESSION_KEY = "agent:main:main"
DEFAULT_CONTROL_UI_DIST_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw" / "dist" / "control-ui"
PUBLIC_STATUS_HTML_NAME = "jarvis-frontstage-status.html"
PUBLIC_STATUS_JSON_NAME = "jarvis-frontstage-status.json"
PUBLIC_SNAPSHOT_JSON_NAME = "jarvis-frontstage-snapshot.json"
FRONTSTAGE_STATUS_CANVAS_DIR_ENV = "OPENCLAW_FRONTSTAGE_STATUS_CANVAS_DIR"
STATUS_SEVERITY_PRIORITY = {"ok": 0, "warn": 1, "critical": 2}
SOURCE_VIEW_LABELS = {
    "frontstage": "前台投递",
    "health": "本地健康",
    "tasks": "任务 / 监工",
    "recovery": "恢复观察",
}
SOURCE_EVENT_LABELS = {
    "broker.source.ingested": "broker 已收下来源事件",
    "frontstage.delivery.sent": "前台辅助消息已投递",
    "local_health.status.changed": "本地健康状态变化",
    "supervisor.status.changed": "监工状态变化",
    "frontstage_recovery.status.changed": "前台恢复状态变化",
}
SCHEMA_VERSION = 1
EVENT_CONTRACT_VERSION = 2
SOURCE_EVENT_RECORD_TYPE = "broker.source.event"
EVENT_LOG_RECORD_TYPE = "frontstage.delivery.sent"
SOURCE_SNAPSHOT_RECORD_TYPE = "frontstage.delivery.latest"
SOURCE_STATE_SNAPSHOT_RECORD_TYPE = "broker.source.latest"
FRONTSTAGE_SNAPSHOT_RECORD_TYPE = "frontstage.snapshot"
SNAPSHOT_VERSION = 1
PRIMARY_BROKER_VIEW = "snapshot"
PRIMARY_PUBLISHED_JSON_KEY = "frontstageSnapshotJson"
PRIMARY_CANVAS_PUBLISHED_JSON_KEY = "frontstageSnapshotCanvasJson"
COMPATIBILITY_VIEW_ALIASES = {
    "overview": PRIMARY_BROKER_VIEW,
}
COMPATIBILITY_PUBLISHED_JSON_ALIASES = {
    "frontstageStatusJson": PRIMARY_PUBLISHED_JSON_KEY,
    "frontstageStatusCanvasJson": PRIMARY_CANVAS_PUBLISHED_JSON_KEY,
}
SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "local-health": {
        "sourceEventType": "local_health.status.changed",
        "sourceView": "health",
        "reportPathKey": "localHealthReport",
    },
    "supervisor": {
        "sourceEventType": "supervisor.status.changed",
        "sourceView": "tasks",
        "reportPathKey": "supervisorStatus",
    },
    "frontstage-recovery": {
        "sourceEventType": "frontstage_recovery.status.changed",
        "sourceView": "recovery",
        "reportPathKey": "recoveryReport",
    },
}


def normalize_source_token(source: str) -> str:
    text = str(source or "").strip().replace("-", "_").replace(" ", "_")
    parts = [part for part in text.split("_") if part]
    return "_".join(parts) or "unknown_source"


def source_contract(source: str) -> dict[str, Any]:
    spec = SOURCE_SPECS.get(source, {})
    return {
        "source": source,
        "sourceEventType": str(spec.get("sourceEventType") or f"{normalize_source_token(source)}.status.changed"),
        "sourceView": spec.get("sourceView"),
        "reportPathKey": spec.get("reportPathKey"),
    }


def build_record_type_contract(description: str, required_fields: list[str], optional_fields: list[str] | None = None) -> dict[str, Any]:
    return {
        "description": description,
        "requiredFields": required_fields,
        "optionalFields": optional_fields or [],
    }


def build_record_type_catalog() -> dict[str, dict[str, Any]]:
    return {
        SOURCE_EVENT_RECORD_TYPE: build_record_type_contract(
            "Append-only source event recorded by broker ingest before any frontstage delivery is required.",
            ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt"],
            ["schemaVersion", "contractVersion", "data", "ingestStatus"],
        ),
        EVENT_LOG_RECORD_TYPE: build_record_type_contract(
            "Append-only frontstage delivery event written after a helper message is actually sent.",
            ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt", "sentAt"],
            ["schemaVersion", "contractVersion", "targetSessionKey", "messageId", "deliveryStatus"],
        ),
        SOURCE_SNAPSHOT_RECORD_TYPE: build_record_type_contract(
            "Latest successful frontstage delivery snapshot for one source inside frontstage.json / snapshot payloads.",
            ["recordType", "source", "sourceEventType", "sourceView"],
            ["eventKey", "sessionKey", "targetSessionKey", "messageId", "message", "sentAt"],
        ),
        SOURCE_STATE_SNAPSHOT_RECORD_TYPE: build_record_type_contract(
            "Latest ingest-side source snapshot for one source, even when no frontstage delivery happened yet.",
            ["recordType", "source", "sourceEventType", "sourceView"],
            ["eventKey", "sessionKey", "message", "recordedAt", "data"],
        ),
    }


def build_event_field_catalog(source_names: list[str]) -> dict[str, dict[str, Any]]:
    source_contracts = [source_contract(name) for name in source_names]
    known_source_views = sorted({str(item.get("sourceView")) for item in source_contracts if item.get("sourceView")})
    known_source_event_types = sorted({str(item.get("sourceEventType")) for item in source_contracts if item.get("sourceEventType")})
    return {
        "sourceEventType": {
            "type": "str",
            "description": "Stable semantic event type for one broker source.",
            "knownValues": known_source_event_types,
        },
        "sourceView": {
            "type": "str|null",
            "description": "Stable logical view bucket used by renderer / infos-handle consumers.",
            "knownValues": known_source_views,
        },
        "eventKey": {
            "type": "str",
            "description": "Source-scoped dedupe / correlation key shared across ingest and delivery records.",
        },
        "recordedAt": {
            "type": "str",
            "description": "Canonical broker event timestamp; always present on append-only events and may also appear on latest snapshots.",
        },
        "sentAt": {
            "type": "str|null",
            "description": "Frontstage delivery timestamp; expected on delivery records and delivery latest snapshots.",
        },
    }


def build_contract_catalog(source_names: list[str] | None = None) -> dict[str, Any]:
    ordered_names = list(dict.fromkeys([*SOURCE_SPECS.keys(), *(source_names or [])]))
    return {
        "version": EVENT_CONTRACT_VERSION,
        "sourceEventRecordType": SOURCE_EVENT_RECORD_TYPE,
        "deliveryEventRecordType": EVENT_LOG_RECORD_TYPE,
        "sourceSnapshotRecordType": SOURCE_SNAPSHOT_RECORD_TYPE,
        "sourceStateSnapshotRecordType": SOURCE_STATE_SNAPSHOT_RECORD_TYPE,
        "sourceEventTypeField": "sourceEventType",
        "sourceViewField": "sourceView",
        "recordTypes": build_record_type_catalog(),
        "eventFieldCatalog": build_event_field_catalog(ordered_names),
        "sources": {name: source_contract(name) for name in ordered_names},
    }


def canonical_source_record(source: str, record: dict[str, Any] | None) -> dict[str, Any]:
    current = record if isinstance(record, dict) else {}
    contract = source_contract(source)
    return {
        "recordType": SOURCE_SNAPSHOT_RECORD_TYPE,
        "source": source,
        "sourceEventType": contract["sourceEventType"],
        "sourceView": contract.get("sourceView"),
        "eventKey": current.get("eventKey"),
        "sessionKey": current.get("sessionKey"),
        "targetSessionKey": current.get("targetSessionKey"),
        "messageId": current.get("messageId"),
        "message": current.get("message"),
        "sentAt": current.get("sentAt"),
    }


def canonical_sources_map(sources: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        source_name: canonical_source_record(source_name, record)
        for source_name, record in sources.items()
        if isinstance(record, dict)
    }


def canonical_source_state_record(source: str, record: dict[str, Any] | None) -> dict[str, Any]:
    current = record if isinstance(record, dict) else {}
    contract = source_contract(source)
    data = current.get("data") if isinstance(current.get("data"), dict) else None
    return {
        "recordType": SOURCE_STATE_SNAPSHOT_RECORD_TYPE,
        "source": source,
        "sourceEventType": str(current.get("sourceEventType") or contract["sourceEventType"]),
        "sourceView": current.get("sourceView") or contract.get("sourceView"),
        "eventKey": current.get("eventKey"),
        "sessionKey": current.get("sessionKey"),
        "message": current.get("message"),
        "recordedAt": current.get("recordedAt"),
        "data": data,
    }


def canonical_source_states_map(source_states: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        source_name: canonical_source_state_record(source_name, record)
        for source_name, record in source_states.items()
        if isinstance(record, dict)
    }


def build_source_event_record(
    source: str,
    event_key: str,
    session_key: str,
    message: str,
    recorded_at: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = source_contract(source)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": EVENT_CONTRACT_VERSION,
        "recordType": SOURCE_EVENT_RECORD_TYPE,
        "source": source,
        "sourceEventType": contract["sourceEventType"],
        "sourceView": contract.get("sourceView"),
        "eventKey": event_key,
        "sessionKey": session_key,
        "message": message,
        "recordedAt": recorded_at,
        "data": data if isinstance(data, dict) else None,
        "ingestStatus": "recorded",
    }


def build_event_record(
    source: str,
    event_key: str,
    session_key: str,
    target_session_key: str | None,
    message_id: Any,
    message: str,
    recorded_at: str,
) -> dict[str, Any]:
    contract = source_contract(source)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": EVENT_CONTRACT_VERSION,
        "recordType": EVENT_LOG_RECORD_TYPE,
        "source": source,
        "sourceEventType": contract["sourceEventType"],
        "sourceView": contract.get("sourceView"),
        "eventKey": event_key,
        "sessionKey": session_key,
        "targetSessionKey": target_session_key,
        "messageId": message_id,
        "message": message,
        "sentAt": recorded_at,
        "recordedAt": recorded_at,
        "deliveryStatus": "sent",
    }


def canonical_event_record(record: dict[str, Any]) -> dict[str, Any]:
    current = record if isinstance(record, dict) else {}
    source = str(current.get("source") or "").strip()
    record_type = str(current.get("recordType") or EVENT_LOG_RECORD_TYPE)
    if record_type == SOURCE_EVENT_RECORD_TYPE:
        recorded_at = str(current.get("recordedAt") or now_iso())
        canonical = dict(current)
        canonical.update(
            build_source_event_record(
                source,
                str(current.get("eventKey") or ""),
                str(current.get("sessionKey") or ""),
                str(current.get("message") or ""),
                recorded_at,
                current.get("data") if isinstance(current.get("data"), dict) else None,
            )
        )
        return canonical

    recorded_at = str(current.get("recordedAt") or current.get("sentAt") or now_iso())
    canonical = dict(current)
    canonical.update(
        build_event_record(
            source,
            str(current.get("eventKey") or ""),
            str(current.get("sessionKey") or ""),
            str(current.get("targetSessionKey")) if current.get("targetSessionKey") is not None else None,
            current.get("messageId"),
            str(current.get("message") or ""),
            recorded_at,
        )
    )
    sent_at = current.get("sentAt")
    if isinstance(sent_at, str) and sent_at.strip():
        canonical["sentAt"] = sent_at.strip()
    canonical["deliveryStatus"] = str(current.get("deliveryStatus") or "sent")
    return canonical


def normalize_event_log(path: Path) -> None:
    if not path.exists():
        return
    normalized_lines: list[str] = []
    changed = False
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            normalized = canonical_event_record(payload if isinstance(payload, dict) else {})
            if normalized != payload:
                changed = True
            normalized_lines.append(json.dumps(normalized, ensure_ascii=False))
    if changed:
        save_text(path, "\n".join(normalized_lines) + "\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


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


def file_mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds")


def extract_timestamp(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def source_file_meta(path: Path, payload: dict[str, Any], *timestamp_keys: str) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "fileMtime": file_mtime_iso(path),
        "reportTimestamp": extract_timestamp(payload, *timestamp_keys),
    }


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def broker_paths(state_path: Path, broker_data_dir: Path) -> dict[str, Path]:
    views_dir = broker_data_dir / VIEWS_DIR_NAME
    source_root = broker_data_dir.parent
    return {
        "state": state_path,
        "events": broker_data_dir / EVENTS_PATH_NAME,
        "manifest": broker_data_dir / "manifest.json",
        "viewsDir": views_dir,
        "frontstageView": views_dir / "frontstage.json",
        "healthView": views_dir / "health.json",
        "tasksView": views_dir / "tasks.json",
        "recoveryView": views_dir / "recovery.json",
        "snapshotView": views_dir / "snapshot.json",
        "overviewView": views_dir / "overview.json",
        "localHealthReport": source_root / "local-health" / "last-report.json",
        "supervisorStatus": source_root / "supervisor" / "supervisor-status.json",
        "recoveryReport": source_root / "frontstage-recovery" / "last-report.json",
        "recoveryNotify": source_root / "frontstage-recovery" / "notify-state.json",
    }


def parse_isoish(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def severity_rank(value: str | None) -> int:
    return STATUS_SEVERITY_PRIORITY.get(str(value or "ok"), 0)


def pick_worst_severity(values: list[str]) -> str:
    return max(values or ["ok"], key=severity_rank)


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def resolve_control_ui_dist_root() -> Path | None:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve()
        if candidate.name == "control-ui" and candidate.exists():
            return candidate
        dist_root = candidate / "dist" / "control-ui"
        if dist_root.exists():
            return dist_root

    if DEFAULT_CONTROL_UI_DIST_ROOT.exists():
        return DEFAULT_CONTROL_UI_DIST_ROOT

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        candidate = Path(npm_root) / "openclaw" / "dist" / "control-ui"
        if candidate.exists():
            return candidate.resolve()
    except Exception:
        pass
    return None


def resolve_frontstage_canvas_dir() -> Path:
    override = os.environ.get(FRONTSTAGE_STATUS_CANVAS_DIR_ENV)
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".openclaw" / "canvas" / "documents" / "frontstage-status").resolve()


def humanize_source_view(source_view: str | None) -> str:
    value = str(source_view or "").strip()
    if value:
        return SOURCE_VIEW_LABELS.get(value, value)
    return "未分组"



def humanize_source_event_type(source_event_type: str | None, source: str | None = None) -> str:
    value = str(source_event_type or "").strip()
    if value:
        return SOURCE_EVENT_LABELS.get(value, value)
    source_value = str(source or "").strip()
    return source_value or "unknown"



def resolve_source_contract_fields(
    source: str,
    record: dict[str, Any],
    contracts: dict[str, Any],
) -> dict[str, Any]:
    contract_sources = contracts.get("sources") if isinstance(contracts.get("sources"), dict) else {}
    contract = contract_sources.get(source) if isinstance(contract_sources.get(source), dict) else {}
    source_event_type = str(record.get("sourceEventType") or contract.get("sourceEventType") or "").strip() or None
    source_view = str(record.get("sourceView") or contract.get("sourceView") or "").strip() or None
    source_view_label = humanize_source_view(source_view)
    source_event_label = humanize_source_event_type(source_event_type, source)
    contract_summary_parts = [part for part in [source_view_label if source_view else None, source_event_type, source] if isinstance(part, str) and part.strip()]
    return {
        "source": source,
        "sourceEventType": source_event_type,
        "sourceEventLabel": source_event_label,
        "sourceView": source_view,
        "sourceViewLabel": source_view_label,
        "contractSummary": " / ".join(contract_summary_parts),
    }



def summarize_health_panel(health_report: dict[str, Any]) -> dict[str, Any]:
    severity = str(health_report.get("severity") or "ok")
    summary = str(health_report.get("summary") or "本地健康状态未知")
    detail = str(health_report.get("issueOverview") or health_report.get("summary") or "")
    return {
        "severity": severity,
        "summary": summary,
        "detail": detail,
        "checkedAt": health_report.get("checkedAt"),
        "raw": health_report or None,
    }


def summarize_supervisor_panel(supervisor_report: dict[str, Any]) -> dict[str, Any]:
    service = supervisor_report.get("service") if isinstance(supervisor_report.get("service"), dict) else {}
    service_state = str(service.get("state") or "unknown")
    status = str(supervisor_report.get("status") or "unavailable")
    detail = str(supervisor_report.get("detail") or supervisor_report.get("summary") or "")

    if status in {"failed", "stalled"}:
        severity = "warn"
    elif status == "unavailable":
        severity = "warn"
    else:
        severity = "ok"

    if service_state == "disabled":
        summary = "监工已关闭"
    elif service_state == "armed" and status == "idle":
        summary = "监工待命中"
    elif status == "running":
        summary = "监工运行中"
    elif status == "failed":
        summary = "后台任务异常结束"
    elif status == "stalled":
        summary = "后台任务可能卡住"
    elif status == "done":
        summary = "后台任务刚完成"
    elif status == "unavailable":
        summary = "监工状态未接入"
    else:
        summary = str(supervisor_report.get("summary") or "监工状态未知")

    return {
        "severity": severity,
        "summary": summary,
        "detail": detail,
        "checkedAt": supervisor_report.get("checkedAt"),
        "status": status,
        "serviceState": service_state,
        "service": service,
        "focusTask": supervisor_report.get("focusTask") if isinstance(supervisor_report.get("focusTask"), dict) else None,
        "recentTerminalTask": supervisor_report.get("recentTerminalTask") if isinstance(supervisor_report.get("recentTerminalTask"), dict) else None,
        "raw": supervisor_report or None,
    }


def summarize_recovery_panel(recovery_report: dict[str, Any], recovery_notify: dict[str, Any]) -> dict[str, Any]:
    pending_projection = bool(recovery_report.get("pendingProjection"))
    anomaly_code = recovery_report.get("anomalyCode")
    detail = str(recovery_report.get("detail") or "")

    if anomaly_code and not pending_projection:
        severity = "warn"
        summary = "前台投影异常"
    elif pending_projection:
        severity = "ok"
        summary = "前台仍在追赶最新状态"
    elif recovery_notify.get("status") == "recovered":
        severity = "ok"
        summary = "前台投影已恢复稳定"
    elif recovery_report:
        severity = "ok"
        summary = "前台投影稳定"
    else:
        severity = "warn"
        summary = "前台恢复观察未接入"

    return {
        "severity": severity,
        "summary": summary,
        "detail": detail,
        "checkedAt": recovery_report.get("checkedAt") or recovery_notify.get("updatedAt") or recovery_notify.get("sentAt"),
        "pendingProjection": pending_projection,
        "pendingReason": recovery_report.get("pendingReason"),
        "anomalyCode": anomaly_code,
        "sessionSnapshot": recovery_report.get("sessionSnapshot") if isinstance(recovery_report.get("sessionSnapshot"), dict) else None,
        "notify": recovery_notify or None,
        "raw": recovery_report or None,
    }


def view_contract_catalog() -> dict[str, dict[str, Any]]:
    return {
        PRIMARY_BROKER_VIEW: {
            "role": "primary",
            "entryClass": "top_level",
            "note": "当前正式顶层 snapshot 入口；新的消费方默认应从这里开始。",
        },
        "overview": {
            "role": "legacy_alias",
            "entryClass": "top_level_alias",
            "canonicalView": PRIMARY_BROKER_VIEW,
            "note": "兼容旧 overview 入口；内容与 snapshot.json 一致，但不应再作为新的正式主入口。",
        },
        "frontstage": {
            "role": "supporting_view",
            "entryClass": "component",
            "note": "按 source 汇总最近辅助投递的支撑视图；供 snapshot 组装，不是顶层入口。",
        },
        "health": {
            "role": "supporting_view",
            "entryClass": "component",
            "note": "local-health 的支撑视图；用于拆面与排查，不是顶层主入口。",
        },
        "tasks": {
            "role": "supporting_view",
            "entryClass": "component",
            "note": "supervisor / recovery 的组合支撑视图；供 snapshot 汇总，不是顶层主入口。",
        },
        "recovery": {
            "role": "supporting_view",
            "entryClass": "component",
            "note": "frontstage-recovery 的支撑视图；用于排查，不是顶层主入口。",
        },
    }


def published_json_contract_catalog() -> dict[str, dict[str, Any]]:
    return {
        PRIMARY_PUBLISHED_JSON_KEY: {
            "role": "primary",
            "entryClass": "public_snapshot",
            "publicName": PUBLIC_SNAPSHOT_JSON_NAME,
            "note": "当前正式公开快照；dock / 轻量消费方应优先读取这里。",
        },
        "frontstageStatusJson": {
            "role": "legacy_alias",
            "entryClass": "public_snapshot_alias",
            "canonicalPublishedJsonKey": PRIMARY_PUBLISHED_JSON_KEY,
            "publicName": PUBLIC_STATUS_JSON_NAME,
            "note": "兼容旧 status.json 公开名；内容与正式 snapshot 一致，但不应再作为新的正式入口。",
        },
        PRIMARY_CANVAS_PUBLISHED_JSON_KEY: {
            "role": "primary",
            "entryClass": "canvas_snapshot",
            "publicName": "snapshot.json",
            "note": "canvas 内部正式 snapshot 副本。",
        },
        "frontstageStatusCanvasJson": {
            "role": "legacy_alias",
            "entryClass": "canvas_snapshot_alias",
            "canonicalPublishedJsonKey": PRIMARY_CANVAS_PUBLISHED_JSON_KEY,
            "publicName": "status.json",
            "note": "canvas 内部兼容别名；内容与 snapshot.json 一致。",
        },
    }


def snapshot_contract_metadata() -> dict[str, Any]:
    return {
        "primaryView": PRIMARY_BROKER_VIEW,
        "primaryPublishedJsonKey": PRIMARY_PUBLISHED_JSON_KEY,
        "compatibilityViewAliases": dict(COMPATIBILITY_VIEW_ALIASES),
        "compatibilityPublishedJsonAliases": dict(COMPATIBILITY_PUBLISHED_JSON_ALIASES),
        "viewCatalog": view_contract_catalog(),
        "publishedJsonCatalog": published_json_contract_catalog(),
        "note": "snapshot / snapshot.json / jarvis-frontstage-snapshot.json 是当前正式主入口；overview / *frontstage-status.json 只保留为兼容别名；frontstage / health / tasks / recovery 这些名字现在只表示支撑视图，不再视作顶层主入口。",
    }


def build_artifact_catalog(paths: dict[str, Path], published_paths: dict[str, str]) -> dict[str, Any]:
    view_paths = {
        "frontstage": paths["frontstageView"],
        "health": paths["healthView"],
        "tasks": paths["tasksView"],
        "recovery": paths["recoveryView"],
        "snapshot": paths["snapshotView"],
        "overview": paths["overviewView"],
    }
    published_json_paths = {
        PRIMARY_PUBLISHED_JSON_KEY: published_paths.get(PRIMARY_PUBLISHED_JSON_KEY),
        "frontstageStatusJson": published_paths.get("frontstageStatusJson"),
        PRIMARY_CANVAS_PUBLISHED_JSON_KEY: published_paths.get(PRIMARY_CANVAS_PUBLISHED_JSON_KEY),
        "frontstageStatusCanvasJson": published_paths.get("frontstageStatusCanvasJson"),
    }
    view_catalog = view_contract_catalog()
    published_catalog = published_json_contract_catalog()
    return {
        "views": {
            name: {
                **view_catalog.get(name, {}),
                "path": str(path),
            }
            for name, path in view_paths.items()
        },
        "publishedJson": {
            key: {
                **published_catalog.get(key, {}),
                "path": value,
            }
            for key, value in published_json_paths.items()
        },
    }


def build_frontstage_status_payload(
    frontstage_view: dict[str, Any],
    health_view_payload: dict[str, Any] | None,
    tasks_view_payload: dict[str, Any] | None,
    recovery_view_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    contracts = frontstage_view.get("contracts") if isinstance(frontstage_view.get("contracts"), dict) else build_contract_catalog()
    health_report = (health_view_payload or {}).get("report") if isinstance(health_view_payload, dict) else {}
    tasks_supervisor = ((tasks_view_payload or {}).get("supervisor") or {}) if isinstance(tasks_view_payload, dict) else {}
    supervisor_report = tasks_supervisor.get("report") if isinstance(tasks_supervisor.get("report"), dict) else {}
    recovery_section = ((tasks_view_payload or {}).get("recovery") or {}) if isinstance(tasks_view_payload, dict) else {}
    recovery_report = (recovery_view_payload or {}).get("report") if isinstance(recovery_view_payload, dict) else {}
    if not recovery_report and isinstance(recovery_section.get("report"), dict):
        recovery_report = recovery_section.get("report")
    recovery_notify = (recovery_view_payload or {}).get("notify") if isinstance(recovery_view_payload, dict) else {}
    if not recovery_notify and isinstance(recovery_section.get("notify"), dict):
        recovery_notify = recovery_section.get("notify")

    health_panel = summarize_health_panel(health_report if isinstance(health_report, dict) else {})
    supervisor_panel = summarize_supervisor_panel(supervisor_report if isinstance(supervisor_report, dict) else {})
    recovery_panel = summarize_recovery_panel(
        recovery_report if isinstance(recovery_report, dict) else {},
        recovery_notify if isinstance(recovery_notify, dict) else {},
    )

    source_records = frontstage_view.get("sources") if isinstance(frontstage_view.get("sources"), dict) else {}
    source_state_records = frontstage_view.get("sourceStates") if isinstance(frontstage_view.get("sourceStates"), dict) else {}
    deliveries: list[dict[str, Any]] = []
    for source_name, record in source_records.items():
        if not isinstance(record, dict):
            continue
        contract_fields = resolve_source_contract_fields(source_name, record, contracts)
        deliveries.append(
            {
                "recordType": record.get("recordType") or SOURCE_SNAPSHOT_RECORD_TYPE,
                "source": source_name,
                "sourceEventType": contract_fields["sourceEventType"],
                "sourceEventLabel": contract_fields["sourceEventLabel"],
                "sourceView": contract_fields["sourceView"],
                "sourceViewLabel": contract_fields["sourceViewLabel"],
                "contractSummary": contract_fields["contractSummary"],
                "eventKey": record.get("eventKey"),
                "targetSessionKey": record.get("targetSessionKey"),
                "message": record.get("message"),
                "messageId": record.get("messageId"),
                "sentAt": record.get("sentAt"),
            }
        )
    deliveries.sort(key=lambda item: item.get("sentAt") or "", reverse=True)
    latest_delivery = deliveries[0] if deliveries else None

    source_state_snapshots: list[dict[str, Any]] = []
    for source_name, record in source_state_records.items():
        if not isinstance(record, dict):
            continue
        contract_fields = resolve_source_contract_fields(source_name, record, contracts)
        source_state_snapshots.append(
            {
                "recordType": record.get("recordType") or SOURCE_STATE_SNAPSHOT_RECORD_TYPE,
                "source": source_name,
                "sourceEventType": contract_fields["sourceEventType"],
                "sourceEventLabel": contract_fields["sourceEventLabel"],
                "sourceView": contract_fields["sourceView"],
                "sourceViewLabel": contract_fields["sourceViewLabel"],
                "contractSummary": contract_fields["contractSummary"],
                "eventKey": record.get("eventKey"),
                "sessionKey": record.get("sessionKey"),
                "message": record.get("message"),
                "recordedAt": record.get("recordedAt"),
                "data": record.get("data") if isinstance(record.get("data"), dict) else None,
            }
        )
    source_state_snapshots.sort(key=lambda item: item.get("recordedAt") or "", reverse=True)
    latest_source_state = source_state_snapshots[0] if source_state_snapshots else None

    issue_labels: list[str] = []
    issue_details: list[str] = []
    severity_candidates = [health_panel["severity"], supervisor_panel["severity"], recovery_panel["severity"]]
    if health_panel["severity"] in {"warn", "critical"}:
        issue_labels.append(f"本地健康：{health_panel['summary']}")
        if health_panel.get("detail"):
            issue_details.append(str(health_panel["detail"]))
    if supervisor_panel["severity"] == "warn":
        issue_labels.append(f"监工：{supervisor_panel['summary']}")
        if supervisor_panel.get("detail"):
            issue_details.append(str(supervisor_panel["detail"]))
    if recovery_panel["severity"] == "warn":
        issue_labels.append(f"前台恢复：{recovery_panel['summary']}")
        if recovery_panel.get("detail"):
            issue_details.append(str(recovery_panel["detail"]))

    overall_severity = pick_worst_severity(severity_candidates)
    if issue_labels:
        summary = issue_labels[0]
        issue_overview = "；".join(issue_labels)
    else:
        summary = "前台状态总体正常"
        issue_overview = "broker / 监工 / 恢复观察 / 本地健康当前都没看到明显异常。"

    actions: list[str] = []
    if isinstance(health_report, dict):
        actions.extend([str(item) for item in health_report.get("selfHelpActions", []) if isinstance(item, str)])
    recent_terminal = supervisor_panel.get("recentTerminalTask") if isinstance(supervisor_panel.get("recentTerminalTask"), dict) else None
    if supervisor_panel["severity"] == "warn" and recent_terminal:
        actions.append(
            f"监工最近一条结束任务是“{recent_terminal.get('label') or recent_terminal.get('taskId') or 'unknown'}”，先核对它的 terminalSummary / error 再决定是否重跑。"
        )
    elif supervisor_panel["severity"] == "warn":
        actions.append("监工显示后台任务有异常时，先看 `supervisor-status.json` 里的 recentTerminalTask，再决定继续等、重跑还是关监工。")
    if recovery_panel["severity"] == "warn":
        actions.append("如果前台恢复观察提示异常，优先刷新当前页面；若仍不稳定，再重开浏览器，并对照 recovery 报告看 anomalyCode。")
    if not actions:
        actions.extend([
            "当前辅助状态都正常；如果只是页面偶发卡住，优先刷新页面。",
            "若刷新后仍不对，再重开浏览器；这更像前端投影或浏览器状态问题，不像 broker 本身已经坏了。",
        ])
    actions = dedupe_preserve_order(actions)[:4]

    freshness = frontstage_view.get("freshness") if isinstance(frontstage_view.get("freshness"), dict) else {}
    host = (
        health_report.get("host") if isinstance(health_report, dict) else None
    ) or (
        supervisor_report.get("host") if isinstance(supervisor_report, dict) else None
    ) or socket.gethostname()

    frontstage_panel = {
        "severity": "ok",
        "summary": "最近辅助投递正常" if latest_delivery else "暂未发生新的辅助投递",
        "detail": str(latest_delivery.get("message") or latest_delivery.get("contractSummary") or latest_delivery.get("eventKey") or "当前 broker 数据层已就位，等待下一次辅助事件。") if latest_delivery else "当前 broker 数据层已就位，等待下一次辅助事件。",
        "checkedAt": latest_delivery.get("sentAt") if latest_delivery else frontstage_view.get("updatedAt"),
        "latestDelivery": latest_delivery,
        "deliveries": deliveries[:6],
    }
    panels = {
        "frontstage": frontstage_panel,
        "health": health_panel,
        "supervisor": supervisor_panel,
        "recovery": recovery_panel,
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": EVENT_CONTRACT_VERSION,
        "recordType": FRONTSTAGE_SNAPSHOT_RECORD_TYPE,
        "snapshotVersion": SNAPSHOT_VERSION,
        "contracts": contracts,
        "snapshotContract": snapshot_contract_metadata(),
        "checkedAt": frontstage_view.get("updatedAt") or now_iso(),
        "host": host,
        "severity": overall_severity,
        "summary": summary,
        "issueOverview": issue_overview,
        "issueDetails": issue_details,
        "selfHelpActions": actions,
        "panels": panels,
        "latestDelivery": latest_delivery,
        "latestSourceState": latest_source_state,
        "sourceSnapshots": source_records,
        "sourceStateSnapshots": source_state_records,
        "sourceStateTimeline": source_state_snapshots[:12],
        "frontstage": frontstage_panel,
        "health": health_panel,
        "supervisor": supervisor_panel,
        "recovery": recovery_panel,
        "freshness": freshness,
        "latestSource": frontstage_view.get("latestSource"),
        "sources": source_records,
    }


def badge_class(severity: str | None) -> str:
    return {"ok": "ok", "warn": "warn", "critical": "bad"}.get(str(severity or "ok"), "warn")


def severity_label(severity: str | None) -> str:
    return {"ok": "正常", "warn": "告警", "critical": "严重异常"}.get(str(severity or "ok"), str(severity or "unknown").upper())


def build_frontstage_status_html(payload: dict[str, Any]) -> str:
    hero_class = badge_class(str(payload.get("severity") or "ok"))
    summary = escape(str(payload.get("summary") or "前台状态未知"))
    issue_overview = escape(str(payload.get("issueOverview") or summary))
    checked_at = escape(str(payload.get("checkedAt") or ""))
    host = escape(str(payload.get("host") or "-"))

    canonical_panels = payload.get("panels") if isinstance(payload.get("panels"), dict) else {}
    panels = {
        "frontstage": canonical_panels.get("frontstage") if isinstance(canonical_panels.get("frontstage"), dict) else (payload.get("frontstage") if isinstance(payload.get("frontstage"), dict) else {}),
        "health": canonical_panels.get("health") if isinstance(canonical_panels.get("health"), dict) else (payload.get("health") if isinstance(payload.get("health"), dict) else {}),
        "supervisor": canonical_panels.get("supervisor") if isinstance(canonical_panels.get("supervisor"), dict) else (payload.get("supervisor") if isinstance(payload.get("supervisor"), dict) else {}),
        "recovery": canonical_panels.get("recovery") if isinstance(canonical_panels.get("recovery"), dict) else (payload.get("recovery") if isinstance(payload.get("recovery"), dict) else {}),
    }

    panel_cards = "".join(
        f"""
        <div class='mini {badge_class(str(panel.get("severity") or "ok"))}'>
          <div class='k'>{escape(title)}</div>
          <div class='v'>{escape(str(panel.get("summary") or "未知"))}</div>
          <div class='d'>{escape(str(panel.get("detail") or ""))}</div>
        </div>
        """
        for title, panel in [
            ("前台投递", panels["frontstage"]),
            ("本地健康", panels["health"]),
            ("监工", panels["supervisor"]),
            ("恢复观察", panels["recovery"]),
        ]
    )

    deliveries = panels["frontstage"].get("deliveries") if isinstance(panels["frontstage"].get("deliveries"), list) else []
    deliveries_html = "".join(
        f"<li><strong>{escape(str(item.get('sourceViewLabel') or item.get('sourceEventLabel') or item.get('source') or 'unknown'))}</strong><span>{escape(str(item.get('sourceEventLabel') or item.get('sourceEventType') or item.get('source') or ''))}｜{escape(str(item.get('message') or item.get('eventKey') or ''))}<small>{escape(str(item.get('contractSummary') or item.get('sourceEventType') or item.get('source') or ''))}</small></span><em>{escape(str(item.get('sentAt') or '-'))}</em></li>"
        for item in deliveries[:6]
        if isinstance(item, dict)
    ) or "<li><strong>暂无</strong><span>当前还没有新的辅助投递记录。<small>等待 broker 新的正式事件快照。</small></span><em>-</em></li>"

    self_help_items = "".join(f"<li>{escape(str(item))}</li>" for item in payload.get("selfHelpActions", []) if isinstance(item, str)) or "<li>暂无</li>"

    freshness = payload.get("freshness") if isinstance(payload.get("freshness"), dict) else {}
    freshness_sources = freshness.get("sources") if isinstance(freshness.get("sources"), dict) else {}
    freshness_html = "".join(
        f"<li><strong>{escape(name)}</strong><span>{escape(str(meta.get('reportTimestamp') or meta.get('fileMtime') or '未发现时间戳'))}</span><em>{escape(str(meta.get('path') or '-'))}</em></li>"
        for name, meta in freshness_sources.items()
        if isinstance(meta, dict)
    ) or "<li><strong>暂无</strong><span>还没拿到 freshness 元数据。</span><em>-</em></li>"

    issue_details = payload.get("issueDetails") if isinstance(payload.get("issueDetails"), list) else []
    issue_details_html = "".join(f"<li>{escape(str(item))}</li>" for item in issue_details if str(item).strip()) or "<li>当前没有额外问题细节。</li>"

    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta http-equiv=\"refresh\" content=\"30\" />
  <title>前台状态总览</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: radial-gradient(circle at top, rgba(67, 97, 238, 0.16), transparent 36%), #081018; color: #eaf2ff; font: 14px/1.55 "Segoe UI", "PingFang SC", sans-serif; }}
    .wrap {{ max-width: 1120px; margin: 0 auto; padding: 24px; }}
    .shell {{ border: 1px solid rgba(120, 153, 198, 0.18); background: linear-gradient(180deg, rgba(10, 18, 28, 0.96), rgba(6, 11, 18, 0.98)); border-radius: 24px; padding: 22px; box-shadow: 0 26px 90px rgba(0,0,0,.30); backdrop-filter: blur(16px); }}
    .top {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; flex-wrap:wrap; }}
    .eyebrow {{ font-size: 12px; letter-spacing: .14em; text-transform: uppercase; color: #7f9cbc; margin-bottom: 8px; }}
    .title {{ font-size: 30px; line-height: 1.15; font-weight: 800; margin: 0; }}
    .sub {{ color: #adc1d8; margin-top: 12px; max-width: 760px; }}
    .meta {{ margin-top: 10px; color: #86a0bf; font-size: 12px; display:flex; gap:14px; flex-wrap:wrap; }}
    .badge {{ padding: 8px 14px; border-radius: 999px; font-size: 12px; font-weight: 800; border: 1px solid transparent; }}
    .badge.ok {{ background: rgba(34,197,94,.14); color: #9ef6bc; border-color: rgba(34,197,94,.28); }}
    .badge.warn {{ background: rgba(245,158,11,.14); color: #ffd796; border-color: rgba(245,158,11,.30); }}
    .badge.bad {{ background: rgba(239,68,68,.14); color: #ffb0b0; border-color: rgba(239,68,68,.34); }}
    .grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-top: 22px; }}
    .mini {{ border-radius: 18px; padding: 16px; border: 1px solid rgba(255,255,255,.07); background: linear-gradient(180deg, rgba(255,255,255,.03), rgba(255,255,255,.02)); min-height: 136px; }}
    .mini .k {{ font-size: 12px; color: #88a4c3; text-transform: uppercase; letter-spacing: .08em; }}
    .mini .v {{ font-size: 20px; line-height: 1.25; font-weight: 800; margin-top: 10px; }}
    .mini .d {{ margin-top: 8px; font-size: 13px; color: #bfd0e3; }}
    .mini.ok .v {{ color: #9ef6bc; }}
    .mini.warn .v {{ color: #ffd796; }}
    .mini.bad .v {{ color: #ffb0b0; }}
    .sections {{ display:grid; grid-template-columns: 1.2fr .8fr; gap: 14px; margin-top: 18px; }}
    .panel {{ border-radius: 18px; padding: 18px; border: 1px solid rgba(255,255,255,.07); background: rgba(255,255,255,.025); }}
    .panel h2 {{ margin: 0 0 12px; font-size: 15px; color: #e6eef9; }}
    .panel .hint {{ margin: -4px 0 12px; color: #8ea8c5; font-size: 12px; }}
    .list {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }}
    .list li {{ display:grid; grid-template-columns: 120px 1fr 180px; gap: 12px; align-items:flex-start; padding: 12px 0; border-top: 1px solid rgba(255,255,255,.06); }}
    .list li:first-child {{ border-top: 0; padding-top: 0; }}
    .list strong {{ color: #edf4ff; font-size: 13px; }}
    .list span {{ color: #bfd0e3; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }}
    .list span small {{ color: #7f98b5; font-size: 12px; }}
    .list em {{ color: #7f98b5; font-size: 12px; font-style: normal; word-break: break-all; }}
    .actions {{ display:flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; min-height: 38px; padding: 0 14px; border-radius: 12px; text-decoration:none; font-size: 13px; font-weight: 700; color: #eff6ff; border: 1px solid rgba(96, 165, 250, 0.22); background: linear-gradient(180deg, rgba(37, 99, 235, 0.92), rgba(29, 78, 216, 0.88)); }}
    .btn.secondary {{ background: transparent; color: #dbe8f6; border-color: rgba(148, 163, 184, 0.24); }}
    .foot {{ margin-top: 14px; font-size: 12px; color: #7f98b5; }}
    @media (max-width: 860px) {{ .sections {{ grid-template-columns: 1fr; }} .list li {{ grid-template-columns: 1fr; }} .title {{ font-size: 26px; }} }}
  </style>
</head>
<body data-checked-at=\"{checked_at}\">
  <div class=\"wrap\">
    <div class=\"shell\">
      <div class=\"top\">
        <div>
          <div class=\"eyebrow\">Jarvis Frontstage Sidecar</div>
          <h1 class=\"title\">前台状态总览</h1>
          <div class=\"sub\">{issue_overview}</div>
          <div class=\"meta\">
            <span>更新时间：{checked_at or '-'}</span>
            <span>主机：{host}</span>
          </div>
        </div>
        <div class=\"badge {hero_class}\">{escape(severity_label(payload.get('severity')))}</div>
      </div>

      <div class=\"grid\">{panel_cards}</div>

      <div class=\"sections\">
        <div class=\"panel\">
          <h2>最近辅助投递</h2>
          <div class=\"hint\">这里展示 broker 最近沉淀下来的前台辅助消息，便于确认“谁在往当前 dashboard 回报”。当前正式 JSON 主入口是 snapshot；status.json 只保留为兼容别名。</div>
          <ul class=\"list\">{deliveries_html}</ul>
          <div class=\"actions\">
            <a class=\"btn\" href=\"/jarvis-local-health-status.html\" target=\"_blank\" rel=\"noopener noreferrer\">打开本地健康页</a>
            <a class=\"btn secondary\" href=\"/jarvis-frontstage-snapshot.json\" target=\"_blank\" rel=\"noopener noreferrer\">查看 snapshot JSON</a>
          </div>
        </div>
        <div class=\"panel\">
          <h2>当前建议</h2>
          <div class=\"hint\">尽量先给你确定性的本地判断，不让这页自己变成新的噪音。</div>
          <ul class=\"list\">{self_help_items}</ul>
        </div>
      </div>

      <div class=\"sections\">
        <div class=\"panel\">
          <h2>当前问题细节</h2>
          <div class=\"hint\">这里只收当前已经能确定的异常线索，不做临场猜测。</div>
          <ul class=\"list\">{issue_details_html}</ul>
        </div>
        <div class=\"panel\">
          <h2>数据新鲜度</h2>
          <div class=\"hint\">这些时间来自 broker sidecar 当前看到的 source 文件，用来判断页面是不是还在吃最新快照。</div>
          <ul class=\"list\">{freshness_html}</ul>
        </div>
      </div>

      <div class=\"foot\">这个页面由 broker sidecar 周期重建，不接管主对话链；它的目标只是把辅助状态收口成一个更稳定、更好看的读面。当前正式数据口径以 snapshot 为准，status.json 仅作兼容别名。</div>
    </div>
  </div>
</body>
</html>
"""


def publish_frontstage_status(payload: dict[str, Any]) -> dict[str, str]:
    html = build_frontstage_status_html(payload)
    canvas_dir = resolve_frontstage_canvas_dir()
    canvas_dir.mkdir(parents=True, exist_ok=True)
    canvas_html = canvas_dir / "index.html"
    canvas_status_json = canvas_dir / "status.json"
    canvas_snapshot_json = canvas_dir / "snapshot.json"
    save_text(canvas_html, html)
    save_json(canvas_status_json, payload)
    save_json(canvas_snapshot_json, payload)

    published = {
        "frontstageStatusCanvasHtml": str(canvas_html),
        "frontstageStatusCanvasJson": str(canvas_status_json),
        "frontstageSnapshotCanvasJson": str(canvas_snapshot_json),
    }

    control_ui_dist_root = resolve_control_ui_dist_root()
    if control_ui_dist_root:
        control_ui_dist_root.mkdir(parents=True, exist_ok=True)
        public_html = control_ui_dist_root / PUBLIC_STATUS_HTML_NAME
        public_status_json = control_ui_dist_root / PUBLIC_STATUS_JSON_NAME
        public_snapshot_json = control_ui_dist_root / PUBLIC_SNAPSHOT_JSON_NAME
        save_text(public_html, html)
        save_json(public_status_json, payload)
        save_json(public_snapshot_json, payload)
        published["frontstageStatusHtml"] = str(public_html)
        published["frontstageStatusJson"] = str(public_status_json)
        published["frontstageSnapshotJson"] = str(public_snapshot_json)

    return published


def emit_frontstage(session_key: str, message: str) -> dict[str, Any]:
    helper_path = Path(__file__).with_name("openclaw-supervisor-subagent.py")
    cmd = [
        sys.executable,
        str(helper_path),
        "send-frontstage",
        "--session-key",
        session_key,
        "--message",
        message,
        "--print-json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "frontstage emit failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid helper json: {exc}") from exc
    return payload if isinstance(payload, dict) else {}


def build_views(state_path: Path, broker_data_dir: Path, *, updated_at: str | None = None, latest_source: str | None = None) -> dict[str, Any]:
    paths = broker_paths(state_path, broker_data_dir)
    normalize_event_log(paths["events"])
    state = load_json(state_path)
    raw_sources = state.get("sources") if isinstance(state.get("sources"), dict) else {}
    raw_source_states = state.get("sourceStates") if isinstance(state.get("sourceStates"), dict) else {}
    sources = canonical_sources_map(raw_sources)
    source_states = canonical_source_states_map(raw_source_states)
    contract_catalog = build_contract_catalog(list(dict.fromkeys([*sources.keys(), *source_states.keys()])))
    effective_updated_at = updated_at or now_iso()

    health_report = load_json(paths["localHealthReport"])
    supervisor_report = load_json(paths["supervisorStatus"])
    recovery_report = load_json(paths["recoveryReport"])
    recovery_notify = load_json(paths["recoveryNotify"])
    freshness = {
        "rebuiltAt": effective_updated_at,
        "brokerState": source_file_meta(paths["state"], state, "updatedAt"),
        "sources": {
            "localHealthReport": source_file_meta(paths["localHealthReport"], health_report, "checkedAt", "updatedAt"),
            "supervisorStatus": source_file_meta(paths["supervisorStatus"], supervisor_report, "updatedAt", "checkedAt"),
            "recoveryReport": source_file_meta(paths["recoveryReport"], recovery_report, "checkedAt", "updatedAt"),
            "recoveryNotify": source_file_meta(paths["recoveryNotify"], recovery_notify, "updatedAt", "sentAt"),
        },
    }

    frontstage_view = {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": EVENT_CONTRACT_VERSION,
        "contracts": contract_catalog,
        "updatedAt": effective_updated_at,
        "latestSource": latest_source,
        "sources": sources,
        "sourceStates": source_states,
        "freshness": freshness,
    }
    save_json(paths["frontstageView"], frontstage_view)

    health_record = sources.get("local-health") if isinstance(sources.get("local-health"), dict) else None
    health_view_payload: dict[str, Any] | None = None
    if health_report or health_record:
        health_view_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": EVENT_CONTRACT_VERSION,
            "contracts": contract_catalog,
            "updatedAt": effective_updated_at,
            "freshness": freshness,
            "report": health_report or None,
            "broker": health_record or None,
            "latest": health_record or health_report,
        }
        save_json(paths["healthView"], health_view_payload)

    supervisor_record = sources.get("supervisor") if isinstance(sources.get("supervisor"), dict) else None
    recovery_record = sources.get("frontstage-recovery") if isinstance(sources.get("frontstage-recovery"), dict) else None
    tasks_view_payload: dict[str, Any] | None = None
    if supervisor_report or recovery_report or supervisor_record or recovery_record:
        tasks_view_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": EVENT_CONTRACT_VERSION,
            "contracts": contract_catalog,
            "updatedAt": effective_updated_at,
            "freshness": freshness,
            "supervisor": {
                "report": supervisor_report or None,
                "broker": supervisor_record or None,
            },
            "recovery": {
                "report": recovery_report or None,
                "broker": recovery_record or None,
                "notify": recovery_notify or None,
            },
        }
        save_json(paths["tasksView"], tasks_view_payload)

    recovery_view_payload: dict[str, Any] | None = None
    if recovery_report or recovery_record or recovery_notify:
        recovery_view_payload = {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": EVENT_CONTRACT_VERSION,
            "contracts": contract_catalog,
            "updatedAt": effective_updated_at,
            "freshness": freshness,
            "report": recovery_report or None,
            "broker": recovery_record or None,
            "notify": recovery_notify or None,
            "latest": recovery_record or recovery_report or recovery_notify,
        }
        save_json(paths["recoveryView"], recovery_view_payload)

    snapshot_payload = build_frontstage_status_payload(frontstage_view, health_view_payload, tasks_view_payload, recovery_view_payload)
    save_json(paths["snapshotView"], snapshot_payload)
    save_json(paths["overviewView"], snapshot_payload)
    published_paths = publish_frontstage_status(snapshot_payload)

    manifest_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "contractVersion": EVENT_CONTRACT_VERSION,
        "contracts": contract_catalog,
        "snapshotContract": snapshot_contract_metadata(),
        "artifacts": build_artifact_catalog(paths, published_paths),
        "updatedAt": effective_updated_at,
        "freshness": freshness,
        "state": {
            "brokerState": str(paths["state"]),
            "events": str(paths["events"]),
        },
        "views": {
            "frontstage": str(paths["frontstageView"]),
            "health": str(paths["healthView"]),
            "tasks": str(paths["tasksView"]),
            "recovery": str(paths["recoveryView"]),
            "snapshot": str(paths["snapshotView"]),
            "overview": str(paths["overviewView"]),
        },
        "sources": {
            "localHealthReport": str(paths["localHealthReport"]),
            "supervisorStatus": str(paths["supervisorStatus"]),
            "recoveryReport": str(paths["recoveryReport"]),
            "recoveryNotify": str(paths["recoveryNotify"]),
        },
        "published": published_paths,
    }
    save_json(paths["manifest"], manifest_payload)

    all_paths = {key: str(value) for key, value in paths.items()}
    all_paths.update(published_paths)
    return all_paths


def ingest_event(
    source: str,
    event_key: str,
    session_key: str,
    message: str,
    state_path: Path,
    broker_data_dir: Path,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_json(state_path)
    sources = state.get("sources") if isinstance(state.get("sources"), dict) else {}
    source_states = state.get("sourceStates") if isinstance(state.get("sourceStates"), dict) else {}
    previous = source_states.get(source) if isinstance(source_states.get(source), dict) else {}
    previous_snapshot = canonical_source_state_record(source, previous)
    paths = broker_paths(state_path, broker_data_dir)
    contract = source_contract(source)

    if previous.get("eventKey") == event_key:
        return {
            "ok": True,
            "skipped": True,
            "reason": "duplicate-source-event",
            "source": source,
            "sourceEventType": contract["sourceEventType"],
            "sourceView": contract.get("sourceView"),
            "eventKey": event_key,
            "sessionKey": previous_snapshot.get("sessionKey") or session_key,
            "message": previous_snapshot.get("message"),
            "recordedAt": previous_snapshot.get("recordedAt"),
            "paths": {key: str(value) for key, value in paths.items()},
        }

    recorded_at = now_iso()
    record = build_source_event_record(source, event_key, session_key, message, recorded_at, data)
    source_states[source] = canonical_source_state_record(source, record)
    save_json(
        state_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": EVENT_CONTRACT_VERSION,
            "sources": canonical_sources_map(sources),
            "sourceStates": canonical_source_states_map(source_states),
            "updatedAt": recorded_at,
        },
    )
    append_jsonl(paths["events"], record)
    all_paths = build_views(state_path, broker_data_dir, updated_at=record["recordedAt"], latest_source=source)
    return {
        "ok": True,
        "skipped": False,
        "source": source,
        **record,
        "paths": all_paths,
    }


def record_delivery_event(
    source: str,
    event_key: str,
    session_key: str,
    target_session_key: str | None,
    message_id: Any,
    message: str,
    state_path: Path,
    broker_data_dir: Path,
) -> dict[str, Any]:
    state = load_json(state_path)
    sources = state.get("sources") if isinstance(state.get("sources"), dict) else {}
    source_states = state.get("sourceStates") if isinstance(state.get("sourceStates"), dict) else {}
    previous = sources.get(source) if isinstance(sources.get(source), dict) else {}
    previous_snapshot = canonical_source_record(source, previous)
    paths = broker_paths(state_path, broker_data_dir)
    contract = source_contract(source)

    if previous.get("eventKey") == event_key:
        return {
            "ok": True,
            "skipped": True,
            "reason": "duplicate-event",
            "source": source,
            "sourceEventType": contract["sourceEventType"],
            "sourceView": contract.get("sourceView"),
            "eventKey": event_key,
            "sessionKey": previous_snapshot.get("sessionKey") or session_key,
            "targetSessionKey": previous_snapshot.get("targetSessionKey"),
            "messageId": previous_snapshot.get("messageId"),
            "message": previous_snapshot.get("message"),
            "paths": {key: str(value) for key, value in paths.items()},
        }

    recorded_at = now_iso()
    record = build_event_record(
        source,
        event_key,
        session_key,
        target_session_key,
        message_id,
        message,
        recorded_at,
    )
    sources[source] = canonical_source_record(source, record)
    save_json(
        state_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "contractVersion": EVENT_CONTRACT_VERSION,
            "sources": canonical_sources_map(sources),
            "sourceStates": canonical_source_states_map(source_states),
            "updatedAt": recorded_at,
        },
    )
    append_jsonl(paths["events"], record)
    all_paths = build_views(state_path, broker_data_dir, updated_at=record["recordedAt"], latest_source=source)
    return {
        "ok": True,
        "skipped": False,
        "source": source,
        **record,
        "paths": all_paths,
    }


def emit_event(source: str, event_key: str, session_key: str, message: str, state_path: Path, broker_data_dir: Path) -> dict[str, Any]:
    response = emit_frontstage(session_key, message)
    helper_response = response.get("response") if isinstance(response.get("response"), dict) else {}
    return record_delivery_event(
        source,
        event_key,
        session_key,
        response.get("targetSessionKey"),
        helper_response.get("messageId"),
        message,
        state_path,
        broker_data_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified frontstage broker for auxiliary messages and sidecar data")
    parser.add_argument("action", choices=["emit", "ingest", "record-delivery", "rebuild-views"], help="Operation to run")
    parser.add_argument("--source", help="Source channel, e.g. supervisor or local-health")
    parser.add_argument("--event-key", help="Stable event key for de-duplication")
    parser.add_argument("--session-key", default=DEFAULT_SESSION_KEY, help="Owner/current session key used to resolve current frontstage")
    parser.add_argument("--message", help="Message or summary text")
    parser.add_argument("--target-session-key", help="Target session key for record-delivery")
    parser.add_argument("--message-id", help="Message id for record-delivery")
    parser.add_argument("--data-json", help="Optional JSON object payload for ingest")
    parser.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR), help="State directory for broker dedupe")
    parser.add_argument("--broker-data-dir", default=str(DEFAULT_BROKER_DATA_DIR), help="Directory for broker events and views")
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable summary")
    args = parser.parse_args()

    state_dir = Path(args.state_dir).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / STATE_PATH_NAME
    broker_data_dir = Path(args.broker_data_dir).expanduser().resolve()
    broker_data_dir.mkdir(parents=True, exist_ok=True)

    if args.action == "rebuild-views":
        payload = {
            "ok": True,
            "action": "rebuild-views",
            "paths": build_views(state_path, broker_data_dir),
        }
    else:
        missing = [name for name, value in {"source": args.source, "event-key": args.event_key, "message": args.message}.items() if not (isinstance(value, str) and value.strip())]
        if missing:
            raise SystemExit(f"{args.action} requires: {', '.join(missing)}")
        data_payload = None
        if args.data_json:
            try:
                parsed = json.loads(args.data_json)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"--data-json must be a JSON object: {exc}") from exc
            if not isinstance(parsed, dict):
                raise SystemExit("--data-json must be a JSON object")
            data_payload = parsed
        if args.action == "ingest":
            payload = ingest_event(
                args.source.strip(),
                args.event_key.strip(),
                args.session_key.strip(),
                args.message.strip(),
                state_path,
                broker_data_dir,
                data=data_payload,
            )
        elif args.action == "record-delivery":
            payload = record_delivery_event(
                args.source.strip(),
                args.event_key.strip(),
                args.session_key.strip(),
                args.target_session_key.strip() if isinstance(args.target_session_key, str) and args.target_session_key.strip() else None,
                args.message_id.strip() if isinstance(args.message_id, str) and args.message_id.strip() else None,
                args.message.strip(),
                state_path,
                broker_data_dir,
            )
        else:
            payload = emit_event(
                args.source.strip(),
                args.event_key.strip(),
                args.session_key.strip(),
                args.message.strip(),
                state_path,
                broker_data_dir,
            )
    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if args.action == "rebuild-views":
            print(f"rebuilt: views={payload.get('paths', {}).get('viewsDir')}")
        elif args.action == "ingest":
            prefix = "skipped" if payload.get("skipped") else "ingested"
            print(
                f"{prefix}: source={payload.get('source')} eventKey={payload.get('eventKey')} "
                f"recordedAt={payload.get('recordedAt')} events={payload.get('paths', {}).get('events')}"
            )
        elif args.action == "record-delivery":
            prefix = "skipped" if payload.get("skipped") else "recorded"
            print(
                f"{prefix}: source={payload.get('source')} target={payload.get('targetSessionKey') or payload.get('sessionKey')} "
                f"messageId={payload.get('messageId')} events={payload.get('paths', {}).get('events')}"
            )
        else:
            prefix = "skipped" if payload.get("skipped") else "sent"
            print(
                f"{prefix}: source={payload.get('source')} target={payload.get('targetSessionKey') or payload.get('sessionKey')} "
                f"messageId={payload.get('messageId')} events={payload.get('paths', {}).get('events')}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
