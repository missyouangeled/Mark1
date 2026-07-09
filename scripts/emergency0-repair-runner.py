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
WORKSPACE = HOME / '.openclaw' / 'workspace'
STATE_DIR = HOME / '.local' / 'state' / 'openclaw' / 'emergency-aggregator'
STATUS_JSON = STATE_DIR / 'status.json'
REPAIR_STATE_JSON = STATE_DIR / 'repair-state.json'
REPAIR_LOG_JSONL = STATE_DIR / 'repair-log.jsonl'
SKILL_ROOT = WORKSPACE / 'skills' / 'emergency-repair-pack'
CONFIG_JSON = WORKSPACE / 'scripts' / 'emergency0-config.json'
DEFAULTS = {
    'backupWarnMinutes': 15,
    'healthStaleMinutes': 10,
    'frontstageStaleMinutes': 10,
    'defaultCooldownMinutes': 30,
    'auditEveryMinutes': 30,
}
CONFIG = {**DEFAULTS, **(json.loads(CONFIG_JSON.read_text()) if CONFIG_JSON.exists() else {})}
COOLDOWN_MINUTES = int(CONFIG['defaultCooldownMinutes'])
BACKUP_WARN_MINUTES = float(CONFIG['backupWarnMinutes'])
HEALTH_STALE_MINUTES = float(CONFIG['healthStaleMinutes'])
FRONTSTAGE_STALE_MINUTES = float(CONFIG['frontstageStaleMinutes'])
AUDIT_EVERY_MINUTES = int(CONFIG['auditEveryMinutes'])

REPAIRS = [
    {
        'action': 'repair_stale_watcher_alerts',
        'script': SKILL_ROOT / 'scripts' / 'repair_stale_watcher_alerts.py',
        'guard': 'watcher_stale_only',
    },
    {
        'action': 'repair_archive_resolved_watcher_alerts',
        'script': SKILL_ROOT / 'scripts' / 'repair_archive_resolved_watcher_alerts.py',
        'guard': 'watcher_resolved_only',
    },
    {
        'action': 'repair_backup_kick_once',
        'script': SKILL_ROOT / 'scripts' / 'repair_backup_kick_once.py',
        'guard': 'backup_kick_once',
    },
    {
        'action': 'repair_health_collect_once',
        'script': SKILL_ROOT / 'scripts' / 'repair_health_collect_once.py',
        'guard': 'health_collect_once',
    },
    {
        'action': 'repair_frontstage_guardian_collect_once',
        'script': SKILL_ROOT / 'scripts' / 'repair_frontstage_guardian_collect_once.py',
        'guard': 'frontstage_collect_once',
    },
    {
        'action': 'repair_audit_snapshot',
        'script': SKILL_ROOT / 'scripts' / 'repair_audit_snapshot.py',
        'guard': 'audit_snapshot',
    },
]


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def append_log(item: dict[str, Any]) -> None:
    with REPAIR_LOG_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return datetime.fromisoformat(text).astimezone(SH_TZ)
    except Exception:
        return None


def cooldown_hit(state: dict[str, Any], action: str, minutes: int = COOLDOWN_MINUTES) -> bool:
    last = state.get('actions', {}).get(action, {})
    ts = parse_iso(last.get('lastRunAt'))
    if not ts:
        return False
    return NOW - ts < timedelta(minutes=minutes)


def run_plugin(script: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        ['python3', str(script)],
        capture_output=True,
        text=True,
    )
    output = ((proc.stdout or '') + (proc.stderr or '')).strip()
    return proc.returncode == 0, output


def guard_reason(guard: str, status: dict[str, Any], state: dict[str, Any]) -> str | None:
    watcher = status.get('watcher') or {}
    stale_items = watcher.get('staleItems') or []
    active_items = watcher.get('activeItems') or []
    resolved_items = watcher.get('resolvedItems') or []
    backup = status.get('backup') or {}
    cron = status.get('cron') or {}
    front = status.get('frontstage') or {}
    health = status.get('health') or {}

    if guard.startswith('watcher_') and active_items:
        return 'active_alerts_present'

    if guard == 'watcher_stale_only':
        if not stale_items:
            return 'no_stale_alerts'
        return None

    if guard == 'watcher_resolved_only':
        if stale_items:
            return 'stale_alerts_present'
        if not resolved_items:
            return 'no_resolved_alerts'
        return None

    if guard == 'backup_kick_once':
        age = backup.get('ageMinutes')
        if age is None or age <= BACKUP_WARN_MINUTES:
            return 'backup_not_stale'
        if cron.get('ok') is not True or cron.get('lastRunStatus') != 'ok':
            return 'cron_not_healthy'
        if front.get('ok') is not True:
            return 'frontstage_not_healthy'
        if health.get('ok') is not True:
            return 'health_not_healthy'
        if status.get('overall') not in ('OK', 'WARN'):
            return 'overall_too_risky'
        return None

    if guard == 'health_collect_once':
        age = health.get('ageMinutes')
        if age is None or age <= HEALTH_STALE_MINUTES:
            return 'health_not_stale'
        if cron.get('ok') is not True or cron.get('lastRunStatus') != 'ok':
            return 'cron_not_healthy'
        if front.get('ok') is not True:
            return 'frontstage_not_healthy'
        if status.get('overall') not in ('OK', 'WARN'):
            return 'overall_too_risky'
        return None

    if guard == 'frontstage_collect_once':
        age = front.get('ageMinutes')
        if age is None or age <= FRONTSTAGE_STALE_MINUTES:
            return 'frontstage_not_stale'
        if cron.get('ok') is not True or cron.get('lastRunStatus') != 'ok':
            return 'cron_not_healthy'
        if health.get('ok') is not True:
            return 'health_not_healthy'
        if status.get('overall') not in ('OK', 'WARN'):
            return 'overall_too_risky'
        return None

    if guard == 'audit_snapshot':
        if cooldown_hit(state, 'repair_audit_snapshot', AUDIT_EVERY_MINUTES):
            return 'audit_cooldown'
        return None

    return 'unknown_guard'


def execute_one(state: dict[str, Any], status: dict[str, Any], spec: dict[str, Any]) -> tuple[bool, str]:
    action = spec['action']
    script = spec['script']
    plugin_available = script.exists()
    result = {
        'ts': NOW.isoformat(),
        'action': action,
        'pluginAvailable': plugin_available,
        'statusOverall': status.get('overall'),
        'executed': False,
        'ok': True,
        'reason': '',
        'output': '',
    }

    if not plugin_available:
        result['reason'] = 'plugin_missing'
        append_log(result)
        return True, 'SKIP plugin_missing'

    reason = guard_reason(spec['guard'], status, state)
    if reason:
        result['reason'] = reason
        append_log(result)
        return True, f'SKIP {reason}'

    if spec['guard'] != 'audit_snapshot' and cooldown_hit(state, action):
        result['reason'] = 'cooldown'
        append_log(result)
        return True, 'SKIP cooldown'

    ok, output = run_plugin(script)
    result['executed'] = True
    result['ok'] = ok
    result['output'] = output
    result['reason'] = 'executed_ok' if ok else 'executed_failed'
    append_log(result)

    state.setdefault('actions', {})[action] = {
        'lastRunAt': NOW.isoformat(),
        'lastOk': ok,
        'lastOutput': output,
    }
    save_json(REPAIR_STATE_JSON, state)

    return ok, ('REPAIR_OK' if ok else f'REPAIR_FAILED {output}')


def main() -> int:
    status = load_json(STATUS_JSON)
    if not isinstance(status, dict):
        print('NO_STATUS')
        return 1

    state = load_json(REPAIR_STATE_JSON)
    if not isinstance(state, dict):
        state = {'actions': {}}

    overall_ok = True
    outputs: list[str] = []
    for spec in REPAIRS:
        ok, output = execute_one(state, status, spec)
        outputs.append(f"{spec['action']}: {output}")
        if not ok:
            overall_ok = False

    print('\n'.join(outputs))
    return 0 if overall_ok else 1


if __name__ == '__main__':
    sys.exit(main())
