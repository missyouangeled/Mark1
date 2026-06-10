#!/usr/bin/env python3
"""Infos-handle main: entry point, broker operations, frontstage notify, CLI argument parsing."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from openclaw_infos_handle_contract import build_compat_delivery_bundle, build_handle_request_payload

from .catalog import (
    QUERY_CONTRACT_VERSION,
    REQUEST_CONTRACT_VERSION,
    ARTIFACT_NOTICE_CONTRACT_VERSION,
    DELIVERY_NOTICE_CONTRACT_VERSION,
    DEFAULT_QUERY_LIMIT,
    READY_OUTPUT_FORMATS,
    PREVIEW_OUTPUT_FORMATS,
    RESERVED_OUTPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
    READY_DELIVERY_MODES,
    DEFAULT_IMAGE_PRESET,
    DEFAULT_AUDIO_RENDER_TIMEOUT_SECONDS,
    QUERY_KINDS,
)
from .snapshot import (
    first_text,
    normalize_limit,
    load_recent_events,
    load_recent_source_events,
    load_json,
    cleanup_stale_artifacts,
    write_text,
    build_output_artifact_payload,
    build_frontstage_artifact_notice_payload,
    build_frontstage_delivery_notice,
    hydrate_frontstage_delivery_target,
)
from .query import (
    build_query_payload,
    build_direct_message_payload,
    normalize_handle_request,
    output_descriptor_for_stdout,
)
from .image import render_image_output
from .audio import render_audio_output

# ── Path / default constants ────────────────────────────────────────────────
DEFAULT_BROKER_ROOT = Path.home() / ".local" / "state" / "openclaw" / "broker"
DEFAULT_VIEWS_DIR = DEFAULT_BROKER_ROOT / "views"
DEFAULT_SNAPSHOT_PATH = DEFAULT_VIEWS_DIR / "snapshot.json"
DEFAULT_EVENTS_PATH = DEFAULT_BROKER_ROOT / "events.jsonl"
DEFAULT_SESSION_KEY = "agent:main:main"
WORKSPACE = Path(__file__).resolve().parents[2]
BROKER_SCRIPT = WORKSPACE / "scripts" / "openclaw-frontstage-broker.py"
FRONTSTAGE_HELPER = WORKSPACE / "scripts" / "openclaw-supervisor-subagent.py"
DEFAULT_OUTPUT_ROOT = WORKSPACE / "tmp" / "infos-handle" / "outputs"
DEFAULT_AUDIO_RENDERER = WORKSPACE / "tools" / "voice-reply" / "voice-reply.sh"
DEFAULT_AUDIO_PRESET = os.environ.get("OPENCLAW_INFOS_HANDLE_AUDIO_PRESET") or os.environ.get("OPENCLAW_VOICE_REPLY_PRESET", "default")


# ── Lazy access helpers (used by other modules to avoid circular imports) ───
def _get_default_audio_renderer() -> Path:
    return DEFAULT_AUDIO_RENDERER


def _get_frontstage_helper_path() -> Path:
    return FRONTSTAGE_HELPER


# ── Request handling / broker / notify ──────────────────────────────────────

def render_output_for_handle(normalized_request: dict[str, Any], query_payload: dict[str, Any]) -> dict[str, Any]:
    output_root = Path(normalized_request["outputRoot"]).expanduser().resolve()
    output_format = str(normalized_request.get("format") or "json")
    if output_format in READY_OUTPUT_FORMATS:
        return output_descriptor_for_stdout(query_payload, output_format)
    if output_format == "image":
        image_preset = str(normalized_request.get("imagePreset") or DEFAULT_IMAGE_PRESET)
        output = render_image_output(query_payload, output_root, image_preset=image_preset)
    elif output_format == "audio":
        output = render_audio_output(
            query_payload,
            output_root,
            normalized_request.get("audioRenderer"),
            str(normalized_request.get("audioPreset") or DEFAULT_AUDIO_PRESET),
        )
    else:
        raise ValueError(f"unsupported format: {output_format}")
    output["artifact"] = build_output_artifact_payload(output)
    return output


def handle_request(request: dict[str, Any], *, request_input_mode: str = "flags", response_output_mode: str = "stdout") -> dict[str, Any]:
    snapshot_path = Path(request["snapshotPath"]).expanduser().resolve()
    events_path = Path(request["eventsPath"]).expanduser().resolve()
    if request.get("kind"):
        query_payload = build_query_payload(
            request["kind"],
            snapshot_path,
            events_path,
            int(request["limit"]),
            str(request["format"]),
            source_name=request.get("sourceName"),
            panel_name=request.get("panelName"),
        )
    else:
        query_payload = build_direct_message_payload(
            str(request.get("message") or "").strip(),
            snapshot_path,
            events_path,
            str(request["format"]),
        )
    output = render_output_for_handle(request, query_payload)
    output_artifact = output.get("artifact") if isinstance(output.get("artifact"), dict) else None
    response_payload = {
        **query_payload,
        "requestContractVersion": REQUEST_CONTRACT_VERSION,
        "output": output,
        "delivery": {
            "contractVersion": None,
            "mode": request.get("deliveryMode") or "none",
            "kind": None,
            "status": "skipped",
            "message": None,
            "artifactRef": None,
            "artifact": None,
            "notice": None,
            "frontstage": None,
            "artifactNotice": None,
            "metadata": None,
            "notify": None,
        },
    }

    if request.get("deliveryMode") == "frontstage":
        delivery_message = str(query_payload.get("text") or "").strip()
        delivery_kind = "message"
        delivery_fallback_text = delivery_message or "[infos-handle] 前台消息已发送。"
        delivery_data = request.get("data") if isinstance(request.get("data"), dict) else None
        artifact_notice = None
        artifact_payload = output_artifact
        if str(request.get("format") or "") in PREVIEW_OUTPUT_FORMATS:
            if artifact_payload is None:
                artifact_payload = build_output_artifact_payload(output)
            artifact_notice = build_frontstage_artifact_notice_payload(output, query_payload, request, artifact_payload)
            delivery_message = artifact_notice["displayText"]
            delivery_kind = artifact_notice["kind"]
            delivery_fallback_text = artifact_notice["fallbackText"]
        delivery_notice = build_frontstage_delivery_notice(
            output,
            query_payload,
            request,
            delivery_kind=delivery_kind,
            display_text=delivery_message,
            fallback_text=delivery_fallback_text,
            artifact=artifact_payload,
        )
        if artifact_notice:
            delivery_data = {
                **(delivery_data or {}),
                "artifactNotice": artifact_notice,
                "artifact": artifact_notice["artifact"],
                "deliveryNotice": delivery_notice,
                "frontstageDelivery": dict(delivery_notice["frontstage"]),
                "queryKind": query_payload.get("kind"),
            }
        notify_payload = notify_frontstage(
            str(request.get("sessionKey") or DEFAULT_SESSION_KEY),
            delivery_message,
            source=request.get("frontstageSource"),
            event_key=request.get("frontstageEventKey"),
            data=delivery_data,
            broker_state_dir=request.get("brokerStateDir"),
            broker_data_dir=request.get("brokerDataDir"),
        )
        hydrate_frontstage_delivery_target(delivery_notice["frontstage"], notify_payload)
        delivery_metadata = dict(delivery_notice["frontstage"])
        if artifact_notice:
            hydrate_frontstage_delivery_target(artifact_notice["delivery"], notify_payload)
        response_payload["delivery"] = {
            "contractVersion": DELIVERY_NOTICE_CONTRACT_VERSION,
            "mode": "frontstage",
            "kind": delivery_kind,
            "status": "sent",
            "message": delivery_message,
            "artifactRef": delivery_notice.get("artifactRef"),
            "artifact": artifact_payload,
            "notice": delivery_notice,
            "frontstage": delivery_notice["frontstage"],
            "artifactNotice": artifact_notice,
            "metadata": delivery_metadata,
            "notify": notify_payload,
        }

    return {
        "ok": True,
        "action": "handle",
        "requestId": request.get("requestId"),
        "requestInputMode": request_input_mode,
        "responseOutputMode": response_output_mode,
        "requestContractVersion": REQUEST_CONTRACT_VERSION,
        "request": request,
        "response": response_payload,
    }


def resolve_frontstage_helper_path() -> Path:
    override = os.environ.get("OPENCLAW_INFOS_HANDLE_FRONTSTAGE_HELPER")
    if override:
        return Path(override).expanduser().resolve()
    return FRONTSTAGE_HELPER


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
    broker_state_dir: str | None = None,
    broker_data_dir: str | None = None,
) -> dict[str, Any]:
    broker_args = {
        "state_dir": broker_state_dir,
        "broker_data_dir": broker_data_dir,
    }
    ingest_payload = None
    if source and event_key:
        ingest_payload = run_broker_action(
            "ingest",
            source=source,
            event_key=event_key,
            session_key=session_key,
            message=message,
            data_json=data,
            **broker_args,
        )

    cmd = [
        sys.executable,
        str(resolve_frontstage_helper_path()),
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

    delivery_payload = None
    if source and event_key:
        delivery_payload = run_broker_action(
            "record-delivery",
            source=source,
            event_key=event_key,
            session_key=session_key,
            target_session_key=payload.get("targetSessionKey"),
            message_id=response.get("messageId"),
            message=message,
            **broker_args,
        )
    if isinstance(payload, dict) and (ingest_payload or delivery_payload):
        payload["broker"] = {
            "ingest": ingest_payload,
            "delivery": delivery_payload,
        }
    return payload if isinstance(payload, dict) else {}


def parse_json_object_arg(raw_text: str, flag_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{flag_name} must be a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{flag_name} must be a JSON object")
    return parsed


def load_request_payload_from_input(request_json: str | None, request_file: str | None) -> tuple[dict[str, Any] | None, str]:
    if request_json and request_file:
        raise SystemExit("use only one of --request-json or --request-file")
    if request_json:
        return parse_json_object_arg(request_json, "--request-json"), "request_json"
    if not request_file:
        return None, "flags"

    if request_file == "-":
        raw_text = sys.stdin.read()
    else:
        try:
            raw_text = Path(request_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"--request-file unreadable: {exc}") from exc
    return parse_json_object_arg(raw_text, "--request-file"), "request_file"


def build_handle_request_from_flags(
    args: argparse.Namespace,
    *,
    data_payload: dict[str, Any] | None,
    snapshot_path: Path,
    events_path: Path,
    output_root: Path,
    output_format: str | None = None,
    delivery_mode: str | None = None,
    kind: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return build_handle_request_payload(
        request_id=args.request_id,
        kind=args.kind if kind is None else kind,
        message=args.message if message is None else message,
        output_format=args.format if output_format is None else output_format,
        limit=args.limit,
        source_name=args.source_name,
        panel_name=args.panel_name,
        session_key=args.session_key,
        delivery_mode=args.delivery_mode if delivery_mode is None else delivery_mode,
        frontstage_source=args.source,
        frontstage_event_key=args.event_key,
        data=data_payload,
        snapshot_path=str(snapshot_path),
        events_path=str(events_path),
        output_root=str(output_root),
        audio_renderer=args.audio_renderer,
        audio_preset=args.audio_preset,
        image_preset=getattr(args, "image_preset", None),
        broker_state_dir=args.broker_state_dir,
        broker_data_dir=args.broker_data_dir,
    )


def emit_handle_payload(payload: dict[str, Any], response_file: str | None) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    if response_file and response_file != "-":
        write_text(Path(response_file).expanduser().resolve(), content + "\n")
        return
    print(content)


def build_query_compat_payload(handle_payload: dict[str, Any]) -> dict[str, Any]:
    response = handle_payload.get("response") if isinstance(handle_payload.get("response"), dict) else {}
    return {
        key: value
        for key, value in response.items()
        if key not in {"requestContractVersion", "output", "delivery"}
    }


def build_notify_frontstage_compat_payload(handle_payload: dict[str, Any]) -> dict[str, Any]:
    compat_bundle = build_compat_delivery_bundle(handle_payload, delivery_mode="frontstage")
    notify_payload = compat_bundle.get("notify") if isinstance(compat_bundle.get("notify"), dict) else None
    compatibility_payload = dict(notify_payload or {})
    frontstage = compat_bundle.get("frontstage") if isinstance(compat_bundle.get("frontstage"), dict) else None
    response = compatibility_payload.get("response") if isinstance(compatibility_payload.get("response"), dict) else {}
    if frontstage and frontstage.get("targetSessionKey") and not compatibility_payload.get("targetSessionKey"):
        compatibility_payload["targetSessionKey"] = frontstage.get("targetSessionKey")
    if frontstage and frontstage.get("messageId") and not response.get("messageId"):
        response["messageId"] = frontstage.get("messageId")
    if response:
        compatibility_payload["response"] = response
    compatibility_payload["action"] = "notify-frontstage"
    compatibility_payload["requestId"] = compat_bundle.get("requestId")
    compatibility_payload["message"] = compat_bundle.get("message")
    compatibility_payload["artifactRef"] = compat_bundle.get("artifactRef")
    compatibility_payload["artifact"] = compat_bundle.get("artifact")
    compatibility_payload["delivery"] = compat_bundle.get("delivery")
    compatibility_payload["notice"] = compat_bundle.get("notice")
    compatibility_payload["deliveryNotice"] = compat_bundle.get("deliveryNotice")
    compatibility_payload["frontstage"] = compat_bundle.get("frontstage")
    compatibility_payload["frontstageDelivery"] = compat_bundle.get("frontstageDelivery")
    compatibility_payload["artifactNotice"] = compat_bundle.get("artifactNotice")
    compatibility_payload["notify"] = notify_payload
    return compatibility_payload


# ── Main CLI entry ──────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal infos-handle layer for broker-backed queries, low-risk rendering, and frontstage notify")
    parser.add_argument("action", choices=["query", "notify-frontstage", "handle"], help="Operation to run")
    parser.add_argument("--kind", choices=sorted(QUERY_KINDS), help="What info to query")
    parser.add_argument("--source-name", help="Source name for source.inspect")
    parser.add_argument("--panel-name", help="Panel name for panel.inspect")
    parser.add_argument("--format", choices=SUPPORTED_OUTPUT_FORMATS, default="text", help="Output format for query/handle")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT_PATH), help="Broker snapshot.json path")
    parser.add_argument("--events-path", default=str(DEFAULT_EVENTS_PATH), help="Broker events.jsonl path")
    parser.add_argument("--limit", type=int, default=DEFAULT_QUERY_LIMIT, help="Max recent events for events.recent or source.inspect")
    parser.add_argument("--session-key", default=DEFAULT_SESSION_KEY, help="Target session key for frontstage notify")
    parser.add_argument("--source", help="Optional source name when notify-frontstage / handle delivery should also ingest/record delivery")
    parser.add_argument("--event-key", help="Optional event key when notify-frontstage / handle delivery should also ingest/record delivery")
    parser.add_argument("--data-json", help="Optional JSON object payload to ingest before notify-frontstage or handle delivery")
    parser.add_argument("--message", help="Direct message for notify-frontstage; when omitted, query text is used")
    parser.add_argument("--request-id", help="Optional correlation id for handle requests built from flags")
    parser.add_argument("--request-json", help="Unified handle request JSON object; overrides most per-flag handle inputs")
    parser.add_argument("--request-file", help="Unified handle request JSON file path; use - to read one request object from stdin")
    parser.add_argument("--response-file", help="Optional handle response JSON file path; use - to keep stdout")
    parser.add_argument("--delivery-mode", choices=READY_DELIVERY_MODES, default="none", help="Optional delivery mode for handle")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Directory for handle image/audio artifact output")
    parser.add_argument("--audio-renderer", help="Optional audio renderer executable path for handle --format audio")
    parser.add_argument("--audio-preset", default=DEFAULT_AUDIO_PRESET, help="Audio preset for handle --format audio")
    parser.add_argument("--image-preset", choices=["summary-card", "summary-card-v3"], default=DEFAULT_IMAGE_PRESET, help="Image card preset for handle --format image")
    parser.add_argument("--broker-state-dir", help="Optional broker state dir override for notify-frontstage / handle delivery")
    parser.add_argument("--broker-data-dir", help="Optional broker data dir override for notify-frontstage / handle delivery")
    parser.add_argument("--cleanup-artifacts-older-than-hours", type=float, default=0, help="Remove image/audio artifacts older than N hours")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot_path).expanduser().resolve()
    events_path = Path(args.events_path).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()

    data_payload = parse_json_object_arg(args.data_json, "--data-json") if args.data_json else None

    if args.response_file and args.action != "handle":
        raise SystemExit("--response-file currently only supports handle")

    if args.cleanup_artifacts_older_than_hours > 0:
        cleanup_result = cleanup_stale_artifacts(output_root, hours=args.cleanup_artifacts_older_than_hours)
        print(json.dumps(cleanup_result, ensure_ascii=False, indent=2), file=sys.stderr)

    if args.action == "query":
        if args.format not in READY_OUTPUT_FORMATS:
            raise SystemExit("query currently only supports --format text|json; use handle for image/audio")
        if not args.kind:
            raise SystemExit("query requires --kind")
        request_payload = build_handle_request_from_flags(
            args,
            data_payload=data_payload,
            snapshot_path=snapshot_path,
            events_path=events_path,
            output_root=output_root,
            delivery_mode="none",
        )
        normalized_request = normalize_handle_request(
            request_payload,
            snapshot_path=snapshot_path,
            events_path=events_path,
            output_root=output_root,
            session_key=args.session_key,
            audio_renderer=args.audio_renderer,
            audio_preset=args.audio_preset,
        )
        try:
            handle_payload = handle_request(
                normalized_request,
                request_input_mode="flags",
                response_output_mode="stdout",
            )
        except Exception as exc:
            raise SystemExit(f"query failed: {exc}") from exc
        if not handle_payload.get("ok"):
            raise SystemExit(str(handle_payload.get("error") or "query failed"))
        payload = build_query_compat_payload(handle_payload)
        if args.format == "json":
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(str(payload.get("text") or ""))
        return 0

    if args.action == "notify-frontstage":
        if not args.message and not args.kind:
            raise SystemExit("notify-frontstage requires --message or --kind")
        request_payload = build_handle_request_from_flags(
            args,
            data_payload=data_payload,
            snapshot_path=snapshot_path,
            events_path=events_path,
            output_root=output_root,
            output_format="text",
            delivery_mode="frontstage",
        )
        normalized_request = normalize_handle_request(
            request_payload,
            snapshot_path=snapshot_path,
            events_path=events_path,
            output_root=output_root,
            session_key=args.session_key,
            audio_renderer=args.audio_renderer,
            audio_preset=args.audio_preset,
        )
        try:
            handle_payload = handle_request(
                normalized_request,
                request_input_mode="flags",
                response_output_mode="stdout",
            )
        except Exception as exc:
            raise SystemExit(f"notify-frontstage failed: {exc}") from exc
        if not handle_payload.get("ok"):
            raise SystemExit(str(handle_payload.get("error") or "notify-frontstage failed"))

        print(json.dumps(build_notify_frontstage_compat_payload(handle_payload), ensure_ascii=False, indent=2))
        return 0

    request_payload, request_input_mode = load_request_payload_from_input(args.request_json, args.request_file)
    if request_payload is None:
        request_payload = build_handle_request_from_flags(
            args,
            data_payload=data_payload,
            snapshot_path=snapshot_path,
            events_path=events_path,
            output_root=output_root,
        )

    normalized_request = normalize_handle_request(
        request_payload,
        snapshot_path=snapshot_path,
        events_path=events_path,
        output_root=output_root,
        session_key=args.session_key,
        audio_renderer=args.audio_renderer,
        audio_preset=args.audio_preset,
    )

    response_output_mode = "response_file" if args.response_file and args.response_file != "-" else "stdout"

    try:
        payload = handle_request(
            normalized_request,
            request_input_mode=request_input_mode,
            response_output_mode=response_output_mode,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "action": "handle",
            "requestId": normalized_request.get("requestId"),
            "requestInputMode": request_input_mode,
            "responseOutputMode": response_output_mode,
            "requestContractVersion": REQUEST_CONTRACT_VERSION,
            "request": normalized_request,
            "response": None,
            "error": f"{exc.__class__.__name__}: {exc}",
        }
    emit_handle_payload(payload, args.response_file)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        raise SystemExit(0)
