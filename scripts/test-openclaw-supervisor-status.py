#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
MODULE_PATH = WORKSPACE / "scripts" / "openclaw-supervisor-status.py"


def load_module():
    spec = importlib.util.spec_from_file_location("openclaw_supervisor_status", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    mod = load_module()
    failures: list[str] = []

    with tempfile.TemporaryDirectory(prefix="supervisor-status-test-") as tmp:
        tmp_path = Path(tmp)
        control_path = tmp_path / "service-control.json"

        original_epoch_ms = mod.epoch_ms
        original_agents_root = mod.DEFAULT_AGENTS_ROOT
        original_default_tasks_db_path = mod.DEFAULT_TASKS_DB_PATH
        original_legacy_tasks_db_path = mod.LEGACY_TASKS_DB_PATH
        try:
            mod.epoch_ms = lambda: 1_000_000
            agents_root = tmp_path / "agents"
            sessions_dir = agents_root / "main" / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            mod.DEFAULT_AGENTS_ROOT = agents_root

            orphaned_session_file = sessions_dir / "orphaned.jsonl"
            orphaned_session_file.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "session", "timestamp": "2026-05-18T07:44:51Z"}, ensure_ascii=False),
                        json.dumps(
                            {
                                "type": "message",
                                "timestamp": "2026-05-18T07:44:52Z",
                                "message": {"role": "user", "timestamp": 1_000_000},
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "type": "message",
                                "timestamp": "2026-05-18T07:44:53Z",
                                "message": {"role": "assistant", "content": []},
                                "stopReason": "error",
                                "errorMessage": "504 status code (no body)",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            ok_session_file = sessions_dir / "ok.jsonl"
            ok_session_file.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "session", "timestamp": "2026-05-18T07:44:51Z"}, ensure_ascii=False),
                        json.dumps(
                            {
                                "type": "message",
                                "timestamp": "2026-05-18T07:44:54Z",
                                "message": {
                                    "role": "assistant",
                                    "timestamp": 1_000_100,
                                    "content": [{"type": "text", "text": "还在继续处理。"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (sessions_dir / "sessions.json").write_text(
                json.dumps(
                    {
                        "agent:main:subagent:orphan": {"sessionFile": str(orphaned_session_file), "status": "running"},
                        "agent:main:subagent:ok": {"sessionFile": str(ok_session_file), "status": "running"},
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            orphaned, orphan_reason = mod.detect_orphaned_running_task(
                {
                    "status": "running",
                    "agent_id": "main",
                    "child_session_key": "agent:main:subagent:orphan",
                    "started_at": 1_000_000,
                    "created_at": 999_000,
                }
            )
            if not orphaned or "504" not in str(orphan_reason):
                failures.append(f"expected orphaned running task to be detected, got orphaned={orphaned} reason={orphan_reason}")
            else:
                print("PASS detect_orphaned_running_task")

            tasks_db = tmp_path / "runs.sqlite"
            conn = sqlite3.connect(tasks_db)
            conn.execute(
                """
                CREATE TABLE task_runs (
                  task_id TEXT PRIMARY KEY,
                  runtime TEXT NOT NULL,
                  source_id TEXT,
                  owner_key TEXT NOT NULL,
                  scope_kind TEXT NOT NULL,
                  child_session_key TEXT,
                  parent_flow_id TEXT,
                  parent_task_id TEXT,
                  agent_id TEXT,
                  run_id TEXT,
                  label TEXT,
                  task TEXT NOT NULL,
                  status TEXT NOT NULL,
                  delivery_status TEXT NOT NULL,
                  notify_policy TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  started_at INTEGER,
                  ended_at INTEGER,
                  last_event_at INTEGER,
                  cleanup_after INTEGER,
                  error TEXT,
                  progress_summary TEXT,
                  terminal_summary TEXT,
                  terminal_outcome TEXT,
                  requester_session_key TEXT,
                  task_kind TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, owner_key, scope_kind, child_session_key, agent_id,
                  label, task, status, delivery_status, notify_policy, created_at, started_at, last_event_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-orphan",
                    "cli",
                    "agent:main:subagent:orphan",
                    "session",
                    "agent:main:subagent:orphan",
                    "main",
                    None,
                    "orphan task",
                    "running",
                    "not_applicable",
                    "silent",
                    999_000,
                    1_000_000,
                    1_000_000,
                ),
            )
            conn.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, owner_key, scope_kind, child_session_key, agent_id,
                  label, task, status, delivery_status, notify_policy, created_at, started_at, last_event_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "task-ok",
                    "cli",
                    "agent:main:subagent:ok",
                    "session",
                    "agent:main:subagent:ok",
                    "main",
                    "正常任务",
                    "ok task",
                    "running",
                    "not_applicable",
                    "silent",
                    999_000,
                    1_000_000,
                    1_000_100,
                ),
            )
            conn.commit()
            conn.close()
            conn = sqlite3.connect(tasks_db)
            conn.row_factory = sqlite3.Row
            active_tasks, active_error = mod.fetch_active_tasks(conn, 1_000_200, 180)
            conn.close()
            if active_error is not None or len(active_tasks) != 1 or active_tasks[0].get("taskId") != "task-ok":
                failures.append(f"expected fetch_active_tasks to prune orphaned running task, got error={active_error} tasks={active_tasks}")
            else:
                print("PASS fetch_active_tasks_prunes_orphaned_running_task")

            conn, resolved_path = mod.open_db(tasks_db)
            if conn is None or resolved_path != tasks_db.resolve():
                failures.append(f"expected open_db to use explicit shared-schema db first, got conn={conn} path={resolved_path}")
            else:
                print("PASS open_db_prefers_explicit_task_runs_db")
            if conn is not None:
                conn.close()

            legacy_db = tmp_path / "legacy-runs.sqlite"
            legacy_conn = sqlite3.connect(legacy_db)
            legacy_conn.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, status TEXT)")
            legacy_conn.commit()
            legacy_conn.close()
            mod.DEFAULT_TASKS_DB_PATH = tmp_path / "missing-default.sqlite"
            mod.LEGACY_TASKS_DB_PATH = tmp_path / "missing-legacy.sqlite"
            fallback_conn, fallback_path = mod.open_db(legacy_db)
            if fallback_conn is None or fallback_path != legacy_db.resolve():
                failures.append(f"expected open_db to return explicit fallback db when no candidate has task_runs, got conn={fallback_conn} path={fallback_path}")
            else:
                print("PASS open_db_falls_back_to_explicit_db_without_task_runs")
            if fallback_conn is not None:
                fallback_conn.close()
            mod.DEFAULT_TASKS_DB_PATH = original_default_tasks_db_path
            mod.LEGACY_TASKS_DB_PATH = original_legacy_tasks_db_path

            mod.save_service_control(
                control_path,
                policy_mode="force_on",
                task_active=True,
                updated_by="test",
                reason="init",
                followup_window=None,
            )
            report_done = {
                "status": "done",
                "hasActiveTask": False,
                "service": {
                    "desiredState": "armed",
                    "policyMode": "force_on",
                    "taskActive": True,
                },
                "recentTerminalTask": {
                    "taskId": "task-1",
                    "label": "实现任务",
                    "ownerKey": "agent:main:main",
                    "terminalAt": "2026-05-18T11:20:00+08:00",
                    "status": "succeeded",
                },
            }
            changed = mod.reconcile_followup_window(report_done, control_path, 180)
            control = mod.load_service_control(control_path)
            if not changed or not isinstance(control.get("followupWindow"), dict):
                failures.append("expected done report to open a followup window")
            else:
                print("PASS open_followup_window_after_done")

            waiting_report = {
                "status": "waiting",
                "service": {"policyMode": "force_on", "state": "armed"},
                "followupWindow": control.get("followupWindow"),
                "recentTerminalTask": report_done["recentTerminalTask"],
            }
            waiting_candidate = mod.build_notification_candidate(waiting_report)
            if not waiting_candidate or "再等 180 秒" not in waiting_candidate.get("message", ""):
                failures.append(f"expected waiting notification candidate, got {waiting_candidate}")
            else:
                print("PASS waiting_notification_candidate")

            active_window = control.get("followupWindow")
            mod.save_service_control(
                control_path,
                policy_mode="force_on",
                task_active=True,
                updated_by="test",
                reason="active-clear",
                followup_window=active_window,
            )
            changed = mod.reconcile_followup_window(
                {
                    "status": "running",
                    "hasActiveTask": True,
                    "service": {
                        "desiredState": "armed",
                        "policyMode": "force_on",
                        "taskActive": True,
                    },
                    "recentTerminalTask": report_done["recentTerminalTask"],
                },
                control_path,
                180,
            )
            control = mod.load_service_control(control_path)
            if not changed or control.get("followupWindow") is not None:
                failures.append("expected active task to clear followup window")
            else:
                print("PASS clear_followup_window_when_new_active_task_appears")

            mod.save_service_control(
                control_path,
                policy_mode="force_on",
                task_active=True,
                updated_by="test",
                reason="expired-window",
                followup_window={
                    "startedAtMs": 1_000,
                    "startedAt": "2026-05-18T11:21:00+08:00",
                    "expiresAtMs": 2_000,
                    "expiresAt": "2026-05-18T11:24:00+08:00",
                    "taskId": "task-2",
                    "taskLabel": "收尾任务",
                    "ownerKey": "agent:main:main",
                    "completedAt": "2026-05-18T11:21:00+08:00",
                    "waitSeconds": 180,
                },
            )
            mod.epoch_ms = lambda: 2_500
            changed = mod.reconcile_followup_window(
                {
                    "status": "waiting",
                    "hasActiveTask": False,
                    "service": {
                        "desiredState": "armed",
                        "policyMode": "force_on",
                        "taskActive": True,
                    },
                    "followupWindow": mod.load_service_control(control_path).get("followupWindow"),
                    "recentTerminalTask": {
                        "taskId": "task-2",
                        "label": "收尾任务",
                        "ownerKey": "agent:main:main",
                        "terminalAt": "2026-05-18T11:21:00+08:00",
                        "status": "succeeded",
                    },
                },
                control_path,
                180,
            )
            control = mod.load_service_control(control_path)
            if not changed or control.get("policyMode") != "auto" or control.get("taskActive") is not False or control.get("followupWindow") is not None:
                failures.append(f"expected expired followup window to auto-close supervisor, got {control}")
            else:
                print("PASS auto_close_after_followup_window_expires")
        finally:
            mod.epoch_ms = original_epoch_ms
            mod.DEFAULT_AGENTS_ROOT = original_agents_root
            mod.DEFAULT_TASKS_DB_PATH = original_default_tasks_db_path
            mod.LEGACY_TASKS_DB_PATH = original_legacy_tasks_db_path

    if failures:
        print("FAILURES:")
        for item in failures:
            print("-", item)
        return 1

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
