#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(SH_TZ)
HOME = Path.home()
STATE_DIR = HOME / '.local' / 'state' / 'openclaw'
EMERGENCY_DIR = STATE_DIR / 'emergency-aggregator'
STATUS_JSON = EMERGENCY_DIR / 'status.json'
AUDIT_JSONL = EMERGENCY_DIR / 'repair-audit.jsonl'


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def main() -> int:
    status = load_json(STATUS_JSON)
    if not isinstance(status, dict):
        print('NO_STATUS')
        return 1

    row = {
        'auditedAt': NOW.isoformat(),
        'overall': status.get('overall'),
        'findingsCount': len(status.get('findings') or []),
        'mainSessionId': (status.get('mainSession') or {}).get('sessionId'),
        'backupAgeMinutes': (status.get('backup') or {}).get('ageMinutes'),
        'frontstageAgeMinutes': (status.get('frontstage') or {}).get('ageMinutes'),
        'healthAgeMinutes': (status.get('health') or {}).get('ageMinutes'),
        'watcherActiveCount': len((status.get('watcher') or {}).get('activeItems') or []),
        'watcherStaleCount': len((status.get('watcher') or {}).get('staleItems') or []),
        'watcherResolvedCount': len((status.get('watcher') or {}).get('resolvedItems') or []),
    }

    with AUDIT_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')

    print('AUDIT_SNAPSHOT_OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
