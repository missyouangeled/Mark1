#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"
SIDECAR_SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle-sidecar.py"
EXPECTED_QUERY_CONTRACT_VERSION = 18
EXPECTED_REQUEST_CONTRACT_VERSION = 6


def run(*args: str, env: dict[str, str] | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    current_env = os.environ.copy()
    if env:
        current_env.update(env)
    return subprocess.run([
        "python3",
        str(SCRIPT),
        *args,
    ], cwd=WORKSPACE, capture_output=True, text=True, check=False, env=current_env, input=input_text)


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])



def fetch_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))



def wait_for_sidecar(url: str, *, timeout_seconds: float = 5.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            payload = fetch_json(url)
            if payload.get("ok") is True:
                return
        except Exception as exc:  # pragma: no cover - retry helper
            last_error = exc
        time.sleep(0.1)
    if last_error is not None:
        raise last_error
    raise RuntimeError("sidecar did not become ready")



def main() -> int:
    with tempfile.TemporaryDirectory(prefix="infos-handle-test-") as tmp:
        tmp_path = Path(tmp)
        snapshot_path = tmp_path / "snapshot.json"
        events_path = tmp_path / "events.jsonl"

        snapshot_payload = {
            "summary": "前台状态总体正常",
            "issueOverview": "broker / 监工 / 恢复观察 / 本地健康当前都没看到明显异常。",
            "severity": "ok",
            "selfHelpActions": ["一切正常，继续工作。"],
            "panels": {
                "health": {
                    "summary": "健康正常",
                    "detail": "当前网络和 Gateway 可达。",
                    "selfHelpActions": ["继续观察网络与 Gateway。", "若出现异常，再检查 broker 视图。"],
                    "checkedAt": "2026-05-15T12:00:00+08:00",
                },
                "supervisor": {
                    "summary": "监工待命中",
                    "detail": "当前没有后台任务。",
                    "checkedAt": "2026-05-15T12:00:01+08:00",
                },
                "recovery": {
                    "summary": "前台投影稳定",
                    "detail": "未发现明显异常。",
                    "checkedAt": "2026-05-15T12:00:02+08:00",
                },
            },
            "latestDelivery": {
                "source": "supervisor",
                "message": "[监工] 后台任务已完成。",
                "eventKey": "done-1",
            },
            "sourceStateSnapshots": {
                "local-health": {
                    "summary": "健康正常",
                    "sourceEventType": "local_health.status.changed",
                    "sourceView": "health",
                    "eventKey": "health-ok-1",
                    "recordedAt": "2026-05-15T12:00:00+08:00",
                },
                "frontstage-recovery": {
                    "recordType": "broker.source.latest",
                    "sourceEventType": "frontstage_recovery.status.changed",
                    "sourceView": "recovery",
                    "message": "前台恢复状态已记录",
                    "eventKey": "recovery-ok-1",
                    "recordedAt": "2026-05-15T12:00:02+08:00",
                    "data": {
                        "summary": "前台投影稳定",
                        "detail": "未发现明显异常。",
                        "status": "recovered",
                        "checkedAt": "2026-05-15T12:00:02+08:00"
                    },
                },
            },
            "sources": {
                "supervisor": {
                    "sourceEventType": "supervisor.status.changed",
                    "sourceView": "tasks",
                    "message": "[监工] 后台任务已完成。",
                    "eventKey": "done-1",
                    "sentAt": "2026-05-15T12:00:03+08:00",
                },
                "local-health": {
                    "recordType": "frontstage.delivery.latest",
                    "sourceEventType": "local_health.status.changed",
                    "sourceView": "health",
                    "message": "[本地健康] 当前已恢复正常。",
                    "eventKey": "health-delivery-1",
                    "sentAt": "2026-05-15T12:00:01+08:00",
                },
            },
            "contractVersion": 2,
            "contracts": {
                "version": 2,
                "sourceEventRecordType": "broker.source.event",
                "deliveryEventRecordType": "frontstage.delivery.sent",
                "sourceSnapshotRecordType": "frontstage.delivery.latest",
                "sourceStateSnapshotRecordType": "broker.source.latest",
                "sourceEventTypeField": "sourceEventType",
                "sourceViewField": "sourceView",
                "recordTypes": {
                    "broker.source.event": {
                        "description": "Append-only source event recorded by broker ingest before any frontstage delivery is required.",
                        "requiredFields": ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt"],
                        "optionalFields": ["schemaVersion", "contractVersion", "data", "ingestStatus"],
                    },
                    "frontstage.delivery.sent": {
                        "description": "Append-only frontstage delivery event written after a helper message is actually sent.",
                        "requiredFields": ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt", "sentAt"],
                        "optionalFields": ["schemaVersion", "contractVersion", "targetSessionKey", "messageId", "deliveryStatus"],
                    },
                    "frontstage.delivery.latest": {
                        "description": "Latest successful frontstage delivery snapshot for one source inside frontstage.json / snapshot payloads.",
                        "requiredFields": ["recordType", "source", "sourceEventType", "sourceView"],
                        "optionalFields": ["eventKey", "sessionKey", "targetSessionKey", "messageId", "message", "sentAt"],
                    },
                    "broker.source.latest": {
                        "description": "Latest ingest-side source snapshot for one source, even when no frontstage delivery happened yet.",
                        "requiredFields": ["recordType", "source", "sourceEventType", "sourceView"],
                        "optionalFields": ["eventKey", "sessionKey", "message", "recordedAt", "data"],
                    },
                },
                "eventFieldCatalog": {
                    "sourceEventType": {
                        "type": "str",
                        "description": "Stable semantic event type for one broker source.",
                        "knownValues": ["local_health.status.changed", "supervisor.status.changed"],
                    },
                    "sourceView": {
                        "type": "str|null",
                        "description": "Stable logical view bucket used by renderer / infos-handle consumers.",
                        "knownValues": ["health", "tasks"],
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
                },
                "sources": {
                    "local-health": {
                        "source": "local-health",
                        "sourceEventType": "local_health.status.changed",
                        "sourceView": "health",
                    },
                    "supervisor": {
                        "source": "supervisor",
                        "sourceEventType": "supervisor.status.changed",
                        "sourceView": "tasks",
                    },
                },
            },
            "snapshotContract": {
                "primaryView": "snapshot",
                "primaryPublishedJsonKey": "frontstageSnapshotJson",
            },
        }
        snapshot_path.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        events_path.write_text(
            "\n".join(
                [
                    json.dumps({
                        "recordType": "broker.source.event",
                        "source": "local-health",
                        "sourceEventType": "local_health.status.changed",
                        "sourceView": "health",
                        "recordedAt": "2026-05-15T12:00:00+08:00",
                        "eventKey": "health-ok-1",
                        "message": "本地健康状态已记录",
                        "ingestStatus": "recorded",
                        "data": {
                            "summary": "健康正常",
                            "severity": "ok",
                            "checkedAt": "2026-05-15T12:00:00+08:00"
                        },
                    }, ensure_ascii=False),
                    json.dumps({
                        "recordType": "frontstage.delivery.sent",
                        "source": "local-health",
                        "sourceEventType": "local_health.status.changed",
                        "sourceView": "health",
                        "recordedAt": "2026-05-15T12:00:01+08:00",
                        "eventKey": "health-delivery-1",
                        "message": "[本地健康] 当前已恢复正常。",
                        "deliveryStatus": "sent",
                    }, ensure_ascii=False),
                    json.dumps({
                        "recordType": "frontstage.delivery.sent",
                        "source": "supervisor",
                        "sourceEventType": "supervisor.status.changed",
                        "sourceView": "tasks",
                        "recordedAt": "2026-05-15T12:00:03+08:00",
                        "eventKey": "done-1",
                        "message": "[监工] 后台任务已完成。",
                        "deliveryStatus": "sent",
                    }, ensure_ascii=False),
                ]
            ) + "\n",
            encoding="utf-8",
        )

        output_root = tmp_path / "infos-handle-output"
        broker_state_dir = tmp_path / "frontstage-state"
        broker_data_dir = tmp_path / "broker-data"
        audio_renderer = tmp_path / "fake-audio-renderer.sh"
        audio_renderer.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "TEXT=\"${1:-}\"\n"
            "PRESET=\"${2:-default}\"\n"
            "OUTDIR=\"$(dirname \"$0\")/fake-audio\"\n"
            "mkdir -p \"$OUTDIR\"\n"
            "OUT=\"$OUTDIR/$(printf '%s' \"$PRESET\" | tr -cs '[:alnum:]' '-')-reply.mp3\"\n"
            "printf 'FAKE AUDIO | %s | %s\n' \"$PRESET\" \"$TEXT\" > \"$OUT\"\n"
            "printf '%s\n' \"$OUT\"\n",
            encoding="utf-8",
        )
        audio_renderer.chmod(0o755)

        fake_frontstage_helper = tmp_path / "fake-frontstage-helper.py"
        fake_frontstage_helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "args = sys.argv[1:]\n"
            "session_key = args[args.index('--session-key') + 1]\n"
            "message = args[args.index('--message') + 1]\n"
            "print(json.dumps({\n"
            "  'ok': True,\n"
            "  'targetSessionKey': f'{session_key}:frontstage',\n"
            "  'response': {'messageId': f'msg::{message}'}\n"
            "}, ensure_ascii=False))\n",
            encoding="utf-8",
        )
        fake_frontstage_helper.chmod(0o755)
        fake_frontstage_env = {
            "OPENCLAW_INFOS_HANDLE_FRONTSTAGE_HELPER": str(fake_frontstage_helper),
        }

        result = run("query", "--kind", "snapshot.summary", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "前台状态总体正常" in result.stdout
        assert "建议：" in result.stdout

        result = run("query", "--kind", "tasks.summary", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "监工：监工待命中" in result.stdout
        assert "恢复观察：前台投影稳定" in result.stdout

        result = run("query", "--kind", "sources.latest", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "local-health｜state=健康正常｜delivery=[本地健康] 当前已恢复正常。" in result.stdout
        assert "supervisor｜state=无 ingest｜delivery=[监工] 后台任务已完成。" in result.stdout

        result = run("query", "--kind", "events.recent", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["kind"] == "events.recent"
        assert payload["format"] == "json"
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert len(payload["events"]) == 3
        assert len(payload["result"]["events"]) == 3
        assert payload["events"][0]["source"] == "supervisor"
        assert payload["result"]["count"] == 3
        assert payload["result"]["latestEventAt"] == "2026-05-15T12:00:03+08:00"
        assert payload["result"]["availableSources"] == ["local-health", "supervisor"]
        assert payload["result"]["sourceEventCount"] == 1
        assert payload["result"]["deliveryCount"] == 2
        assert payload["result"]["recordTypeCounts"] == {
            "frontstage.delivery.sent": 2,
            "broker.source.event": 1,
        }
        assert payload["result"]["latestBySource"] == {
            "supervisor": {
                "source": "supervisor",
                "eventCount": 1,
                "deliveryCount": 1,
                "latestEventAt": "2026-05-15T12:00:03+08:00",
                "latestRecordType": "frontstage.delivery.sent",
                "latestEventSummary": "[监工] 后台任务已完成。",
                "latestEventKey": "done-1",
                "sourceEventType": "supervisor.status.changed",
                "sourceView": "tasks",
                "isDelivery": True,
            },
            "local-health": {
                "source": "local-health",
                "eventCount": 2,
                "deliveryCount": 1,
                "latestEventAt": "2026-05-15T12:00:01+08:00",
                "latestRecordType": "frontstage.delivery.sent",
                "latestEventSummary": "[本地健康] 当前已恢复正常。",
                "latestEventKey": "health-delivery-1",
                "sourceEventType": "local_health.status.changed",
                "sourceView": "health",
                "isDelivery": True,
            },
        }
        assert payload["result"]["latestBySourceItems"] == [
            {
                "source": "supervisor",
                "eventCount": 1,
                "deliveryCount": 1,
                "latestEventAt": "2026-05-15T12:00:03+08:00",
                "latestRecordType": "frontstage.delivery.sent",
                "latestEventSummary": "[监工] 后台任务已完成。",
                "latestEventKey": "done-1",
                "sourceEventType": "supervisor.status.changed",
                "sourceView": "tasks",
                "isDelivery": True,
            },
            {
                "source": "local-health",
                "eventCount": 2,
                "deliveryCount": 1,
                "latestEventAt": "2026-05-15T12:00:01+08:00",
                "latestRecordType": "frontstage.delivery.sent",
                "latestEventSummary": "[本地健康] 当前已恢复正常。",
                "latestEventKey": "health-delivery-1",
                "sourceEventType": "local_health.status.changed",
                "sourceView": "health",
                "isDelivery": True,
            },
        ]
        assert len(payload["result"]["eventItems"]) == 3
        assert payload["result"]["eventItems"][0]["recordType"] == "frontstage.delivery.sent"
        assert payload["result"]["eventItems"][0]["source"] == "supervisor"
        assert payload["result"]["eventItems"][0]["sourceView"] == "tasks"
        assert payload["result"]["eventItems"][0]["sourceEventType"] == "supervisor.status.changed"
        assert payload["result"]["eventItems"][0]["summary"] == "[监工] 后台任务已完成。"
        assert payload["result"]["eventItems"][0]["isDelivery"] is True
        assert payload["result"]["eventItems"][1]["recordType"] == "frontstage.delivery.sent"
        assert payload["result"]["eventItems"][2]["recordType"] == "broker.source.event"
        assert payload["result"]["eventItems"][2]["summary"] == "健康正常"
        assert payload["result"]["eventItems"][2]["severity"] == "ok"
        assert payload["result"]["eventItems"][2]["checkedAt"] == "2026-05-15T12:00:00+08:00"
        assert payload["result"]["eventItems"][2]["ingestStatus"] == "recorded"

        result = run("query", "--kind", "events.recent", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "count=3｜sources=local-health, supervisor｜recordTypes=frontstage.delivery.sent:2, broker.source.event:1" in result.stdout
        assert "latestBySource: supervisor=frontstage.delivery.sent, local-health=frontstage.delivery.sent" in result.stdout
        assert "- [frontstage.delivery.sent] supervisor｜view=tasks｜eventType=supervisor.status.changed｜2026-05-15T12:00:03+08:00｜[监工] 后台任务已完成。" in result.stdout

        result = run("query", "--kind", "sources.latest", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["result"]["count"] == 3
        assert payload["result"]["availableSources"] == ["frontstage-recovery", "local-health", "supervisor"]
        source_rows = {item["source"]: item for item in payload["result"]["sourceItems"]}
        assert source_rows["local-health"]["latestEventSummary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["latestEventItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["latestEventItem"]["isDelivery"] is True
        assert source_rows["local-health"]["latestDeliveryItem"]["recordType"] == "frontstage.delivery.latest"
        assert source_rows["local-health"]["latestDeliveryItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["frontstage-recovery"]["latestEventSummary"] == "前台投影稳定"
        assert source_rows["frontstage-recovery"]["latestEventItem"]["reportStatus"] == "recovered"
        assert source_rows["supervisor"]["latestDeliveryMessage"] == "[监工] 后台任务已完成。"
        assert payload["result"]["sourceStateSnapshots"]["local-health"]["summary"] == "健康正常"
        assert payload["result"]["sources"]["supervisor"]["message"] == "[监工] 后台任务已完成。"

        result = run("query", "--kind", "sources.catalog", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["result"]["count"] == 3
        source_rows = {item["source"]: item for item in payload["result"]["sources"]}
        assert source_rows["local-health"]["sourceView"] == "health"
        assert source_rows["local-health"]["hasSourceState"] is True
        assert source_rows["local-health"]["latestEventAt"] == "2026-05-15T12:00:01+08:00"
        assert source_rows["local-health"]["latestRecordType"] == "frontstage.delivery.latest"
        assert source_rows["local-health"]["latestEventSummary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["latestEventKey"] == "health-delivery-1"
        assert source_rows["local-health"]["latestEventItem"]["recordType"] == "frontstage.delivery.latest"
        assert source_rows["local-health"]["latestEventItem"]["sourceEventType"] == "local_health.status.changed"
        assert source_rows["local-health"]["latestEventItem"]["sourceView"] == "health"
        assert source_rows["local-health"]["latestEventItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["latestEventItem"]["deliveryStatus"] is None
        assert source_rows["local-health"]["latestSourceStateSummary"] == "健康正常"
        assert source_rows["local-health"]["latestSourceStateRecordedAt"] == "2026-05-15T12:00:00+08:00"
        assert source_rows["local-health"]["latestDeliveryMessage"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["latestDeliveryEventKey"] == "health-delivery-1"
        assert source_rows["local-health"]["latestDeliveryRecordType"] == "frontstage.delivery.latest"
        assert source_rows["local-health"]["latestDeliverySentAt"] == "2026-05-15T12:00:01+08:00"
        assert source_rows["local-health"]["latestDeliveryItem"]["recordType"] == "frontstage.delivery.latest"
        assert source_rows["local-health"]["latestDeliveryItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert source_rows["local-health"]["contract"]["sourceView"] == "health"
        assert source_rows["supervisor"]["hasDelivery"] is True
        assert source_rows["supervisor"]["latestDeliveryMessage"] == "[监工] 后台任务已完成。"
        assert source_rows["frontstage-recovery"]["hasDelivery"] is False
        assert source_rows["frontstage-recovery"]["latestEventSummary"] == "前台投影稳定"
        assert source_rows["frontstage-recovery"]["latestEventKey"] == "recovery-ok-1"
        assert source_rows["frontstage-recovery"]["latestEventItem"]["summary"] == "前台投影稳定"
        assert source_rows["frontstage-recovery"]["latestEventItem"]["detail"] == "未发现明显异常。"
        assert source_rows["frontstage-recovery"]["latestEventItem"]["reportStatus"] == "recovered"
        assert source_rows["frontstage-recovery"]["latestSourceStateSummary"] == "前台投影稳定"
        assert source_rows["frontstage-recovery"]["latestDeliveryMessage"] is None

        result = run("query", "--kind", "source.inspect", "--source-name", "local-health", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["sourceName"] == "local-health"
        assert payload["result"]["source"] == "local-health"
        assert payload["result"]["exists"] is True
        assert payload["result"]["availableSources"] == ["frontstage-recovery", "local-health", "supervisor"]
        assert payload["result"]["sourceEventType"] == "local_health.status.changed"
        assert payload["result"]["sourceView"] == "health"
        assert payload["result"]["hasContract"] is True
        assert payload["result"]["hasSourceState"] is True
        assert payload["result"]["hasDelivery"] is True
        assert payload["result"]["recentEventCount"] == 2
        assert payload["result"]["recentDeliveryCount"] == 1
        assert payload["result"]["latestEventAt"] == "2026-05-15T12:00:01+08:00"
        assert payload["result"]["latestRecordType"] == "frontstage.delivery.sent"
        assert payload["result"]["latestEventSummary"] == "[本地健康] 当前已恢复正常。"
        assert payload["result"]["latestEventKey"] == "health-delivery-1"
        assert payload["result"]["latestEventItem"]["recordType"] == "frontstage.delivery.sent"
        assert payload["result"]["latestEventItem"]["source"] == "local-health"
        assert payload["result"]["latestEventItem"]["sourceEventType"] == "local_health.status.changed"
        assert payload["result"]["latestEventItem"]["sourceView"] == "health"
        assert payload["result"]["latestEventItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert payload["result"]["latestSourceStateSummary"] == "健康正常"
        assert payload["result"]["latestSourceStateRecordedAt"] == "2026-05-15T12:00:00+08:00"
        assert payload["result"]["latestDeliveryMessage"] == "[本地健康] 当前已恢复正常。"
        assert payload["result"]["latestDeliveryEventKey"] == "health-delivery-1"
        assert payload["result"]["latestDeliveryRecordType"] == "frontstage.delivery.latest"
        assert payload["result"]["latestDeliverySentAt"] == "2026-05-15T12:00:01+08:00"
        assert payload["result"]["latestDeliveryItem"]["recordType"] == "frontstage.delivery.latest"
        assert payload["result"]["latestDeliveryItem"]["summary"] == "[本地健康] 当前已恢复正常。"
        assert payload["result"]["contract"]["sourceView"] == "health"
        assert payload["result"]["latestSourceState"]["summary"] == "健康正常"
        assert payload["result"]["latestDelivery"]["message"] == "[本地健康] 当前已恢复正常。"
        assert len(payload["result"]["recentEventItems"]) == 2
        assert payload["result"]["recentEventItems"][0]["recordType"] == "frontstage.delivery.sent"
        assert payload["result"]["recentEventItems"][0]["summary"] == "[本地健康] 当前已恢复正常。"
        assert payload["result"]["recentEventItems"][0]["deliveryStatus"] == "sent"
        assert payload["result"]["recentEventItems"][1]["recordType"] == "broker.source.event"
        assert payload["result"]["recentEventItems"][1]["summary"] == "健康正常"
        assert payload["result"]["recentEventItems"][1]["severity"] == "ok"
        assert payload["result"]["recentEventItems"][1]["checkedAt"] == "2026-05-15T12:00:00+08:00"
        assert payload["result"]["recentEventItems"][1]["ingestStatus"] == "recorded"
        assert len(payload["result"]["recentDeliveryItems"]) == 1
        assert payload["result"]["recentDeliveryItems"][0]["recordType"] == "frontstage.delivery.sent"
        assert payload["result"]["recentDeliveryItems"][0]["summary"] == "[本地健康] 当前已恢复正常。"
        assert len(payload["result"]["recentEvents"]) == 2

        result = run("query", "--kind", "panel.inspect", "--panel-name", "health", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["panelName"] == "health"
        assert payload["result"]["panelName"] == "health"
        assert payload["result"]["exists"] is True
        assert payload["result"]["summary"] == "健康正常"
        assert payload["result"]["detail"] == "当前网络和 Gateway 可达。"
        assert payload["result"]["severity"] is None
        assert payload["result"]["checkedAt"] == "2026-05-15T12:00:00+08:00"
        assert payload["result"]["panel"]["summary"] == "健康正常"
        assert payload["result"]["availablePanels"] == ["health", "recovery", "supervisor"]

        result = run("query", "--kind", "panels.catalog", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["result"]["count"] == 3
        panel_rows = {item["panelName"]: item for item in payload["result"]["panels"]}
        assert panel_rows["health"]["available"] is True
        assert panel_rows["health"]["summary"] == "健康正常"
        assert panel_rows["health"]["checkedAt"] == "2026-05-15T12:00:00+08:00"
        assert panel_rows["supervisor"]["detail"] == "当前没有后台任务。"
        assert panel_rows["recovery"]["severity"] is None

        result = run("query", "--kind", "contract.catalog", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["format"] == "json"
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["result"]["requestContractVersion"] == EXPECTED_REQUEST_CONTRACT_VERSION
        assert payload["result"]["brokerContractVersion"] == 2
        assert payload["result"]["snapshotContract"]["primaryView"] == "snapshot"
        assert payload["result"]["contracts"]["sources"]["supervisor"]["sourceView"] == "tasks"
        assert payload["result"]["contracts"]["recordTypes"]["broker.source.event"]["requiredFields"] == ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt"]
        assert payload["result"]["contracts"]["recordTypes"]["frontstage.delivery.sent"]["optionalFields"] == ["schemaVersion", "contractVersion", "targetSessionKey", "messageId", "deliveryStatus"]
        assert payload["result"]["contracts"]["eventFieldCatalog"]["sourceEventType"]["knownValues"] == ["local_health.status.changed", "supervisor.status.changed"]
        assert payload["result"]["contracts"]["eventFieldCatalog"]["sentAt"]["type"] == "str|null"
        assert payload["result"]["queryCatalog"]["defaultLimit"] == 6
        assert payload["result"]["queryCatalog"]["readyOutputFormats"] == ["text", "json"]
        assert payload["result"]["queryCatalog"]["previewOutputFormats"] == ["image", "audio"]
        assert payload["result"]["queryCatalog"]["reservedOutputFormats"] == []
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["text"]["status"] == "ready"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["json"]["delivery"] == "stdout"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["image"]["status"] == "preview"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["image"]["delivery"] == "artifact_file"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["image"]["frontstageDeliveryKind"] == "artifact_notice"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["image"]["artifactNoticeContractVersion"] == 1
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["audio"]["delivery"] == "artifact_file"
        assert payload["result"]["queryCatalog"]["outputFormatCatalog"]["audio"]["artifactNoticeContractVersion"] == 1
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v2"]["artifactMediaType"] == "image/svg+xml"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v2"]["frontstageDeliveryKind"] == "artifact_notice"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v2"]["renderResultShape"]["layout"] == "str"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v2"]["renderResultShape"]["panels"] == "array[imageCardPanel]"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v3"]["artifactMediaType"] == "image/svg+xml"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v3"]["imagePreset"] == "summary-card-v3"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v3"]["renderResultShape"]["cardVersion"] == "int"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v3"]["renderResultShape"]["gradientShell"] == "bool"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["image.summary-card.v3"]["renderResultShape"]["statusSparkLine"] == "bool"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["audio.local-tts.v2"]["defaultRenderer"].endswith("tools/voice-reply/voice-reply.sh")
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["audio.local-tts.v2"]["artifactNoticeContractVersion"] == 1
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["audio.local-tts.v2"]["renderResultShape"]["segmentCount"] == "int"
        assert payload["result"]["queryCatalog"]["outputHandlerCatalog"]["audio.local-tts.v2"]["renderResultShape"]["estimatedDurationSeconds"] == "number"
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["panelName"] == "str|null"
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["format"] == "str"
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["output"] == "object|null"
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["requestContractVersion"] == "int|null"
        assert payload["result"]["requestCatalog"]["requestContractVersion"] == EXPECTED_REQUEST_CONTRACT_VERSION
        assert payload["result"]["requestCatalog"]["artifactNoticeContractVersion"] == 1
        assert payload["result"]["requestCatalog"]["deliveryNoticeContractVersion"] == 1
        assert payload["result"]["requestCatalog"]["deliveryModes"] == ["none", "frontstage"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["supportedFormats"] == ["text", "json", "image", "audio"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestInputModes"] == ["flags", "request_json", "request_file"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["preferredRequestInputMode"] == "request_file"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["preferredRequestFileValue"] == "-"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["responseOutputModes"] == ["stdout", "response_file"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["preferredResponseOutputMode"] == "stdout"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperModule"] == "openclaw_infos_handle_contract.py"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperFunctions"] == [
            "build_handle_request_payload",
            "invoke_handle_request",
            "invoke_handle_query",
            "extract_handle_response_snapshot",
            "extract_frontstage_notify_payload",
            "extract_delivery_snapshot",
            "build_compat_delivery_bundle",
        ]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["artifactNoticeFormats"] == ["image", "audio"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["formatDeliveryMatrix"]["image"] == ["none", "frontstage"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["formatDeliveryMatrix"]["audio"] == ["none", "frontstage"]
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestShape"]["requestId"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestShape"]["message"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestShape"]["audioRenderer"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestShape"]["brokerStateDir"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["requestShape"]["brokerDataDir"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["cliTransportShape"]["responseFile"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["artifactShape"]["ref"] == "str"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["outputShape"]["artifact"] == "artifact|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["deliveryShape"]["artifactRef"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["deliveryShape"]["notice"] == "deliveryNotice|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["deliveryNoticeShape"]["frontstage"] == "frontstageDelivery"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["frontstageDeliveryShape"]["messageId"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["frontstageDeliveryShape"]["artifactRef"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["frontstageDeliveryShape"]["displayText"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["artifactNoticeShape"]["artifactRef"] == "str"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["artifactNoticeShape"]["delivery"] == "frontstageDelivery"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["responseShape"]["requestId"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["responseShape"]["requestInputMode"] == "str"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["responseShape"]["responseOutputMode"] == "str"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["kind"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["format"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["notice"] == "deliveryNotice|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["deliveryNotice"] == "deliveryNotice|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["frontstage"] == "frontstageDelivery|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["frontstageDelivery"] == "frontstageDelivery|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["artifactNotice"] == "artifactNotice|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["notify"] == "object|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["artifact"] == "artifact|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["targetSessionKey"] == "str|null"
        assert payload["result"]["requestCatalog"]["actions"]["handle"]["clientHelperResponseShape"]["messageId"] == "str|null"
        assert payload["result"]["handlerCatalog"]["json.stdout.v1"]["delivery"] == "stdout"
        assert payload["result"]["handlerCatalog"]["image.summary-card.v2"]["deliveryModes"] == ["none", "frontstage"]
        assert payload["result"]["handlerCatalog"]["image.summary-card.v2"]["frontstageDeliveryKind"] == "artifact_notice"
        assert payload["result"]["handlerCatalog"]["image.summary-card.v2"]["renderResultShape"]["badge"] == "str|null"
        assert payload["result"]["handlerCatalog"]["image.summary-card.v3"]["deliveryModes"] == ["none", "frontstage"]
        assert payload["result"]["handlerCatalog"]["image.summary-card.v3"]["imagePreset"] == "summary-card-v3"
        assert payload["result"]["handlerCatalog"]["image.summary-card.v3"]["renderResultShape"]["panelGradients"] == "bool"
        assert payload["result"]["handlerCatalog"]["audio.local-tts.v2"]["deliveryModes"] == ["none", "frontstage"]
        assert payload["result"]["handlerCatalog"]["audio.local-tts.v2"]["artifactNoticeContractVersion"] == 1
        assert payload["result"]["handlerCatalog"]["audio.local-tts.v2"]["renderResultShape"]["segments"] == "array[str]"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["count"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["availableSources"] == "array[str]"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["sourceItems"] == "array[sourceLatestItem]"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["sourceLatestItem"]["latestEventItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["sourceLatestItem"]["latestDeliveryMessage"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.latest"]["resultShape"]["sourceLatestItem"]["latestDeliveryItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["requiredArgs"] == ["source_name"]
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["exists"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["recentEventCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["recentDeliveryCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestEventAt"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestRecordType"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestEventSummary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestEventKey"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestEventItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestSourceStateSummary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestDeliveryMessage"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestDeliveryEventKey"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestDeliveryRecordType"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["latestDeliveryItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["recentEventItems"] == "array[sourceEventItem]"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["recentDeliveryItems"] == "array[sourceEventItem]"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["sourceEventItem"]["summary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["sourceEventItem"]["isDelivery"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["optionalArgs"] == ["limit"]
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["count"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["latestEventAt"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["availableSources"] == "array[str]"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["sourceEventCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["deliveryCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["recordTypeCounts"] == "object[str,int]"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["latestBySource"] == "object[str,sourceRecentSummary]"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["latestBySourceItems"] == "array[sourceRecentSummary]"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["sourceRecentSummary"]["eventCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["sourceRecentSummary"]["latestEventSummary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["sourceRecentSummary"]["isDelivery"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["eventItems"] == "array[brokerEventItem]"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["brokerEventItem"]["summary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["events.recent"]["resultShape"]["brokerEventItem"]["isDelivery"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["formats"] == ["text", "json"]
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestEventSummary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestEventKey"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestEventItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceEventItem"]["summary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestSourceStateSummary"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestDeliveryMessage"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestDeliveryEventKey"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestDeliveryRecordType"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["latestDeliveryItem"] == "sourceEventItem"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["resultShape"]["sourceCatalogItem"]["contract"] == "object"
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["requiredArgs"] == ["panel_name"]
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["resultShape"]["exists"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["resultShape"]["checkedAt"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["panels.catalog"]["formats"] == ["text", "json"]
        assert payload["result"]["queryCatalog"]["queries"]["panels.catalog"]["resultShape"]["panelCatalogItem"]["available"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["panels.catalog"]["resultShape"]["panelCatalogItem"]["checkedAt"] == "str|null"
        assert payload["result"]["paths"]["snapshotPath"] == str(snapshot_path)

        result = run(
            "notify-frontstage",
            "--kind", "snapshot.summary",
            "--session-key", "agent:main:test",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["action"] == "notify-frontstage"
        assert payload["requestId"] is None
        assert payload["targetSessionKey"] == "agent:main:test:frontstage"
        assert payload["response"]["messageId"].startswith("msg::[ok] 前台状态总体正常")
        assert payload["delivery"]["kind"] == "message"
        assert payload["notice"]["kind"] == "message"
        assert payload["deliveryNotice"]["kind"] == "message"
        assert payload["frontstage"]["noticeKind"] == "message"
        assert payload["frontstageDelivery"]["noticeKind"] == "message"
        assert payload["frontstageDelivery"]["displayText"].startswith("[ok] 前台状态总体正常")
        assert payload["artifact"] is None
        assert payload["artifactNotice"] is None
        assert payload["delivery"]["artifactRef"] is None
        assert payload["delivery"]["artifact"] is None
        assert payload["delivery"]["artifactNotice"] is None
        assert payload["delivery"]["notice"]["artifactRef"] is None
        assert payload["delivery"]["frontstage"]["artifactRef"] is None
        assert payload["delivery"]["metadata"]["messageId"] == payload["response"]["messageId"]
        assert payload["notify"]["targetSessionKey"] == "agent:main:test:frontstage"

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "json",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["action"] == "handle"
        assert payload["requestContractVersion"] == EXPECTED_REQUEST_CONTRACT_VERSION
        assert payload["request"]["format"] == "json"
        assert payload["response"]["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["response"]["output"]["handler"] == "json.stdout.v1"
        assert payload["response"]["output"]["mediaType"] == "application/json"
        assert payload["response"]["delivery"]["mode"] == "none"

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "image",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        image_output = payload["response"]["output"]
        assert payload["ok"] is True
        assert payload["request"]["format"] == "image"
        assert image_output["format"] == "image"
        assert image_output["handler"] == "image.summary-card.v2"
        assert image_output["mediaType"] == "image/svg+xml"
        assert image_output["artifact"]["ref"] == image_output["artifactRef"]
        assert image_output["artifact"]["fileName"] == image_output["fileName"]
        assert Path(image_output["path"]).exists()
        assert image_output["path"].endswith(".svg")
        assert "snapshot.summary" in Path(image_output["path"]).name
        assert image_output["result"]["cardVersion"] == 3
        assert image_output["result"]["layout"] == "dashboard"
        assert image_output["result"]["badge"] == "正常"
        assert len(image_output["result"]["panels"]) == 3
        assert "健康" in image_output["result"]["panels"][0]["label"]
        assert "任务" in image_output["result"]["panels"][1]["label"]
        assert "恢复" in image_output["result"]["panels"][2]["label"]
        assert image_output["result"]["panels"][0]["tone"] == "health"
        assert image_output["result"]["panels"][1]["tone"] == "supervisor"
        assert image_output["result"]["panels"][2]["tone"] == "recovery"
        assert image_output["result"]["panels"][0]["severity"] == "ok"
        image_svg = Path(image_output["path"]).read_text(encoding="utf-8")
        assert "前台状态总体正常" in image_svg
        assert "健康" in image_svg
        assert "任务" in image_svg

        # --- v3 image card tests ---
        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "image",
            "--image-preset", "summary-card-v3",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        v3_output = payload["response"]["output"]
        assert payload["ok"] is True
        assert v3_output["handler"] == "image.summary-card.v3"
        assert v3_output["mediaType"] == "image/svg+xml"
        assert v3_output["preset"] == "summary-card-v3"
        assert v3_output["artifact"]["ref"] == v3_output["artifactRef"]
        assert Path(v3_output["path"]).exists()
        assert v3_output["result"]["cardVersion"] == 4
        assert v3_output["result"]["layout"] == "dashboard"
        assert v3_output["result"]["badge"] == "正常"
        assert v3_output["result"]["gradientShell"] is True
        assert v3_output["result"]["panelGradients"] is True
        assert v3_output["result"]["statusSparkLine"] is True
        assert len(v3_output["result"]["panels"]) == 3
        assert "checkedAt" in v3_output["result"]["panels"][0]
        assert len(v3_output["result"]["sparklineData"]) == 3
        v3_svg = Path(v3_output["path"]).read_text(encoding="utf-8")
        assert "v3 richer dashboard" in v3_svg
        assert "<defs>" in v3_svg
        assert "linearGradient" in v3_svg
        assert "url(#shellGrad)" in v3_svg
        assert "url(#accentGrad)" in v3_svg
        assert "url(#panelGrad0)" in v3_svg

        # v3 with frontstage delivery
        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "image",
            "--image-preset", "summary-card-v3",
            "--delivery-mode", "frontstage",
            "--session-key", "agent:main:test",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        v3_delivery = payload["response"]["delivery"]
        assert v3_delivery["metadata"]["handler"] == "image.summary-card.v3"
        assert v3_delivery["artifactRef"] == v3_delivery["artifact"]["ref"]
        assert v3_delivery["kind"] == "artifact_notice"

        # backward compat: v2 still works when preset is default or not set
        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "image",
            "--image-preset", "summary-card",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["response"]["output"]["handler"] == "image.summary-card.v2"
        assert payload["response"]["output"]["result"]["cardVersion"] == 3

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "image",
            "--delivery-mode", "frontstage",
            "--session-key", "agent:main:test",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        image_delivery = payload["response"]["delivery"]
        assert payload["ok"] is True
        assert image_delivery["contractVersion"] == 1
        assert image_delivery["mode"] == "frontstage"
        assert image_delivery["kind"] == "artifact_notice"
        assert image_delivery["artifactRef"] == image_delivery["artifact"]["ref"]
        assert image_delivery["artifact"]["format"] == "image"
        assert image_delivery["artifact"]["ref"].startswith("infos-handle:image:")
        assert image_delivery["artifact"]["fileName"].endswith(".svg")
        assert image_delivery["notice"]["contractVersion"] == 1
        assert image_delivery["notice"]["kind"] == "artifact_notice"
        assert image_delivery["notice"]["artifactRef"] == image_delivery["artifact"]["ref"]
        assert image_delivery["notice"]["displayText"] == image_delivery["message"]
        assert image_delivery["frontstage"] == image_delivery["notice"]["frontstage"]
        assert image_delivery["frontstage"]["noticeKind"] == "artifact_notice"
        assert image_delivery["frontstage"]["artifactRef"] == image_delivery["artifact"]["ref"]
        assert image_delivery["frontstage"]["displayText"] == image_delivery["message"]
        assert image_delivery["artifactNotice"]["contractVersion"] == 1
        assert image_delivery["artifactNotice"]["artifactRef"] == image_delivery["artifact"]["ref"]
        assert image_delivery["artifactNotice"]["displayText"] == image_delivery["message"]
        assert image_delivery["artifactNotice"]["fallbackText"] == "[infos-handle] 图片 artifact 已生成。"
        assert image_delivery["artifactNotice"]["delivery"]["artifactRef"] == image_delivery["artifact"]["ref"]
        assert image_delivery["artifactNotice"]["delivery"]["messageId"].startswith("msg::[infos-handle] 已生成图片 artifact：")
        assert image_delivery["metadata"]["handler"] == "image.summary-card.v2"
        assert image_delivery["metadata"]["requestedSessionKey"] == "agent:main:test"
        assert image_delivery["metadata"]["targetSessionKey"] == "agent:main:test:frontstage"
        assert image_delivery["notify"]["targetSessionKey"] == "agent:main:test:frontstage"
        assert image_delivery["notify"]["response"]["messageId"].startswith("msg::[infos-handle] 已生成图片 artifact：")

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "audio",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            "--audio-renderer", str(audio_renderer),
            "--audio-preset", "demo-voice",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        audio_output = payload["response"]["output"]
        assert payload["ok"] is True
        assert payload["request"]["format"] == "audio"
        assert audio_output["format"] == "audio"
        assert audio_output["handler"] == "audio.local-tts.v2"
        assert audio_output["preset"] == "demo-voice"
        assert audio_output["mediaType"] == "audio/mpeg"
        assert audio_output["artifact"]["ref"] == audio_output["artifactRef"]
        assert audio_output["artifact"]["fileName"] == audio_output["fileName"]
        assert Path(audio_output["path"]).exists()
        audio_text = Path(audio_output["path"]).read_text(encoding="utf-8")
        assert audio_text.startswith("FAKE AUDIO | demo-voice | 系统状态汇报：")
        assert "前台状态总体正常" in audio_text
        assert "建议：一切正常，继续工作" in audio_text
        assert "系统状态汇报" in audio_output["spokenText"]
        assert "前台状态总体正常" in audio_output["spokenText"]
        assert "建议：一切正常，继续工作" in audio_output["spokenText"]
        assert audio_output["summary"] == "前台状态总体正常"
        assert audio_output["result"]["textPlanVersion"] == 3
        assert audio_output["result"]["strategy"] == "stable_lines_v3"
        assert audio_output["result"]["connectorStyle"] == "natural_transitions"
        assert audio_output["result"]["segmentCount"] == 3
        assert audio_output["result"]["segments"][0] == "前台状态总体正常。"
        assert "——" in audio_output["result"]["segments"][1]
        assert "——" in audio_output["result"]["segments"][2]
        assert "broker、监工" in audio_output["result"]["segments"][1]
        assert "建议：一切正常，继续工作。" in audio_output["result"]["segments"][2]
        assert audio_output["result"]["preamble"] == "系统状态汇报："
        assert audio_output["result"]["estimatedDurationSeconds"] > 1
        assert audio_output["result"]["sourceKind"] == "snapshot.summary"
        assert audio_output["sourcePath"].endswith("reply.mp3")

        result = run(
            "handle",
            "--kind", "health.summary",
            "--format", "audio",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            "--audio-renderer", str(audio_renderer),
            "--audio-preset", "demo-voice",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        audio_output = payload["response"]["output"]
        assert payload["ok"] is True
        assert payload["request"]["kind"] == "health.summary"
        assert payload["request"]["format"] == "audio"
        assert "健康检查结果" in audio_output["spokenText"]
        assert "健康正常" in audio_output["spokenText"]
        assert "建议：继续观察网络与 Gateway" in audio_output["spokenText"]
        assert audio_output["summary"] == "健康正常"
        assert audio_output["result"]["segmentCount"] == 3
        assert audio_output["result"]["segments"][0] == "健康正常。"
        assert "——" in audio_output["result"]["segments"][1]
        assert "——" in audio_output["result"]["segments"][2]
        assert audio_output["result"]["preamble"] == "健康检查结果："
        assert audio_output["result"]["sourceKind"] == "health.summary"
        health_audio_text = Path(audio_output["path"]).read_text(encoding="utf-8")
        assert "建议：继续观察网络与 Gateway。" in health_audio_text
        assert "若出现异常，再检查 broker 视图。" not in health_audio_text

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "audio",
            "--delivery-mode", "frontstage",
            "--session-key", "agent:main:test",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            "--audio-renderer", str(audio_renderer),
            "--audio-preset", "demo-voice",
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        audio_delivery = payload["response"]["delivery"]
        assert payload["ok"] is True
        assert audio_delivery["contractVersion"] == 1
        assert audio_delivery["mode"] == "frontstage"
        assert audio_delivery["kind"] == "artifact_notice"
        assert audio_delivery["artifactRef"] == audio_delivery["artifact"]["ref"]
        assert audio_delivery["artifact"]["format"] == "audio"
        assert audio_delivery["artifact"]["ref"].startswith("infos-handle:audio:")
        assert audio_delivery["artifact"]["fileName"].endswith(".mp3")
        assert audio_delivery["notice"]["contractVersion"] == 1
        assert audio_delivery["notice"]["kind"] == "artifact_notice"
        assert audio_delivery["notice"]["artifactRef"] == audio_delivery["artifact"]["ref"]
        assert audio_delivery["notice"]["displayText"] == audio_delivery["message"]
        assert audio_delivery["frontstage"] == audio_delivery["notice"]["frontstage"]
        assert audio_delivery["frontstage"]["noticeKind"] == "artifact_notice"
        assert audio_delivery["frontstage"]["artifactRef"] == audio_delivery["artifact"]["ref"]
        assert audio_delivery["frontstage"]["displayText"] == audio_delivery["message"]
        assert audio_delivery["artifactNotice"]["contractVersion"] == 1
        assert audio_delivery["artifactNotice"]["artifactRef"] == audio_delivery["artifact"]["ref"]
        assert audio_delivery["artifactNotice"]["displayText"] == audio_delivery["message"]
        assert audio_delivery["artifactNotice"]["fallbackText"] == "[infos-handle] 音频 artifact 已生成。"
        assert audio_delivery["artifactNotice"]["delivery"]["artifactRef"] == audio_delivery["artifact"]["ref"]
        assert audio_delivery["artifactNotice"]["delivery"]["messageId"].startswith("msg::[infos-handle] 已生成音频 artifact：")
        assert audio_delivery["metadata"]["handler"] == "audio.local-tts.v2"
        assert audio_delivery["metadata"]["requestedSessionKey"] == "agent:main:test"
        assert audio_delivery["metadata"]["targetSessionKey"] == "agent:main:test:frontstage"
        assert audio_delivery["notify"]["targetSessionKey"] == "agent:main:test:frontstage"
        assert audio_delivery["notify"]["response"]["messageId"].startswith("msg::[infos-handle] 已生成音频 artifact：")

        result = run(
            "handle",
            "--message", "把 artifact notice 也收进 broker 数据层。",
            "--format", "image",
            "--delivery-mode", "frontstage",
            "--session-key", "agent:main:test",
            "--source", "local-health",
            "--event-key", "artifact-image-1",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            "--broker-state-dir", str(broker_state_dir),
            "--broker-data-dir", str(broker_data_dir),
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        broker_delivery = payload["response"]["delivery"]
        broker_notify = broker_delivery["notify"]["broker"]
        broker_events_path = Path(broker_notify["delivery"]["paths"]["events"])
        broker_events = [json.loads(line) for line in broker_events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert payload["request"]["brokerStateDir"] == str(broker_state_dir.resolve())
        assert payload["request"]["brokerDataDir"] == str(broker_data_dir.resolve())
        assert broker_delivery["artifactNotice"]["artifactRef"] == broker_delivery["artifact"]["ref"]
        assert broker_notify["ingest"]["paths"]["events"] == str(broker_events_path)
        assert broker_notify["delivery"]["paths"]["events"] == str(broker_events_path)
        assert len(broker_events) == 2
        assert broker_events[0]["recordType"] == "broker.source.event"
        assert broker_events[0]["data"]["artifactNotice"]["artifactRef"] == broker_delivery["artifact"]["ref"]
        assert broker_events[0]["data"]["artifactNotice"]["displayText"] == broker_delivery["message"]
        assert broker_events[0]["data"]["deliveryNotice"]["artifactRef"] == broker_delivery["artifact"]["ref"]
        assert broker_events[0]["data"]["deliveryNotice"]["frontstage"]["requestedSessionKey"] == "agent:main:test"
        assert broker_events[0]["data"]["frontstageDelivery"]["frontstageEventKey"] == "artifact-image-1"
        assert broker_events[1]["recordType"] == "frontstage.delivery.sent"
        assert broker_events[1]["eventKey"] == "artifact-image-1"
        assert broker_events[1]["message"] == broker_delivery["message"]

        result = run(
            "handle",
            "--request-json", json.dumps({
                "kind": "events.recent",
                "format": "image",
                "limit": 2,
                "snapshotPath": str(snapshot_path),
                "eventsPath": str(events_path),
                "outputRoot": str(output_root),
            }, ensure_ascii=False),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["request"]["limit"] == 2
        assert payload["response"]["kind"] == "events.recent"
        assert payload["response"]["output"]["handler"] == "image.summary-card.v2"
        assert Path(payload["response"]["output"]["path"]).exists()

        request_file = tmp_path / "handle-request.json"
        request_file.write_text(json.dumps({
            "requestId": "test-handle-request-file",
            "message": "文件入口也能直发前台。",
            "format": "text",
            "deliveryMode": "frontstage",
            "sessionKey": "agent:main:test",
        }, ensure_ascii=False), encoding="utf-8")
        result = run(
            "handle",
            "--request-file", str(request_file),
            env=fake_frontstage_env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        text_delivery = payload["response"]["delivery"]
        assert payload["ok"] is True
        assert payload["requestId"] == "test-handle-request-file"
        assert payload["requestInputMode"] == "request_file"
        assert payload["responseOutputMode"] == "stdout"
        assert payload["request"]["requestId"] == "test-handle-request-file"
        assert payload["request"]["message"] == "文件入口也能直发前台。"
        assert text_delivery["contractVersion"] == 1
        assert text_delivery["kind"] == "message"
        assert text_delivery["message"] == "文件入口也能直发前台。"
        assert text_delivery["artifactRef"] is None
        assert text_delivery["artifact"] is None
        assert text_delivery["artifactNotice"] is None
        assert text_delivery["notice"]["kind"] == "message"
        assert text_delivery["notice"]["displayText"] == "文件入口也能直发前台。"
        assert text_delivery["notice"]["artifactRef"] is None
        assert text_delivery["frontstage"] == text_delivery["notice"]["frontstage"]
        assert text_delivery["frontstage"]["noticeKind"] == "message"
        assert text_delivery["frontstage"]["artifactRef"] is None
        assert text_delivery["frontstage"]["displayText"] == "文件入口也能直发前台。"
        assert text_delivery["metadata"]["messageId"] == text_delivery["notify"]["response"]["messageId"]
        assert text_delivery["metadata"]["targetSessionKey"] == "agent:main:test:frontstage"

        result = run(
            "handle",
            "--request-file", "-",
            env=fake_frontstage_env,
            input_text=json.dumps({
                "requestId": "test-handle-request-stdin",
                "message": "stdin 入口也能复用统一请求。",
                "format": "text",
                "deliveryMode": "frontstage",
                "sessionKey": "agent:main:test",
            }, ensure_ascii=False),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["requestId"] == "test-handle-request-stdin"
        assert payload["requestInputMode"] == "request_file"
        assert payload["responseOutputMode"] == "stdout"
        assert payload["request"]["requestId"] == "test-handle-request-stdin"
        assert payload["request"]["message"] == "stdin 入口也能复用统一请求。"
        assert payload["response"]["delivery"]["frontstage"]["displayText"] == "stdin 入口也能复用统一请求。"

        response_file = tmp_path / "handle-response.json"
        result = run(
            "handle",
            "--request-id", "test-handle-response-file",
            "--kind", "contract.catalog",
            "--format", "json",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--response-file", str(response_file),
        )
        assert result.returncode == 0, result.stderr
        assert (result.stdout or "").strip() == ""
        payload = json.loads(response_file.read_text(encoding="utf-8"))
        assert payload["ok"] is True
        assert payload["requestId"] == "test-handle-response-file"
        assert payload["requestInputMode"] == "flags"
        assert payload["responseOutputMode"] == "response_file"
        assert payload["request"]["requestId"] == "test-handle-response-file"
        assert payload["response"]["kind"] == "contract.catalog"
        assert payload["response"]["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION

        result = run(
            "handle",
            "--message", "直接走统一入口的前台摘要。",
            "--format", "image",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["ok"] is True
        assert payload["request"]["kind"] is None
        assert payload["request"]["message"] == "直接走统一入口的前台摘要。"
        assert payload["response"]["kind"] == "direct.message"
        assert payload["response"]["result"] == {
            "message": "直接走统一入口的前台摘要。",
            "messageSource": "direct",
        }
        assert payload["response"]["output"]["handler"] == "image.summary-card.v2"
        assert Path(payload["response"]["output"]["path"]).exists()

        result = run(
            "handle",
            "--kind", "snapshot.summary",
            "--format", "audio",
            "--snapshot-path", str(snapshot_path),
            "--events-path", str(events_path),
            "--output-root", str(output_root),
            "--audio-renderer", str(tmp_path / "missing-audio-renderer.sh"),
        )
        assert result.returncode != 0
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert "audio renderer not found" in payload["error"]
        assert payload["request"]["format"] == "audio"

        result = run("query", "--kind", "source.inspect", "--source-name", "local-health", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "source=local-health" in result.stdout
        assert "exists=true" in result.stdout
        assert "hasContract=true｜hasState=true｜hasDelivery=true｜recentEvents=2｜recentDeliveries=1" in result.stdout
        assert "latestRecord: frontstage.delivery.sent @ 2026-05-15T12:00:01+08:00" in result.stdout
        assert "latestState: 健康正常" in result.stdout
        assert "- [broker.source.event] 2026-05-15T12:00:00+08:00｜健康正常" in result.stdout

        result = run("query", "--kind", "source.inspect", "--source-name", "missing-source", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["sourceName"] == "missing-source"
        assert payload["result"]["source"] == "missing-source"
        assert payload["result"]["exists"] is False
        assert payload["result"]["availableSources"] == ["frontstage-recovery", "local-health", "supervisor"]
        assert payload["result"]["sourceEventType"] is None
        assert payload["result"]["sourceView"] is None
        assert payload["result"]["hasContract"] is False
        assert payload["result"]["hasSourceState"] is False
        assert payload["result"]["hasDelivery"] is False
        assert payload["result"]["recentEventCount"] == 0
        assert payload["result"]["recentDeliveryCount"] == 0
        assert payload["result"]["latestEventAt"] is None
        assert payload["result"]["latestRecordType"] is None
        assert payload["result"]["latestEventSummary"] is None
        assert payload["result"]["latestEventKey"] is None
        assert payload["result"]["latestSourceStateSummary"] is None
        assert payload["result"]["latestSourceStateRecordedAt"] is None
        assert payload["result"]["latestDeliveryMessage"] is None
        assert payload["result"]["latestDeliveryEventKey"] is None
        assert payload["result"]["latestDeliveryRecordType"] is None
        assert payload["result"]["latestDeliverySentAt"] is None
        assert payload["result"]["latestDeliveryItem"] == {}
        assert payload["result"]["contract"] == {}
        assert payload["result"]["latestEventItem"] == {}
        assert payload["result"]["latestSourceState"] == {}
        assert payload["result"]["latestDelivery"] == {}
        assert payload["result"]["recentEventItems"] == []
        assert payload["result"]["recentDeliveryItems"] == []
        assert payload["result"]["recentEvents"] == []

        result = run("query", "--kind", "source.inspect", "--source-name", "missing-source", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "source=missing-source" in result.stdout
        assert "exists=false" in result.stdout
        assert "availableSources: frontstage-recovery, local-health, supervisor" in result.stdout

        result = run("query", "--kind", "source.inspect", "--source-name", "frontstage-recovery", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["result"]["source"] == "frontstage-recovery"
        assert payload["result"]["exists"] is True
        assert payload["result"]["recentEventCount"] == 0
        assert payload["result"]["recentDeliveryCount"] == 0
        assert payload["result"]["latestEventAt"] == "2026-05-15T12:00:02+08:00"
        assert payload["result"]["latestRecordType"] == "broker.source.latest"
        assert payload["result"]["latestEventSummary"] == "前台投影稳定"
        assert payload["result"]["latestEventKey"] == "recovery-ok-1"
        assert payload["result"]["latestEventItem"]["summary"] == "前台投影稳定"
        assert payload["result"]["latestEventItem"]["detail"] == "未发现明显异常。"
        assert payload["result"]["latestEventItem"]["reportStatus"] == "recovered"
        assert payload["result"]["latestSourceStateSummary"] == "前台投影稳定"
        assert payload["result"]["latestSourceStateRecordedAt"] == "2026-05-15T12:00:02+08:00"
        assert payload["result"]["latestDeliveryMessage"] is None
        assert payload["result"]["latestDeliveryEventKey"] is None
        assert payload["result"]["latestDeliveryRecordType"] is None
        assert payload["result"]["latestDeliverySentAt"] is None
        assert payload["result"]["latestDeliveryItem"] == {}
        assert payload["result"]["recentDeliveryItems"] == []

        result = run("query", "--kind", "sources.catalog", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "local-health｜view=health｜eventType=local_health.status.changed｜hasState=true｜hasDelivery=true" in result.stdout

        result = run("query", "--kind", "panel.inspect", "--panel-name", "health", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "panel=health" in result.stdout
        assert "exists=true" in result.stdout
        assert "summary: 健康正常" in result.stdout
        assert "checkedAt: 2026-05-15T12:00:00+08:00" in result.stdout

        result = run("query", "--kind", "panels.catalog", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "health｜available=true｜severity=unknown｜summary=健康正常｜checkedAt=2026-05-15T12:00:00+08:00" in result.stdout
        assert "supervisor｜available=true｜severity=unknown｜summary=监工待命中｜checkedAt=2026-05-15T12:00:01+08:00" in result.stdout

        result = run("query", "--kind", "panel.inspect", "--panel-name", "missing-panel", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == EXPECTED_QUERY_CONTRACT_VERSION
        assert payload["panelName"] == "missing-panel"
        assert payload["result"]["panelName"] == "missing-panel"
        assert payload["result"]["exists"] is False
        assert payload["result"]["availablePanels"] == ["health", "recovery", "supervisor"]
        assert payload["result"]["summary"] is None
        assert payload["result"]["detail"] is None
        assert payload["result"]["severity"] is None
        assert payload["result"]["checkedAt"] is None
        assert payload["result"]["panel"] == {}

        result = run("query", "--kind", "panel.inspect", "--panel-name", "missing-panel", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "panel=missing-panel" in result.stdout
        assert "exists=false" in result.stdout
        assert "availablePanels: health, recovery, supervisor" in result.stdout

        sidecar_port = pick_free_port()
        sidecar_process = subprocess.Popen(
            [
                "python3",
                str(SIDECAR_SCRIPT),
                "--host",
                "127.0.0.1",
                "--port",
                str(sidecar_port),
                "--snapshot-path",
                str(snapshot_path),
                "--events-path",
                str(events_path),
                "--output-root",
                str(output_root),
            ],
            cwd=WORKSPACE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            wait_for_sidecar(f"http://127.0.0.1:{sidecar_port}/healthz")
            healthz_payload = fetch_json(f"http://127.0.0.1:{sidecar_port}/healthz")
            assert healthz_payload["artifactRoutePrefix"] == "/v1/artifacts"
            assert isinstance(healthz_payload.get("sseConnections"), int)
            assert healthz_payload["sseConnections"] >= 0

            # verify REQUEST_ENTITY_TOO_LARGE for oversized body
            oversize_req = urllib.request.Request(
                f"http://127.0.0.1:{sidecar_port}/v1/handle",
                data=b"{\"x\":\"" + b"y" * (512 * 1024) + b"\"}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(oversize_req, timeout=5)
                raise AssertionError("oversized body should have returned 413")
            except urllib.error.HTTPError as exc:
                assert exc.code == 413, f"expected 413, got {exc.code}"
                oversize_body = json.loads(exc.read().decode("utf-8"))
                assert oversize_body.get("error") is not None

            snapshot_summary = fetch_json(f"http://127.0.0.1:{sidecar_port}/v1/query/snapshot.summary?format=json")
            assert snapshot_summary["kind"] == "snapshot.summary"
            assert snapshot_summary["result"]["summary"] == "前台状态总体正常"
            contract_catalog = fetch_json(f"http://127.0.0.1:{sidecar_port}/v1/query/contract.catalog?format=json")
            assert contract_catalog["kind"] == "contract.catalog"
            assert contract_catalog["result"]["requestCatalog"]["requestContractVersion"] == EXPECTED_REQUEST_CONTRACT_VERSION
            request = urllib.request.Request(
                f"http://127.0.0.1:{sidecar_port}/v1/handle",
                data=json.dumps({"kind": "snapshot.summary", "format": "json"}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                handle_payload = json.loads(response.read().decode("utf-8"))
            assert handle_payload["ok"] is True
            assert handle_payload["response"]["kind"] == "snapshot.summary"
            assert handle_payload["response"]["output"]["handler"] == "json.stdout.v1"

            image_request = urllib.request.Request(
                f"http://127.0.0.1:{sidecar_port}/v1/handle",
                data=json.dumps({"kind": "snapshot.summary", "format": "image"}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(image_request, timeout=5) as response:
                image_payload = json.loads(response.read().decode("utf-8"))
            image_output = image_payload["response"]["output"]
            image_href = image_output["artifactHref"]
            assert image_href.startswith("/v1/artifacts/")
            assert image_output["artifact"]["href"] == image_href
            with urllib.request.urlopen(f"http://127.0.0.1:{sidecar_port}{image_href}", timeout=5) as response:
                image_body = response.read().decode("utf-8")
                image_content_type = response.headers.get_content_type()
            assert image_content_type == "image/svg+xml"
            assert "<svg" in image_body

            # v3 image via sidecar
            v3_image_request = urllib.request.Request(
                f"http://127.0.0.1:{sidecar_port}/v1/handle",
                data=json.dumps({"kind": "snapshot.summary", "format": "image", "imagePreset": "summary-card-v3"}, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(v3_image_request, timeout=5) as response:
                v3_payload = json.loads(response.read().decode("utf-8"))
            v3_output = v3_payload["response"]["output"]
            assert v3_output["handler"] == "image.summary-card.v3"
            assert v3_output["result"]["cardVersion"] == 4
            v3_href = v3_output["artifactHref"]
            with urllib.request.urlopen(f"http://127.0.0.1:{sidecar_port}{v3_href}", timeout=5) as response:
                v3_body = response.read().decode("utf-8")
                v3_content_type = response.headers.get_content_type()
            assert v3_content_type == "image/svg+xml"
            assert "v3 richer dashboard" in v3_body
            assert "linearGradient" in v3_body

            audio_request = urllib.request.Request(
                f"http://127.0.0.1:{sidecar_port}/v1/handle",
                data=json.dumps(
                    {
                        "kind": "snapshot.summary",
                        "format": "audio",
                        "audioRenderer": str(audio_renderer),
                        "audioPreset": "demo-voice",
                    },
                    ensure_ascii=False,
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(audio_request, timeout=10) as response:
                audio_payload = json.loads(response.read().decode("utf-8"))
            audio_output = audio_payload["response"]["output"]
            audio_href = audio_output["artifactHref"]
            assert audio_href.startswith("/v1/artifacts/")
            assert audio_output["artifact"]["href"] == audio_href
            with urllib.request.urlopen(f"http://127.0.0.1:{sidecar_port}{audio_href}?download=1", timeout=5) as response:
                audio_body = response.read().decode("utf-8")
                audio_content_type = response.headers.get_content_type()
                audio_disposition = response.headers.get("Content-Disposition")
            assert audio_content_type == "audio/mpeg"
            assert audio_disposition is not None and audio_disposition.startswith("attachment;")
            assert audio_body.startswith("FAKE AUDIO | demo-voice | 系统状态汇报：")

            with urllib.request.urlopen(
                f"http://127.0.0.1:{sidecar_port}/v1/events/stream?kind=snapshot.summary&intervalMs=1000",
                timeout=5,
            ) as response:
                stream_chunk = "".join(response.readline().decode("utf-8") for _ in range(4))
            assert "event: snapshot" in stream_chunk
            assert "前台状态总体正常" in stream_chunk
        finally:
            sidecar_process.terminate()
            try:
                sidecar_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sidecar_process.kill()
                sidecar_process.wait(timeout=5)

        print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
