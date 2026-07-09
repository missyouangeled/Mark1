#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SH_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(SH_TZ)
HOME = Path.home()
WATCHER_DIR = HOME / '.local' / 'state' / 'openclaw' / 'session-size-watcher'
ALERTS_JSON = WATCHER_DIR / 'alerts.json'
ARCHIVE_JSONL = WATCHER_DIR / 'archived-alerts.jsonl'
TRAJECTORY_WARN_MB = 5.0
STALE_HOURS = 1.0


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        return datetime.fromisoformat(text).astimezone(SH_TZ)
    except Exception:
        return None


def age_hours(ts: datetime | None) -> float | None:
    if not ts:
        return None
    return (NOW - ts).total_seconds() / 3600.0


def append_archive(item: dict[str, Any]) -> None:
    with ARCHIVE_JSONL.open('a', encoding='utf-8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')


def main() -> int:
    data = load_json(ALERTS_JSON)
    if not isinstance(data, dict):
        print('NO_ALERTS_JSON')
        return 1

    items = data.get('items') or []
    kept = []
    archived = []

    for item in items:
        ts = parse_iso(item.get('time'))
        ah = age_hours(ts)
        detail = item.get('detail') or {}
        traj_mb = float(detail.get('trajectory_mb') or 0)
        # 仅归档：超过 1 小时且 trajectory 明显属于旧告警的历史项
        if ah is not None and ah > STALE_HOURS and traj_mb >= TRAJECTORY_WARN_MB:
            archived.append(item)
        else:
            kept.append(item)

    if not archived:
        print('NO_ARCHIVE_NEEDED')
        return 0

    for item in archived:
        append_archive({
            'archivedAt': NOW.isoformat(),
            'reason': 'stale_watcher_alert',
            'item': item,
        })

    data['items'] = kept
    data['unread'] = bool(kept)
    save_json(ALERTS_JSON, data)
    print(f'ARCHIVED {len(archived)} KEPT {len(kept)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
