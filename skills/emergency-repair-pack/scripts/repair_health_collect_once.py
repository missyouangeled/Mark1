#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

WORKSPACE = Path.home() / '.openclaw' / 'workspace'
HEALTH_SCRIPT = WORKSPACE / 'scripts' / 'openclaw-health-collector.py'


def main() -> int:
    if not HEALTH_SCRIPT.exists():
        print('HEALTH_SCRIPT_MISSING')
        return 1

    proc = subprocess.run(
        ['python3', str(HEALTH_SCRIPT), '--print-human'],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    output = ((proc.stdout or '') + (proc.stderr or '')).strip()
    if proc.returncode == 0:
        print('HEALTH_COLLECT_OK')
        if output:
            print(output)
        return 0

    print('HEALTH_COLLECT_FAILED')
    if output:
        print(output)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
