#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def message(role: str, text: str, timestamp: str) -> dict:
    return {
        "role": role,
        "timestamp": timestamp,
        "content": [{"type": "text", "text": text}],
    }


def assistant_tool_call(timestamp: str) -> dict:
    return {
        "role": "assistant",
        "timestamp": timestamp,
        "content": [{"type": "toolCall", "name": "sessions_yield", "arguments": {}}],
    }


def yielded_tool_result(text: str, timestamp: str) -> dict:
    return {
        "role": "toolResult",
        "timestamp": timestamp,
        "content": [{"type": "text", "text": '{"status":"yielded","message":' + json.dumps(text, ensure_ascii=False) + '}'}],
    }


def assistant_attachment(timestamp: str, *, kind: str = "image") -> dict:
    return {
        "role": "assistant",
        "timestamp": timestamp,
        "content": [{"type": "attachment", "attachment": {"kind": kind, "url": f"https://example.test/{kind}"}}],
    }


def assistant_canvas(timestamp: str, *, view_id: str = "status-card") -> dict:
    return {
        "role": "assistant",
        "timestamp": timestamp,
        "content": [{"type": "canvas", "surface": "assistant_message", "render": "url", "viewId": view_id, "url": "https://example.test/canvas"}],
    }

MODULE_PATH = Path(__file__).with_name("openclaw-frontstage-recovery-watch.py")


def load_module():
    spec = importlib.util.spec_from_file_location("frontstage_recovery_watch", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mod = load_module()
    cases: list[tuple[str, dict, dict, dict, dict | None]] = [
        (
            "anomaly_from_ok",
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            {},
            {
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "assistant_missing_in_history",
                "detail": "transcript 里有可见 assistant 回复，但 chat.history 投影里没有对应稳定结果。",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "transcriptLatestAssistant": {"timestamp": "2026-05-14T01:40:00Z", "text": "测试回复"},
            },
            {"status": "anomaly", "anomalyCode": "assistant_missing_in_history"},
        ),
        (
            "same_anomaly_duplicate_suppressed",
            {
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "assistant_missing_in_history",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "transcriptLatestAssistant": {"timestamp": "2026-05-14T01:40:00Z", "text": "测试回复"},
            },
            {},
            {
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "assistant_missing_in_history",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "transcriptLatestAssistant": {"timestamp": "2026-05-14T01:40:00Z", "text": "测试回复"},
            },
            None,
        ),
        (
            "recover_from_previous_report_anomaly",
            {
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "assistant_missing_in_history",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:dashboard:test",
                "transcriptLatestAssistant": {"timestamp": "2026-05-14T01:40:00Z", "text": "测试回复"},
            },
            {},
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            {"status": "recovered", "anomalyCode": "assistant_missing_in_history"},
        ),
        (
            "recover_from_previous_notify_anomaly",
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            {
                "status": "anomaly",
                "eventKey": "assistant_missing_in_history|agent:main:dashboard:test|anchor-1",
                "anomalyCode": "assistant_missing_in_history",
            },
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            {"status": "recovered", "anomalyCode": "assistant_missing_in_history"},
        ),
        (
            "pending_does_not_recover",
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            {
                "status": "anomaly",
                "eventKey": "assistant_missing_in_history|agent:main:dashboard:test|anchor-1",
                "anomalyCode": "assistant_missing_in_history",
            },
            {"ok": True, "pendingProjection": True, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:dashboard:test"},
            None,
        ),
        (
            "yielded_replay_message",
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:main"},
            {},
            {
                "ok": False,
                "pendingProjection": False,
                "anomalyCode": "yielded_tool_result_missing_visible_reply",
                "requestedSessionKey": "agent:main:main",
                "targetSessionKey": "agent:main:main",
                "transcriptLatestYielded": {"timestamp": "2026-05-15T07:33:59+08:00", "text": "后台阶段结果已经出来了。"},
            },
            {"status": "replayed", "anomalyCode": "yielded_tool_result_missing_visible_reply", "message": "后台阶段结果已经出来了。"},
        ),
        (
            "yielded_replay_does_not_send_recovered",
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:main"},
            {
                "status": "replayed",
                "eventKey": "yielded_tool_result_missing_visible_reply|agent:main:main|anchor-1",
                "anomalyCode": "yielded_tool_result_missing_visible_reply",
            },
            {"ok": True, "pendingProjection": False, "requestedSessionKey": "agent:main:main", "targetSessionKey": "agent:main:main"},
            None,
        ),
    ]

    failures: list[str] = []
    for name, previous_report, previous_notify, current_report, expected in cases:
        actual = mod.build_notification_candidate(previous_report, previous_notify, current_report)
        if expected is None:
            if actual is not None:
                failures.append(f"{name}: expected None, got {actual}")
            else:
                print(f"PASS {name}")
            continue
        if actual is None:
            failures.append(f"{name}: expected {expected}, got None")
            continue
        mismatch = []
        for key, value in expected.items():
            if actual.get(key) != value:
                mismatch.append(f"{key} expected={value!r} actual={actual.get(key)!r}")
        if mismatch:
            failures.append(f"{name}: " + "; ".join(mismatch))
        else:
            print(f"PASS {name}")

    silent_projection = mod.analyze_projection(
        [message("user", "继续 runtime event", "2026-05-14T17:00:00+08:00"), message("assistant", "NO_REPLY", "2026-05-14T17:00:05+08:00")],
        [message("user", "继续 runtime event", "2026-05-14T17:00:00+08:00"), message("assistant", "NO_REPLY", "2026-05-14T17:00:05+08:00")],
        {"status": "ended", "hasActiveRun": False, "endedAt": "2026-05-14T17:00:06+08:00"},
    )
    if not silent_projection.get("ok") or silent_projection.get("anomalyCode") is not None:
        failures.append(f"silent_no_reply_projection: expected ok without anomaly (NO_REPLY is expected behavior), got {silent_projection}")
    else:
        print("PASS silent_no_reply_projection")

    attachment_projection = mod.analyze_projection(
        [message("user", "发我图片", "2026-05-15T09:00:00+08:00"), assistant_attachment("2026-05-15T09:00:05+08:00")],
        [message("user", "发我图片", "2026-05-15T09:00:00+08:00"), assistant_attachment("2026-05-15T09:00:05+08:00")],
        {"status": "done", "hasActiveRun": False, "endedAt": "2026-05-15T09:00:06+08:00"},
    )
    if not attachment_projection.get("ok") or attachment_projection.get("anomalyCode") is not None:
        failures.append(f"attachment_only_projection_visible: expected ok without anomaly, got {attachment_projection}")
    else:
        print("PASS attachment_only_projection_visible")

    canvas_projection = mod.analyze_projection(
        [message("user", "打开卡片", "2026-05-15T09:01:00+08:00"), assistant_canvas("2026-05-15T09:01:05+08:00")],
        [message("user", "打开卡片", "2026-05-15T09:01:00+08:00"), assistant_canvas("2026-05-15T09:01:05+08:00")],
        {"status": "done", "hasActiveRun": False, "endedAt": "2026-05-15T09:01:06+08:00"},
    )
    if not canvas_projection.get("ok") or canvas_projection.get("anomalyCode") is not None:
        failures.append(f"canvas_only_projection_visible: expected ok without anomaly, got {canvas_projection}")
    else:
        print("PASS canvas_only_projection_visible")

    attachment_missing_projection = mod.analyze_projection(
        [message("user", "再发一张", "2026-05-15T09:02:00+08:00"), assistant_attachment("2026-05-15T09:02:05+08:00")],
        [message("user", "再发一张", "2026-05-15T09:02:00+08:00")],
        {"status": "done", "hasActiveRun": False, "endedAt": "2026-05-15T09:02:06+08:00"},
    )
    if attachment_missing_projection.get("anomalyCode") != "assistant_missing_in_history":
        failures.append(f"attachment_only_missing_in_history: expected assistant_missing_in_history, got {attachment_missing_projection}")
    else:
        print("PASS attachment_only_missing_in_history")

    yielded_projection = mod.analyze_projection(
        [
            message("user", "继续后台任务", "2026-05-15T07:33:47+08:00"),
            assistant_tool_call("2026-05-15T07:33:48+08:00"),
            yielded_tool_result("后台阶段结果已经出来了。", "2026-05-15T07:33:59+08:00"),
        ],
        [
            message("user", "继续后台任务", "2026-05-15T07:33:47+08:00"),
            assistant_tool_call("2026-05-15T07:33:48+08:00"),
            yielded_tool_result("后台阶段结果已经出来了。", "2026-05-15T07:33:59+08:00"),
        ],
        {"status": "done", "hasActiveRun": False, "endedAt": "2026-05-15T07:34:00+08:00"},
    )
    if yielded_projection.get("anomalyCode") != "yielded_tool_result_missing_visible_reply":
        failures.append(f"yielded_projection: expected yielded_tool_result_missing_visible_reply, got {yielded_projection}")
    else:
        print("PASS yielded_projection")

    running_empty_turn_projection = mod.analyze_projection(
        [
            message("user", "继续排查", "2026-05-15T08:33:47+08:00"),
            assistant_tool_call("2026-05-15T08:33:48+08:00"),
        ],
        [
            message("user", "继续排查", "2026-05-15T08:33:47+08:00"),
            assistant_tool_call("2026-05-15T08:33:48+08:00"),
        ],
        {"status": "running", "hasActiveRun": False, "endedAt": None},
    )
    if not running_empty_turn_projection.get("pendingProjection") or running_empty_turn_projection.get("anomalyCode") is not None:
        failures.append(f"running_empty_assistant_turn_pending: expected pending without anomaly, got {running_empty_turn_projection}")
    else:
        print("PASS running_empty_assistant_turn_pending")

    stale_active_run_projection = mod.analyze_projection(
        [
            message("user", "继续", "2026-05-15T08:10:00+08:00"),
            message("assistant", "测试回复", "2026-05-15T08:10:05+08:00"),
        ],
        [
            message("user", "继续", "2026-05-15T08:10:00+08:00"),
        ],
        {"status": "done", "hasActiveRun": True, "endedAt": "2026-05-15T08:10:06+08:00"},
    )
    if stale_active_run_projection.get("pendingProjection") or stale_active_run_projection.get("anomalyCode") != "assistant_missing_in_history":
        failures.append(f"stale_active_run_done_not_pending: expected assistant_missing_in_history without pending, got {stale_active_run_projection}")
    else:
        print("PASS stale_active_run_done_not_pending")

    if failures:
        print("FAILURES:")
        for item in failures:
            print("-", item)
        return 1

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
