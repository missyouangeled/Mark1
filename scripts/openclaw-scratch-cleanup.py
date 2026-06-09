#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

SCRATCH = Path('/mnt/data/openclaw/scratch')
KEEP_MARKER = '.keep'


def age_days(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 86400.0


def should_skip(path: Path) -> tuple[bool, str]:
    if path.is_dir():
        if (path / KEEP_MARKER).exists():
            return True, 'keep-marker'
        for marker in path.rglob(KEEP_MARKER):
            if marker.is_file():
                return True, f'keep-marker:{marker.relative_to(path)}'
    return False, ''


def main() -> int:
    ap = argparse.ArgumentParser(description='清理 scratch 过期目录/文件（支持 keep 标记）')
    ap.add_argument('--days', type=int, default=7, help='清理超过多少天未修改的项目（默认 7）')
    ap.add_argument('--dry-run', action='store_true', help='只预览，不实际删除')
    ap.add_argument('--print-kept', action='store_true', help='同时打印保留项')
    args = ap.parse_args()

    if not SCRATCH.exists():
        print(f'❌ scratch 不存在: {SCRATCH}')
        return 2

    removed = []
    kept = []
    for item in sorted(SCRATCH.iterdir()):
        skip, reason = should_skip(item) if item.is_dir() else (False, '')
        days = age_days(item)
        if skip:
            kept.append((item, reason, days))
            continue
        if days < args.days:
            kept.append((item, 'recent', days))
            continue
        removed.append((item, days))

    print(f'📂 scratch: {SCRATCH}')
    print(f'🛡️ keep marker: {KEEP_MARKER}')
    print(f'⏳ 清理阈值: {args.days} 天')
    print(f'🧾 候选删除: {len(removed)} | 保留: {len(kept)}')

    if args.print_kept and kept:
        print('\n保留项:')
        # 分层：🛡️ keep 保护 / 📅 近 N 天内
        protected = [(it, r, d) for it, r, d in kept if r.startswith('keep')]
        recent = [(it, r, d) for it, r, d in kept if not r.startswith('keep')]
        if protected:
            print(f'  🛡️ .keep 保护 ({len(protected)} 项):')
            for item, reason, days in protected:
                marker = reason.replace('keep-marker:', '.keep→') if reason != 'keep-marker' else '.keep'
                print(f'     {item.name}/  ({days:.1f} 天, {marker})')
        if recent:
            print(f'  📅 近 {args.days} 天内 ({len(recent)} 项):')
            for item, _reason, days in recent:
                print(f'     {item.name}/  ({days:.1f} 天)')

    if removed:
        print('\n候选删除项:')
        for item, days in removed:
            print(f'- {item.name} ({days:.1f} 天)')

    if args.dry_run:
        print('\n[dry-run] 未实际删除')
        return 0

    deleted = 0
    for item, _days in removed:
        try:
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)
            deleted += 1
        except Exception as exc:
            print(f'[warn] 删除失败: {item} -> {exc}')

    print(f'\n✅ 实际删除: {deleted}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
