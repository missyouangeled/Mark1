#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WORKSPACE = Path.home() / '.openclaw' / 'workspace'
SCRATCH = Path('/mnt/data/openclaw/scratch')


def run(cmd: str) -> None:
    print(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=False)


def clean_workspace_tmp() -> int:
    tmp_dir = WORKSPACE / 'tmp'
    if not tmp_dir.exists():
        return 0
    cleaned = 0
    for item in tmp_dir.iterdir():
        if item.name == 'voice-replies':
            continue
        try:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {item} -> {exc}")
    return cleaned


def clean_pyc() -> int:
    cleaned = 0
    for p in WORKSPACE.rglob('__pycache__'):
        try:
            shutil.rmtree(p)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {p} -> {exc}")
    for p in WORKSPACE.rglob('*.pyc'):
        try:
            p.unlink(missing_ok=True)
            cleaned += 1
        except Exception as exc:
            print(f"[warn] 清理失败: {p} -> {exc}")
    return cleaned


def main() -> int:
    print('=== OpenClaw 大工程收尾 ===')
    run('free -h')
    run('df -h / /mnt/data')

    tmp_cleaned = clean_workspace_tmp()
    pyc_cleaned = clean_pyc()
    print(f"[ok] tmp 清理: {tmp_cleaned} 项")
    print(f"[ok] pyc/__pycache__ 清理: {pyc_cleaned} 项")

    run('journalctl --vacuum-size=100M')
    run('sync && echo 3 | sudo tee /proc/sys/vm/drop_caches')
    run('python3 scripts/openclaw-system-summary.py --print-human')
    run('free -h')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
