#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

WORKSPACE = Path(__file__).resolve().parents[1]


def load_module(script_name: str, module_name: str):
    module_path = WORKSPACE / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def completed_process(*, returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


def assert_handle_frontstage_command(
    cmd: list[str],
    *,
    source: str,
    message: str,
    event_key: str,
    request_id: str | None = None,
    input_text: str | None = None,
    request_transport: str = "request_json",
) -> dict[str, object]:
    assert cmd[2] == "handle", cmd
    assert "notify-frontstage" not in cmd, cmd
    if request_transport == "request_file_stdin":
        assert "--request-file" in cmd, cmd
        assert cmd[cmd.index("--request-file") + 1] == "-", cmd
        assert input_text, cmd
        payload = json.loads(input_text)
    else:
        assert "--request-json" in cmd, cmd
        payload = json.loads(cmd[cmd.index("--request-json") + 1])
    assert payload["format"] == "text", payload
    assert payload["deliveryMode"] == "frontstage", payload
    assert payload["frontstageSource"] == source, payload
    assert payload["frontstageEventKey"] == event_key, payload
    assert payload["message"] == message, payload
    if request_id is not None:
        assert payload["requestId"] == request_id, payload
    data_payload = payload.get("data")
    assert isinstance(data_payload, dict), payload
    return data_payload


def main() -> int:
    failures: list[str] = []

    contract = load_module("openclaw_infos_handle_contract.py", "infos_handle_contract")
    handle_snapshot = contract.extract_delivery_snapshot({
        "ok": True,
        "action": "handle",
        "requestId": "request-contract-adapter-test",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "response": {
            "delivery": {
                "mode": "frontstage",
                "kind": "artifact_notice",
                "message": "[infos-handle] 已生成图片 artifact：snapshot.svg｜当前正常",
                "artifactRef": "infos-handle:image:snapshot",
                "artifact": {"ref": "infos-handle:image:snapshot", "format": "image"},
                "notice": {
                    "kind": "artifact_notice",
                    "displayText": "[infos-handle] 已生成图片 artifact：snapshot.svg｜当前正常",
                    "artifactRef": "infos-handle:image:snapshot",
                },
                "frontstage": {
                    "targetSessionKey": "agent:main:dashboard:test",
                    "messageId": "msg-artifact-1",
                },
            }
        },
    })
    if handle_snapshot.get("kind") != "artifact_notice" or handle_snapshot.get("artifactRef") != "infos-handle:image:snapshot":
        failures.append(f"contract adapter handle snapshot mismatch: {handle_snapshot}")
    elif handle_snapshot.get("messageId") != "msg-artifact-1" or handle_snapshot.get("targetSessionKey") != "agent:main:dashboard:test":
        failures.append(f"contract adapter frontstage target mismatch: {handle_snapshot}")
    elif handle_snapshot.get("requestId") != "request-contract-adapter-test":
        failures.append(f"contract adapter request id mismatch: {handle_snapshot}")
    elif (handle_snapshot.get("deliveryNotice") or {}).get("displayText") != "[infos-handle] 已生成图片 artifact：snapshot.svg｜当前正常":
        failures.append(f"contract adapter delivery notice alias mismatch: {handle_snapshot}")
    elif (handle_snapshot.get("frontstageDelivery") or {}).get("messageId") != "msg-artifact-1":
        failures.append(f"contract adapter frontstage alias mismatch: {handle_snapshot}")
    elif handle_snapshot.get("artifactNotice") is not None:
        failures.append(f"contract adapter unexpected artifact notice alias mismatch: {handle_snapshot}")
    else:
        print("PASS contract_adapter_handle_delivery")

    helper_request = contract.build_handle_request_payload(
        request_id="helper-request-1",
        message="统一请求 helper 也走 request-file stdin。",
        output_format="text",
        delivery_mode="frontstage",
        session_key="agent:main:main",
        frontstage_source="supervisor",
        frontstage_event_key="helper-event-1",
        data={"checkedAt": "2026-05-18T10:00:00+08:00"},
    )
    if helper_request != {
        "requestId": "helper-request-1",
        "message": "统一请求 helper 也走 request-file stdin。",
        "format": "text",
        "sessionKey": "agent:main:main",
        "deliveryMode": "frontstage",
        "frontstageSource": "supervisor",
        "frontstageEventKey": "helper-event-1",
        "data": {"checkedAt": "2026-05-18T10:00:00+08:00"},
    }:
        failures.append(f"contract helper request payload mismatch: {helper_request}")
    else:
        print("PASS contract_helper_build_request")

    helper_calls: list[tuple[list[str], str | None]] = []

    def helper_run(cmd, capture_output, text, check, input=None):
        helper_calls.append((cmd, input))
        return completed_process(
            stdout=json.dumps(
                {
                    "ok": True,
                    "action": "handle",
                    "requestId": "helper-request-1",
                    "requestInputMode": "request_file",
                    "responseOutputMode": "stdout",
                    "response": {"delivery": {"mode": "frontstage", "status": "sent"}},
                },
                ensure_ascii=False,
            )
        )

    helper_response = contract.invoke_handle_request(
        WORKSPACE / "scripts" / "openclaw-infos-handle.py",
        helper_request,
        python_executable="python-test",
        run=helper_run,
    )
    if len(helper_calls) != 1:
        failures.append(f"contract helper invoke expected 1 call, got {len(helper_calls)}")
    elif helper_calls[0][0] != [
        "python-test",
        str(WORKSPACE / "scripts" / "openclaw-infos-handle.py"),
        "handle",
        "--request-file",
        "-",
    ]:
        failures.append(f"contract helper invoke command mismatch: {helper_calls[0][0]}")
    elif json.loads(helper_calls[0][1] or "{}") != helper_request:
        failures.append(f"contract helper invoke input mismatch: {helper_calls[0][1]}")
    elif helper_response.get("requestInputMode") != "request_file":
        failures.append(f"contract helper invoke response mismatch: {helper_response}")
    else:
        print("PASS contract_helper_invoke_handle")

    helper_file_calls: list[tuple[list[str], str | None]] = []
    with tempfile.TemporaryDirectory(prefix="infos-handle-helper-file-") as tmp:
        tmp_path = Path(tmp)
        request_file = tmp_path / "request.json"
        response_file = tmp_path / "response.json"

        def helper_file_run(cmd, capture_output, text, check, input=None):
            helper_file_calls.append((cmd, input))
            response_file.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "action": "handle",
                        "requestId": "helper-request-1",
                        "requestInputMode": "request_file",
                        "responseOutputMode": "response_file",
                        "response": {"kind": "contract.catalog"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return completed_process(stdout="")

        helper_file_response = contract.invoke_handle_request(
            WORKSPACE / "scripts" / "openclaw-infos-handle.py",
            helper_request,
            python_executable="python-test",
            run=helper_file_run,
            request_file=request_file,
            response_file=response_file,
        )
        if len(helper_file_calls) != 1:
            failures.append(f"contract helper file invoke expected 1 call, got {len(helper_file_calls)}")
        elif helper_file_calls[0][0] != [
            "python-test",
            str(WORKSPACE / "scripts" / "openclaw-infos-handle.py"),
            "handle",
            "--request-file",
            str(request_file.resolve()),
            "--response-file",
            str(response_file.resolve()),
        ]:
            failures.append(f"contract helper file invoke command mismatch: {helper_file_calls[0][0]}")
        elif helper_file_calls[0][1] is not None:
            failures.append(f"contract helper file invoke should not use stdin input: {helper_file_calls[0][1]}")
        elif json.loads(request_file.read_text(encoding="utf-8")) != helper_request:
            failures.append(f"contract helper file invoke request mismatch: {request_file.read_text(encoding='utf-8')}")
        elif helper_file_response.get("responseOutputMode") != "response_file":
            failures.append(f"contract helper file invoke response mismatch: {helper_file_response}")
        else:
            print("PASS contract_helper_invoke_handle_file_response")

    response_snapshot = contract.extract_handle_response_snapshot({
        "ok": True,
        "action": "handle",
        "requestId": "helper-query-1",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "request": {"kind": "contract.catalog", "format": "json"},
        "response": {
            "kind": "contract.catalog",
            "format": "json",
            "queryContractVersion": 17,
            "text": "contract ok",
            "result": {"requestCatalog": {"actions": {"handle": {"preferredRequestInputMode": "request_file"}}}},
            "output": {
                "format": "json",
                "artifact": {"ref": "infos-handle:json:catalog", "format": "json"},
            },
            "delivery": {
                "mode": "frontstage",
                "kind": "message",
                "message": "contract ok",
                "artifact": {"ref": "infos-handle:json:catalog", "format": "json"},
                "notice": {
                    "kind": "message",
                    "displayText": "contract ok",
                    "frontstage": {
                        "targetSessionKey": "agent:main:dashboard:test",
                        "messageId": "msg-query-1",
                    },
                },
                "artifactNotice": {
                    "kind": "artifact_notice",
                    "artifactRef": "infos-handle:json:catalog",
                    "displayText": "contract ok",
                },
                "frontstage": {
                    "targetSessionKey": "agent:main:dashboard:test",
                    "messageId": "msg-query-1",
                },
            },
        },
    })
    if response_snapshot.get("kind") != "contract.catalog" or response_snapshot.get("format") != "json":
        failures.append(f"contract helper response snapshot mismatch: {response_snapshot}")
    elif response_snapshot.get("queryContractVersion") != 17 or response_snapshot.get("text") != "contract ok":
        failures.append(f"contract helper response query metadata mismatch: {response_snapshot}")
    elif response_snapshot.get("result", {}).get("requestCatalog", {}).get("actions", {}).get("handle", {}).get("preferredRequestInputMode") != "request_file":
        failures.append(f"contract helper response result mismatch: {response_snapshot}")
    elif (response_snapshot.get("notice") or {}).get("displayText") != "contract ok":
        failures.append(f"contract helper response notice alias mismatch: {response_snapshot}")
    elif (response_snapshot.get("frontstage") or {}).get("messageId") != "msg-query-1":
        failures.append(f"contract helper response frontstage alias mismatch: {response_snapshot}")
    elif (response_snapshot.get("artifactNotice") or {}).get("artifactRef") != "infos-handle:json:catalog":
        failures.append(f"contract helper response artifact notice mismatch: {response_snapshot}")
    elif response_snapshot.get("notify") is not None:
        failures.append(f"contract helper response notify alias mismatch: {response_snapshot}")
    elif response_snapshot.get("artifactRef") != "infos-handle:json:catalog":
        failures.append(f"contract helper response artifact ref mismatch: {response_snapshot}")
    elif response_snapshot.get("targetSessionKey") != "agent:main:dashboard:test" or response_snapshot.get("messageId") != "msg-query-1":
        failures.append(f"contract helper response target alias mismatch: {response_snapshot}")
    else:
        print("PASS contract_helper_extract_handle_response")

    query_calls: list[tuple[list[str], str | None]] = []

    def query_run(cmd, capture_output, text, check, input=None):
        query_calls.append((cmd, input))
        return completed_process(
            stdout=json.dumps(
                {
                    "ok": True,
                    "action": "handle",
                    "requestId": "helper-query-1",
                    "requestInputMode": "request_file",
                    "responseOutputMode": "stdout",
                    "request": {"kind": "contract.catalog", "format": "json"},
                    "response": {
                        "kind": "contract.catalog",
                        "format": "json",
                        "queryContractVersion": 17,
                        "result": {
                            "requestCatalog": {
                                "actions": {
                                    "handle": {
                                        "clientHelperModule": "openclaw_infos_handle_contract.py",
                                        "clientHelperFunctions": ["invoke_handle_query", "extract_handle_response_snapshot"],
                                    }
                                }
                            }
                        },
                    },
                },
                ensure_ascii=False,
            )
        )

    query_response = contract.invoke_handle_query(
        WORKSPACE / "scripts" / "openclaw-infos-handle.py",
        kind="contract.catalog",
        output_format="json",
        request_id="helper-query-1",
        python_executable="python-test",
        run=query_run,
    )
    if len(query_calls) != 1:
        failures.append(f"contract helper query expected 1 call, got {len(query_calls)}")
    elif query_calls[0][0] != [
        "python-test",
        str(WORKSPACE / "scripts" / "openclaw-infos-handle.py"),
        "handle",
        "--request-file",
        "-",
    ]:
        failures.append(f"contract helper query command mismatch: {query_calls[0][0]}")
    elif json.loads(query_calls[0][1] or "{}") != {
        "requestId": "helper-query-1",
        "kind": "contract.catalog",
        "format": "json",
    }:
        failures.append(f"contract helper query input mismatch: {query_calls[0][1]}")
    elif query_response.get("kind") != "contract.catalog" or query_response.get("requestInputMode") != "request_file":
        failures.append(f"contract helper query response mismatch: {query_response}")
    elif query_response.get("result", {}).get("requestCatalog", {}).get("actions", {}).get("handle", {}).get("clientHelperModule") != "openclaw_infos_handle_contract.py":
        failures.append(f"contract helper query result mismatch: {query_response}")
    else:
        print("PASS contract_helper_invoke_query")

    infos_handle = load_module("openclaw-infos-handle.py", "infos_handle_query_compat")
    query_shell_calls: dict[str, object] = {}

    def query_shell_handle_request(request, *, request_input_mode="flags", response_output_mode="stdout"):
        query_shell_calls["request"] = request
        query_shell_calls["requestInputMode"] = request_input_mode
        query_shell_calls["responseOutputMode"] = response_output_mode
        return {
            "ok": True,
            "action": "handle",
            "requestId": "query-shell-1",
            "requestInputMode": request_input_mode,
            "responseOutputMode": response_output_mode,
            "response": {
                "ok": True,
                "kind": "sources.catalog",
                "format": "json",
                "queryContractVersion": 17,
                "snapshotPath": request.get("snapshotPath"),
                "eventsPath": request.get("eventsPath"),
                "result": {
                    "count": 2,
                    "sourceItems": [
                        {"source": "local-health"},
                        {"source": "supervisor"},
                    ],
                },
                "sourceName": None,
                "panelName": None,
                "snapshot": {},
                "events": [],
                "text": "sources ok",
                "requestContractVersion": 6,
                "output": {"handler": "json.stdout.v1"},
                "delivery": {
                    "mode": "none",
                    "artifact": None,
                    "notice": None,
                    "frontstage": None,
                    "artifactNotice": None,
                    "notify": None,
                },
            },
        }

    infos_handle.handle_request = query_shell_handle_request
    original_argv = sys.argv[:]
    query_stdout = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="infos-handle-query-shell-") as tmp:
        tmp_path = Path(tmp)
        try:
            sys.argv = [
                str(WORKSPACE / "scripts" / "openclaw-infos-handle.py"),
                "query",
                "--kind",
                "sources.catalog",
                "--format",
                "json",
                "--snapshot-path",
                str(tmp_path / "snapshot.json"),
                "--events-path",
                str(tmp_path / "events.jsonl"),
            ]
            with redirect_stdout(query_stdout):
                query_shell_rc = infos_handle.main()
        finally:
            sys.argv = original_argv
    query_shell_payload = json.loads(query_stdout.getvalue())
    if query_shell_rc != 0:
        failures.append(f"query compat shell expected rc=0, got {query_shell_rc}")
    elif query_shell_calls.get("requestInputMode") != "flags" or query_shell_calls.get("responseOutputMode") != "stdout":
        failures.append(f"query compat shell handle routing mismatch: {query_shell_calls}")
    elif (query_shell_calls.get("request") or {}).get("kind") != "sources.catalog" or (query_shell_calls.get("request") or {}).get("deliveryMode") != "none":
        failures.append(f"query compat shell request mismatch: {query_shell_calls.get('request')}")
    elif query_shell_payload.get("kind") != "sources.catalog" or query_shell_payload.get("format") != "json":
        failures.append(f"query compat shell payload mismatch: {query_shell_payload}")
    elif "requestContractVersion" in query_shell_payload or "output" in query_shell_payload or "delivery" in query_shell_payload:
        failures.append(f"query compat shell leaked handle-only fields: {query_shell_payload}")
    else:
        print("PASS query_compat_shell_via_handle")

    post_upgrade = load_module("openclaw-post-upgrade-self-check.py", "post_upgrade_self_check")
    post_upgrade.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "post-upgrade-self-check:contract.catalog",
        "kind": "contract.catalog",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "result": {
            "requestCatalog": {
                "actions": {
                    "handle": {
                        "preferredRequestInputMode": "request_file",
                        "clientHelperModule": "openclaw_infos_handle_contract.py",
                        "clientHelperFunctions": ["invoke_handle_query", "extract_handle_response_snapshot"],
                    }
                }
            }
        },
    }
    post_upgrade_check = post_upgrade.check_infos_handle_contract_entry()
    if post_upgrade_check != {
        "name": "infos_handle_contract_entry",
        "ok": True,
        "required": True,
        "detail": "requestId=post-upgrade-self-check:contract.catalog input=request_file kind=contract.catalog helper=openclaw_infos_handle_contract.py",
    }:
        failures.append(f"post-upgrade self-check infos-handle contract mismatch: {post_upgrade_check}")
    else:
        print("PASS post_upgrade_infos_handle_contract_consumer")

    post_upgrade.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "post-upgrade-self-check:snapshot.summary",
        "kind": "snapshot.summary",
        "format": "json",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "result": {
            "severity": "ok",
            "summary": "前台状态总体正常",
        },
    }
    post_upgrade_summary_check = post_upgrade.check_infos_handle_snapshot_summary_entry()
    if post_upgrade_summary_check != {
        "name": "infos_handle_snapshot_summary_entry",
        "ok": True,
        "required": True,
        "detail": "requestId=post-upgrade-self-check:snapshot.summary kind=snapshot.summary severity=ok summary=前台状态总体正常",
    }:
        failures.append(f"post-upgrade self-check infos-handle snapshot summary mismatch: {post_upgrade_summary_check}")
    else:
        print("PASS post_upgrade_infos_handle_snapshot_summary_consumer")

    post_upgrade.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "post-upgrade-self-check:sources.latest",
        "kind": "sources.latest",
        "format": "json",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "result": {
            "count": 2,
            "availableSources": ["local-health", "supervisor"],
            "sourceItems": [
                {"source": "local-health"},
                {"source": "supervisor"},
            ],
        },
    }
    post_upgrade_sources_check = post_upgrade.check_infos_handle_sources_latest_entry()
    if post_upgrade_sources_check != {
        "name": "infos_handle_sources_latest_entry",
        "ok": True,
        "required": True,
        "detail": "requestId=post-upgrade-self-check:sources.latest kind=sources.latest count=2 sources=2",
    }:
        failures.append(f"post-upgrade self-check infos-handle sources latest mismatch: {post_upgrade_sources_check}")
    else:
        print("PASS post_upgrade_infos_handle_sources_latest_consumer")

    post_upgrade.run = lambda cmd: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "controlUiInfosHandleSidecar": {
                "ok": True,
                "summaryKind": "snapshot.summary",
                "summarySeverity": "ok",
                "sseReady": True,
            }
        }, ensure_ascii=False),
        stderr="",
    )
    post_upgrade_sidecar_live = post_upgrade.check_infos_handle_sidecar_live()
    if post_upgrade_sidecar_live != {
        "name": "infos_handle_sidecar_live",
        "ok": True,
        "required": True,
        "detail": "summaryKind=snapshot.summary severity=ok sseReady=True",
    }:
        failures.append(f"post-upgrade self-check sidecar live mismatch: {post_upgrade_sidecar_live}")
    else:
        print("PASS post_upgrade_infos_handle_sidecar_live")

    post_upgrade.run = lambda cmd: SimpleNamespace(
        returncode=0,
        stdout=json.dumps({
            "ok": True,
            "mode": "http",
            "verify": {
                "ok": True,
                "mode": "http",
                "port": 18788,
                "localHealthzOk": True,
                "localSummaryCode": 200,
                "lanIp": "192.168.1.20",
                "remoteNoAuthCode": 401,
                "remoteWithAuthCode": 200,
            },
        }, ensure_ascii=False),
        stderr="",
    )
    post_upgrade_proxy_verify = post_upgrade.check_infos_handle_unified_proxy_verify()
    if post_upgrade_proxy_verify != {
        "name": "infos_handle_unified_proxy_verify",
        "ok": True,
        "required": True,
        "detail": "mode=http port=18788 local=200 remoteNoAuth=401 remoteWithAuth=200",
    }:
        failures.append(f"post-upgrade self-check unified proxy verify mismatch: {post_upgrade_proxy_verify}")
    else:
        print("PASS post_upgrade_infos_handle_unified_proxy_verify")

    post_upgrade.systemd_unit_state = lambda unit: (True, {"LoadState": "loaded", "UnitFileState": "enabled", "ActiveState": "active", "SubState": "running"})
    post_upgrade_user_service = post_upgrade.check_user_service("openclaw-infos-handle-sidecar.service")
    if post_upgrade_user_service != {
        "name": "openclaw-infos-handle-sidecar.service",
        "ok": True,
        "required": True,
        "detail": json.dumps({"LoadState": "loaded", "UnitFileState": "enabled", "ActiveState": "active", "SubState": "running"}, ensure_ascii=False),
    }:
        failures.append(f"post-upgrade self-check user service mismatch: {post_upgrade_user_service}")
    else:
        print("PASS post_upgrade_infos_handle_sidecar_service")

    apply_frontstage = load_module("apply-openclaw-frontstage-broker-data.py", "apply_frontstage_broker_data")
    apply_frontstage.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:contract-catalog-query",
        "kind": "contract.catalog",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "queryContractVersion": 17,
        "result": {
            "requestCatalog": {
                "requestContractVersion": 6,
                "actions": {
                    "handle": {
                        "preferredRequestInputMode": "request_file",
                        "clientHelperModule": "openclaw_infos_handle_contract.py",
                        "clientHelperResponseShape": {
                            "notice": "deliveryNotice|null",
                            "frontstage": "frontstageDelivery|null",
                            "artifactNotice": "artifactNotice|null",
                            "notify": "object|null",
                        },
                    }
                },
            }
        },
    }
    apply_contract_check = apply_frontstage.verify_infos_handle_contract_consumer()
    if apply_contract_check != {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:contract-catalog-query",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "kind": "contract.catalog",
        "queryContractVersion": 17,
        "requestContractVersion": 6,
        "helperModule": "openclaw_infos_handle_contract.py",
        "helperNoticeAlias": "deliveryNotice|null",
        "helperFrontstageAlias": "frontstageDelivery|null",
        "helperArtifactNotice": "artifactNotice|null",
        "helperNotify": "object|null",
    }:
        failures.append(f"apply frontstage broker data infos-handle consumer mismatch: {apply_contract_check}")
    else:
        print("PASS apply_frontstage_infos_handle_contract_consumer")

    apply_frontstage.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:snapshot-summary-query",
        "kind": "snapshot.summary",
        "format": "json",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "result": {
            "severity": "ok",
            "summary": "前台状态总体正常",
        },
    }
    apply_snapshot_check = apply_frontstage.verify_infos_handle_snapshot_summary_consumer()
    if apply_snapshot_check != {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:snapshot-summary-query",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "kind": "snapshot.summary",
        "format": "json",
        "severity": "ok",
        "summary": "前台状态总体正常",
    }:
        failures.append(f"apply frontstage broker data infos-handle snapshot summary consumer mismatch: {apply_snapshot_check}")
    else:
        print("PASS apply_frontstage_infos_handle_snapshot_summary_consumer")

    apply_frontstage.invoke_handle_query = lambda *args, **kwargs: {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:events-recent-query",
        "kind": "events.recent",
        "format": "json",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "result": {
            "count": 1,
            "latestEventAt": "2026-05-18T10:05:00+08:00",
            "sourceEventCount": 1,
            "deliveryCount": 0,
            "recordTypeCounts": {"broker.source.event": 1},
            "latestBySourceItems": [{"source": "local-health", "latestRecordType": "broker.source.event"}],
            "eventItems": [{"source": "local-health", "recordType": "broker.source.event"}],
        },
    }
    apply_events_recent_check = apply_frontstage.verify_infos_handle_events_recent_consumer()
    if apply_events_recent_check != {
        "ok": True,
        "requestId": "apply-frontstage-broker-data:events-recent-query",
        "requestInputMode": "request_file",
        "responseOutputMode": "stdout",
        "kind": "events.recent",
        "format": "json",
        "count": 1,
        "latestEventAt": "2026-05-18T10:05:00+08:00",
        "sourceEventCount": 1,
        "deliveryCount": 0,
    }:
        failures.append(f"apply frontstage broker data infos-handle events recent consumer mismatch: {apply_events_recent_check}")
    else:
        print("PASS apply_frontstage_infos_handle_events_recent_consumer")

    apply_frontstage.fetch_json_url = lambda url, **kwargs: {
        "http://127.0.0.1:18790/healthz": {
            "ok": True,
            "service": "infos-handle-sidecar",
        },
        "http://127.0.0.1:18790/v1/query/snapshot.summary?format=json": {
            "ok": True,
            "kind": "snapshot.summary",
            "requestInputMode": "request_file",
            "responseOutputMode": "stdout",
            "result": {
                "summary": "前台状态总体正常",
                "severity": "ok",
            },
        },
        "http://127.0.0.1:18790/v1/query/contract.catalog?format=json": {
            "ok": True,
            "kind": "contract.catalog",
            "requestInputMode": "request_file",
            "responseOutputMode": "stdout",
            "requestContractVersion": 6,
            "result": {
                "requestCatalog": {
                    "requestContractVersion": 6,
                    "actions": {
                        "handle": {
                            "clientHelperModule": "openclaw_infos_handle_contract.py",
                        }
                    },
                }
            },
        },
    }[url]
    apply_frontstage.fetch_sse_preview = lambda url, **kwargs: 'event: snapshot\ndata: {"kind":"snapshot.summary","result":{"summary":"前台状态总体正常"}}\n'
    apply_frontstage.probe_infos_handle_sidecar_image_artifact = lambda summary_href: {
        "artifactHref": "/v1/artifacts/infos-handle%3Aimage%3Asmoke",
        "artifactRef": "infos-handle:image:smoke",
        "artifactMediaType": "image/svg+xml",
    }
    apply_sidecar_check = apply_frontstage.verify_control_ui_infos_handle_sidecar(
        {
            "infosHandleDirectReady": True,
            "usesInfosHandleSse": True,
            "infosHandleSummaryHref": "http://127.0.0.1:18790/v1/query/snapshot.summary?format=json",
            "infosHandleContractHref": "http://127.0.0.1:18790/v1/query/contract.catalog?format=json",
            "infosHandleSseHref": "http://127.0.0.1:18790/v1/events/stream?kind=snapshot.summary",
        }
    )
    if apply_sidecar_check != {
        "ok": True,
        "healthzHref": "http://127.0.0.1:18790/healthz",
        "summaryHref": "http://127.0.0.1:18790/v1/query/snapshot.summary?format=json",
        "contractHref": "http://127.0.0.1:18790/v1/query/contract.catalog?format=json",
        "sseHref": "http://127.0.0.1:18790/v1/events/stream?kind=snapshot.summary",
        "service": "infos-handle-sidecar",
        "summaryKind": "snapshot.summary",
        "summarySeverity": "ok",
        "summaryText": "前台状态总体正常",
        "queryContractVersion": None,
        "requestContractVersion": 6,
        "helperModule": "openclaw_infos_handle_contract.py",
        "imageArtifactHref": "/v1/artifacts/infos-handle%3Aimage%3Asmoke",
        "imageArtifactRef": "infos-handle:image:smoke",
        "imageArtifactMediaType": "image/svg+xml",
        "sseConfigured": True,
        "sseReady": True,
        "ssePreview": 'event: snapshot\ndata: {"kind":"snapshot.summary","result":{"summary":"前台状态总体正常"}}\n',
    }:
        failures.append(f"apply frontstage broker data infos-handle sidecar verify mismatch: {apply_sidecar_check}")
    else:
        print("PASS apply_frontstage_control_ui_infos_handle_sidecar")

    alias_snapshot = contract.extract_delivery_snapshot({
        "ok": True,
        "action": "handle",
        "requestId": "request-contract-alias-test",
        "response": {
            "delivery": {
                "mode": "frontstage",
                "artifactNotice": {
                    "kind": "artifact_notice",
                    "artifactRef": "infos-handle:audio:alias",
                    "displayText": "[infos-handle] 已生成音频 artifact：alias.mp3｜当前正常",
                    "fallbackText": "[infos-handle] 音频 artifact 已生成。",
                    "artifact": {"ref": "infos-handle:audio:alias", "format": "audio"},
                    "delivery": {
                        "targetSessionKey": "agent:main:dashboard:test",
                        "messageId": "msg-alias-1",
                    },
                },
                "metadata": {
                    "requestedSessionKey": "agent:main:main",
                    "targetSessionKey": "agent:main:dashboard:test",
                    "messageId": "msg-alias-1",
                    "noticeKind": "artifact_notice",
                    "artifactRef": "infos-handle:audio:alias",
                    "displayText": "[infos-handle] 已生成音频 artifact：alias.mp3｜当前正常",
                },
            }
        },
    })
    if alias_snapshot.get("kind") != "artifact_notice" or alias_snapshot.get("artifactRef") != "infos-handle:audio:alias":
        failures.append(f"contract adapter alias snapshot mismatch: {alias_snapshot}")
    elif alias_snapshot.get("messageId") != "msg-alias-1" or alias_snapshot.get("targetSessionKey") != "agent:main:dashboard:test":
        failures.append(f"contract adapter alias frontstage mismatch: {alias_snapshot}")
    elif (alias_snapshot.get("notice") or {}).get("displayText") != "[infos-handle] 已生成音频 artifact：alias.mp3｜当前正常":
        failures.append(f"contract adapter alias notice mismatch: {alias_snapshot}")
    elif (alias_snapshot.get("deliveryNotice") or {}).get("artifactRef") != "infos-handle:audio:alias":
        failures.append(f"contract adapter alias delivery notice alias mismatch: {alias_snapshot}")
    elif (alias_snapshot.get("frontstageDelivery") or {}).get("messageId") != "msg-alias-1":
        failures.append(f"contract adapter alias frontstage alias mismatch: {alias_snapshot}")
    elif (alias_snapshot.get("artifactNotice") or {}).get("artifactRef") != "infos-handle:audio:alias":
        failures.append(f"contract adapter alias artifact notice mismatch: {alias_snapshot}")
    else:
        print("PASS contract_adapter_alias_delivery")

    legacy_snapshot = contract.extract_delivery_snapshot({"targetSessionKey": "legacy-target", "response": {"messageId": "legacy-mid"}})
    if legacy_snapshot.get("messageId") != "legacy-mid" or legacy_snapshot.get("targetSessionKey") != "legacy-target":
        failures.append(f"contract adapter legacy snapshot mismatch: {legacy_snapshot}")
    elif (legacy_snapshot.get("frontstageDelivery") or {}).get("targetSessionKey") != "legacy-target":
        failures.append(f"contract adapter legacy frontstage alias mismatch: {legacy_snapshot}")
    else:
        print("PASS contract_adapter_legacy_delivery")

    supervisor = load_module("openclaw-supervisor-status.py", "supervisor_status")
    legacy_supervisor = supervisor.extract_frontstage_notify_payload({"targetSessionKey": "legacy-target", "response": {"messageId": "legacy-mid"}})
    if legacy_supervisor.get("targetSessionKey") != "legacy-target":
        failures.append(f"supervisor legacy adapter: expected legacy payload passthrough, got {legacy_supervisor}")
    else:
        print("PASS supervisor_legacy_adapter")

    supervisor_saved: dict[str, object] = {}
    supervisor_logs: list[str] = []
    supervisor_calls: list[list[str]] = []

    def supervisor_run(cmd, capture_output, text, check, input=None):
        supervisor_calls.append(cmd)
        data_payload = assert_handle_frontstage_command(
            cmd,
            source="supervisor",
            event_key="failed|task-1|2026-05-18T09:45:00+08:00|agent:main:main",
            message="[监工] 构建任务 异常结束，我正在接手检查。",
            request_id="supervisor:failed|task-1|2026-05-18T09:45:00+08:00|agent:main:main",
            input_text=input,
            request_transport="request_file_stdin",
        )
        assert data_payload == {
            "status": "failed",
            "taskId": "task-1",
            "checkedAt": "2026-05-18T09:46:00+08:00",
        }, data_payload
        return completed_process(
            stdout=json.dumps(
                {
                    "ok": True,
                    "action": "handle",
                    "requestId": "supervisor:failed|task-1|2026-05-18T09:45:00+08:00|agent:main:main",
                    "requestInputMode": "request_file",
                    "responseOutputMode": "stdout",
                    "response": {
                        "delivery": {
                            "mode": "frontstage",
                            "status": "sent",
                            "frontstage": {
                                "targetSessionKey": "agent:main:dashboard:test",
                                "messageId": "msg-supervisor-1",
                            },
                        }
                    },
                },
                ensure_ascii=False,
            )
        )

    supervisor.load_json = lambda path: {}
    supervisor.save_json = lambda path, payload: supervisor_saved.update({"path": str(path), "payload": payload})
    supervisor.append_log = lambda path, line: supervisor_logs.append(line)
    supervisor.subprocess.run = supervisor_run

    with tempfile.TemporaryDirectory(prefix="infos-handle-caller-supervisor-") as tmp:
        supervisor.maybe_send_transition_notification(
            {
                "checkedAt": "2026-05-18T09:46:00+08:00",
                "status": "failed",
                "service": {"policyMode": "auto", "state": "active"},
                "recentTerminalTask": {
                    "taskId": "task-1",
                    "label": "构建任务",
                    "ownerKey": "agent:main:main",
                    "terminalAt": "2026-05-18T09:45:00+08:00",
                },
            },
            Path(tmp),
            Path(tmp) / "supervisor-events.log",
        )

    if len(supervisor_calls) != 1:
        failures.append(f"supervisor caller: expected 1 handle call, got {len(supervisor_calls)}")
    elif supervisor_saved.get("payload") != {
        "sentAt": "2026-05-18T09:46:00+08:00",
        "eventKey": "failed|task-1|2026-05-18T09:45:00+08:00|agent:main:main",
        "status": "failed",
        "taskId": "task-1",
        "sessionKey": "agent:main:main",
        "targetSessionKey": "agent:main:dashboard:test",
        "messageId": "msg-supervisor-1",
        "message": "[监工] 构建任务 异常结束，我正在接手检查。",
    }:
        failures.append(f"supervisor notify state mismatch: {supervisor_saved.get('payload')}")
    else:
        print("PASS supervisor_handle_frontstage_migration")

    recovery = load_module("openclaw-frontstage-recovery-watch.py", "frontstage_recovery_watch")
    legacy_recovery = recovery.extract_frontstage_notify_payload({"targetSessionKey": "legacy-target", "messageId": "legacy-mid"})
    if legacy_recovery.get("targetSessionKey") != "legacy-target":
        failures.append(f"recovery legacy adapter: expected legacy payload passthrough, got {legacy_recovery}")
    else:
        print("PASS recovery_legacy_adapter")

    recovery_saved: dict[str, object] = {}
    recovery_logs: list[str] = []
    recovery_calls: list[list[str]] = []

    def recovery_run(cmd, capture_output, text, check, input=None):
        recovery_calls.append(cmd)
        data_payload = assert_handle_frontstage_command(
            cmd,
            source="frontstage-recovery",
            event_key="assistant_missing_in_history|agent:main:dashboard:test|2026-05-18T09:47:00+08:00",
            message="[前台恢复观察] 检测到主回复在前台投影里可能不稳定:transcript 里有可见 assistant 回复，但 chat.history 投影里没有对应稳定结果。",
            request_id="frontstage-recovery:assistant_missing_in_history|agent:main:dashboard:test|2026-05-18T09:47:00+08:00",
            input_text=input,
            request_transport="request_file_stdin",
        )
        assert data_payload == {
            "status": "anomaly",
            "anomalyCode": "assistant_missing_in_history",
            "checkedAt": "2026-05-18T09:47:30+08:00",
        }, data_payload
        return completed_process(
            stdout=json.dumps(
                {
                    "ok": True,
                    "action": "handle",
                    "requestId": "frontstage-recovery:assistant_missing_in_history|agent:main:dashboard:test|2026-05-18T09:47:00+08:00",
                    "requestInputMode": "request_file",
                    "responseOutputMode": "stdout",
                    "response": {
                        "delivery": {
                            "mode": "frontstage",
                            "status": "sent",
                            "frontstage": {
                                "targetSessionKey": "agent:main:dashboard:test",
                                "messageId": "msg-recovery-1",
                            },
                        }
                    },
                },
                ensure_ascii=False,
            )
        )

    recovery.load_json = lambda path: {}
    recovery.save_json = lambda path, payload: recovery_saved.update({"path": str(path), "payload": payload})
    recovery.append_log = lambda path, line: recovery_logs.append(line)
    recovery.subprocess.run = recovery_run

    with tempfile.TemporaryDirectory(prefix="infos-handle-caller-recovery-") as tmp:
        recovery.maybe_send_frontstage(
            {},
            {
                "checkedAt": "2026-05-18T09:47:30+08:00",
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "assistant_missing_in_history",
                "detail": "transcript 里有可见 assistant 回复，但 chat.history 投影里没有对应稳定结果。",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "transcriptLatestAssistant": {
                    "timestamp": "2026-05-18T09:47:00+08:00",
                    "text": "测试回复",
                },
            },
            Path(tmp),
            Path(tmp) / "frontstage-recovery-events.log",
            True,
        )

    if len(recovery_calls) != 1:
        failures.append(f"recovery caller: expected 1 handle call, got {len(recovery_calls)}")
    elif recovery_saved.get("payload") != {
        "sentAt": "2026-05-18T09:47:30+08:00",
        "eventKey": "assistant_missing_in_history|agent:main:dashboard:test|2026-05-18T09:47:00+08:00",
        "status": "anomaly",
        "anomalyCode": "assistant_missing_in_history",
        "sessionKey": "agent:main:main",
        "targetSessionKey": "agent:main:dashboard:test",
        "messageId": "msg-recovery-1",
        "message": "[前台恢复观察] 检测到主回复在前台投影里可能不稳定:transcript 里有可见 assistant 回复，但 chat.history 投影里没有对应稳定结果。",
    }:
        failures.append(f"recovery notify state mismatch: {recovery_saved.get('payload')}")
    else:
        print("PASS recovery_handle_frontstage_migration")

    local_health = load_module("openclaw-local-health-diagnose.py", "local_health_diagnose")
    local_health_calls: list[list[str]] = []

    def local_health_run(cmd, capture_output, text, check, input=None):
        local_health_calls.append(cmd)
        data_payload = assert_handle_frontstage_command(
            cmd,
            source="local-health",
            event_key="warn|AI 模型路由部分异常|2026-05-18T09:48:00+08:00",
            message="[本地健康] 当前有告警：AI 模型路由部分异常",
            request_id="local-health:warn|AI 模型路由部分异常|2026-05-18T09:48:00+08:00",
            input_text=input,
            request_transport="request_file_stdin",
        )
        assert data_payload == {
            "severity": "warn",
            "summary": "AI 模型路由部分异常",
            "checkedAt": "2026-05-18T09:48:00+08:00",
        }, data_payload
        return completed_process(stdout='{}')

    local_health.subprocess.run = local_health_run
    local_health.maybe_send_frontstage(
        {"severity": "ok", "summary": "本地健康检查正常"},
        {"severity": "warn", "summary": "AI 模型路由部分异常", "checkedAt": "2026-05-18T09:48:00+08:00"},
        True,
    )

    if len(local_health_calls) != 1:
        failures.append(f"local-health caller: expected 1 handle call, got {len(local_health_calls)}")
    else:
        print("PASS local_health_handle_frontstage_migration")

    if failures:
        print("FAILURES:")
        for item in failures:
            print("-", item)
        return 1

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
