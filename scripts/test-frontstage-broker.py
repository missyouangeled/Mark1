#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = Path(__file__).with_name("openclaw-frontstage-broker.py")


def load_module():
    spec = importlib.util.spec_from_file_location("frontstage_broker", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    previous_package_root = os.environ.get("OPENCLAW_PACKAGE_ROOT")
    previous_canvas_dir = os.environ.get("OPENCLAW_FRONTSTAGE_STATUS_CANVAS_DIR")

    with tempfile.TemporaryDirectory(prefix="frontstage-broker-test-") as tmp:
        tmp_path = Path(tmp)
        package_root = tmp_path / "package-root"
        dist_root = package_root / "dist" / "control-ui"
        dist_root.mkdir(parents=True, exist_ok=True)
        canvas_dir = tmp_path / "canvas" / "frontstage-status"

        os.environ["OPENCLAW_PACKAGE_ROOT"] = str(package_root)
        os.environ["OPENCLAW_FRONTSTAGE_STATUS_CANVAS_DIR"] = str(canvas_dir)

        mod = load_module()

        state_path = tmp_path / "frontstage" / "broker-state.json"
        broker_data_dir = tmp_path / "broker"

        handle_calls: list[list[str]] = []

        def fake_run(cmd, capture_output, text, check, input=None):
            handle_calls.append(cmd)
            assert cmd[1].endswith("openclaw-infos-handle.py"), cmd
            assert cmd[2] == "handle", cmd
            assert "--request-file" in cmd, cmd
            assert cmd[cmd.index("--request-file") + 1] == "-", cmd
            request_payload = json.loads(input)
            assert request_payload == {
                "requestId": (
                    "broker.emit:local-health:health-1"
                    if len(handle_calls) < 3
                    else "broker.emit:frontstage-recovery:recovery-1"
                ),
                "message": "健康恢复" if len(handle_calls) < 3 else "前台恢复观察",
                "format": "text",
                "sessionKey": "agent:main:main",
                "deliveryMode": "frontstage",
                "frontstageSource": "local-health" if len(handle_calls) < 3 else "frontstage-recovery",
                "frontstageEventKey": "health-1" if len(handle_calls) < 3 else "recovery-1",
                "brokerStateDir": str(state_path.parent.resolve()),
                "brokerDataDir": str(broker_data_dir.resolve()),
            }, request_payload
            message = request_payload["message"]
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "ok": True,
                        "action": "handle",
                        "requestId": request_payload["requestId"],
                        "requestInputMode": "request_file",
                        "responseOutputMode": "stdout",
                        "response": {
                            "delivery": {
                                "mode": "frontstage",
                                "kind": "message",
                                "status": "sent",
                                "message": message,
                                "notice": {
                                    "kind": "message",
                                    "displayText": message,
                                    "frontstage": {
                                        "targetSessionKey": "agent:main:dashboard:test",
                                        "messageId": f"msg-{message}",
                                    },
                                },
                                "frontstage": {
                                    "targetSessionKey": "agent:main:dashboard:test",
                                    "messageId": f"msg-{message}",
                                },
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                stderr="",
            )

        mod.subprocess.run = fake_run

        ingested = mod.ingest_event(
            "local-health",
            "health-source-1",
            "agent:main:main",
            "本地健康状态已记录",
            state_path,
            broker_data_dir,
            data={"severity": "ok", "summary": "健康正常"},
        )
        assert ingested["ok"] is True and ingested["skipped"] is False
        assert ingested["recordType"] == "broker.source.event"

        first = mod.emit_event(
            "local-health",
            "health-1",
            "agent:main:main",
            "健康恢复",
            state_path,
            broker_data_dir,
        )
        assert first["ok"] is True and first["skipped"] is False
        assert first["compatibilityMode"] == "legacy_emit"
        assert first["transport"] == "infos_handle_handle"
        assert first["delivery"]["mode"] == "frontstage"
        assert first["notice"]["kind"] == "message"
        assert first["deliveryNotice"]["kind"] == "message"
        assert first["frontstage"]["targetSessionKey"] == "agent:main:dashboard:test"
        assert first["frontstageDelivery"]["targetSessionKey"] == "agent:main:dashboard:test"
        assert first["artifact"] is None
        assert first["artifactNotice"] is None
        assert first["delivery"]["artifactRef"] is None
        assert first["delivery"]["artifact"] is None
        assert first["delivery"]["artifactNotice"] is None
        assert first["delivery"]["notice"]["artifactRef"] is None
        assert first["delivery"]["frontstage"]["artifactRef"] is None
        assert first["delivery"]["metadata"]["messageId"] == "msg-健康恢复"
        assert first["notify"]["targetSessionKey"] == "agent:main:dashboard:test"
        assert first["delivery"]["notify"]["targetSessionKey"] == "agent:main:dashboard:test"
        assert first["delivery"]["notify"]["response"]["messageId"] == "msg-健康恢复"

        second = mod.emit_event(
            "local-health",
            "health-1",
            "agent:main:main",
            "健康恢复",
            state_path,
            broker_data_dir,
        )
        assert second["ok"] is True and second["skipped"] is True
        assert second["compatibilityMode"] == "legacy_emit"
        assert second["transport"] == "infos_handle_handle"
        assert second["frontstageDelivery"]["messageId"] == "msg-健康恢复"
        assert second["notify"]["response"]["messageId"] == "msg-健康恢复"
        assert second["artifact"] is None
        assert second["artifactNotice"] is None
        assert second["delivery"]["status"] == "skipped"

        legacy_state_path = tmp_path / "legacy-frontstage" / "broker-state.json"
        legacy_broker_data_dir = tmp_path / "legacy-broker"
        mod.emit_frontstage = lambda session_key, outgoing_message: {
            "ok": True,
            "targetSessionKey": f"{session_key}:legacy-frontstage",
            "response": {"messageId": f"legacy-msg::{outgoing_message}"},
        }
        legacy_emit = mod.emit_compatibility_event(
            "legacy-source",
            "legacy-health-1",
            "agent:main:main",
            "兼容壳前台消息",
            legacy_state_path,
            legacy_broker_data_dir,
        )
        assert legacy_emit["transport"] == "legacy_broker_emit"
        assert legacy_emit["frontstageDelivery"]["targetSessionKey"] == "agent:main:main:legacy-frontstage"
        assert legacy_emit["notify"]["response"]["messageId"] == "legacy-msg::兼容壳前台消息"
        assert legacy_emit["deliveryNotice"] is None
        assert legacy_emit["artifact"] is None
        assert legacy_emit["artifactNotice"] is None
        assert legacy_emit["delivery"]["artifactRef"] is None
        assert legacy_emit["delivery"]["artifact"] is None
        assert legacy_emit["delivery"]["artifactNotice"] is None
        assert legacy_emit["delivery"]["notify"]["response"]["messageId"] == "legacy-msg::兼容壳前台消息"
        assert legacy_emit["delivery"]["metadata"]["messageId"] == "legacy-msg::兼容壳前台消息"
        assert legacy_emit["delivery"]["frontstage"]["messageId"] == "legacy-msg::兼容壳前台消息"

        third = mod.emit_event(
            "frontstage-recovery",
            "recovery-1",
            "agent:main:main",
            "前台恢复观察",
            state_path,
            broker_data_dir,
        )
        assert third["ok"] is True and third["skipped"] is False
        assert third["transport"] == "infos_handle_handle"
        assert len(handle_calls) == 3

        paths = mod.broker_paths(state_path, broker_data_dir)
        with paths["events"].open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "source": "supervisor",
                "eventKey": "legacy-supervisor-1",
                "sessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "messageId": "legacy-msg",
                "message": "旧格式事件",
                "sentAt": "2026-05-14T16:29:00+08:00",
                "recordedAt": "2026-05-14T16:29:00+08:00",
                "deliveryStatus": "sent",
            }, ensure_ascii=False) + "\n")

        events_lines = paths["events"].read_text(encoding="utf-8").strip().splitlines()
        assert len(events_lines) == 4, f"expected 4 total events after legacy append, got {len(events_lines)}"

        (tmp_path / 'local-health').mkdir(parents=True, exist_ok=True)
        (tmp_path / 'supervisor').mkdir(parents=True, exist_ok=True)
        (tmp_path / 'frontstage-recovery').mkdir(parents=True, exist_ok=True)
        (tmp_path / 'local-health' / 'last-report.json').write_text(json.dumps({'summary': '健康正常', 'severity': 'ok', 'issueOverview': '正常', 'checkedAt': '2026-05-14T16:30:00+08:00', 'host': 'test-host', 'selfHelpActions': ['一切正常，继续工作。']}, ensure_ascii=False), encoding='utf-8')
        (tmp_path / 'supervisor' / 'supervisor-status.json').write_text(json.dumps({'status': 'idle', 'summary': '监工待机', 'detail': '当前没有后台任务。', 'updatedAt': '2026-05-14T16:31:00+08:00', 'checkedAt': '2026-05-14T16:31:00+08:00', 'service': {'state': 'armed', 'policyMode': 'auto', 'taskActive': True, 'desiredState': 'armed'}}, ensure_ascii=False), encoding='utf-8')
        (tmp_path / 'frontstage-recovery' / 'last-report.json').write_text(json.dumps({'ok': True, 'detail': '未发现明显异常。', 'checkedAt': '2026-05-14T16:32:00+08:00'}, ensure_ascii=False), encoding='utf-8')
        (tmp_path / 'frontstage-recovery' / 'notify-state.json').write_text(json.dumps({'status': 'recovered', 'anomalyCode': 'assistant_missing_in_history', 'updatedAt': '2026-05-14T16:33:00+08:00'}, ensure_ascii=False), encoding='utf-8')

        rebuilt_paths = mod.build_views(state_path, broker_data_dir)

        migrated_event_records = [json.loads(line) for line in paths["events"].read_text(encoding="utf-8").strip().splitlines()]
        assert len(migrated_event_records) == 4
        assert {item["recordType"] for item in migrated_event_records} == {"broker.source.event", "frontstage.delivery.sent"}
        assert {item["sourceEventType"] for item in migrated_event_records} >= {"local_health.status.changed", "frontstage_recovery.status.changed", "supervisor.status.changed"}
        assert {item["sourceView"] for item in migrated_event_records} >= {"health", "recovery", "tasks"}
        assert Path(rebuilt_paths['frontstageView']).exists()
        assert Path(rebuilt_paths['manifest']).exists()
        assert Path(rebuilt_paths['snapshotView']).exists()
        assert Path(rebuilt_paths['overviewView']).exists()
        assert Path(rebuilt_paths['frontstageStatusCanvasHtml']).exists()
        assert Path(rebuilt_paths['frontstageStatusCanvasJson']).exists()
        assert Path(rebuilt_paths['frontstageSnapshotCanvasJson']).exists()
        assert Path(rebuilt_paths['frontstageStatusHtml']).exists()
        assert Path(rebuilt_paths['frontstageStatusJson']).exists()
        assert Path(rebuilt_paths['frontstageSnapshotJson']).exists()

        frontstage_view = json.loads(paths["frontstageView"].read_text(encoding="utf-8"))
        assert frontstage_view["schemaVersion"] == 1
        assert frontstage_view["contractVersion"] == 2
        assert frontstage_view["contracts"]["sourceEventRecordType"] == "broker.source.event"
        assert frontstage_view["contracts"]["deliveryEventRecordType"] == "frontstage.delivery.sent"
        assert frontstage_view["contracts"]["recordTypes"]["broker.source.event"]["requiredFields"] == ["recordType", "source", "sourceEventType", "sourceView", "eventKey", "sessionKey", "message", "recordedAt"]
        assert frontstage_view["contracts"]["recordTypes"]["frontstage.delivery.sent"]["optionalFields"] == ["schemaVersion", "contractVersion", "targetSessionKey", "messageId", "deliveryStatus"]
        assert frontstage_view["contracts"]["eventFieldCatalog"]["sourceView"]["knownValues"] == ["health", "recovery", "tasks"]
        assert frontstage_view["contracts"]["eventFieldCatalog"]["sentAt"]["type"] == "str|null"
        assert frontstage_view["contracts"]["sources"]["local-health"]["sourceEventType"] == "local_health.status.changed"
        assert "local-health" in frontstage_view["sources"]
        assert "frontstage-recovery" in frontstage_view["sources"]
        assert frontstage_view["sources"]["local-health"]["recordType"] == "frontstage.delivery.latest"
        assert frontstage_view["sources"]["local-health"]["sourceEventType"] == "local_health.status.changed"
        assert frontstage_view["sources"]["frontstage-recovery"]["sourceView"] == "recovery"
        assert frontstage_view["sourceStates"]["local-health"]["recordType"] == "broker.source.latest"
        assert frontstage_view["sourceStates"]["local-health"]["message"] == "本地健康状态已记录"
        assert frontstage_view["updatedAt"] == frontstage_view["freshness"]["rebuiltAt"]
        assert frontstage_view["freshness"]["sources"]["localHealthReport"]["reportTimestamp"] == "2026-05-14T16:30:00+08:00"

        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        assert manifest["schemaVersion"] == 1
        assert manifest["contractVersion"] == 2
        assert manifest["contracts"]["sourceSnapshotRecordType"] == "frontstage.delivery.latest"
        assert manifest["contracts"]["sourceStateSnapshotRecordType"] == "broker.source.latest"
        assert manifest["contracts"]["recordTypes"]["broker.source.latest"]["description"].startswith("Latest ingest-side source snapshot")
        assert manifest["contracts"]["eventFieldCatalog"]["sourceEventType"]["knownValues"] == ["frontstage_recovery.status.changed", "local_health.status.changed", "supervisor.status.changed"]
        assert manifest["snapshotContract"]["primaryView"] == "snapshot"
        assert manifest["snapshotContract"]["primaryPublishedJsonKey"] == "frontstageSnapshotJson"
        assert manifest["snapshotContract"]["compatibilityViewAliases"]["overview"] == "snapshot"
        assert manifest["snapshotContract"]["compatibilityPublishedJsonAliases"]["frontstageStatusJson"] == "frontstageSnapshotJson"
        assert manifest["snapshotContract"]["viewCatalog"]["snapshot"]["role"] == "primary"
        assert manifest["snapshotContract"]["viewCatalog"]["overview"]["role"] == "legacy_alias"
        assert manifest["snapshotContract"]["viewCatalog"]["frontstage"]["role"] == "supporting_view"
        assert manifest["snapshotContract"]["publishedJsonCatalog"]["frontstageSnapshotJson"]["role"] == "primary"
        assert manifest["snapshotContract"]["publishedJsonCatalog"]["frontstageStatusJson"]["role"] == "legacy_alias"
        assert manifest["snapshotContract"]["publishedJsonCatalog"]["frontstageStatusJson"]["canonicalPublishedJsonKey"] == "frontstageSnapshotJson"
        assert manifest["artifacts"]["views"]["snapshot"]["role"] == "primary"
        assert manifest["artifacts"]["views"]["overview"]["role"] == "legacy_alias"
        assert manifest["artifacts"]["views"]["tasks"]["role"] == "supporting_view"
        assert manifest["artifacts"]["publishedJson"]["frontstageSnapshotJson"]["role"] == "primary"
        assert manifest["artifacts"]["publishedJson"]["frontstageStatusJson"]["role"] == "legacy_alias"
        assert manifest["artifacts"]["publishedJson"]["frontstageStatusJson"]["canonicalPublishedJsonKey"] == "frontstageSnapshotJson"
        assert manifest["views"]["frontstage"].endswith("frontstage.json")
        assert manifest["views"]["snapshot"].endswith("snapshot.json")
        assert manifest["views"]["overview"].endswith("overview.json")
        assert manifest["updatedAt"] == manifest["freshness"]["rebuiltAt"]
        assert manifest["freshness"]["sources"]["recoveryNotify"]["reportTimestamp"] == "2026-05-14T16:33:00+08:00"
        assert manifest["publicationMode"] == "best_effort"
        assert manifest["publicationWarnings"] == []
        assert manifest["published"]["frontstageStatusHtml"].endswith("jarvis-frontstage-status.html")
        assert manifest["published"]["frontstageSnapshotJson"].endswith("jarvis-frontstage-snapshot.json")

        health_view = json.loads(paths["healthView"].read_text(encoding="utf-8"))
        assert health_view["report"]["summary"] == "健康正常"
        assert health_view["contracts"]["sources"]["local-health"]["sourceView"] == "health"
        assert health_view["broker"]["eventKey"] == "health-1"
        assert health_view["broker"]["sourceEventType"] == "local_health.status.changed"

        recovery_view = json.loads(paths["recoveryView"].read_text(encoding="utf-8"))
        assert recovery_view["report"]["detail"] == "未发现明显异常。"
        assert recovery_view["broker"]["eventKey"] == "recovery-1"
        assert recovery_view["broker"]["sourceEventType"] == "frontstage_recovery.status.changed"
        assert recovery_view["notify"]["status"] == "recovered"

        tasks_view = json.loads(paths["tasksView"].read_text(encoding="utf-8"))
        assert tasks_view["supervisor"]["report"]["status"] == "idle"
        assert tasks_view["contracts"]["sources"]["supervisor"]["sourceEventType"] == "supervisor.status.changed"
        assert tasks_view["recovery"]["broker"]["eventKey"] == "recovery-1"

        snapshot_view = json.loads(paths["snapshotView"].read_text(encoding="utf-8"))
        assert snapshot_view["recordType"] == "frontstage.snapshot"
        assert snapshot_view["snapshotVersion"] == 1
        assert snapshot_view["severity"] == "ok"
        assert snapshot_view["contractVersion"] == 2
        assert snapshot_view["snapshotContract"]["primaryView"] == "snapshot"
        assert snapshot_view["snapshotContract"]["compatibilityViewAliases"]["overview"] == "snapshot"
        assert snapshot_view["snapshotContract"]["viewCatalog"]["snapshot"]["role"] == "primary"
        assert snapshot_view["snapshotContract"]["viewCatalog"]["overview"]["role"] == "legacy_alias"
        assert snapshot_view["snapshotContract"]["publishedJsonCatalog"]["frontstageStatusJson"]["role"] == "legacy_alias"
        assert snapshot_view["contracts"]["sources"]["frontstage-recovery"]["sourceView"] == "recovery"
        assert snapshot_view["panels"]["frontstage"]["latestDelivery"]["source"] in {"local-health", "frontstage-recovery"}
        assert snapshot_view["panels"]["frontstage"]["latestDelivery"]["sourceEventLabel"] in {"本地健康状态变化", "前台恢复状态变化"}
        assert snapshot_view["panels"]["frontstage"]["latestDelivery"]["sourceViewLabel"] in {"本地健康", "恢复观察"}
        assert {item["source"] for item in snapshot_view["panels"]["frontstage"]["deliveries"]} >= {"local-health", "frontstage-recovery"}
        assert {item["sourceEventType"] for item in snapshot_view["panels"]["frontstage"]["deliveries"]} >= {"local_health.status.changed", "frontstage_recovery.status.changed"}
        assert {item["sourceEventLabel"] for item in snapshot_view["panels"]["frontstage"]["deliveries"]} >= {"本地健康状态变化", "前台恢复状态变化"}
        assert {item["sourceViewLabel"] for item in snapshot_view["panels"]["frontstage"]["deliveries"]} >= {"本地健康", "恢复观察"}
        assert any("frontstage_recovery.status.changed" in (item.get("contractSummary") or "") for item in snapshot_view["panels"]["frontstage"]["deliveries"])
        assert snapshot_view["panels"]["health"]["summary"] == "健康正常"
        assert snapshot_view["panels"]["supervisor"]["summary"] == "监工待命中"
        assert snapshot_view["sourceSnapshots"]["local-health"]["sourceEventType"] == "local_health.status.changed"
        assert snapshot_view["sourceStateSnapshots"]["local-health"]["recordType"] == "broker.source.latest"
        assert snapshot_view["latestSourceState"]["eventKey"] == "health-source-1"

        overview_view = json.loads(paths["overviewView"].read_text(encoding="utf-8"))
        assert overview_view == snapshot_view

        public_status = json.loads(Path(rebuilt_paths['frontstageStatusJson']).read_text(encoding='utf-8'))
        assert public_status["summary"] == "前台状态总体正常"
        assert "broker / 监工 / 恢复观察 / 本地健康" in public_status["issueOverview"]
        assert public_status["snapshotContract"]["publishedJsonCatalog"]["frontstageStatusJson"]["role"] == "legacy_alias"
        assert public_status["panels"]["frontstage"]["latestDelivery"]["sourceEventType"] in {"local_health.status.changed", "frontstage_recovery.status.changed"}

        public_snapshot = json.loads(Path(rebuilt_paths['frontstageSnapshotJson']).read_text(encoding='utf-8'))
        assert public_snapshot["recordType"] == "frontstage.snapshot"
        assert public_snapshot["snapshotContract"]["primaryPublishedJsonKey"] == "frontstageSnapshotJson"
        assert public_snapshot["snapshotContract"]["publishedJsonCatalog"]["frontstageStatusJson"]["canonicalPublishedJsonKey"] == "frontstageSnapshotJson"
        assert public_snapshot["panels"]["health"]["summary"] == "健康正常"

        public_html = Path(rebuilt_paths['frontstageStatusHtml']).read_text(encoding='utf-8')
        assert "前台状态总览" in public_html
        assert "最近辅助投递" in public_html
        assert "frontstage_recovery.status.changed" in public_html
        assert "恢复观察" in public_html
        assert "/jarvis-frontstage-snapshot.json" in public_html

        original_save_text = mod.save_text

        def flaky_save_text(path: Path, content: str) -> None:
            path_text = str(path)
            if path.name in {
                "index.html",
                "status.json",
                "snapshot.json",
                "jarvis-frontstage-status.html",
                "jarvis-frontstage-status.json",
                "jarvis-frontstage-snapshot.json",
            } and ("frontstage-status" in path_text or "jarvis-frontstage" in path.name):
                raise PermissionError("simulated publication failure")
            return original_save_text(path, content)

        mod.save_text = flaky_save_text
        degraded_paths = mod.build_views(state_path, broker_data_dir)
        mod.save_text = original_save_text

        degraded_manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        assert degraded_manifest["publicationMode"] == "best_effort"
        assert len(degraded_manifest["publicationWarnings"]) == 6
        assert {item["artifact"] for item in degraded_manifest["publicationWarnings"]} == {
            "frontstageStatusCanvasHtml",
            "frontstageStatusCanvasJson",
            "frontstageSnapshotCanvasJson",
            "frontstageStatusHtml",
            "frontstageStatusJson",
            "frontstageSnapshotJson",
        }
        assert all("PermissionError: simulated publication failure" == item["error"] for item in degraded_manifest["publicationWarnings"])
        assert degraded_manifest["published"] == {}
        assert "frontstageStatusHtml" not in degraded_paths
        assert Path(degraded_paths["snapshotView"]).exists()
        assert Path(degraded_paths["manifest"]).exists()

        print("ALL PASS")
        print(paths["events"])

    if previous_package_root is None:
        os.environ.pop("OPENCLAW_PACKAGE_ROOT", None)
    else:
        os.environ["OPENCLAW_PACKAGE_ROOT"] = previous_package_root

    if previous_canvas_dir is None:
        os.environ.pop("OPENCLAW_FRONTSTAGE_STATUS_CANVAS_DIR", None)
    else:
        os.environ["OPENCLAW_FRONTSTAGE_STATUS_CANVAS_DIR"] = previous_canvas_dir
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
