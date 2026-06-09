#!/usr/bin/env python3
"""
military-rename-v1.py — Military 目录 V3 批量重命名
"""

import json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

MILITARY = Path("/media/missyouangeled/WD_BLACK/Project_amend_01/Assets/AssetScene/SceneModels/Military")

META_EXTS = {'.prefab', '.fbx', '.mat', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.tga', '.exr', '.hdr', '.psd'}

# PascalCase 复合词拆分
COMPOUND_SPLITS = {
    'BunkerOther': 'Bunker_Other', 'BunkerPipe': 'Bunker_Pipe',
    'BunkerVentsA': 'Bunker_Vents_A', 'BunkerConcrete': 'Bunker_Concrete',
    'BunkerConcreteTile': 'Bunker_Concrete_Tile', 'BunkerOtherGroup': 'Bunker_Other_Group',
    'WatchTower': 'Watch_Tower', 'WatchTowerMetal': 'Watch_Tower_Metal',
    'WatchTowerWooden': 'Watch_Tower_Wooden',
    'NetTent': 'Net_Tent', 'CampTent': 'Camp_Tent', 'RoadCross': 'Road_Cross',
    'SandBags': 'Sand_Bags', 'Sandbag': 'Sandbag', 'Sandbags': 'Sandbags',
    'SentrBox': 'Sentry_Box', 'SentryBox': 'Sentry_Box',
    'BarbedWire': 'Barbed_Wire', 'BarbedWireG': 'Barbed_Wire_G',
    'TentCanvas': 'Tent_Canvas', 'TentMetal': 'Tent_Metal', 'TentRope': 'Tent_Rope',
    'TentWood': 'Tent_Wood',
    'BaseMap': 'Base_Map', 'MaskMap': 'Mask_Map', 'NormalMap': 'Normal_Map',
    'RoughnessMask': 'Roughness_Mask', 'AlbedoTransparency': 'Albedo_Transparency',
    'MetallicSmoothness': 'Metallic_Smoothness', 'OpenGL': 'Open_GL',
    'DefaultMaterial': 'Default_Material', 'GMask': 'G_Mask',
    'WoodBox': 'Wood_Box', 'WoodenBox': 'Wooden_Box', 'MetalBox': 'Metal_Box',
    'Roadblock': 'Roadblock', 'Doorframe': 'Doorframe',
    'forER': 'for_ER', 'BaseER': 'Base_ER',
    'LowSpeaker': 'Low_Speaker', 'LowSpeakers': 'Low_Speaker',
    'H06m': 'H_06m',
    'Searchlight101': 'Searchlight_101',
    'PalatkaLow': 'Palatka_Low',
    'CampTentA': 'Camp_Tent_A', 'CampTentB': 'Camp_Tent_B', 'CampTentC': 'Camp_Tent_C',
}

# 拼写修正
SPELLING_FIXES = [
    ('shabao', 'Sandbags'), ('Shabao', 'Sandbags'),
    ('Barrer', 'Barrier'), ('barrer', 'barrier'),
    ('Bunke_', 'Bunker_'), ('BunkeD', 'BunkerD'),
    ('Grounp', 'Group'), ('grounp', 'group'),
    ('Sandbabs', 'Sandbags'),
    ('Ttench', 'Trench'),
    ('low_speaker', 'low_Speaker'),  # speaker→Speaker（仍在 low_ 后面）
]

# 拼音名不动的词根
PINYIN_ROOTS = {
    'jiqiangyanti', 'gaoshejiqiangyanti', 'zakou', 'wuzakou',
    'zhichengjia', 'zhanhaoyanti', 'shu', 'zhuanjie', 'zuhe', 'yanti',
    'deguo', 'yingmei',
    'balki', 'krisha', 'osnova', 'prost', 'shtory', 'virezka', 'palatka',
    'mirador',
}


def has_chinese(s: str) -> bool:
    return bool(re.search(r'[\u4e00-\u9fff]', s))


def has_pinyin(name_lower: str) -> bool:
    for pw in PINYIN_ROOTS:
        if pw in name_lower:
            return True
    return False


def apply_compound_splits(stem: str) -> str:
    for key in sorted(COMPOUND_SPLITS.keys(), key=len, reverse=True):
        if key in stem:
            stem = stem.replace(key, COMPOUND_SPLITS[key])
    return stem


def normalize_meters(s: str) -> str:
    # H1m→H_1m, H120→H_120（不补零）
    s = re.sub(r'\b([A-Z])(\d+)([Mm]?)\b', lambda m: f'{m.group(1)}_{m.group(2)}{m.group(3)}', s)
    s = re.sub(r'\bL(\d+)\b', r'L_\1', s)
    return s


def extract_variant(name: str) -> tuple:
    """提取 #变体"""
    m = re.search(r'#([\w.]+)$', name)
    if m:
        base = name[:m.start()]
        variant = m.group(1)
        variant = apply_compound_splits(variant)
        variant = re.sub(r'_x$', '_X', variant, flags=re.I)
        variant = re.sub(r'_xx$', '_Xx', variant, flags=re.I)
        return base, variant
    return name, ''


def apply_rules(filepath: Path, root: Path) -> tuple:
    """返回 (new_rel, note) 或 (None, '')"""
    rel = str(filepath.relative_to(root)).replace('\\', '/')
    stem = filepath.stem
    ext = filepath.suffix.lower()
    parent = str(Path(rel).parent) if Path(rel).parent != Path('.') else ''
    notes = []

    if filepath.name.endswith('.meta') or ext in ('.json', '.md', '.sample'):
        return None, ''
    if ext not in META_EXTS:
        return None, ''

    # ── 目录结构调整 ──
    new_parent = parent

    # 1. Bunker_YXY20250414/Group/ → Groups/
    if parent.startswith('Bunker_YXY20250414/Group'):
        new_parent = parent.replace('Bunker_YXY20250414/Group', 'Groups')
        notes.append('Group→Groups 移目录')

    # 2. Trench/Type-01_wooden/ → Trench_Wooden_01/
    if parent.startswith('Trench/Type-01_wooden'):
        new_parent = parent.replace('Trench/Type-01_wooden', 'Trench_Wooden_01')
        notes.append('上移一级→Trench_Wooden_01')

    # 3. Mdoel/ → Model/
    if '/Mdoel/' in new_parent:
        new_parent = new_parent.replace('/Mdoel/', '/Model/')
        notes.append('Mdoel→Model 目录修正')
    elif '/Mdoel' in new_parent and new_parent.endswith('/Mdoel'):
        new_parent = new_parent[:-5] + 'Model'
        notes.append('Mdoel→Model 目录修正')

    # ── 拼音检查 ──
    is_pinyin = has_pinyin(stem.lower())
    if is_pinyin:
        notes.append('拼音/外来语词根，不拆分')

    # ── 拼音名里 # 换成 _ ──
    if is_pinyin and '#' in stem:
        stem = stem.replace('#', '_')

    # ── 拼写修正 ──
    for old, new in SPELLING_FIXES:
        if old in stem:
            stem = stem.replace(old, new)
            if '拼写修正' not in notes:
                notes.append('拼写修正')

    # ── 大小写修正 ──
    if stem.lower().startswith('speaker') and stem[0].islower():
        stem = 'Speaker' + stem[7:]
        if '大小写修正' not in notes:
            notes.append('大小写修正')
    if stem.lower().startswith('searchlight') and stem[0].islower():
        stem = 'Searchlight' + stem[11:]

    # ── 特殊覆盖（RoadSentry） ──
    if parent.startswith('RoadSentry/Prefab'):
        if stem == 'Props_RoadCross_02':
            return new_parent + '/Military_Road_Cross_01' + ext, '特殊覆盖'
        if stem == 'Props_RoadCross_03_yingmei':
            return new_parent + '/Military_Sentry_Box_Allies' + ext, '特殊覆盖'

    # ── 去 #变体 ──
    if not is_pinyin:
        stem, variant = extract_variant(stem)
    else:
        variant = ''

    # ── 去 Type## ──
    stem = re.sub(r'[_]?Type[_-]?\d+[_]?', '_', stem)
    stem = re.sub(r'^Type\d+_?', '', stem)
    stem = re.sub(r'_+', '_', stem).strip('_')

    # ── PascalCase 拆分 ──
    if not is_pinyin:
        stem = apply_compound_splits(stem)

    # ── 数字规范化 ──
    stem = normalize_meters(stem)

    # ── _x/_xx 后缀 ──
    stem = re.sub(r'_xx(\d+)$', lambda m: f'_Xx_{int(m.group(1)):02d}', stem, flags=re.I)
    stem = re.sub(r'_xx(\d+)_', lambda m: f'_Xx_{int(m.group(1)):02d}_', stem, flags=re.I)
    stem = re.sub(r'_x$', '_X', stem, flags=re.I)
    stem = re.sub(r'_x_', '_X_', stem, flags=re.I)

    # ── 末尾编号（保持原宽度） ──
    stem = re.sub(r'_([A-Za-z]+)(\d+)_', lambda m: f'_{m.group(1)}_{int(m.group(2)):02d}_', stem)
    stem = re.sub(r'_([A-Za-z]+)(\d+)$', lambda m: f'_{m.group(1)}_{int(m.group(2)):02d}', stem)

    # ── 清理 ──
    stem = re.sub(r'_+', '_', stem).strip('_')

    # ── 拼装变体 ──
    if variant:
        stem += '_' + variant

    # ── 加前缀 ──
    prefix = 'Mat_' if ext == '.mat' else 'Military_'
    stem_lower = stem.lower()

    if prefix == 'Mat_':
        stem = re.sub(r'^Mat_', '', stem, flags=re.I)
        stem = 'Mat_' + stem
    else:
        stem = re.sub(r'^Mat_', '', stem, flags=re.I)
        stem = re.sub(r'^Props_', '', stem, flags=re.I)
        if not stem_lower.startswith('military_'):
            stem = 'Military_' + stem

    stem = re.sub(r'^military_', 'Military_', stem, flags=re.I)
    stem = re.sub(r'^mat_', 'Mat_', stem, flags=re.I)

    # ── .FBX → .fbx ──
    ext_out = ext if ext != '.fbx' else '.fbx'

    new_rel = (new_parent + '/' + stem + ext_out) if new_parent else (stem + ext_out)

    if new_rel != rel:
        return new_rel, '；'.join(notes)
    return None, ''


def main():
    confirm = '--confirm' in sys.argv
    root = MILITARY.resolve()
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        return 1

    print("🔍 扫描文件...")
    mappings = []
    for fp in sorted(root.rglob('*')):
        if not fp.is_file() or '.git' in fp.parts:
            continue
        r, n = apply_rules(fp, root)
        if r:
            rel = str(fp.relative_to(root)).replace('\\', '/')
            mappings.append((rel, r, fp.suffix.lower().lstrip('.'), n))

    if not mappings:
        print("✅ 全部合规，无需改名")
        return 0

    # 冲突检测
    targets = defaultdict(list)
    for o, n, t, note in mappings:
        targets[n].append(o)
    conflicts = {k: v for k, v in targets.items() if len(v) > 1}

    print(f"\n📊 需改名: {len(mappings)} 项  |  冲突: {len(conflicts)}")

    # 备注统计
    note_ct = defaultdict(int)
    for *_, n in mappings:
        if n:
            for p in n.split('；'):
                note_ct[p] += 1
    for k, v in sorted(note_ct.items()):
        print(f"   {k}: {v} 项")

    # 映射表
    md = root / 'military-rename-v1-mapping.md'
    lines = [
        '# Military 重命名映射表 (V1)', '',
        f'- **根目录**: `{root}`',
        f'- **时间**: {datetime.now(timezone.utc).isoformat()}', '',
        '## 规则', '',
        '| # | 规则 |',
        '|---|------|',
        '| 1 | `.prefab`/`.fbx`/贴图 → `Military_` 前缀，`.mat` → `Mat_` |',
        '| 2 | 删除 `Type##`/`SceneStatic` |',
        '| 3 | PascalCase 拆分（复合词） |',
        '| 4 | `#`变体保留 |',
        '| 5 | 数字规范化（不补零） |',
        '| 6 | `.meta` 同步 |',
        '| 7 | 拼音名/中文目录不动 |',
        '', '## 拼写修正', '',
        '| 原文 | 改为 |',
        '|------|------|',
        '| shabao | Sandbags |',
        '| Barrer | Barrier |',
        '| Mdoel | Model（目录） |',
        '| Grounp | Group |',
        '| Sandbabs | Sandbags |',
        '| Bunke | Bunker |',
        '| Ttench | Trench |',
        '', '## 全部映射', '',
        '| 子目录 | 原名 | 新名 | 备注 |',
        '|--------|------|------|------|',
    ]
    for old, new, ftype, note in sorted(mappings):
        parts = old.rsplit('/', 1)
        folder = parts[0] if len(parts) > 1 else ''
        orig = parts[-1]
        new_name = new.rsplit('/', 1)[-1]
        cf = ' ⚠️' if new in conflicts else ''
        lines.append(f'| {folder}/ | {orig} | {new_name}{cf} | {note} |')

    md.write_text('\n'.join(lines), encoding='utf-8')
    print(f"\n📄 映射表: {md}")

    if conflicts:
        print(f"\n❌ 有冲突，跳过执行")
        for t, srcs in sorted(conflicts.items()):
            print(f"  {t}:")
            for s in srcs:
                print(f"    ← {s}")
        return 1

    if confirm:
        import shutil
        print("\n⚡ 执行改名...")
        subprocess.run(['python3', 'scripts/unity-file-manager.py', 'snapshot', str(root),
                       '-m', 'Military V1 改名前快照'], check=True, cwd=Path(__file__).parent.parent)

        ok = 0
        for old_rel, new_rel, ftype, note in sorted(mappings):
            src = root / old_rel
            dst = root / new_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                src.rename(dst)
                ok += 1
                # .meta 同步
                meta_src = root / (old_rel + '.meta')
                meta_dst = root / (new_rel + '.meta')
                if meta_src.exists():
                    meta_dst.parent.mkdir(parents=True, exist_ok=True)
                    meta_src.rename(meta_dst)
            except Exception as e:
                print(f"  ❌ {old_rel}: {e}")

        subprocess.run(['python3', 'scripts/unity-file-manager.py', 'snapshot', str(root),
                       '-m', 'Military V1 改名后快照'], check=True, cwd=Path(__file__).parent.parent)
        subprocess.run(['python3', 'scripts/unity-file-manager.py', 'verify', str(root)],
                      check=False, cwd=Path(__file__).parent.parent)
        print(f"\n✅ 改名: {ok} 文件")
    else:
        print(f"\n💡 dry-run。加 --confirm 执行")

    return 0


if __name__ == '__main__':
    sys.exit(main())
