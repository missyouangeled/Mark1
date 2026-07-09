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
WATCHER_ALERTS = STATE_DIR / 'session-size-watcher' / 'alerts.json'
STATUS_JSON = EMERGENCY_DIR / 'status.json'
ARCHIVE_JSONL = EMERGENCY_DIR / 'watcher-resolved-archive.jsonl'


def load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def item_key(item: dict) -> str:
    detail = item.get('detail') or {}
    return json.dumps({
        'time': item.get('time'),
        'level': item.get('level'),
        'message': item.get('message'),
        'detail': detail,
    }, ensure_ascii=False, sort_keys=True)


def main() -> int:
    status = load_json(STATUS_JSON) or {}
    watcher = status.get('watcher') or {}
    resolved_items = watcher.get('resolvedItems') or []
    if not resolved_items:
        print('NO_RESOLVED_ITEMS')
        return 0

    alerts = load_json(WATCHER_ALERTS)
    if not isinstance(alerts, dict):
        print('ALERTS_UNREADABLE')
        return 1

    existing_keys = {item_key(it) for it in resolved_items}
    items = alerts.get('items') or []
    kept = []
    archived = []
    for item in items:
        if item_key(item) in existing_keys:
            archived.append(item)
        else:
            kept.append(item)

    if not archived:
        print('NO_MATCHED_RESOLVED_ITEMS')
        return 0

    with ARCHIVE_JSONL.open('a', encoding='utf-8') as f:
        for item in archived:
            row = {
                'archivedAt': NOW.isoformat(),
                'source': 'repair_archive_resolved_watcher_alerts',
                'item': item,
            }
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

    alerts['items'] = kept
    alerts['unread'] = bool(kept) and bool(alerts.get('unread'))
    alerts['lastArchiveAt'] = NOW.isoformat()
    WATCHER_ALERTS.write_text(json.dumps(alerts, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'ARCHIVED_RESOLVED_ITEMS {len(archived)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
