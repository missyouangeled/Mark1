#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "scripts" / "openclaw-infos-handle.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([
        "python3",
        str(SCRIPT),
        *args,
    ], cwd=WORKSPACE, capture_output=True, text=True, check=False)


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
        assert payload["queryContractVersion"] == 11
        assert len(payload["events"]) == 3
        assert len(payload["result"]["events"]) == 3
        assert payload["events"][0]["source"] == "supervisor"

        result = run("query", "--kind", "sources.latest", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
        assert payload["result"]["brokerContractVersion"] == 2
        assert payload["result"]["snapshotContract"]["primaryView"] == "snapshot"
        assert payload["result"]["contracts"]["sources"]["supervisor"]["sourceView"] == "tasks"
        assert payload["result"]["queryCatalog"]["defaultLimit"] == 6
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["panelName"] == "str|null"
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
        assert payload["queryContractVersion"] == 11
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
        assert payload["queryContractVersion"] == 11
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

        print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
