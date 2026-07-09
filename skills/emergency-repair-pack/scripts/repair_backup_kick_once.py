#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(SH_TZ)
WORKSPACE = Path.home() / '.openclaw' / 'workspace'
BACKUP_SCRIPT = WORKSPACE / 'scripts' / 'openclaw-session-backup.py'


def main() -> int:
    if not BACKUP_SCRIPT.exists():
        print('BACKUP_SCRIPT_MISSING')
        return 1

    proc = subprocess.run(
        ['python3', str(BACKUP_SCRIPT), '--quiet'],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    output = ((proc.stdout or '') + (proc.stderr or '')).strip()
    if proc.returncode == 0:
        print('BACKUP_KICK_OK')
        if output:
            print(output)
        return 0

    print('BACKUP_KICK_FAILED')
    if output:
        print(output)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
