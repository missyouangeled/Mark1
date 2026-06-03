#!/usr/bin/env python3
"""
模型批量重命名（非单位/人物/机甲/坦克/武器）
规范: docs/项目资产命名与整理规范.md
"""

import os, sys, re, argparse

BASE = "/media/missyouangeled/WD_BLACK/Project/Project/Assets"

# ─── 工具函数 ─────────────────────────

def rename_file(filepath, new_name, dry_run=True, rename_log=None):
    dirname = os.path.dirname(filepath)
    oldname = os.path.basename(filepath)
    ext = os.path.splitext(oldname)[1]
    newname = new_name + ext
    new_path = os.path.join(dirname, newname)
    if new_path == filepath:
        return None
    if dry_run:
        print(f"  [DRY] {oldname} → {newname}")
    else:
        if os.path.exists(new_path):
            print(f"  ⚠ 跳过: {newname}")
            return None
        os.rename(filepath, new_path)
        meta_old = filepath + '.meta'
        meta_new = new_path + '.meta'
        if os.path.exists(meta_old):
            if os.path.exists(meta_new):
                os.remove(meta_old)
            else:
                os.rename(meta_old, meta_new)
        print(f"  ✓ {oldname} → {newname}")
        if rename_log is not None:
            rename_log.append(f"{oldname}  →  {newname}")
    return (filepath, new_path)


def write_rename_log(dirpath, rename_log, label):
    if not rename_log:
        return
    log_path = os.path.join(dirpath, 'rename_log.txt')
    with open(log_path, 'w') as f:
        f.write(f"# {label} 重命名日志\n")
        f.write("# 时间: 2026-06-03\n\n")
        for entry in rename_log:
            f.write(entry + '\n')
    print(f"  📝 rename_log.txt: {len(rename_log)} 条")


# ─── Building_Standard 命名公式 ───────

def clean_building_name(name):
    damage = ''
    name = re.sub(r'\s+', '_', name)
    m = re.search(r'(_xx|_x)(\s+Variant|\s*$)', name, re.IGNORECASE)
    if m:
        damage = '_xx' if m.group(1).lower() == '_xx' else '_X'
        name = name[:m.start()] + name[m.end():]
    name = re.sub(r'\s+Variant\s*(\d+)\s*$', r'_Variant_\1', name)
    name = re.sub(r'\s+Variant\s*$', '', name)
    removals = [
        (r'_uv_', '_'), (r'_uv$', ''),
        (r'_LODSta_', '_'), (r'_LODSta$', ''), (r'_LODSta#', '#'),
        (r'_LOD_Standard_', '_'), (r'_LOD_Standard$', ''), (r'_LOD_Standard#', '#'),
        (r'_LOD_Sta_', '_'), (r'_LOD_Sta$', ''), (r'_LOD_Sta#', '#'),
        (r'_LOD#', '#'), (r'_LOD_', '_'), (r'_LOD$', ''),
        (r'_LODS_', '_'), (r'_LODS$', ''), (r'_LODS#', '#'),
        (r'_FJL\d*', ''), (r'_MJ$', ''), (r'_MJ_', '_'),
        (r'_YXY\d+', ''), (r'_WS\d+', ''),
        (r'_Sta_', '_'), (r'_Sta$', ''),
        (r'_Standard_\d+_', '_'), (r'_Standard_\d+$', ''), (r'_Standard_', '_'),
        (r'_Standard$', ''), (r'_Standard#', '#'),
        (r'_xable$', '_X'),
    ]
    for pat, repl in removals:
        name = re.sub(pat, repl, name, flags=re.IGNORECASE)
    name = re.sub(r'_+', '_', name).strip('_')
    if damage:
        name = name + damage
    parts = name.split('_')
    parts = [p[0].upper() + p[1:] if p else p for p in parts]
    return '_'.join(parts)


# ─── AssetNature 命名清理 ─────────────

VENDOR_PATTERNS = [
    r'_sjll[Xx]_?', r'_qilgP\d?_?', r'_vmcobd0ja_?', r'_wfzobb2ia_?',
    r'_wk2oaeyqx_?', r'_kicj[Mm]\d?_?', r'_HDRP_?',
    r'_ms_?$', r'_raw_?$', r'_3dplant_ms_?$',
]

def clean_nature_name(name):
    name = name.replace(' ', '_')
    for pat in VENDOR_PATTERNS:
        name = re.sub(pat, '_', name, flags=re.IGNORECASE)
    name = re.sub(r'_Prefab$', '', name)
    name = re.sub(r'^P_', '', name)
    name = re.sub(r'^prefab_', '', name, flags=re.IGNORECASE)
    # 通用 PascalCase：每部分首字母大写（保留已有的如LOD/Var/Med等）
    if '_' in name and not name.isupper():
        parts = name.split('_')
        new_parts = []
        for p in parts:
            if p and p[0].islower():
                p = p[0].upper() + p[1:]
            new_parts.append(p)
        name = '_'.join(new_parts)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


# ─── 场景物件命名清理 ────────────────

SCENE_CLEAN_PATTERNS = [
    (r'_YXY\d+', ''),
    (r'_WS\d+', ''),
    (r'_FJL\d*', ''),
    (r'_MJ$', ''),
    (r'_MJ_', '_'),
    (r'_LOD$', ''),  # 单独的 LOD 末尾
    (r'^P_en_', ''),  # P_en_ 前缀
]

TYPO_FIXES = {
    'gorup': 'Group', 'Grounp': 'Group', 'Groiup': 'Group',
    'grounp': 'group', 'groiup': 'group',
    'Lod': 'LOD', 'lod': 'LOD',
}

def clean_scene_name(name):
    name = name.replace(' ', '_')
    for pat, repl in SCENE_CLEAN_PATTERNS:
        name = re.sub(pat, repl, name, flags=re.IGNORECASE)
    name = re.sub(r'_+', '_', name).strip('_')
    # 修复常见拼写错误
    for wrong, fix in TYPO_FIXES.items():
        name = name.replace(wrong, fix)
    # 移除 Type- 前缀 (Props_Haystack_Type-01 → Props_Haystack_01)
    name = re.sub(r'_Type-0?', '_', name)
    # PascalCase
    parts = name.split('_')
    parts = [p[0].upper() + p[1:] if p and p[0].islower() else p for p in parts]
    return '_'.join(parts)


def process_scene_category(cat_name, dry_run=True):
    base = os.path.join(BASE, "AssetScene/SceneModels", cat_name)
    if not os.path.isdir(base):
        return []
    print(f"\n  📁 {cat_name}")
    rename_log = [] if not dry_run else None
    renamed = []
    for dirpath, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.meta'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.prefab', '.fbx', '.obj', '.blend'):
                continue
            fp = os.path.join(dirpath, f)
            name = os.path.splitext(f)[0]
            nn = clean_scene_name(name)
            if nn != name:
                r = rename_file(fp, nn, dry_run, rename_log)
                if r:
                    renamed.append(r)
    write_rename_log(base, rename_log, cat_name)
    print(f"    {len(renamed)} 个文件")
    return renamed


def process_scene_models(dry_run=True):
    """处理所有场景物件模型（不含建筑和Unit）"""
    cats = ['Military', 'Props', 'Farmland', 'Fence', 'FenceAndPierWooden',
            'Industrial', 'Wall', 'Railway', 'RoadSide', 'SceneStatic',
            'ChurchAndGrave', 'Fumiture',
            'Building_Module']  # Building_Module 基本规范，只做轻度清理
    print(f"\n{'='*60}")
    print(f"🏗️  场景物件模型\n")
    total = 0
    for cat in cats:
        r = process_scene_category(cat, dry_run)
        total += len(r)
    print(f"\n  场景物件合计: {total} 个文件")
    return total

def process_building_standard(dry_run=True):
    base = os.path.join(BASE, "AssetScene/SceneModels/Building_Standard")
    print(f"\n{'='*60}\n🏠 Building_Standard\n")
    rename_log = [] if not dry_run else None
    renamed = []
    for dirpath, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.meta'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.prefab', '.fbx', '.obj', '.blend'):
                continue
            fp = os.path.join(dirpath, f)
            name = os.path.splitext(f)[0]
            nn = clean_building_name(name)
            if nn != name:
                r = rename_file(fp, nn, dry_run, rename_log)
                if r:
                    renamed.append(r)
    write_rename_log(base, rename_log, "Building_Standard")
    print(f"  共 {len(renamed)} 个文件\n")
    return renamed


def process_asset_nature(dry_run=True):
    base = os.path.join(BASE, "AssetNature")
    print(f"\n{'='*60}\n🌿 AssetNature\n")
    rename_log = [] if not dry_run else None
    renamed = []
    for dirpath, dirs, files in os.walk(base):
        for f in files:
            if f.endswith('.meta'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.prefab', '.fbx', '.obj', '.blend'):
                continue
            fp = os.path.join(dirpath, f)
            name = os.path.splitext(f)[0]
            nn = clean_nature_name(name)
            if nn != name:
                r = rename_file(fp, nn, dry_run, rename_log)
                if r:
                    renamed.append(r)
    write_rename_log(base, rename_log, "AssetNature")
    print(f"  共 {len(renamed)} 个文件\n")
    return renamed


# ─── 入口 ─────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--category', choices=['building_std','nature','scene','all'], default='all')
    args = parser.parse_args()
    dry_run = not args.execute
    print("🔍 预览模式\n" if dry_run else "⚠️ 执行模式\n")

    if args.category in ('building_std', 'all'):
        process_building_standard(dry_run)
    if args.category in ('scene', 'all'):
        process_scene_models(dry_run)

    if dry_run:
        print(f"{'='*60}")
        print("确认后执行: python3 scripts/rename-models.py --execute")


if __name__ == '__main__':
    main()
