#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH = timezone(timedelta(hours=8))
HOME = Path.home()
WORKSPACE = HOME / '.openclaw' / 'workspace'
STATE = HOME / '.local' / 'state' / 'openclaw'
EMERGENCY = STATE / 'emergency-aggregator'
HEALTH = STATE / 'health-collector' / 'last-report.json'
STATUS = EMERGENCY / 'status.json'
SESSIONS = HOME / '.openclaw' / 'agents' / 'main' / 'sessions' / 'sessions.json'
BACKUP = Path('/mnt/data/openclaw/session-backup/backup-manifest.json')


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
    return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()


def load_json(path: Path):
    return json.loads(path.read_text())


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def case_health_timeout() -> bool:
    orig = HEALTH.read_text()
    try:
        data = json.loads(orig)
        data['ok'] = False
        data['overall'] = '⚠'
        data['checkedAt'] = datetime.now(SH).isoformat(timespec='seconds')
        for c in data.get('checks', []):
            if c.get('label') == 'stuck-session-detect':
                c['ok'] = False
                c['summary'] = 'stuck-session-detect /exception/timeout'
                c['stdoutRaw'] = ''
        save_json(HEALTH, data)
        rc, _ = run(['python3', str(WORKSPACE / 'scripts' / 'emergency0-aggregator.py')])
        status = load_json(STATUS)
        codes = [x.get('code') for x in status.get('findings', [])]
        return rc == 0 and 'HEALTH_STALE' in codes and any('timeout' in (x.get('message') or '') or x.get('code','').startswith('HEALTH_') for x in status.get('findings', []))
    finally:
        HEALTH.write_text(orig, encoding='utf-8')


def case_sessions_missing_sessionfile() -> bool:
    orig = SESSIONS.read_text()
    try:
        data = json.loads(orig)
        main = data.get('agent:main:main') or {}
        main['sessionFile'] = ''
        data['agent:main:main'] = main
        save_json(SESSIONS, data)
        rc, out = run(['python3', str(WORKSPACE / 'scripts' / 'emergency1-orchestrator.py')])
        return rc == 0 and ('[救命 1 静默]' in out or '[救命 1 告警已发]' in out)
    finally:
        SESSIONS.write_text(orig, encoding='utf-8')


def case_backup_manifest_broken() -> bool:
    if not BACKUP.exists():
        return True
    bak = BACKUP.with_suffix('.json.regression.bak')
    shutil.copy2(BACKUP, bak)
    try:
        BACKUP.write_text('{broken', encoding='utf-8')
        rc, _ = run(['python3', str(WORKSPACE / 'scripts' / 'emergency0-aggregator.py')])
        status = load_json(STATUS)
        codes = [x.get('code') for x in status.get('findings', [])]
        return rc == 0 and 'BACKUP_STALE' in codes
    finally:
        shutil.move(str(bak), str(BACKUP))


def main() -> int:
    results = {
        'health_timeout': case_health_timeout(),
        'sessions_missing_sessionfile': case_sessions_missing_sessionfile(),
        'backup_manifest_broken': case_backup_manifest_broken(),
    }
    ok = all(results.values())
    print(json.dumps({'ok': ok, 'results': results}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
