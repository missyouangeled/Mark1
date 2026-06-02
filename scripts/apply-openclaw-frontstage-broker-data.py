#!/usr/bin/env python3
# 适用机器：通用（当前已在公司（Linux）验证）
# 系统 / OS：Linux / macOS / Windows（取决于本机 Python 与 OpenClaw 路径）
# 用途：为当前机器重建并验证 frontstage broker 的 sidecar 数据层产物，适合作为升级后重装与最小回归入口。

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from openclaw_infos_handle_contract import build_handle_request_payload, invoke_handle_query, invoke_handle_request

WORKSPACE = Path(__file__).resolve().parents[1]
BROKER_SCRIPT = WORKSPACE / "scripts" / "openclaw-frontstage-broker.py"
BROKER_TEST = WORKSPACE / "scripts" / "test-frontstage-broker.py"
INFOS_HANDLE_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
INFOS_HANDLE_SIDECAR_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle-sidecar.py"
INFOS_HANDLE_TEST = WORKSPACE / "scripts" / "test-openclaw-infos-handle.py"
FRONTSTAGE_RECOVERY_TEST = WORKSPACE / "scripts" / "test-frontstage-recovery-watch.py"
INFOS_HANDLE_CALLER_TEST = WORKSPACE / "scripts" / "test-infos-handle-frontstage-callers.py"
SUPERVISOR_STATUS_SCRIPT = WORKSPACE / "scripts" / "openclaw-supervisor-status.py"
FRONTSTAGE_RECOVERY_SCRIPT = WORKSPACE / "scripts" / "openclaw-frontstage-recovery-watch.py"
LOCAL_HEALTH_SCRIPT = WORKSPACE / "scripts" / "openclaw-local-health-diagnose.py"
BROKER_REBUILD_SERVICE = WORKSPACE / "tools" / "openclaw-frontstage-broker" / "openclaw-frontstage-broker-rebuild.service"
BROKER_REBUILD_TIMER = WORKSPACE / "tools" / "openclaw-frontstage-broker" / "openclaw-frontstage-broker-rebuild.timer"
BRANDING_SCRIPT = WORKSPACE / "scripts" / "apply-openclaw-control-ui-branding.py"
DEFAULT_PACKAGE_ROOT = Path.home() / ".npm-global" / "lib" / "node_modules" / "openclaw"
OVERRIDE_SCRIPT_NAME = "jarvis-branding-override.js"
USER_SYSTEMD_DIR = Path.home() / ".config" / "systemd" / "user"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=WORKSPACE, capture_output=True, text=True, check=False)


def resolve_control_ui_dist_root() -> Path | None:
    env_override = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    if env_override:
        candidate = Path(env_override).expanduser().resolve() / "dist" / "control-ui"
        if candidate.exists():
            return candidate

    candidate = DEFAULT_PACKAGE_ROOT / "dist" / "control-ui"
    if candidate.exists():
        return candidate

    try:
        npm_root = subprocess.run(
            ["npm", "root", "-g"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
    except Exception:
        npm_root = ""
    if npm_root:
        candidate = Path(npm_root).expanduser().resolve() / "openclaw" / "dist" / "control-ui"
        if candidate.exists():
            return candidate
    return None


def inspect_control_ui_snapshot_dock() -> dict[str, object]:
    dist_root = resolve_control_ui_dist_root()
    payload: dict[str, object] = {
        "available": bool(dist_root),
        "distRoot": str(dist_root) if dist_root else None,
        "overrideScript": None,
        "snapshotJsonHref": None,
        "legacyStatusJsonHref": None,
        "statusJsonHref": None,
        "infosHandleSummaryHref": None,
        "infosHandleContractHref": None,
        "infosHandleSseHref": None,
        "effectiveJsonHref": None,
        "statusPageHref": None,
        "snapshotFirst": False,
        "infosHandleDirectReady": False,
        "legacyStatusAliasMarked": False,
        "usesNormalizeFrontstageSnapshot": False,
        "usesInfosHandleSse": False,
    }
    if not dist_root:
        return payload

    override_script = dist_root / OVERRIDE_SCRIPT_NAME
    payload["overrideScript"] = str(override_script)
    if not override_script.exists():
        return payload

    script_text = override_script.read_text(encoding="utf-8")
    snapshot_json_match = re.search(r'"snapshotJsonHref":\s*"([^"]+)"', script_text)
    legacy_status_json_match = re.search(r'"legacyStatusJsonHref":\s*"([^"]+)"', script_text)
    status_json_match = re.search(r'"statusJsonHref":\s*"([^"]+)"', script_text)
    infos_handle_summary_match = re.search(r'"infosHandleSummaryHref":\s*"([^"]+)"', script_text)
    infos_handle_contract_match = re.search(r'"infosHandleContractHref":\s*"([^"]+)"', script_text)
    infos_handle_sse_match = re.search(r'"infosHandleSseHref":\s*"([^"]+)"', script_text)
    infos_handle_tasks_match = re.search(r'"infosHandleTasksHref":\s*"([^"]+)"', script_text)
    infos_handle_recovery_match = re.search(r'"infosHandleRecoveryHref":\s*"([^"]+)"', script_text)
    status_page_match = re.search(r'"href":\s*"([^"]+/jarvis-frontstage-status\.html|/jarvis-frontstage-status\.html)"', script_text)
    snapshot_json_href = snapshot_json_match.group(1) if snapshot_json_match else None
    legacy_status_json_href = legacy_status_json_match.group(1) if legacy_status_json_match else None
    status_json_href = status_json_match.group(1) if status_json_match else None
    infos_handle_summary_href = infos_handle_summary_match.group(1) if infos_handle_summary_match else None
    infos_handle_contract_href = infos_handle_contract_match.group(1) if infos_handle_contract_match else None
    infos_handle_sse_href = infos_handle_sse_match.group(1) if infos_handle_sse_match else None
    infos_handle_tasks_href = infos_handle_tasks_match.group(1) if infos_handle_tasks_match else None
    infos_handle_recovery_href = infos_handle_recovery_match.group(1) if infos_handle_recovery_match else None
    status_page_href = status_page_match.group(1) if status_page_match else None
    effective_json_href = snapshot_json_href or status_json_href
    payload["snapshotJsonHref"] = snapshot_json_href
    payload["legacyStatusJsonHref"] = legacy_status_json_href
    payload["statusJsonHref"] = status_json_href
    payload["infosHandleSummaryHref"] = infos_handle_summary_href
    payload["infosHandleContractHref"] = infos_handle_contract_href
    payload["infosHandleSseHref"] = infos_handle_sse_href
    payload["infosHandleTasksHref"] = infos_handle_tasks_href
    payload["infosHandleRecoveryHref"] = infos_handle_recovery_href
    payload["effectiveJsonHref"] = effective_json_href
    payload["statusPageHref"] = status_page_href
    payload["snapshotFirst"] = effective_json_href == "/jarvis-frontstage-snapshot.json"
    payload["infosHandleDirectReady"] = bool(infos_handle_summary_href and infos_handle_contract_href)
    payload["legacyStatusAliasMarked"] = legacy_status_json_href == "/jarvis-frontstage-status.json" or (
        bool(snapshot_json_href) and status_json_href == "/jarvis-frontstage-status.json"
    )
    payload["usesNormalizeFrontstageSnapshot"] = "function normalizeFrontstageSnapshot" in script_text
    payload["usesInfosHandleSse"] = "function connectHealthDockSse" in script_text and "new EventSource(href)" in script_text
    return payload



def inspect_live_frontstage_publication() -> dict[str, object]:
    dist_root = resolve_control_ui_dist_root()
    payload: dict[str, object] = {
        "available": bool(dist_root),
        "distRoot": str(dist_root) if dist_root else None,
        "snapshotJsonPath": None,
        "legacyStatusJsonPath": None,
        "snapshotJsonExists": False,
        "legacyStatusJsonExists": False,
        "snapshotContractPrimaryView": None,
        "snapshotContractPrimaryPublishedJsonKey": None,
        "legacyStatusAliasMarked": False,
        "legacyStatusMatchesSnapshot": False,
        "snapshotFirstReady": False,
    }
    if not dist_root:
        return payload

    snapshot_path = dist_root / "jarvis-frontstage-snapshot.json"
    legacy_status_path = dist_root / "jarvis-frontstage-status.json"
    payload["snapshotJsonPath"] = str(snapshot_path)
    payload["legacyStatusJsonPath"] = str(legacy_status_path)
    payload["snapshotJsonExists"] = snapshot_path.exists()
    payload["legacyStatusJsonExists"] = legacy_status_path.exists()

    snapshot_payload = None
    legacy_status_payload = None
    if snapshot_path.exists():
        try:
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            snapshot_payload = None
    if legacy_status_path.exists():
        try:
            legacy_status_payload = json.loads(legacy_status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            legacy_status_payload = None

    snapshot_contract = snapshot_payload.get("snapshotContract") if isinstance(snapshot_payload, dict) and isinstance(snapshot_payload.get("snapshotContract"), dict) else {}
    published_catalog = snapshot_contract.get("publishedJsonCatalog") if isinstance(snapshot_contract.get("publishedJsonCatalog"), dict) else {}
    legacy_status_contract = published_catalog.get("frontstageStatusJson") if isinstance(published_catalog.get("frontstageStatusJson"), dict) else {}
    payload["snapshotContractPrimaryView"] = snapshot_contract.get("primaryView")
    payload["snapshotContractPrimaryPublishedJsonKey"] = snapshot_contract.get("primaryPublishedJsonKey")
    payload["legacyStatusAliasMarked"] = (
        legacy_status_contract.get("role") == "legacy_alias"
        and legacy_status_contract.get("canonicalPublishedJsonKey") == "frontstageSnapshotJson"
    )
    payload["legacyStatusMatchesSnapshot"] = isinstance(snapshot_payload, dict) and isinstance(legacy_status_payload, dict) and snapshot_payload == legacy_status_payload
    payload["snapshotFirstReady"] = (
        payload["snapshotJsonExists"]
        and payload["legacyStatusJsonExists"]
        and payload["snapshotContractPrimaryView"] == "snapshot"
        and payload["snapshotContractPrimaryPublishedJsonKey"] == "frontstageSnapshotJson"
        and payload["legacyStatusAliasMarked"]
        and payload["legacyStatusMatchesSnapshot"]
    )
    return payload


def verify_infos_handle_contract_consumer() -> dict[str, object]:
    request_id = "apply-frontstage-broker-data:contract-catalog-query"
    snapshot = invoke_handle_query(
        INFOS_HANDLE_SCRIPT,
        kind="contract.catalog",
        output_format="json",
        request_id=request_id,
        python_executable=sys.executable,
        run=subprocess.run,
    )
    if not snapshot.get("ok"):
        raise RuntimeError(str(snapshot.get("error") or "infos-handle query consumer response not ok"))
    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    request_catalog = result.get("requestCatalog") if isinstance(result.get("requestCatalog"), dict) else {}
    actions = request_catalog.get("actions") if isinstance(request_catalog.get("actions"), dict) else {}
    handle_catalog = actions.get("handle") if isinstance(actions.get("handle"), dict) else {}
    helper_shape = handle_catalog.get("clientHelperResponseShape") if isinstance(handle_catalog.get("clientHelperResponseShape"), dict) else {}
    if snapshot.get("requestId") != request_id:
        raise RuntimeError(f"infos-handle query consumer requestId mismatch: {snapshot.get('requestId')!r}")
    if snapshot.get("requestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle query consumer requestInputMode mismatch: {snapshot.get('requestInputMode')!r}")
    if snapshot.get("responseOutputMode") != "stdout":
        raise RuntimeError(f"infos-handle query consumer responseOutputMode mismatch: {snapshot.get('responseOutputMode')!r}")
    if snapshot.get("kind") != "contract.catalog":
        raise RuntimeError(f"infos-handle query consumer kind mismatch: {snapshot.get('kind')!r}")
    if handle_catalog.get("preferredRequestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle query consumer preferred input mismatch: {handle_catalog.get('preferredRequestInputMode')!r}")
    if handle_catalog.get("clientHelperModule") != "openclaw_infos_handle_contract.py":
        raise RuntimeError(f"infos-handle query consumer helper module mismatch: {handle_catalog.get('clientHelperModule')!r}")
    if helper_shape.get("notice") != "deliveryNotice|null" or helper_shape.get("frontstage") != "frontstageDelivery|null":
        raise RuntimeError(f"infos-handle query consumer helper alias shape mismatch: {helper_shape!r}")
    if helper_shape.get("artifactNotice") != "artifactNotice|null":
        raise RuntimeError(f"infos-handle query consumer artifact notice shape mismatch: {helper_shape!r}")
    if helper_shape.get("notify") != "object|null":
        raise RuntimeError(f"infos-handle query consumer notify shape mismatch: {helper_shape!r}")
    return {
        "ok": True,
        "requestId": request_id,
        "requestInputMode": snapshot.get("requestInputMode"),
        "responseOutputMode": snapshot.get("responseOutputMode"),
        "kind": snapshot.get("kind"),
        "queryContractVersion": snapshot.get("queryContractVersion"),
        "requestContractVersion": request_catalog.get("requestContractVersion"),
        "helperModule": handle_catalog.get("clientHelperModule"),
        "helperNoticeAlias": helper_shape.get("notice"),
        "helperFrontstageAlias": helper_shape.get("frontstage"),
        "helperArtifactNotice": helper_shape.get("artifactNotice"),
        "helperNotify": helper_shape.get("notify"),
    }


def verify_infos_handle_snapshot_summary_consumer() -> dict[str, object]:
    request_id = "apply-frontstage-broker-data:snapshot-summary-query"
    snapshot = invoke_handle_query(
        INFOS_HANDLE_SCRIPT,
        kind="snapshot.summary",
        output_format="json",
        request_id=request_id,
        python_executable=sys.executable,
        run=subprocess.run,
    )
    if not snapshot.get("ok"):
        raise RuntimeError(str(snapshot.get("error") or "infos-handle snapshot summary consumer response not ok"))
    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    summary = result.get("summary") if isinstance(result.get("summary"), str) else None
    if snapshot.get("requestId") != request_id:
        raise RuntimeError(f"infos-handle snapshot summary consumer requestId mismatch: {snapshot.get('requestId')!r}")
    if snapshot.get("requestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle snapshot summary consumer requestInputMode mismatch: {snapshot.get('requestInputMode')!r}")
    if snapshot.get("responseOutputMode") != "stdout":
        raise RuntimeError(f"infos-handle snapshot summary consumer responseOutputMode mismatch: {snapshot.get('responseOutputMode')!r}")
    if snapshot.get("kind") != "snapshot.summary":
        raise RuntimeError(f"infos-handle snapshot summary consumer kind mismatch: {snapshot.get('kind')!r}")
    if snapshot.get("format") != "json":
        raise RuntimeError(f"infos-handle snapshot summary consumer format mismatch: {snapshot.get('format')!r}")
    if not summary or not summary.strip():
        raise RuntimeError(f"infos-handle snapshot summary consumer summary missing: {result!r}")
    return {
        "ok": True,
        "requestId": request_id,
        "requestInputMode": snapshot.get("requestInputMode"),
        "responseOutputMode": snapshot.get("responseOutputMode"),
        "kind": snapshot.get("kind"),
        "format": snapshot.get("format"),
        "severity": result.get("severity"),
        "summary": summary,
    }



def verify_infos_handle_events_recent_consumer() -> dict[str, object]:
    request_id = "apply-frontstage-broker-data:events-recent-query"
    snapshot = invoke_handle_query(
        INFOS_HANDLE_SCRIPT,
        kind="events.recent",
        output_format="json",
        request_id=request_id,
        limit=1,
        python_executable=sys.executable,
        run=subprocess.run,
    )
    if not snapshot.get("ok"):
        raise RuntimeError(str(snapshot.get("error") or "infos-handle events recent consumer response not ok"))
    result = snapshot.get("result") if isinstance(snapshot.get("result"), dict) else {}
    event_items = result.get("eventItems") if isinstance(result.get("eventItems"), list) else None
    latest_by_source_items = result.get("latestBySourceItems") if isinstance(result.get("latestBySourceItems"), list) else None
    record_type_counts = result.get("recordTypeCounts") if isinstance(result.get("recordTypeCounts"), dict) else None
    if snapshot.get("requestId") != request_id:
        raise RuntimeError(f"infos-handle events recent consumer requestId mismatch: {snapshot.get('requestId')!r}")
    if snapshot.get("requestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle events recent consumer requestInputMode mismatch: {snapshot.get('requestInputMode')!r}")
    if snapshot.get("responseOutputMode") != "stdout":
        raise RuntimeError(f"infos-handle events recent consumer responseOutputMode mismatch: {snapshot.get('responseOutputMode')!r}")
    if snapshot.get("kind") != "events.recent":
        raise RuntimeError(f"infos-handle events recent consumer kind mismatch: {snapshot.get('kind')!r}")
    if snapshot.get("format") != "json":
        raise RuntimeError(f"infos-handle events recent consumer format mismatch: {snapshot.get('format')!r}")
    if not isinstance(result.get("count"), int):
        raise RuntimeError(f"infos-handle events recent consumer count missing: {result!r}")
    if event_items is None or latest_by_source_items is None or record_type_counts is None:
        raise RuntimeError(f"infos-handle events recent consumer result shape mismatch: {result!r}")
    return {
        "ok": True,
        "requestId": request_id,
        "requestInputMode": snapshot.get("requestInputMode"),
        "responseOutputMode": snapshot.get("responseOutputMode"),
        "kind": snapshot.get("kind"),
        "format": snapshot.get("format"),
        "count": result.get("count"),
        "latestEventAt": result.get("latestEventAt"),
        "sourceEventCount": result.get("sourceEventCount"),
        "deliveryCount": result.get("deliveryCount"),
    }



def verify_infos_handle_request_entry() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="infos-handle-request-entry-") as tmp:
        tmp_path = Path(tmp)
        request_path = tmp_path / "request.json"
        response_path = tmp_path / "response.json"
        request_id = "apply-frontstage-broker-data:contract-catalog"
        payload = invoke_handle_request(
            INFOS_HANDLE_SCRIPT,
            build_handle_request_payload(
                request_id=request_id,
                kind="contract.catalog",
                output_format="json",
            ),
            python_executable=sys.executable,
            run=subprocess.run,
            request_file=request_path,
            response_file=response_path,
        )
        if not request_path.exists():
            raise RuntimeError("infos-handle request-entry smoke did not materialize request file")
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError(str((payload or {}).get("error") or "infos-handle request-entry response not ok"))
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        if payload.get("requestId") != request_id:
            raise RuntimeError(f"infos-handle request-entry requestId mismatch: {payload.get('requestId')!r}")
        if payload.get("requestInputMode") != "request_file":
            raise RuntimeError(f"infos-handle request-entry requestInputMode mismatch: {payload.get('requestInputMode')!r}")
        if payload.get("responseOutputMode") != "response_file":
            raise RuntimeError(f"infos-handle request-entry responseOutputMode mismatch: {payload.get('responseOutputMode')!r}")
        if response.get("kind") != "contract.catalog":
            raise RuntimeError(f"infos-handle request-entry response kind mismatch: {response.get('kind')!r}")
        return {
            "ok": True,
            "requestId": request_id,
            "requestFile": str(request_path),
            "responseFile": str(response_path),
            "requestInputMode": payload.get("requestInputMode"),
            "responseOutputMode": payload.get("responseOutputMode"),
            "format": request.get("format"),
            "kind": response.get("kind"),
            "queryContractVersion": response.get("queryContractVersion"),
            "requestContractVersion": payload.get("requestContractVersion"),
        }


def resolve_runtime_url(url: str) -> str:
    if isinstance(url, str) and url.startswith("/"):
        return urllib.parse.urljoin("http://127.0.0.1:18788/", url.lstrip("/"))
    return url



def fetch_json_url(url: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    url = resolve_runtime_url(url)
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"url fetch failed: {url} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"url json decode failed: {url} ({exc})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"url did not return a JSON object: {url}")
    return payload



def fetch_sse_preview(url: str, *, timeout_seconds: float = 5.0, lines: int = 4) -> str:
    url = resolve_runtime_url(url)
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            chunks: list[str] = []
            for _ in range(max(1, lines)):
                raw = response.readline()
                if not raw:
                    break
                chunks.append(raw.decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"sse fetch failed: {url} ({exc})") from exc
    return "".join(chunks)



def derive_infos_handle_sidecar_base_url(summary_href: str | None) -> str | None:
    if not isinstance(summary_href, str) or not summary_href.strip():
        return None
    parsed = urllib.parse.urlsplit(summary_href)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    if summary_href.startswith("/"):
        return "http://127.0.0.1:18788"
    return None



def derive_infos_handle_sidecar_healthz_href(summary_href: str | None) -> str | None:
    base_url = derive_infos_handle_sidecar_base_url(summary_href)
    if not base_url:
        return None
    parsed = urllib.parse.urlsplit(base_url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/healthz", "", ""))



def fetch_url_text(url: str, *, timeout_seconds: float = 5.0) -> tuple[str, str]:
    url = resolve_runtime_url(url)
    try:
        with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            content_type = response.headers.get_content_type()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"url fetch failed: {url} ({exc})") from exc
    return body, content_type



def invoke_infos_handle_sidecar_handle(base_url: str, request_payload: dict[str, object], *, timeout_seconds: float = 10.0) -> dict[str, Any]:
    handle_href = urllib.parse.urljoin(base_url.rstrip("/") + "/", "v1/handle")
    request = urllib.request.Request(
        handle_href,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"sidecar handle failed: {handle_href} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"sidecar handle json decode failed: {handle_href} ({exc})") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"sidecar handle did not return a JSON object: {handle_href}")
    return payload



def probe_infos_handle_sidecar_image_artifact(summary_href: str) -> dict[str, object]:
    base_url = derive_infos_handle_sidecar_base_url(summary_href)
    if not base_url:
        raise RuntimeError(f"cannot derive sidecar base url from summary href: {summary_href!r}")
    handle_payload = invoke_infos_handle_sidecar_handle(base_url, {"kind": "snapshot.summary", "format": "image"})
    response = handle_payload.get("response") if isinstance(handle_payload.get("response"), dict) else {}
    output = response.get("output") if isinstance(response.get("output"), dict) else {}
    artifact = output.get("artifact") if isinstance(output.get("artifact"), dict) else {}
    artifact_href = output.get("artifactHref") if isinstance(output.get("artifactHref"), str) and output.get("artifactHref") else artifact.get("href")
    artifact_ref = output.get("artifactRef") if isinstance(output.get("artifactRef"), str) and output.get("artifactRef") else artifact.get("ref")
    if handle_payload.get("ok") is not True:
        raise RuntimeError(f"sidecar image handle not ok: {handle_payload!r}")
    if not isinstance(artifact_href, str) or not artifact_href.startswith("/v1/artifacts/"):
        raise RuntimeError(f"sidecar image artifact href missing: {handle_payload!r}")
    artifact_url = urllib.parse.urljoin(base_url.rstrip("/") + "/", artifact_href)
    artifact_body, artifact_content_type = fetch_url_text(artifact_url)
    if artifact_content_type != "image/svg+xml":
        raise RuntimeError(f"sidecar image artifact content type mismatch: {artifact_content_type!r}")
    if "<svg" not in artifact_body:
        raise RuntimeError("sidecar image artifact body missing <svg")
    return {
        "artifactHref": artifact_href,
        "artifactRef": artifact_ref,
        "artifactMediaType": artifact_content_type,
    }



def build_infos_handle_sidecar_failure_payload(dock_snapshot: dict[str, object] | None, error: str) -> dict[str, object]:
    dock_payload = dock_snapshot if isinstance(dock_snapshot, dict) else {}
    return {
        "ok": False,
        "error": error,
        "infosHandleDirectReady": bool(dock_payload.get("infosHandleDirectReady")),
        "usesInfosHandleSse": bool(dock_payload.get("usesInfosHandleSse")),
        "healthzHref": derive_infos_handle_sidecar_healthz_href(dock_payload.get("infosHandleSummaryHref") if isinstance(dock_payload.get("infosHandleSummaryHref"), str) else None),
        "summaryHref": dock_payload.get("infosHandleSummaryHref"),
        "contractHref": dock_payload.get("infosHandleContractHref"),
        "sseHref": dock_payload.get("infosHandleSseHref"),
    }



def verify_control_ui_infos_handle_sidecar(dock_snapshot: dict[str, object]) -> dict[str, object]:
    summary_href = dock_snapshot.get("infosHandleSummaryHref") if isinstance(dock_snapshot.get("infosHandleSummaryHref"), str) else None
    contract_href = dock_snapshot.get("infosHandleContractHref") if isinstance(dock_snapshot.get("infosHandleContractHref"), str) else None
    sse_href = dock_snapshot.get("infosHandleSseHref") if isinstance(dock_snapshot.get("infosHandleSseHref"), str) else None
    if not bool(dock_snapshot.get("infosHandleDirectReady")):
        raise RuntimeError("control-ui branding has not exposed a ready infos-handle direct path")
    if not summary_href or not contract_href:
        raise RuntimeError("control-ui infos-handle summary/contract href missing")

    healthz_href = derive_infos_handle_sidecar_healthz_href(summary_href)
    healthz_payload = fetch_json_url(healthz_href) if healthz_href else {}
    if healthz_href:
        if healthz_payload.get("ok") is not True:
            raise RuntimeError(f"infos-handle sidecar healthz not ok: {healthz_payload!r}")
        if healthz_payload.get("service") != "infos-handle-sidecar":
            raise RuntimeError(f"infos-handle sidecar service mismatch: {healthz_payload.get('service')!r}")

    summary_payload = fetch_json_url(summary_href)
    summary_result = summary_payload.get("result") if isinstance(summary_payload.get("result"), dict) else {}
    if summary_payload.get("ok") is not True:
        raise RuntimeError(f"infos-handle summary query not ok: {summary_payload!r}")
    if summary_payload.get("kind") != "snapshot.summary":
        raise RuntimeError(f"infos-handle summary kind mismatch: {summary_payload.get('kind')!r}")
    if summary_payload.get("requestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle summary requestInputMode mismatch: {summary_payload.get('requestInputMode')!r}")
    if summary_payload.get("responseOutputMode") != "stdout":
        raise RuntimeError(f"infos-handle summary responseOutputMode mismatch: {summary_payload.get('responseOutputMode')!r}")
    if not isinstance(summary_result.get("summary"), str) or not summary_result.get("summary").strip():
        raise RuntimeError(f"infos-handle summary result missing summary: {summary_result!r}")

    contract_payload = fetch_json_url(contract_href)
    contract_result = contract_payload.get("result") if isinstance(contract_payload.get("result"), dict) else {}
    request_catalog = contract_result.get("requestCatalog") if isinstance(contract_result.get("requestCatalog"), dict) else {}
    actions = request_catalog.get("actions") if isinstance(request_catalog.get("actions"), dict) else {}
    handle_catalog = actions.get("handle") if isinstance(actions.get("handle"), dict) else {}
    if contract_payload.get("ok") is not True:
        raise RuntimeError(f"infos-handle contract query not ok: {contract_payload!r}")
    if contract_payload.get("kind") != "contract.catalog":
        raise RuntimeError(f"infos-handle contract kind mismatch: {contract_payload.get('kind')!r}")
    if contract_payload.get("requestInputMode") != "request_file":
        raise RuntimeError(f"infos-handle contract requestInputMode mismatch: {contract_payload.get('requestInputMode')!r}")
    if contract_payload.get("responseOutputMode") != "stdout":
        raise RuntimeError(f"infos-handle contract responseOutputMode mismatch: {contract_payload.get('responseOutputMode')!r}")
    if request_catalog.get("requestContractVersion") != contract_payload.get("requestContractVersion"):
        raise RuntimeError(
            "infos-handle contract requestContractVersion mismatch: "
            f"{request_catalog.get('requestContractVersion')!r} vs {contract_payload.get('requestContractVersion')!r}"
        )
    if handle_catalog.get("clientHelperModule") != "openclaw_infos_handle_contract.py":
        raise RuntimeError(f"infos-handle contract helper module mismatch: {handle_catalog.get('clientHelperModule')!r}")

    image_artifact_check = probe_infos_handle_sidecar_image_artifact(summary_href)

    sse_preview = None
    sse_ready = False
    if sse_href and bool(dock_snapshot.get("usesInfosHandleSse")):
        sse_preview = fetch_sse_preview(sse_href)
        if "event: snapshot" not in sse_preview:
            raise RuntimeError(f"infos-handle sidecar sse preview missing snapshot event: {sse_preview!r}")
        if '"kind": "snapshot.summary"' not in sse_preview and '"kind":"snapshot.summary"' not in sse_preview:
            raise RuntimeError(f"infos-handle sidecar sse preview missing snapshot.summary payload: {sse_preview!r}")
        sse_ready = True

    return {
        "ok": True,
        "healthzHref": healthz_href,
        "summaryHref": summary_href,
        "contractHref": contract_href,
        "sseHref": sse_href,
        "service": healthz_payload.get("service") if isinstance(healthz_payload, dict) else None,
        "summaryKind": summary_payload.get("kind"),
        "summarySeverity": summary_result.get("severity"),
        "summaryText": summary_result.get("summary"),
        "queryContractVersion": contract_payload.get("queryContractVersion"),
        "requestContractVersion": contract_payload.get("requestContractVersion"),
        "helperModule": handle_catalog.get("clientHelperModule"),
        "imageArtifactHref": image_artifact_check.get("artifactHref"),
        "imageArtifactRef": image_artifact_check.get("artifactRef"),
        "imageArtifactMediaType": image_artifact_check.get("artifactMediaType"),
        "sseConfigured": bool(sse_href and bool(dock_snapshot.get("usesInfosHandleSse"))),
        "sseReady": sse_ready,
        "ssePreview": (sse_preview[:400] + "…") if isinstance(sse_preview, str) and len(sse_preview) > 400 else sse_preview,
    }



def install_user_systemd() -> dict[str, str]:
    if sys.platform.startswith("win"):
        raise RuntimeError("user systemd install is not supported on Windows")
    if shutil.which("systemctl") is None:
        raise RuntimeError("systemctl not found")
    USER_SYSTEMD_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BROKER_REBUILD_SERVICE, USER_SYSTEMD_DIR / BROKER_REBUILD_SERVICE.name)
    shutil.copy2(BROKER_REBUILD_TIMER, USER_SYSTEMD_DIR / BROKER_REBUILD_TIMER.name)
    for cmd in [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", BROKER_REBUILD_TIMER.name],
        ["systemctl", "--user", "start", BROKER_REBUILD_SERVICE.name],
    ]:
        result = run(cmd)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or f"command failed: {' '.join(cmd)}").strip())
    return {
        "service": str(USER_SYSTEMD_DIR / BROKER_REBUILD_SERVICE.name),
        "timer": str(USER_SYSTEMD_DIR / BROKER_REBUILD_TIMER.name),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply and verify frontstage broker data layer")
    parser.add_argument("--install-user-systemd", action="store_true", help="Also install and enable broker rebuild user systemd units on Linux")
    parser.add_argument("--apply-control-ui-branding", action="store_true", help="Also re-apply the current Control UI branding patch before snapshot-first verification")
    parser.add_argument("--verify-control-ui-snapshot-dock", action="store_true", help="Inspect the live Control UI override script plus live public JSON, and report whether snapshot is first while status.json is only a legacy alias")
    parser.add_argument("--require-control-ui-snapshot-dock", action="store_true", help="Fail if the live Control UI snapshot-first chain is not ready")
    parser.add_argument("--verify-control-ui-infos-handle-sidecar", action="store_true", help="Probe the live infos-handle sidecar URLs referenced by the current Control UI branding override")
    parser.add_argument("--require-control-ui-infos-handle-sidecar", action="store_true", help="Fail if the live Control UI infos-handle sidecar direct path is not ready")
    args = parser.parse_args()

    steps = [
        [
            sys.executable,
            "-m",
            "py_compile",
            str(BROKER_SCRIPT),
            str(BROKER_TEST),
            str(INFOS_HANDLE_SCRIPT),
            str(INFOS_HANDLE_SIDECAR_SCRIPT),
            str(INFOS_HANDLE_TEST),
            str(SUPERVISOR_STATUS_SCRIPT),
            str(FRONTSTAGE_RECOVERY_SCRIPT),
            str(LOCAL_HEALTH_SCRIPT),
            str(FRONTSTAGE_RECOVERY_TEST),
            str(INFOS_HANDLE_CALLER_TEST),
            str(BRANDING_SCRIPT),
        ],
        [sys.executable, str(BROKER_TEST)],
        [sys.executable, str(INFOS_HANDLE_TEST)],
        [sys.executable, str(FRONTSTAGE_RECOVERY_TEST)],
        [sys.executable, str(INFOS_HANDLE_CALLER_TEST)],
    ]
    if args.apply_control_ui_branding:
        steps.append([sys.executable, str(BRANDING_SCRIPT)])
    steps.append(
        [
            sys.executable,
            str(BROKER_SCRIPT),
            "rebuild-views",
            "--print-json",
        ]
    )

    rebuild_payload = None
    infos_handle_contract_consumer_check = None
    infos_handle_snapshot_summary_consumer_check = None
    infos_handle_events_recent_consumer_check = None
    infos_handle_request_entry_check = None
    installed_units = None
    dock_snapshot_check = None
    frontstage_publication_check = None
    control_ui_infos_handle_sidecar_check = None
    for cmd in steps:
        result = run(cmd)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or result.stdout or f"command failed: {' '.join(cmd)}\n")
            return result.returncode
        if cmd[1:3] != ["-m", "py_compile"]:
            output = (result.stdout or "").strip()
            if output.startswith("{"):
                try:
                    rebuild_payload = json.loads(output)
                except json.JSONDecodeError:
                    pass
            else:
                print(output)

    try:
        infos_handle_contract_consumer_check = verify_infos_handle_contract_consumer()
    except RuntimeError as exc:
        sys.stderr.write(f"verify-infos-handle-contract-consumer failed: {exc}\n")
        return 1

    try:
        infos_handle_snapshot_summary_consumer_check = verify_infos_handle_snapshot_summary_consumer()
    except RuntimeError as exc:
        sys.stderr.write(f"verify-infos-handle-snapshot-summary-consumer failed: {exc}\n")
        return 1

    try:
        infos_handle_events_recent_consumer_check = verify_infos_handle_events_recent_consumer()
    except RuntimeError as exc:
        sys.stderr.write(f"verify-infos-handle-events-recent-consumer failed: {exc}\n")
        return 1

    try:
        infos_handle_request_entry_check = verify_infos_handle_request_entry()
    except RuntimeError as exc:
        sys.stderr.write(f"verify-infos-handle-request-entry failed: {exc}\n")
        return 1

    if args.install_user_systemd:
        try:
            installed_units = install_user_systemd()
        except RuntimeError as exc:
            sys.stderr.write(f"install-user-systemd failed: {exc}\n")
            return 1

    if (
        args.verify_control_ui_snapshot_dock
        or args.require_control_ui_snapshot_dock
        or args.verify_control_ui_infos_handle_sidecar
        or args.require_control_ui_infos_handle_sidecar
        or args.apply_control_ui_branding
    ):
        dock_snapshot_check = inspect_control_ui_snapshot_dock()
        frontstage_publication_check = inspect_live_frontstage_publication()
        if args.require_control_ui_snapshot_dock and not (
            bool(dock_snapshot_check.get("snapshotFirst")) and bool(frontstage_publication_check.get("snapshotFirstReady"))
        ):
            sys.stderr.write(
                json.dumps(
                    {
                        "controlUiSnapshotDock": dock_snapshot_check,
                        "frontstagePublication": frontstage_publication_check,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
            return 1

    if args.verify_control_ui_infos_handle_sidecar or args.require_control_ui_infos_handle_sidecar:
        if dock_snapshot_check is None:
            dock_snapshot_check = inspect_control_ui_snapshot_dock()
        try:
            control_ui_infos_handle_sidecar_check = verify_control_ui_infos_handle_sidecar(dock_snapshot_check)
        except RuntimeError as exc:
            control_ui_infos_handle_sidecar_check = build_infos_handle_sidecar_failure_payload(dock_snapshot_check, str(exc))
            if args.require_control_ui_infos_handle_sidecar:
                sys.stderr.write(
                    json.dumps(
                        {
                            "controlUiSnapshotDock": dock_snapshot_check,
                            "controlUiInfosHandleSidecar": control_ui_infos_handle_sidecar_check,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                )
                return 1

    print("Applied frontstage broker data layer.")
    if isinstance(rebuild_payload, dict):
        print(json.dumps(rebuild_payload, ensure_ascii=False, indent=2))
    if infos_handle_contract_consumer_check is not None:
        print(json.dumps({"infosHandleContractConsumer": infos_handle_contract_consumer_check}, ensure_ascii=False, indent=2))
    if infos_handle_snapshot_summary_consumer_check is not None:
        print(json.dumps({"infosHandleSnapshotSummaryConsumer": infos_handle_snapshot_summary_consumer_check}, ensure_ascii=False, indent=2))
    if infos_handle_events_recent_consumer_check is not None:
        print(json.dumps({"infosHandleEventsRecentConsumer": infos_handle_events_recent_consumer_check}, ensure_ascii=False, indent=2))
    if infos_handle_request_entry_check is not None:
        print(json.dumps({"infosHandleRequestEntry": infos_handle_request_entry_check}, ensure_ascii=False, indent=2))
    if dock_snapshot_check is not None:
        print(json.dumps({"controlUiSnapshotDock": dock_snapshot_check}, ensure_ascii=False, indent=2))
    if frontstage_publication_check is not None:
        print(json.dumps({"frontstagePublication": frontstage_publication_check}, ensure_ascii=False, indent=2))
    if control_ui_infos_handle_sidecar_check is not None:
        print(json.dumps({"controlUiInfosHandleSidecar": control_ui_infos_handle_sidecar_check}, ensure_ascii=False, indent=2))
    if installed_units:
        print(json.dumps({"installedUserSystemd": installed_units}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
