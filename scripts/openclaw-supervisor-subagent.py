#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_AGENT_ID = "main"
DEFAULT_PREFIX = "main-supervisor-lite｜"
DEFAULT_TASK = (
    "只做当前轮轻量监工：读取后台任务状态；若发现 stalled / failed / 空返回，"
    "或超过 3 分钟仍无可见产出，则用一条简短自然语言向主会话汇报；"
    "若当前没有需要补位的异常，就回复 NO_REPLY。"
)


def run_gateway_call(method: str, params: dict[str, Any]) -> dict[str, Any]:
    cmd = [
        "openclaw",
        "gateway",
        "call",
        method,
        "--params",
        json.dumps(params, ensure_ascii=False),
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or f"gateway call failed: {method}").strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid gateway response: {exc}") from exc


def parse_agent_id_from_session_key(session_key: str) -> str:
    parts = session_key.strip().split(":")
    if len(parts) >= 3 and parts[0] == "agent" and parts[1].strip():
        return parts[1].strip()
    return DEFAULT_AGENT_ID


def session_store_path(agent_id: str) -> Path:
    return Path.home() / ".openclaw" / "agents" / agent_id / "sessions" / "sessions.json"


def load_session_store(agent_id: str) -> dict[str, Any]:
    path = session_store_path(agent_id)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def is_dashboard_session_key(session_key: str, agent_id: str) -> bool:
    return session_key.startswith(f"agent:{agent_id}:dashboard:")


def resolve_root_session_key(session_key: str, store: dict[str, Any]) -> str:
    current = session_key.strip()
    seen: set[str] = set()
    while current and current not in seen:
        seen.add(current)
        row = store.get(current)
        if not isinstance(row, dict):
            break
        parent = row.get("parentSessionKey")
        if not isinstance(parent, str) or not parent.strip():
            break
        current = parent.strip()
    return current or session_key


def resolve_frontstage_binding(session_key: str) -> dict[str, Any]:
    requested_session_key = session_key.strip()
    agent_id = parse_agent_id_from_session_key(requested_session_key)
    store = load_session_store(agent_id)
    owner_session_key = resolve_root_session_key(requested_session_key, store)
    requested_row = store.get(requested_session_key) if isinstance(store.get(requested_session_key), dict) else None

    dashboard_candidates: list[tuple[int, str]] = []
    for candidate_key, row in store.items():
        if not isinstance(row, dict) or not is_dashboard_session_key(candidate_key, agent_id):
            continue
        if resolve_root_session_key(candidate_key, store) != owner_session_key:
            continue
        updated_at = row.get("updatedAt")
        dashboard_candidates.append((updated_at if isinstance(updated_at, int) else 0, candidate_key))

    latest_dashboard: tuple[int, str] | None = max(dashboard_candidates, key=lambda item: (item[0], item[1])) if dashboard_candidates else None
    requested_updated_at = requested_row.get("updatedAt") if isinstance(requested_row, dict) and isinstance(requested_row.get("updatedAt"), int) else 0

    if latest_dashboard and requested_session_key == owner_session_key:
        _, target_session_key = latest_dashboard
        target_kind = "dashboard"
    elif latest_dashboard and not is_dashboard_session_key(requested_session_key, agent_id) and requested_updated_at >= latest_dashboard[0]:
        target_session_key = requested_session_key
        target_kind = "requested"
    elif latest_dashboard:
        _, target_session_key = latest_dashboard
        target_kind = "dashboard"
    elif requested_row:
        target_session_key = requested_session_key
        target_kind = "requested"
    else:
        target_session_key = owner_session_key
        target_kind = "root"

    return {
        "requestedSessionKey": requested_session_key,
        "resolvedOwnerSessionKey": owner_session_key,
        "targetSessionKey": target_session_key,
        "targetKind": target_kind,
        "sessionStorePath": str(session_store_path(agent_id)),
    }


def invoke_subagents(session_key: str, action: str, target: str | None = None) -> dict[str, Any]:
    args: dict[str, Any] = {"action": action}
    if target:
        args["target"] = target
    payload = run_gateway_call(
        "tools.invoke",
        {
            "name": "subagents",
            "sessionKey": session_key,
            "args": args,
        },
    )
    if not payload.get("ok"):
        error = payload.get("error") or {}
        raise RuntimeError(str(error.get("message") or error.get("code") or "subagents tool failed"))
    output = payload.get("output") or {}
    details = output.get("details")
    return details if isinstance(details, dict) else payload


def send_slash_command(session_key: str, message: str) -> dict[str, Any]:
    return run_gateway_call(
        "chat.send",
        {
            "sessionKey": session_key,
            "idempotencyKey": str(uuid.uuid4()),
            "message": message,
        },
    )


def inject_message(session_key: str, message: str) -> dict[str, Any]:
    return run_gateway_call(
        "chat.inject",
        {
            "sessionKey": session_key,
            "message": message,
        },
    )


def build_spawn_message(agent_id: str, task: str) -> str:
    task_text = task.strip()
    if not task_text:
        raise ValueError("spawn task cannot be empty")
    return f"/subagents spawn {agent_id} {task_text}"


def build_default_task(prefix: str, owner_session_key: str) -> str:
    routing_note = (
        f"在 WebChat / Control UI 直聊里，不要把回报绑死到启动你的旧 dashboard 页面；"
        f"若需要汇报，统一执行 `python3 scripts/openclaw-supervisor-subagent.py send-frontstage --session-key {owner_session_key} --message '这里换成你的简短汇报'`。"
        f"这个动作会自动先解析同一父会话下最新的 dashboard 前台，再把消息 inject 过去；"
        f"若确实没有可用 dashboard 前台，才退回 `{owner_session_key}`。"
    )
    return f"{prefix}{DEFAULT_TASK}{routing_note}"


def print_human_list(details: dict[str, Any]) -> None:
    print(details.get("text") or json.dumps(details, ensure_ascii=False, indent=2))


def print_human_binding(binding: dict[str, Any]) -> None:
    print(f"requested={binding['requestedSessionKey']}")
    print(f"owner={binding['resolvedOwnerSessionKey']}")
    print(f"frontstage={binding['targetSessionKey']} ({binding['targetKind']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage lightweight OpenClaw supervisor subagent runs via gateway RPC")
    parser.add_argument("action", choices=["list", "spawn", "kill", "resolve-frontstage", "send-frontstage"], help="Operation to run")
    parser.add_argument("--session-key", required=True, help="Current/frontstage session key; dashboard keys auto-resolve to the shared owner session")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID, help="Target agent id for /subagents spawn")
    parser.add_argument("--task", help="Task text for spawn")
    parser.add_argument("--message", help="Message text for send-frontstage")
    parser.add_argument("--prefix", default=DEFAULT_PREFIX, help="Prefix added to the default spawn task")
    parser.add_argument("--target", help="Target id/index for kill, e.g. #1 or runId")
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--print-human", action="store_true", help="Print human-readable output")
    args = parser.parse_args()

    binding = resolve_frontstage_binding(args.session_key)
    owner_session_key = binding["resolvedOwnerSessionKey"]

    if args.action == "resolve-frontstage":
        if args.print_json:
            print(json.dumps(binding, ensure_ascii=False, indent=2))
        else:
            print_human_binding(binding)
        return 0

    if args.action == "list":
        details = invoke_subagents(owner_session_key, "list")
        payload = {**binding, "details": details}
        if args.print_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_human_binding(binding)
            print_human_list(details)
        return 0

    if args.action == "send-frontstage":
        if not args.message or not args.message.strip():
            raise SystemExit("--message is required for send-frontstage")
        response = inject_message(binding["targetSessionKey"], args.message.strip())
        payload = {**binding, "response": response}
        if args.print_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_human_binding(binding)
            print(f"sent to frontstage: messageId={response.get('messageId')}")
        return 0

    if args.action == "kill":
        if not args.target:
            raise SystemExit("--target is required for kill")
        details = invoke_subagents(owner_session_key, "kill", target=args.target)
        payload = {**binding, "details": details}
        if args.print_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_human_binding(binding)
            print(details.get("text") or json.dumps(details, ensure_ascii=False, indent=2))
        return 0

    task = args.task.strip() if args.task else build_default_task(args.prefix, owner_session_key)
    response = send_slash_command(owner_session_key, build_spawn_message(args.agent_id, task))
    payload = {**binding, "response": response}
    if args.print_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human_binding(binding)
        print(
            f"spawn started: owner={owner_session_key} frontstage={binding['targetSessionKey']} "
            f"runId={response.get('runId')} status={response.get('status')}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
