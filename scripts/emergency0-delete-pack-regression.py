#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

WORKSPACE = Path.home() / '.openclaw' / 'workspace'
PACK = WORKSPACE / 'skills' / 'emergency-repair-pack'
PARK = WORKSPACE / 'skills' / '.emergency-repair-pack.disabled'
RUNNER = WORKSPACE / 'scripts' / 'emergency0-repair-runner.py'
AGG = WORKSPACE / 'scripts' / 'emergency0-aggregator.py'


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE))
    return p.returncode, ((p.stdout or '') + (p.stderr or '')).strip()


def main() -> int:
    if not PACK.exists():
        print('PACK_MISSING')
        return 1
    if PARK.exists():
        print('PARK_ALREADY_EXISTS')
        return 1

    shutil.move(str(PACK), str(PARK))
    try:
        rc1, out1 = run(['python3', str(RUNNER)])
        rc2, out2 = run(['python3', str(AGG)])
        ok = rc1 == 0 and rc2 == 0 and 'plugin_missing' in out1
        print('DELETE_PACK_REGRESSION_OK' if ok else 'DELETE_PACK_REGRESSION_FAILED')
        print('--- repair-runner ---')
        print(out1)
        print('--- aggregator ---')
        print(out2)
        return 0 if ok else 1
    finally:
        shutil.move(str(PARK), str(PACK))


if __name__ == '__main__':
    raise SystemExit(main())
