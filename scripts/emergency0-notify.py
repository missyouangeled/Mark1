#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SH_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(SH_TZ)
HOME = Path.home()
STATE_DIR = HOME / '.local' / 'state' / 'openclaw' / 'emergency-aggregator'
STATUS_JSON = STATE_DIR / 'status.json'
EVENTS_JSONL = STATE_DIR / 'events.jsonl'
NOTIFY_STATE_JSON = STATE_DIR / 'notify-state.json'
WORKSPACE = HOME / '.openclaw' / 'workspace'
INJECTOR = WORKSPACE / 'scripts' / 'openclaw-proactive-inject.py'

COOLDOWN_MINUTES = 30
ALERT_LEVELS = {'WARN', 'CRITICAL', 'DEADMAN'}
SEVERE_LEVELS = {'CRITICAL', 'DEADMAN'}


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return datetime.fromisoformat(text).astimezone(SH_TZ)
    except Exception:
        return None


def load_last_event() -> dict[str, Any]:
    if not EVENTS_JSONL.exists():
        return {}
    lines = [line for line in EVENTS_JSONL.read_text().splitlines() if line.strip()]
    if not lines:
        return {}
    try:
        data = json.loads(lines[-1])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def should_skip_by_cooldown(state: dict[str, Any], overall: str, event_kind: str) -> bool:
    if event_kind == 'level_change':
        return False
    last_ts = parse_iso(state.get('lastNotifyAt'))
    last_overall = state.get('lastNotifiedOverall')
    if not last_ts or last_overall != overall:
        return False
    return NOW - last_ts < timedelta(minutes=COOLDOWN_MINUTES)


def already_notified_same_snapshot(state: dict[str, Any], status: dict[str, Any], event: dict[str, Any]) -> bool:
    return (
        state.get('lastStatusGeneratedAt') == status.get('generatedAt')
        and state.get('lastEventKind') == (event.get('kind') or 'heartbeat')
        and state.get('lastNotifiedOverall') == (status.get('overall') or 'UNKNOWN')
        and state.get('lastNotifyOk') is True
    )


def build_message(status: dict[str, Any], event: dict[str, Any]) -> str | None:
    overall = status.get('overall') or 'UNKNOWN'
    findings = status.get('findings') or []
    main_session = status.get('mainSession') or {}
    event_kind = event.get('kind') or 'heartbeat'
    finding_lines = []
    for item in findings[:5]:
        if not isinstance(item, dict):
            continue
        finding_lines.append(f"- [{item.get('level')}] {item.get('code')}: {item.get('message')}")

    if overall in SEVERE_LEVELS:
        return (
            f"[保命聚合器告警] 当前状态 {overall}，主 session={main_session.get('sessionId') or 'unknown'}。\n"
            + ('\n'.join(finding_lines) if finding_lines else '- 无细项')
            + "\n（自动只读巡检触发，建议优先查看 docs/runtime/保命状态快照.md）"
        )

    if overall == 'WARN' and event_kind == 'level_change':
        return (
            f"[保命聚合器预警] 当前状态 WARN，主 session={main_session.get('sessionId') or 'unknown'}。\n"
            + ('\n'.join(finding_lines) if finding_lines else '- 无细项')
            + "\n（已自动留痕；当前策略不自动修主会话）"
        )

    if overall == 'OK' and event_kind == 'level_change':
        return (
            f"[保命聚合器恢复] 当前状态已回到 OK，主 session={main_session.get('sessionId') or 'unknown'}。\n"
            "最新快照已刷新，可继续按当前节奏运行。"
        )
    return None


def save_state(state: dict[str, Any]) -> None:
    NOTIFY_STATE_JSON.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def inject(message: str) -> tuple[bool, str]:
    if not INJECTOR.exists():
        return False, 'injector_missing'
    proc = subprocess.run(
        ['python3', str(INJECTOR), '--source', 'emergency-aggregator', message],
        capture_output=True,
        text=True,
    )
    ok = proc.returncode == 0
    output = (proc.stdout or proc.stderr).strip()
    return ok, output


def main() -> int:
    status = load_json(STATUS_JSON)
    if not isinstance(status, dict):
        print('NO_STATUS')
        return 1

    event = load_last_event()
    notify_state = load_json(NOTIFY_STATE_JSON)
    if not isinstance(notify_state, dict):
        notify_state = {}

    overall = status.get('overall') or 'UNKNOWN'
    event_kind = event.get('kind') or 'heartbeat'
    message = build_message(status, event)

    if overall not in ALERT_LEVELS and event_kind != 'level_change':
        print(f'SKIP overall={overall} kind={event_kind}')
        return 0
    if not message:
        print(f'SKIP overall={overall} kind={event_kind}')
        return 0
    if already_notified_same_snapshot(notify_state, status, event):
        print(f'DUPLICATE overall={overall} kind={event_kind}')
        return 0
    if should_skip_by_cooldown(notify_state, overall, event_kind):
        print(f'COOLDOWN overall={overall} kind={event_kind}')
        return 0

    ok, output = inject(message)
    new_state = {
        'lastNotifyAt': NOW.isoformat(),
        'lastNotifiedOverall': overall,
        'lastEventKind': event_kind,
        'lastOutput': output,
        'lastStatusGeneratedAt': status.get('generatedAt'),
        'lastNotifyOk': ok,
    }
    save_state(new_state)
    if ok:
        print(f'NOTIFIED overall={overall} kind={event_kind}')
        return 0
    print(f'NOTIFY_FAILED overall={overall} kind={event_kind} output={output}')
    return 1


if __name__ == '__main__':
    sys.exit(main())
