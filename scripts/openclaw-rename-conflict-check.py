#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

TEXTURE_EXTS = {'.tif', '.tiff', '.png', '.jpg', '.jpeg', '.tga', '.exr', '.hdr', '.psd'}
MODEL_EXTS = {'.fbx', '.dae', '.obj'}
PREFAB_EXTS = {'.prefab'}
MAT_EXTS = {'.mat'}


def split_compound(name: str) -> str:
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
    return name


def cleanup_name(name: str, *, strip_hash_suffix: bool = False) -> str:
    name = name.replace(' ', '_')
    name = re.sub(r'^SceneStatic_', '', name, flags=re.I)
    name = re.sub(r'^Type[-_]+', '', name, flags=re.I)
    name = re.sub(r'[-].*$', '', name)
    name = re.sub(r'_Type[_-]?\d+', '', name, flags=re.I)
    if strip_hash_suffix:
        name = re.sub(r'#.*$', '', name)
    name = split_compound(name)
    name = re.sub(r'__+', '_', name).strip('_')
    return name


def infer_target(filename: str, *, strip_hash_suffix: bool = False, prefix: str | None = None) -> str:
    p = Path(filename)
    stem = p.stem
    ext = p.suffix

    if ext.lower() in MAT_EXTS:
        cleaned = cleanup_name(stem, strip_hash_suffix=strip_hash_suffix)
        if cleaned.startswith('Mat_'):
            base = cleaned
        else:
            base = 'Mat_' + cleaned
    elif ext.lower() in PREFAB_EXTS | MODEL_EXTS | TEXTURE_EXTS:
        effective = prefix if prefix is not None else 'Props_'
        if effective == '':
            base = cleanup_name(stem, strip_hash_suffix=strip_hash_suffix)
        else:
            pfx = effective.rstrip('_')
            # 检查原始 stem 是否已包含该前缀（跳过 cleanup，避免拆分 RoadSide→Road_Side）
            if stem.startswith(pfx + '_') or stem == pfx:
                base_stem = stem
                base_stem = re.sub(r'_Type[_-]?\d+', '', base_stem, flags=re.I)
                if strip_hash_suffix:
                    base_stem = re.sub(r'#.*$', '', base_stem)
                base = base_stem
            else:
                cleaned = cleanup_name(stem, strip_hash_suffix=strip_hash_suffix)
                if cleaned.startswith(pfx + '_'):
                    base = cleaned
                else:
                    base = pfx + '_' + cleaned
    else:
        base = cleanup_name(stem, strip_hash_suffix=strip_hash_suffix)
    return base + ext


def main() -> int:
    ap = argparse.ArgumentParser(description='批量改名前冲突预扫')
    ap.add_argument('path', help='目标目录')
    ap.add_argument('--report-out', help='输出 JSON 报告路径')
    ap.add_argument('--samples', type=int, default=20)
    ap.add_argument('--strip-hash-suffix', action='store_true', help='按当前任务规则删除 # 及后面内容，用于预扫覆盖风险')
    ap.add_argument('--prefix', default=None, help='资源前缀（如 Props_/RoadSide_/Wall_）。传空字符串表示无前缀。默认 Props_')
    args = ap.parse_args()
    prefix = args.prefix if args.prefix is None or args.prefix != '' else ''
    if args.prefix is None:
        prefix = None  # None → 向后兼容，走默认 Props_ 逻辑
    elif args.prefix == '':
        prefix = ''  # 空字符串 → 无前缀

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        print(f'❌ 路径不存在: {root}')
        return 2

    mapping: dict[str, list[str]] = defaultdict(list)
    total = 0
    considered = 0
    for fp in root.rglob('*'):
        if not fp.is_file() or fp.name.endswith('.meta'):
            continue
        total += 1
        ext = fp.suffix.lower()
        if ext not in (TEXTURE_EXTS | MODEL_EXTS | PREFAB_EXTS | MAT_EXTS):
            continue
        considered += 1
        target = infer_target(fp.name, strip_hash_suffix=args.strip_hash_suffix, prefix=prefix)
        rel = str(fp.relative_to(root))
        mapping[target].append(rel)

    conflicts = {k: v for k, v in mapping.items() if len(v) > 1}
    unchanged = 0
    renamed = 0
    for target, sources in mapping.items():
        for rel in sources:
            if Path(rel).name == target:
                unchanged += 1
            else:
                renamed += 1

    print(f'📂 目标目录: {root}')
    print(f'📊 总文件: {total} | 纳入规则: {considered}')
    print(f'📝 预计改名涉及: {renamed} | 原样保持: {unchanged}')
    print(f'⚠️ 冲突目标名: {len(conflicts)}')

    shown = 0
    for target, sources in sorted(conflicts.items()):
        if shown >= args.samples:
            break
        print(f'\n[冲突] {target}')
        for s in sources:
            print(f'  - {s}')
        shown += 1

    report = {
        'root': str(root),
        'totalFiles': total,
        'consideredFiles': considered,
        'wouldRename': renamed,
        'unchanged': unchanged,
        'conflictCount': len(conflicts),
        'stripHashSuffix': args.strip_hash_suffix,
        'prefix': args.prefix,
        'conflicts': conflicts,
    }
    if args.report_out:
        out = Path(args.report_out).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n📝 报告已写入: {out}')

    return 1 if conflicts else 0


if __name__ == '__main__':
    raise SystemExit(main())
