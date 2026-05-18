#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def build_handle_request_payload(
    *,
    request_id: str | None = None,
    kind: str | None = None,
    message: str | None = None,
    output_format: str | None = None,
    limit: int | None = None,
    source_name: str | None = None,
    panel_name: str | None = None,
    session_key: str | None = None,
    delivery_mode: str | None = None,
    frontstage_source: str | None = None,
    frontstage_event_key: str | None = None,
    data: dict[str, Any] | None = None,
    snapshot_path: str | None = None,
    events_path: str | None = None,
    output_root: str | None = None,
    audio_renderer: str | None = None,
    audio_preset: str | None = None,
    broker_state_dir: str | None = None,
    broker_data_dir: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if request_id is not None:
        payload["requestId"] = request_id
    if kind is not None:
        payload["kind"] = kind
    if message is not None:
        payload["message"] = message
    if output_format is not None:
        payload["format"] = output_format
    if limit is not None:
        payload["limit"] = limit
    if source_name is not None:
        payload["sourceName"] = source_name
    if panel_name is not None:
        payload["panelName"] = panel_name
    if session_key is not None:
        payload["sessionKey"] = session_key
    if delivery_mode is not None:
        payload["deliveryMode"] = delivery_mode
    if frontstage_source is not None:
        payload["frontstageSource"] = frontstage_source
    if frontstage_event_key is not None:
        payload["frontstageEventKey"] = frontstage_event_key
    if data is not None:
        payload["data"] = data
    if snapshot_path is not None:
        payload["snapshotPath"] = snapshot_path
    if events_path is not None:
        payload["eventsPath"] = events_path
    if output_root is not None:
        payload["outputRoot"] = output_root
    if audio_renderer is not None:
        payload["audioRenderer"] = audio_renderer
    if audio_preset is not None:
        payload["audioPreset"] = audio_preset
    if broker_state_dir is not None:
        payload["brokerStateDir"] = broker_state_dir
    if broker_data_dir is not None:
        payload["brokerDataDir"] = broker_data_dir
    return payload


def invoke_handle_request(
    handle_script: str | Path,
    request_payload: dict[str, Any],
    *,
    python_executable: str | None = None,
    run: Any | None = None,
    request_file: str | Path | None = None,
    response_file: str | Path | None = None,
) -> dict[str, Any]:
    script_path = Path(handle_script).expanduser().resolve()
    response_path: Path | None = None
    request_path: Path | None = None
    request_input: str | None = None
    cmd = [
        python_executable or sys.executable,
        str(script_path),
        "handle",
        "--request-file",
    ]
    if request_file and str(request_file) != "-":
        request_path = Path(request_file).expanduser().resolve()
        try:
            request_path.parent.mkdir(parents=True, exist_ok=True)
            request_path.write_text(json.dumps(request_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"unable to write infos-handle request file: {exc}") from exc
        cmd.append(str(request_path))
    else:
        cmd.append("-")
        request_input = json.dumps(request_payload, ensure_ascii=False)
    if response_file and str(response_file) != "-":
        response_path = Path(response_file).expanduser().resolve()
        cmd.extend(["--response-file", str(response_path)])

    runner = run or subprocess.run
    result = runner(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        input=request_input,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "infos-handle handle failed").strip())

    if response_path is not None:
        try:
            raw_text = response_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"unable to read infos-handle response file: {exc}") from exc
    else:
        raw_text = result.stdout

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid infos-handle json: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("infos-handle response must be a JSON object")
    return payload



def invoke_handle_query(
    handle_script: str | Path,
    *,
    kind: str,
    output_format: str = "json",
    request_id: str | None = None,
    limit: int | None = None,
    source_name: str | None = None,
    panel_name: str | None = None,
    snapshot_path: str | None = None,
    events_path: str | None = None,
    python_executable: str | None = None,
    run: Any | None = None,
    request_file: str | Path | None = None,
    response_file: str | Path | None = None,
) -> dict[str, Any]:
    payload = invoke_handle_request(
        handle_script,
        build_handle_request_payload(
            request_id=request_id,
            kind=kind,
            output_format=output_format,
            limit=limit,
            source_name=source_name,
            panel_name=panel_name,
            snapshot_path=snapshot_path,
            events_path=events_path,
        ),
        python_executable=python_executable,
        run=run,
        request_file=request_file,
        response_file=response_file,
    )
    return extract_handle_response_snapshot(payload)


def _legacy_frontstage_payload(payload: dict[str, Any]) -> dict[str, Any]:
    response = _mapping(payload.get("response"))
    message_id = _first_text(response.get("messageId"), payload.get("messageId"))
    target_session_key = _first_text(payload.get("targetSessionKey"))
    if not target_session_key and not message_id:
        return {}
    return {
        "mode": "frontstage",
        "channel": "frontstage_message",
        "requestedSessionKey": payload.get("requestedSessionKey"),
        "targetSessionKey": target_session_key,
        "messageId": message_id,
        "frontstageSource": payload.get("frontstageSource"),
        "frontstageEventKey": payload.get("frontstageEventKey"),
        "queryKind": payload.get("queryKind"),
        "handler": payload.get("handler"),
        "noticeKind": payload.get("noticeKind"),
        "artifactRef": payload.get("artifactRef"),
        "displayText": _first_text(payload.get("message"), payload.get("displayText")),
    }


def extract_delivery_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _mapping(payload)
    if payload.get("action") != "handle":
        legacy_frontstage = _legacy_frontstage_payload(payload) or None
        return {
            "delivery": {},
            "notice": None,
            "deliveryNotice": None,
            "frontstage": legacy_frontstage,
            "frontstageDelivery": legacy_frontstage,
            "artifactNotice": None,
            "notify": payload or None,
            "artifact": None,
            "artifactRef": _first_text(payload.get("artifactRef"), (legacy_frontstage or {}).get("artifactRef")),
            "kind": _first_text(payload.get("noticeKind")),
            "message": _first_text(payload.get("message"), (legacy_frontstage or {}).get("displayText")),
            "requestId": _first_text(payload.get("requestId")),
            "targetSessionKey": (legacy_frontstage or {}).get("targetSessionKey"),
            "messageId": (legacy_frontstage or {}).get("messageId"),
        }

    response = _mapping(payload.get("response"))
    delivery = _mapping(response.get("delivery"))
    artifact_notice = _mapping(delivery.get("artifactNotice"))
    metadata = _mapping(delivery.get("metadata"))
    notice = _mapping(delivery.get("notice"))
    artifact = _mapping(delivery.get("artifact"))
    notice_frontstage = _mapping(notice.get("frontstage"))
    artifact_notice_delivery = _mapping(artifact_notice.get("delivery"))
    frontstage = _mapping(delivery.get("frontstage")) or notice_frontstage or artifact_notice_delivery or metadata
    notify = _mapping(delivery.get("notify"))
    notify_response = _mapping(notify.get("response"))
    if not notice and artifact_notice:
        notice = {
            "contractVersion": artifact_notice.get("contractVersion"),
            "kind": artifact_notice.get("kind"),
            "displayText": artifact_notice.get("displayText"),
            "fallbackText": artifact_notice.get("fallbackText"),
            "summary": artifact_notice.get("summary"),
            "queryKind": _first_text(delivery.get("queryKind"), response.get("kind")),
            "artifactRef": artifact_notice.get("artifactRef"),
            "artifact": artifact_notice.get("artifact"),
            "frontstage": artifact_notice_delivery,
        }
    if not artifact:
        artifact = _mapping(notice.get("artifact")) or _mapping(artifact_notice.get("artifact"))

    artifact_ref = _first_text(
        delivery.get("artifactRef"),
        notice.get("artifactRef"),
        artifact_notice.get("artifactRef"),
        frontstage.get("artifactRef"),
        metadata.get("artifactRef"),
        artifact.get("ref"),
    )
    kind = _first_text(
        delivery.get("kind"),
        notice.get("kind"),
        artifact_notice.get("kind"),
        frontstage.get("noticeKind"),
        metadata.get("noticeKind"),
    )
    message = _first_text(
        delivery.get("message"),
        notice.get("displayText"),
        artifact_notice.get("displayText"),
        frontstage.get("displayText"),
        metadata.get("displayText"),
        notice.get("fallbackText"),
        artifact_notice.get("fallbackText"),
    )

    normalized_frontstage = dict(frontstage) if frontstage else {}
    if not normalized_frontstage and notify:
        normalized_frontstage = {
            "mode": delivery.get("mode") or "frontstage",
            "channel": "frontstage_message",
            "targetSessionKey": notify.get("targetSessionKey"),
            "messageId": _first_text(notify_response.get("messageId"), notify.get("messageId")),
        }
    if normalized_frontstage:
        normalized_frontstage.setdefault("mode", delivery.get("mode") or "frontstage")
        normalized_frontstage.setdefault("channel", "frontstage_message")
        normalized_frontstage["requestedSessionKey"] = _first_text(
            normalized_frontstage.get("requestedSessionKey"),
            metadata.get("requestedSessionKey"),
            notice_frontstage.get("requestedSessionKey"),
            artifact_notice_delivery.get("requestedSessionKey"),
        )
        normalized_frontstage["targetSessionKey"] = _first_text(
            normalized_frontstage.get("targetSessionKey"),
            metadata.get("targetSessionKey"),
            notice_frontstage.get("targetSessionKey"),
            artifact_notice_delivery.get("targetSessionKey"),
            notify.get("targetSessionKey"),
        )
        normalized_frontstage["messageId"] = _first_text(
            normalized_frontstage.get("messageId"),
            metadata.get("messageId"),
            notice_frontstage.get("messageId"),
            artifact_notice_delivery.get("messageId"),
            notify_response.get("messageId"),
            notify.get("messageId"),
        )
        normalized_frontstage["noticeKind"] = _first_text(normalized_frontstage.get("noticeKind"), kind)
        normalized_frontstage["artifactRef"] = _first_text(normalized_frontstage.get("artifactRef"), artifact_ref)
        normalized_frontstage["displayText"] = _first_text(normalized_frontstage.get("displayText"), message)

    normalized_notice = notice or None
    normalized_frontstage_payload = normalized_frontstage or None
    normalized_artifact_notice = artifact_notice or None
    normalized_notify = notify or None
    normalized_artifact = artifact or None

    return {
        "delivery": delivery,
        "notice": normalized_notice,
        "deliveryNotice": normalized_notice,
        "frontstage": normalized_frontstage_payload,
        "frontstageDelivery": normalized_frontstage_payload,
        "artifactNotice": normalized_artifact_notice,
        "notify": normalized_notify,
        "artifact": normalized_artifact,
        "artifactRef": artifact_ref,
        "kind": kind,
        "message": message,
        "requestId": _first_text(payload.get("requestId"), response.get("requestId")),
        "targetSessionKey": (normalized_frontstage_payload or {}).get("targetSessionKey") or (normalized_notify or {}).get("targetSessionKey"),
        "messageId": _first_text(
            (normalized_frontstage_payload or {}).get("messageId"),
            notify_response.get("messageId"),
            (normalized_notify or {}).get("messageId"),
        ),
    }



def extract_handle_response_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _mapping(payload)
    request = _mapping(payload.get("request"))
    response = _mapping(payload.get("response"))
    output = _mapping(response.get("output"))
    delivery_snapshot = extract_delivery_snapshot(payload)
    artifact = _mapping(output.get("artifact")) or _mapping(delivery_snapshot.get("artifact"))
    artifact_payload = artifact or None
    artifact_ref = _first_text(output.get("artifactRef"), delivery_snapshot.get("artifactRef"), artifact.get("ref"))
    delivery = delivery_snapshot.get("delivery") if isinstance(delivery_snapshot.get("delivery"), dict) else {}
    notice = delivery_snapshot.get("deliveryNotice") if isinstance(delivery_snapshot.get("deliveryNotice"), dict) else None
    frontstage = delivery_snapshot.get("frontstageDelivery") if isinstance(delivery_snapshot.get("frontstageDelivery"), dict) else None
    artifact_notice = delivery_snapshot.get("artifactNotice") if isinstance(delivery_snapshot.get("artifactNotice"), dict) else None
    notify = delivery_snapshot.get("notify") if isinstance(delivery_snapshot.get("notify"), dict) else None
    return {
        "ok": bool(payload.get("ok")),
        "action": _first_text(payload.get("action")),
        "requestId": _first_text(
            payload.get("requestId"),
            response.get("requestId"),
            request.get("requestId"),
            delivery_snapshot.get("requestId"),
        ),
        "requestInputMode": _first_text(payload.get("requestInputMode")),
        "responseOutputMode": _first_text(payload.get("responseOutputMode")),
        "requestContractVersion": payload.get("requestContractVersion") if isinstance(payload.get("requestContractVersion"), int) else None,
        "queryContractVersion": response.get("queryContractVersion") if isinstance(response.get("queryContractVersion"), int) else None,
        "request": request,
        "response": response,
        "kind": _first_text(response.get("kind"), request.get("kind")),
        "format": _first_text(response.get("format"), output.get("format"), request.get("format")),
        "text": _first_text(response.get("text"), output.get("text")),
        "result": response.get("result"),
        "output": output,
        "delivery": delivery,
        "notice": notice,
        "deliveryNotice": notice,
        "frontstage": frontstage,
        "frontstageDelivery": frontstage,
        "artifactNotice": artifact_notice,
        "notify": notify,
        "artifact": artifact_payload,
        "artifactRef": artifact_ref,
        "message": delivery_snapshot.get("message"),
        "targetSessionKey": delivery_snapshot.get("targetSessionKey"),
        "messageId": delivery_snapshot.get("messageId"),
        "error": _first_text(payload.get("error")),
    }



def extract_frontstage_notify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    source_payload = _mapping(payload)
    snapshot = extract_handle_response_snapshot(source_payload) if source_payload.get("action") == "handle" else extract_delivery_snapshot(source_payload)
    notify_payload: dict[str, Any] = {}
    if snapshot.get("targetSessionKey"):
        notify_payload["targetSessionKey"] = snapshot.get("targetSessionKey")
    if snapshot.get("messageId"):
        notify_payload["messageId"] = snapshot.get("messageId")
        notify_payload["response"] = {"messageId": snapshot.get("messageId")}
    return notify_payload if notify_payload else (source_payload if source_payload.get("action") != "handle" else {})



def build_compat_delivery_bundle(
    payload: dict[str, Any],
    *,
    delivery_mode: str = "frontstage",
    delivery_status: str | None = None,
) -> dict[str, Any]:
    source_payload = _mapping(payload)
    snapshot = extract_handle_response_snapshot(source_payload) if source_payload.get("action") == "handle" else extract_delivery_snapshot(source_payload)
    delivery = snapshot.get("delivery") if isinstance(snapshot.get("delivery"), dict) else {}
    notice = snapshot.get("deliveryNotice") if isinstance(snapshot.get("deliveryNotice"), dict) else None
    frontstage = snapshot.get("frontstageDelivery") if isinstance(snapshot.get("frontstageDelivery"), dict) else None
    artifact_notice = snapshot.get("artifactNotice") if isinstance(snapshot.get("artifactNotice"), dict) else None
    notify = snapshot.get("notify") if isinstance(snapshot.get("notify"), dict) else None
    artifact = snapshot.get("artifact") if isinstance(snapshot.get("artifact"), dict) else None

    normalized_frontstage = dict(frontstage) if frontstage else None
    if normalized_frontstage is not None:
        normalized_frontstage.setdefault("mode", delivery_mode)
        normalized_frontstage.setdefault("channel", "frontstage_message")
        normalized_frontstage["requestedSessionKey"] = _first_text(normalized_frontstage.get("requestedSessionKey"))
        normalized_frontstage["targetSessionKey"] = _first_text(normalized_frontstage.get("targetSessionKey"))
        normalized_frontstage["messageId"] = _first_text(normalized_frontstage.get("messageId"))
        normalized_frontstage["frontstageSource"] = _first_text(normalized_frontstage.get("frontstageSource"))
        normalized_frontstage["frontstageEventKey"] = _first_text(normalized_frontstage.get("frontstageEventKey"))
        normalized_frontstage["queryKind"] = _first_text(normalized_frontstage.get("queryKind"))
        normalized_frontstage["handler"] = _first_text(normalized_frontstage.get("handler"))
        normalized_frontstage["noticeKind"] = _first_text(normalized_frontstage.get("noticeKind"), snapshot.get("kind"))
        normalized_frontstage["artifactRef"] = _first_text(normalized_frontstage.get("artifactRef"), snapshot.get("artifactRef"))
        normalized_frontstage["displayText"] = _first_text(normalized_frontstage.get("displayText"), snapshot.get("message"))

    normalized_notice = dict(notice) if notice else None
    if normalized_notice is not None:
        normalized_notice["contractVersion"] = normalized_notice.get("contractVersion") if isinstance(normalized_notice.get("contractVersion"), int) else None
        normalized_notice["kind"] = _first_text(normalized_notice.get("kind"), snapshot.get("kind"))
        normalized_notice["displayText"] = _first_text(normalized_notice.get("displayText"), snapshot.get("message"))
        normalized_notice["fallbackText"] = _first_text(normalized_notice.get("fallbackText"), normalized_notice.get("displayText"))
        normalized_notice["summary"] = _first_text(normalized_notice.get("summary"))
        normalized_notice["queryKind"] = _first_text(normalized_notice.get("queryKind"))
        normalized_notice["artifactRef"] = _first_text(normalized_notice.get("artifactRef"), snapshot.get("artifactRef"))
        normalized_notice["artifact"] = artifact
        normalized_notice["frontstage"] = normalized_frontstage

    metadata = delivery.get("metadata") if isinstance(delivery.get("metadata"), dict) else normalized_frontstage
    return {
        "requestId": _first_text(snapshot.get("requestId")),
        "message": _first_text(snapshot.get("message")),
        "artifactRef": _first_text(snapshot.get("artifactRef")),
        "artifact": artifact,
        "notice": normalized_notice,
        "deliveryNotice": normalized_notice,
        "frontstage": normalized_frontstage,
        "frontstageDelivery": normalized_frontstage,
        "artifactNotice": artifact_notice,
        "notify": notify,
        "delivery": {
            **delivery,
            "mode": _first_text(delivery.get("mode"), delivery_mode),
            "kind": _first_text(delivery.get("kind"), snapshot.get("kind")),
            "status": _first_text(delivery.get("status"), delivery_status),
            "message": _first_text(delivery.get("message"), snapshot.get("message")),
            "artifactRef": _first_text(delivery.get("artifactRef"), snapshot.get("artifactRef")),
            "artifact": artifact,
            "notice": normalized_notice,
            "frontstage": normalized_frontstage,
            "artifactNotice": artifact_notice,
            "metadata": metadata,
            "notify": notify,
        },
    }
