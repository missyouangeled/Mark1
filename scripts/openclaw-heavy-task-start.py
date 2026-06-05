#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

SCRATCH = Path('/mnt/data/openclaw/scratch')


def run(cmd: list[str]) -> int:
    res = subprocess.run(cmd, check=False)
    return res.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description='OpenClaw 大工程统一开工入口')
    ap.add_argument('path', help='目标目录')
    ap.add_argument('--task-name', required=True, help='任务名，用于 scratch 子目录')
    ap.add_argument('--keep', action='store_true', help='为该任务目录写入 .keep 保留标记')
    ap.add_argument('--strip-hash-suffix', action='store_true', help='若改名规则会删除 # 及后面内容，则输出对应冲突预扫建议')
    args = ap.parse_args()

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f'❌ 路径不存在: {target}')
        return 2

    task_dir = SCRATCH / args.task_name
    task_dir.mkdir(parents=True, exist_ok=True)
    if args.keep:
        (task_dir / '.keep').write_text('keep\n', encoding='utf-8')

    print('=== OpenClaw 大工程开工入口 ===')
    print(f'📂 目标目录: {target}')
    print(f'📁 scratch 目录: {task_dir}')
    if args.keep:
        print('🛡️ 已写入 .keep 保留标记')

    print('\n--- 预检 ---', flush=True)
    run(['python3', 'scripts/openclaw-heavy-task-preflight.py', str(target), '--task-name', args.task_name])

    report = SCRATCH / 'reports' / f'{args.task_name}-conflicts.json'
    report.parent.mkdir(parents=True, exist_ok=True)
    conflict_cmd = ['python3', 'scripts/openclaw-rename-conflict-check.py', str(target), '--report-out', str(report)]
    if args.strip_hash_suffix:
        conflict_cmd.append('--strip-hash-suffix')

    print('\n--- 建议下一步 ---')
    print('$ ' + ' '.join(conflict_cmd))
    print('$ python3 scripts/openclaw-system-summary.py --print-human')
    print('$ python3 scripts/openclaw-heavy-task-finish.py   # 完工后执行')
    print('\n说明：先看预检，再跑冲突预扫；无冲突后再正式执行重活。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
