#!/usr/bin/env python3
"""Proactive message injector — inject a message into the current frontstage session.

Usage:
  python3 scripts/openclaw-proactive-inject.py '消息内容'
  python3 scripts/openclaw-proactive-inject.py --file tmp/proactive-msg.txt
  python3 scripts/openclaw-proactive-inject.py --source 'afternoon-greeting' '消息内容'
"""

import json
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPTS_DIR.parent


def find_current_dashboard() -> str | None:
    """Find the most recent active dashboard session key."""
    sessions_json = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / "sessions.json"
    if not sessions_json.exists():
        return None

    try:
        data = json.loads(sessions_json.read_text())
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    candidates = []
    for key, session in data.items():
        if not isinstance(session, dict):
            continue
        # Dashboard sessions identified by key pattern + chatType
        if "dashboard" not in key:
            continue
        if session.get("chatType") != "direct":
            continue
        status = session.get("status", "")
        updated = session.get("updatedAt", 0)
        if status in ("running", "idle"):
            candidates.append((updated, key))

    # Fallback: if no running dashboard, accept recent "done" ones
    if not candidates:
        for key, session in data.items():
            if not isinstance(session, dict):
                continue
            if "dashboard" not in key:
                continue
            if session.get("chatType") != "direct":
                continue
            status = session.get("status", "")
            updated = session.get("updatedAt", 0)
            if status == "done":
                candidates.append((updated, key))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def inject_via_infos_handle(message: str, source: str = "proactive") -> bool:
    """Inject a message into the frontstage session via infos-handle."""
    sys.path.insert(0, str(SCRIPTS_DIR))

    try:
        from openclaw_infos_handle_contract import (
            build_handle_request_payload,
            invoke_handle_request,
        )
    except ImportError:
        return False

    session_key = find_current_dashboard()
    if not session_key:
        return False

    handle_script = SCRIPTS_DIR / "openclaw-infos-handle.py"
    if not handle_script.exists():
        return False

    event_key = f"proactive|{source}|{int(time.time() // 60)}"
    payload = build_handle_request_payload(
        request_id=f"proactive:{event_key}",
        message=message,
        output_format="text",
        delivery_mode="frontstage",
        frontstage_source=source,
        frontstage_event_key=event_key,
        session_key=session_key,
    )

    result = invoke_handle_request(
        handle_script=handle_script,
        request_payload=payload,
    )

    if isinstance(result, dict):
        return result.get("ok", False)
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Inject proactive message into frontstage")
    parser.add_argument("message", nargs="?", help="Message text to inject")
    parser.add_argument("--file", help="Read message from file")
    parser.add_argument("--source", default="proactive", help="Source tag (e.g., morning-greeting)")
    args = parser.parse_args()

    if args.file:
        msg = Path(args.file).read_text(encoding="utf-8").strip()
    elif args.message:
        msg = args.message
    else:
        parser.print_help()
        sys.exit(1)

    ok = inject_via_infos_handle(msg, args.source)
    if ok:
        print(f"✅ 注入成功: {msg[:60]}...")
    else:
        print("❌ 注入失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
