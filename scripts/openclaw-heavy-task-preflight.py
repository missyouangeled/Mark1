#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

RULE_EXTS = {'.prefab', '.fbx', '.dae', '.obj', '.mat', '.png', '.jpg', '.jpeg', '.tga', '.tif', '.tiff', '.psd', '.exr', '.hdr'}
SCRATCH = Path('/mnt/data/openclaw/scratch')


def human_gb(n: int) -> str:
    return f"{n / (1024**3):.1f}GiB"


def count_files(root: Path) -> tuple[int, int]:
    total = 0
    considered = 0
    for p in root.rglob('*'):
        if not p.is_file() or p.name.endswith('.meta'):
            continue
        total += 1
        if p.suffix.lower() in RULE_EXTS:
            considered += 1
    return total, considered


def mem_available_bytes() -> int:
    try:
        with open('/proc/meminfo', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('MemAvailable:'):
                    kb = int(line.split()[1])
                    return kb * 1024
    except Exception:
        pass
    return 0


def disk_free_bytes(path: str) -> int:
    usage = shutil.disk_usage(path)
    return usage.free


def active_user_failed_units() -> int:
    res = subprocess.run(['systemctl', '--user', 'list-units', '--failed', '--no-legend'], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return -1
    lines = [x for x in res.stdout.splitlines() if x.strip()]
    return len(lines)


def recommendation(considered: int, mem_avail: int, root_free: int) -> list[str]:
    rec = []
    if considered > 200:
        rec.append('必须后台分身执行，聊天只放摘要。')
    elif considered > 50:
        rec.append('建议分批执行，优先后台。')
    else:
        rec.append('规模较小，可前台轻量处理。')

    if mem_avail and mem_avail < 2 * 1024**3:
        rec.append('当前可用内存偏低，强烈建议不要在主会话同步跑重活。')
    if root_free < 8 * 1024**3:
        rec.append('根盘低于 8GiB 安全线，大产物必须落 /mnt/data scratch。')
    else:
        rec.append('结果文档/中间产物仍建议默认落 scratch。')
    rec.append('正式改名前先跑 openclaw-rename-conflict-check.py。')
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description='OpenClaw 大工程开工前预检')
    ap.add_argument('path', help='目标目录')
    ap.add_argument('--task-name', help='任务名（用于建议 scratch 子目录）', default='task')
    args = ap.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        print(f'❌ 路径不存在: {root}')
        return 2

    total, considered = count_files(root)
    mem_avail = mem_available_bytes()
    root_free = disk_free_bytes('/')
    scratch_free = disk_free_bytes('/mnt/data') if Path('/mnt/data').exists() else 0
    failed_units = active_user_failed_units()

    scratch_hint = SCRATCH / args.task_name

    print(f'📂 目标目录: {root}')
    print(f'📊 文件总数(不含 .meta): {total}')
    print(f'🎯 纳入重命名/扫描规则: {considered}')
    print(f'🧠 可用内存: {human_gb(mem_avail) if mem_avail else "未知"}')
    print(f'💽 根盘剩余: {human_gb(root_free)}')
    print(f'🗄️ 数据盘剩余: {human_gb(scratch_free)}')
    print(f'📁 建议 scratch 路径: {scratch_hint}')
    if failed_units >= 0:
        print(f'⚙️ 当前 user failed units: {failed_units}')

    print('\n建议：')
    for item in recommendation(considered, mem_avail, root_free):
        print(f'- {item}')

    print('\n建议命令：')
    print(f"- python3 scripts/openclaw-rename-conflict-check.py '{root}' --report-out '{SCRATCH}/reports/{args.task_name}-conflicts.json'")
    print(f"- mkdir -p '{scratch_hint}'")
    print(f"- 大工程结束后: python3 scripts/openclaw-heavy-task-finish.py")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
