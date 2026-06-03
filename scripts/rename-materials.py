#!/usr/bin/env python3
"""
批量重命名材质文件，按项目命名规范执行。
规范来源: docs/项目资产命名与整理规范.md

策略：
1. 贴图后缀标准化（Albedo→Col, Normal→N, MaskMap→Mask 等）
2. 材质球加 Mat_ 前缀
3. 文件名空格→下划线
4. 不做激进清理（避免误删有意义单词）
"""

import os, sys, shutil, re, argparse
from collections import OrderedDict

BASE = "/media/missyouangeled/WD_BLACK/Project/Project/Assets"

# 贴图后缀映射（按长度降序，长后缀优先匹配）
MAP_SUFFIX = OrderedDict([
    ('_BaseColorAlpha', '_Col'),
    ('_BaseColor', '_Col'),
    ('_BaseCol2', '_Col'),
    ('_BaseCol', '_Col'),
    ('_Basecolor', '_Col'),
    ('_Albedo', '_Col'),
    ('_albedo', '_Col'),
    ('_RoughnessMask1', '_Mask'),
    ('_RoughnessMask6', '_Mask'),
    ('_RoughnessMask9', '_Mask'),
    ('_RoughnessMask12', '_Mask'),
    ('_MaskMap', '_Mask'),
    ('_Mask', '_Mask'),
    ('_mask', '_Mask'),
    ('_Normal_OS', '_N'),
    ('_normal_OS', '_N'),
    ('_Normals', '_N'),
    ('_Normal', '_N'),
    ('_normal', '_N'),
    ('_NM', '_N'),
    ('_NRM', '_N'),
    ('_Height', '_H'),
    ('_height', '_H'),
    ('_Hight', '_H'),
    ('_Glossiness', '_Gloss'),
    ('_GLOSS', '_Gloss'),
    ('_Roughness', '_Rough'),
    ('_Metallic', '_Metal'),
    ('_Smoothness', '_Smooth'),
    ('_Translucency', '_Trans'),
    ('_Subsurface', '_SubSurf'),
    ('_Specular', '_Spec'),
    ('_spec', '_Spec'),
    ('_Detail', '_Detail'),
    ('_Detial', '_Detail'),
    ('_LayerMask', '_LayerMask'),
    ('_Layer', '_Layer'),
    ('_AO', '_AO'),
    ('_SM', '_SM'),
    ('_TGA', '_Col'),
    ('_COL', '_Col'),
    ('_Color', '_Col'),
    ('_color', '_Col'),
    ('_BC', '_Col'),
    ('_BC2', '_Col'),
    ('_D', '_Col'),
    ('_M', '_Mask'),
])

# 需要清理的特定无意义前缀/后缀
STRIP_PREFIXES = [
    'TexturesCom_',
]

STRIP_SUFFIXES = [
    '_4K-PNG', '_2k_jpg', '_2K', '_4K', '_1K', '_6K', '_8K',
    '_seamless_',
]

def clean_basename(name):
    """清理材质名称"""
    # 去除特定前缀
    for pfx in STRIP_PREFIXES:
        if name.startswith(pfx):
            name = name[len(pfx):]
    
    # 去除特定后缀
    for sfx in STRIP_SUFFIXES:
        if sfx in name:
            name = name.replace(sfx, '')
    
    # 连续下划线合并
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')
    
    # 首字母大写（保留已有大写）
    parts = name.split('_')
    parts = [p[0].upper() + p[1:] if p else p for p in parts]
    name = '_'.join(parts)
    
    return name


def rename_texture(filepath, dry_run=True, rename_log=None):
    """重命名单张贴图文件，返回 (old_path, new_path) 或 None"""
    dirname = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    
    new_name = name
    changed = False
    
    # 1. 匹配后缀映射
    for old_suf, new_suf in MAP_SUFFIX.items():
        if new_name.endswith(old_suf):
            new_name = new_name[:-len(old_suf)] + new_suf
            changed = True
            break
    
    # 2. 清理无意义前缀/后缀
    cleaned = clean_basename(new_name)
    if cleaned != new_name:
        new_name = cleaned
        changed = True
    
    # 3. 空格→下划线
    if ' ' in new_name:
        new_name = new_name.replace(' ', '_')
        changed = True
    
    if not changed:
        return None
    
    new_filename = new_name + ext_lower
    new_path = os.path.join(dirname, new_filename)
    
    if new_path == filepath:
        return None
    
    if dry_run:
        print(f"  [DRY] {filename} → {new_filename}")
    else:
        meta_old = filepath + '.meta'
        meta_new = new_path + '.meta'
        if os.path.exists(new_path):
            print(f"  ⚠ 跳过（目标已存在）: {new_filename}")
            return None
        os.rename(filepath, new_path)
        if os.path.exists(meta_old):
            if os.path.exists(meta_new):
                os.remove(meta_old)
            else:
                os.rename(meta_old, meta_new)
        print(f"  ✓ {filename} → {new_filename}")
        if rename_log is not None:
            rename_log.append(f"{filename}  →  {new_filename}")
    
    return (filepath, new_path)


def rename_material(filepath, dry_run=True, rename_log=None):
    """材质球加 Mat_ 前缀，空格→下划线"""
    dirname = os.path.dirname(filepath)
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    
    new_name = name.replace(' ', '_')
    if not new_name.startswith('Mat_'):
        new_name = 'Mat_' + new_name
    else:
        new_name = 'Mat_' + new_name[4:].replace(' ', '_')
    
    if new_name == name:
        return None
    
    new_filename = new_name + ext
    new_path = os.path.join(dirname, new_filename)
    
    if new_path == filepath:
        return None
    
    if dry_run:
        print(f"  [DRY] {filename} → {new_filename}")
    else:
        meta_old = filepath + '.meta'
        meta_new = new_path + '.meta'
        if os.path.exists(new_path):
            print(f"  ⚠ 跳过（目标已存在）: {new_filename}")
            return None
        os.rename(filepath, new_path)
        if os.path.exists(meta_old):
            if os.path.exists(meta_new):
                os.remove(meta_old)
            else:
                os.rename(meta_old, meta_new)
        print(f"  ✓ {filename} → {new_filename}")
        if rename_log is not None:
            rename_log.append(f"{filename}  →  {new_filename}")
    
    return (filepath, new_path)


def process_dir(dirpath, dry_run=True, rename_log=None):
    """处理一个目录下的所有贴图和材质球"""
    if not os.path.isdir(dirpath):
        return []
    
    all_files = [f for f in os.listdir(dirpath) 
                if not f.endswith('.meta') and os.path.isfile(os.path.join(dirpath, f))]
    
    tex_exts = {'.tif','.tiff','.png','.jpg','.jpeg','.tga','.exr','.hdr','.psd'}
    renamed = []
    
    for f in all_files:
        fp = os.path.join(dirpath, f)
        ext = os.path.splitext(f)[1].lower()
        
        if ext in tex_exts:
            result = rename_texture(fp, dry_run, rename_log)
        elif ext == '.mat':
            result = rename_material(fp, dry_run, rename_log)
        else:
            continue
        
        if result:
            renamed.append(result)
    
    return renamed


def walk_and_process(root_dir, dry_run=True):
    """递归处理目录树，返回 (renamed_list, rename_log)"""
    renamed = []
    rename_log = [] if not dry_run else None
    for dirpath, dirs, files in os.walk(root_dir):
        r = process_dir(dirpath, dry_run, rename_log)
        renamed.extend(r)
    if rename_log:
        log_path = os.path.join(root_dir, 'rename_log.txt')
        with open(log_path, 'w') as f:
            f.write(f"# 重命名日志 — {os.path.basename(root_dir)}\n")
            f.write(f"# 时间: 2026-06-03\n")
            f.write(f"# 共 {len(rename_log)} 条\n\n")
            for entry in rename_log:
                f.write(entry + '\n')
        print(f"\n  📝 rename_log.txt: {len(rename_log)} 条")
    return renamed


# ─── 分类入口 ───────────────────────────────────────

def process_rubble(dry_run=True):
    path = os.path.join(BASE, "AssetOther", "Building _DBK", "Rubble", "Material")
    print(f"\n{'='*60}\n🏚️  砖石瓦砾: {path}")
    return walk_and_process(path, dry_run)


def process_wood2(dry_run=True):
    path = os.path.join(BASE, "AssetNature", "Other", "Wood2")
    print(f"\n{'='*60}\n🪵 木材/树枝/树桩: {path}")
    return walk_and_process(path, dry_run)


def process_doodats(dry_run=True):
    path = os.path.join(BASE, "AssetNature", "Other", "Doodats_ForestWinter")
    print(f"\n{'='*60}\n🌲 Doodats_ForestWinter: {path}")
    return walk_and_process(path, dry_run)


def process_rocks_fw(dry_run=True):
    path = os.path.join(BASE, "AssetNature", "Other", "Rocks_ForestWinter")
    print(f"\n{'='*60}\n🪨 Rocks_ForestWinter: {path}")
    return walk_and_process(path, dry_run)


def process_materials_standard(dry_run=True):
    path = os.path.join(BASE, "AssetScene", "SceneMaterials", "Materials_Standard")
    print(f"\n{'='*60}\n🏗️  Materials_Standard: {path}")
    return walk_and_process(path, dry_run)


def process_terrain(dry_run=True):
    path = os.path.join(BASE, "AssetScene", "SceneMaterials", "Terrain_Materials")
    print(f"\n{'='*60}\n⛰️  Terrain_Materials: {path}")
    return walk_and_process(path, dry_run)


CATEGORIES = {
    'rubble': ('砖石瓦砾', process_rubble),
    'wood2': ('木材/树枝/树桩', process_wood2),
    'doodats': ('Doodats_ForestWinter', process_doodats),
    'rocks_fw': ('Rocks_ForestWinter', process_rocks_fw),
    'materials_standard': ('Materials_Standard', process_materials_standard),
    'terrain': ('Terrain_Materials', process_terrain),
}


def main():
    parser = argparse.ArgumentParser(description='材质批量重命名')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='预览模式（默认）')
    parser.add_argument('--execute', action='store_true',
                       help='正式执行重命名')
    parser.add_argument('--category', choices=list(CATEGORIES.keys()) + ['all'],
                       default='all', help='处理的分类')
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("🔍 预览模式 — 不会实际改动文件\n")
    else:
        print("⚠️  正式执行模式 — 将实际重命名文件！\n")
        print("   建议先对单个分类执行: --category rubble --execute")
    
    total = 0
    
    for cat_name, (cat_label, cat_func) in CATEGORIES.items():
        if args.category in (cat_name, 'all'):
            r = cat_func(dry_run)
            total += len(r)
    
    print(f"\n{'='*60}")
    if dry_run:
        print(f"📋 预览完毕，共 {total} 个文件待重命名")
        print(f"   确认无误后运行:")
        print(f"   python3 scripts/rename-materials.py --execute --category rubble    # 单类")
        print(f"   python3 scripts/rename-materials.py --execute --category all       # 全部")
    else:
        print(f"✅ 重命名完毕，共处理 {total} 个文件")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
