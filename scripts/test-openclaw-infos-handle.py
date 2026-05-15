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
                    "eventKey": "health-ok-1",
                },
                "frontstage-recovery": {
                    "summary": "前台投影稳定",
                    "eventKey": "recovery-ok-1",
                },
            },
            "sources": {
                "supervisor": {
                    "message": "[监工] 后台任务已完成。",
                    "eventKey": "done-1",
                },
                "local-health": {
                    "message": "[本地健康] 当前已恢复正常。",
                    "eventKey": "health-delivery-1",
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
                        "recordedAt": "2026-05-15T12:00:00+08:00",
                        "message": "本地健康状态已记录",
                    }, ensure_ascii=False),
                    json.dumps({
                        "recordType": "frontstage.delivery.sent",
                        "source": "supervisor",
                        "recordedAt": "2026-05-15T12:00:03+08:00",
                        "message": "[监工] 后台任务已完成。",
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
        assert payload["queryContractVersion"] == 4
        assert len(payload["events"]) == 2
        assert len(payload["result"]["events"]) == 2
        assert payload["events"][0]["source"] == "supervisor"

        result = run("query", "--kind", "sources.latest", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["result"]["sourceStateSnapshots"]["local-health"]["summary"] == "健康正常"
        assert payload["result"]["sources"]["supervisor"]["message"] == "[监工] 后台任务已完成。"

        result = run("query", "--kind", "sources.catalog", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
        assert payload["result"]["count"] == 3
        source_rows = {item["source"]: item for item in payload["result"]["sources"]}
        assert source_rows["local-health"]["sourceView"] == "health"
        assert source_rows["local-health"]["hasSourceState"] is True
        assert source_rows["supervisor"]["hasDelivery"] is True
        assert source_rows["frontstage-recovery"]["hasDelivery"] is False

        result = run("query", "--kind", "source.inspect", "--source-name", "local-health", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
        assert payload["sourceName"] == "local-health"
        assert payload["result"]["source"] == "local-health"
        assert payload["result"]["exists"] is True
        assert payload["result"]["availableSources"] == ["frontstage-recovery", "local-health", "supervisor"]
        assert payload["result"]["sourceEventType"] == "local_health.status.changed"
        assert payload["result"]["sourceView"] == "health"
        assert payload["result"]["hasContract"] is True
        assert payload["result"]["hasSourceState"] is True
        assert payload["result"]["hasDelivery"] is True
        assert payload["result"]["recentEventCount"] == 1
        assert payload["result"]["contract"]["sourceView"] == "health"
        assert payload["result"]["latestSourceState"]["summary"] == "健康正常"
        assert payload["result"]["latestDelivery"]["message"] == "[本地健康] 当前已恢复正常。"
        assert len(payload["result"]["recentEvents"]) == 1

        result = run("query", "--kind", "panel.inspect", "--panel-name", "health", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
        assert payload["panelName"] == "health"
        assert payload["result"]["panelName"] == "health"
        assert payload["result"]["exists"] is True
        assert payload["result"]["summary"] == "健康正常"
        assert payload["result"]["detail"] == "当前网络和 Gateway 可达。"
        assert payload["result"]["severity"] is None
        assert payload["result"]["checkedAt"] == "2026-05-15T12:00:00+08:00"
        assert payload["result"]["panel"]["summary"] == "健康正常"
        assert payload["result"]["availablePanels"] == ["health", "recovery", "supervisor"]

        result = run("query", "--kind", "contract.catalog", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
        assert payload["result"]["brokerContractVersion"] == 2
        assert payload["result"]["snapshotContract"]["primaryView"] == "snapshot"
        assert payload["result"]["contracts"]["sources"]["supervisor"]["sourceView"] == "tasks"
        assert payload["result"]["queryCatalog"]["defaultLimit"] == 6
        assert payload["result"]["queryCatalog"]["responseEnvelope"]["panelName"] == "str|null"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["requiredArgs"] == ["source_name"]
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["exists"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["source.inspect"]["resultShape"]["recentEventCount"] == "int"
        assert payload["result"]["queryCatalog"]["queries"]["sources.catalog"]["formats"] == ["text", "json"]
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["requiredArgs"] == ["panel_name"]
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["resultShape"]["exists"] == "bool"
        assert payload["result"]["queryCatalog"]["queries"]["panel.inspect"]["resultShape"]["checkedAt"] == "str|null"
        assert payload["result"]["paths"]["snapshotPath"] == str(snapshot_path)

        result = run("query", "--kind", "source.inspect", "--source-name", "local-health", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "source=local-health" in result.stdout
        assert "exists=true" in result.stdout
        assert "hasContract=true｜hasState=true｜hasDelivery=true｜recentEvents=1" in result.stdout
        assert "latestState: 健康正常" in result.stdout

        result = run("query", "--kind", "source.inspect", "--source-name", "missing-source", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
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
        assert payload["result"]["contract"] == {}
        assert payload["result"]["latestSourceState"] == {}
        assert payload["result"]["latestDelivery"] == {}
        assert payload["result"]["recentEvents"] == []

        result = run("query", "--kind", "source.inspect", "--source-name", "missing-source", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "source=missing-source" in result.stdout
        assert "exists=false" in result.stdout
        assert "availableSources: frontstage-recovery, local-health, supervisor" in result.stdout

        result = run("query", "--kind", "sources.catalog", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "local-health｜view=health｜eventType=local_health.status.changed｜hasState=true｜hasDelivery=true" in result.stdout

        result = run("query", "--kind", "panel.inspect", "--panel-name", "health", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        assert "panel=health" in result.stdout
        assert "exists=true" in result.stdout
        assert "summary: 健康正常" in result.stdout
        assert "checkedAt: 2026-05-15T12:00:00+08:00" in result.stdout

        result = run("query", "--kind", "panel.inspect", "--panel-name", "missing-panel", "--format", "json", "--snapshot-path", str(snapshot_path), "--events-path", str(events_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["queryContractVersion"] == 4
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
