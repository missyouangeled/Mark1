#!/usr/bin/env python3
"""
模型批量重命名 v2 — 按新规范执行。
范围：AssetNature + AssetOther + AssetScene（排除Unit/中的非拖拉机项）
"""

import os, sys, re, argparse

BASE = "/media/missyouangeled/WD_BLACK/Project/Assets"
MODEL_EXT = {'.fbx','.obj','.prefab','.blend','.mesh','.3ds'}

# ═══════════════════════════════════════════════════
# Unit/ 目录中排除的子目录（只留拖拉机）
# ═══════════════════════════════════════════════════

UNIT_EXCLUDE = {
    'BeetleFusca', 'Car_Ger_DKW_F8', 'Cart_01', 'Cart_02', 'Cart_03', 'Cart_04',
    'Crash', 'Field_Kitchen_WW2_YXY241231', 'Old Ford Model T', 'Opel',
    'Train_German', 'Truck01', 'Truck_Type-06', 'tuoban',
}

# ═══════════════════════════════════════════════════
# 复合词拆分
# ═══════════════════════════════════════════════════

COMPOUNDS = [
    ('BronzeOld', 'Bronze_Old'), ('BronzeNew', 'Bronze_New'),
    ('ItalianOld', 'Italian_Old'), ('ItalianNew', 'Italian_New'),
    ('SquareOld', 'Square_Old'), ('SquareNew', 'Square_New'),
    ('RoundOld', 'Round_Old'), ('RoundNew', 'Round_New'),
    ('PantileOld', 'Pantile_Old'),
    ('AsbestosOndulated', 'Asbestos_Ondulated'),
    ('WoodPlanks', 'Wood_Planks'),
    ('CorrugatedRusted', 'Corrugated_Rusted'),
    ('LightRust', 'Light_Rust'), ('MedRust', 'Med_Rust'), ('HeavyRust', 'Heavy_Rust'),
    ('BrickIndustrial', 'Brick_Industrial'),
    ('ConcreteFenceSoviet', 'Fence_Concrete_Soviet'),
    ('SmallWoodenShingles', 'Roof_Shingle_Wood'),
    ('RidgeTille', 'Ridge_Tile'),
    ('castle_wall_slates', 'Wall_Castle_Slate'),
    ('concrete_floor', 'Floor_Concrete'),
    ('rusty_metal', 'Metal_Rusty'),
    ('grey_roof_tiles', 'Roof_Grey_Tile'),
]

# ═══════════════════════════════════════════════════
# 需要清除的内容
# ═══════════════════════════════════════════════════

STRIP_PREFIXES = ['TexturesCom_', 'texturescom_', 'TCom_', 'tcom_']

STRIP_PATTERNS = [
    r'_1[Kk]', r'_2[Kk]', r'_4[Kk]', r'_6[Kk]', r'_8[Kk]',
    r'_512', r'_1024', r'_2048', r'_4096',
    r'_\d+x\d+[a-z]*_\d+', r'_\d[\.,]?\d*x\d[\.,]?\d*[a-z]*',
]

# ═══════════════════════════════════════════════════
# 编号修复：把尾部的 01_01 这种重复改成 _(区分词)
# ═══════════════════════════════════════════════════

def fix_duplicate_number(name):
    """Props_Box_01_01 → Props_Box_01"""
    m = re.match(r'^(.+?_\d{2,})_(\d{2,})$', name)
    if m:
        return m.group(1)
    return name

def pad_numbers(name):
    """数字补零"""
    def repl(m):
        word = m.group(1)
        num = m.group(2)
        return f'{word}_{int(num):02d}'
    return re.sub(r'(?<=[a-zA-Z])([a-zA-Z_]+?)(\d{1,2})(?![0-9])', repl, name)

def strip_junk(name):
    for pfx in STRIP_PREFIXES:
        if name.lower().startswith(pfx.lower()):
            name = name[len(pfx):]
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)
    name = re.sub(r'_+', '_', name).strip('_')
    return name

def split_compound(name):
    for old, new in COMPOUNDS:
        if name == old or name.startswith(old + '_') or name == old.lower() or name.lower().startswith(old.lower() + '_'):
            name = new + name[len(old):]
    return name

def camel_case(name):
    name = name.replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    parts = name.split('_')
    new_parts = []
    for p in parts:
        if not p:
            continue
        if re.match(r'^\d', p):
            new_parts.append(p)
        elif p.startswith('#'):
            new_parts.append(p)
        elif p.startswith('('):
            new_parts.append(p)
        else:
            new_parts.append(p[0].upper() + p[1:])
    return '_'.join(new_parts)

def clean_model_name(name):
    original = name
    
    # 保留 Unit_/Props_ 等已知前缀
    known_prefixes = ['Unit_', 'Props_', 'Mat_', 'SM_', 'T_', 'M_']
    prefix = ''
    for kp in known_prefixes:
        if name.startswith(kp):
            prefix = kp
            name = name[len(kp):]
            break
    
    name = strip_junk(name)
    name = split_compound(name)
    name = fix_duplicate_number(name)
    name = pad_numbers(name)
    name = camel_case(name)
    
    result = prefix + name
    return result if result != original else original


def rename_file(filepath, new_basename, dry_run=True, rename_log=None):
    dirname = os.path.dirname(filepath)
    oldname = os.path.basename(filepath)
    ext = os.path.splitext(oldname)[1]
    newname = new_basename + ext
    new_path = os.path.join(dirname, newname)
    
    if new_path == filepath:
        return None
    
    if dry_run:
        print(f"  [DRY] {oldname} → {newname}")
    else:
        if os.path.exists(new_path):
            print(f"  ⚠ 跳过（目标已存在）: {newname}")
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


def should_exclude(dirpath):
    """判断目录是否在排除列表中（Unit/中非拖拉机子目录）"""
    parts = dirpath.replace(BASE, '').strip('/').split('/')
    if 'Unit' in parts:
        idx = parts.index('Unit')
        if idx + 1 < len(parts):
            sub = parts[idx + 1]
            if sub in UNIT_EXCLUDE:
                return True
    return False


def process_dir(root_dir, dry_run=True):
    if not os.path.isdir(root_dir):
        print(f"  ❌ 路径不存在: {root_dir}")
        return []
    
    renamed = []
    rename_log = [] if not dry_run else None
    
    for dirpath, dirs, files in os.walk(root_dir):
        if should_exclude(dirpath):
            dirs.clear()
            continue
        
        for f in files:
            if f.endswith('.meta'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in MODEL_EXT:
                continue
            fp = os.path.join(dirpath, f)
            name = os.path.splitext(f)[0]
            new_name = clean_model_name(name)
            if new_name != name:
                r = rename_file(fp, new_name, dry_run, rename_log)
                if r:
                    renamed.append(r)
    
    if rename_log and renamed:
        log_path = os.path.join(root_dir, 'model_rename_log.txt')
        with open(log_path, 'w') as f:
            f.write(f"# 模型重命名日志 — {os.path.basename(root_dir)}\n")
            f.write("# 时间: 2026-06-03\n")
            f.write(f"# 共 {len(rename_log)} 条\n\n")
            for entry in rename_log:
                f.write(entry + '\n')
        print(f"\n  📝 model_rename_log.txt: {len(rename_log)} 条")
    
    return renamed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--dir', type=str, default='',
                       help='指定目录路径')
    args = parser.parse_args()
    dry_run = not args.execute
    
    targets = []
    if args.dir:
        targets = [args.dir]
    else:
        targets = [
            os.path.join(BASE, 'AssetNature'),
            os.path.join(BASE, 'AssetOther'),
            os.path.join(BASE, 'AssetScene'),
        ]
    
    for target in targets:
        print(f"\n{'🔍 预览模式' if dry_run else '⚠️ 执行模式'}: {target}\n")
        renamed = process_dir(target, dry_run)
        print(f"\n📊 {len(renamed)} 个模型文件待重命名\n")
    
    if dry_run:
        print("确认后执行: python3 scripts/rename-models.py --execute")


if __name__ == '__main__':
    main()
