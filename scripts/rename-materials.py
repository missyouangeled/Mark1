#!/usr/bin/env python3
"""
材质批量重命名 v2 — 按新规范执行。
规范：2026-06-03 更新版
"""

import os, sys, re, argparse
from collections import OrderedDict

BASE = "/media/missyouangeled/WD_BLACK/Project/Project/Assets"

# ═══════════════════════════════════════════════════
# 后缀标准化映射（按长度降序，长后缀优先）
# 规则：Color保持Color, Albedo保持Albedo, Diffuse保持Diffuse 不互转
# ═══════════════════════════════════════════════════

SUFFIX_MAP = OrderedDict([
    # ── Mask 统一（所有 Mask 变体 → Mask）──
    ('_RoughnessMask', '_Mask'),
    ('_roughnessMask', '_Mask'),
    ('_RoughMask', '_Mask'),
    ('_roughMask', '_Mask'),
    ('_rough_4kMask', '_Mask'),
    ('_rough_2kMask', '_Mask'),
    ('_rough_4kMask1', '_Mask'),
    ('_GLOSSMask', '_Mask'),
    ('_GLOSSMask2', '_Mask'),
    ('_GLOSSMask5', '_Mask'),
    ('_GLOSSMask25', '_Mask'),
    ('_GlossMask', '_Mask'),
    ('_glossMask', '_Mask'),
    ('_glossMask1', '_Mask'),
    ('_glossMask5', '_Mask'),
    ('_DISPMask', '_Mask'),
    ('_DISPMask3', '_Mask'),
    ('_DISP', '_Height'),
    ('_OcclusionMask', '_Mask'),
    ('_OcclusionMask6', '_Mask'),
    ('_RAOMask', '_Mask'),
    ('_MaskMap', '_Mask'),
    ('_RMask', '_Mask'),
    ('_SM', '_Mask'),
    ('_MS', '_Mask'),
    ('_Mask1', '_Mask'),
    ('_Mask2', '_Mask'),
    ('_Mask3', '_Mask'),
    ('_Mask4', '_Mask'),
    ('_Mask5', '_Mask'),
    ('_Mask6', '_Mask'),
    ('_Mask7', '_Mask'),
    ('_Mask8', '_Mask'),
    ('_Mask9', '_Mask'),
    ('_Mask10', '_Mask'),
    ('_Mask14', '_Mask'),
    ('_Mask15', '_Mask'),
    ('_Mask19', '_Mask'),
    ('_Mask23', '_Mask'),

    # ── Normal 统一 ──
    ('_NormalGL', '_Normal'),
    ('_Normal_OS', '_Normal'),
    ('_normal_OS', '_Normal'),
    ('_Normals', '_Normal'),
    ('_normal', '_Normal'),
    ('_Normal', '_Normal'),
    ('_nor_gl', '_Normal'),
    ('_nor', '_Normal'),
    ('_NM', '_Normal'),
    ('_NRM', '_Normal'),
    ('_N', '_Normal'),

    # ── Height / Displacement 统一 ──
    ('_Displacement', '_Height'),
    ('_displacement', '_Height'),
    ('_disp', '_Height'),
    ('_height', '_Height'),
    ('_Height', '_Height'),
    ('_Hight', '_Height'),
    ('_H', '_Height'),

    # ── Albedo 保持 ──
    ('_albedo', '_Albedo'),
    ('_Albedo', '_Albedo'),
    ('_Albedo2', '_Albedo'),
    ('_albedo2', '_Albedo'),
    ('_Albedo3', '_Albedo'),
    ('_A', '_Albedo'),

    # ── Diffuse 保持 ──
    ('_Diff', '_Diffuse'),
    ('_diff', '_Diffuse'),
    ('_Diffuse', '_Diffuse'),
    ('_D', '_Diffuse'),

    # ── Color 统一 ──
    ('_BaseColorAlpha', '_Color'),
    ('_BaseColor', '_Color'),
    ('_BaseCol2', '_Color'),
    ('_BaseCol', '_Color'),
    ('_Basecolor', '_Color'),
    ('_BC2', '_Color'),
    ('_BC', '_Color'),
    ('_Colour', '_Color'),
    ('_colour', '_Color'),
    ('_COL', '_Color'),
    ('_Col', '_Color'),
    ('_col', '_Color'),
    ('_Color', '_Color'),
    ('_color', '_Color'),
    ('_TGA', '_Color'),

    # ── 其他贴图后缀 ──
    ('_Roughness', '_Roughness'),
    ('_roughness', '_Roughness'),
    ('_Metallic', '_Metallic'),
    ('_metallic', '_Metallic'),
    ('_Glossiness', '_Glossiness'),
    ('_GLOSS', '_Glossiness'),
    ('_Gloss', '_Glossiness'),
    ('_gloss', '_Glossiness'),
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
    ('_Mask', '_Mask'),
    ('_mask', '_Mask'),
    ('_M', '_Mask'),
])

# ═══════════════════════════════════════════════════
# 需要清除的内容
# ═══════════════════════════════════════════════════

STRIP_PREFIXES = [
    'TexturesCom_', 'texturescom_', 'TCom_', 'tcom_',
]

STRIP_PATTERNS = [
    r'_1[Kk]', r'_2[Kk]', r'_4[Kk]', r'_6[Kk]', r'_8[Kk]',
    r'_512', r'_1024', r'_2048', r'_4096',
    r'_seamless_?',
    r'_4K-PNG', r'_2k_jpg',
    r'_\d+x\d+[a-z]*_\d+',  # _1.5x1.5_512
    r'_\d[\.,]?\d*x\d[\.,]?\d*[a-z]*',  # _1.5x1.5
    r'_\d+p?x\d+p?[a-z]*',  # _512x512
]

# ═══════════════════════════════════════════════════
# 倒装规则 —— 把归类词放最前面
# 格式: (末尾词, 移到前面的词)
# ═══════════════════════════════════════════════════

INVERSION_MAP = [
    # StoneWall → Wall_Stone
    ('Stone', 'Wall', 'Wall'),     # 如果以Wall结尾且前面是Stone → Wall_Stone
    ('Brick', 'Wall', 'Wall'),
    ('Concrete', 'Floor', 'Floor'),
    ('Concrete', 'Wall', 'Wall'),
    ('Wood', 'Wall', 'Wall'),
    ('Metal', 'Roof', 'Roof'),
    ('Rusty', 'Metal', 'Metal'),
    ('Bronze', 'Roof', 'Roof'),
    ('Slate', 'Wall', 'Wall'),
    ('Marble', 'Wall', 'Wall'),
    ('Marble', 'Floor', 'Floor'),
    ('Glass', 'Window', 'Window'),
    ('Ceramic', 'Floor', 'Floor'),
    ('Terracotta', 'Floor', 'Floor'),
    ('Tile', 'Floor', 'Floor'),
    ('Tile', 'Wall', 'Wall'),
    ('Plaster', 'Wall', 'Wall'),
    ('Plaster', 'Ceiling', 'Ceiling'),
    ('Mortar', 'Wall', 'Wall'),
    ('Granite', 'Wall', 'Wall'),
    ('Granite', 'Floor', 'Floor'),
]

# 需要 # 分隔的材质属性词
ATTR_WORDS = {'Red', 'Green', 'Blue', 'Yellow', 'White', 'Black', 'Grey', 'Gray',
              'Dark', 'Light', 'Old', 'New', 'Dirty', 'Clean',
              'Glossy', 'Matte', 'Rough', 'Smooth',
              'Big', 'Small', 'Large', 'Medium'}


def apply_suffix(name):
    """应用后缀映射（大小写不敏感），返回 (new_name, changed)"""
    name_lower = name.lower()
    for old, new in SUFFIX_MAP.items():
        if name_lower.endswith(old.lower()):
            result = name[:-len(old)] + new
            return result, old != new
    return name, False


def strip_junk(name):
    """清除无意义前缀/容量信息"""
    for pfx in STRIP_PREFIXES:
        if name.lower().startswith(pfx.lower()):
            name = name[len(pfx):]
    for pat in STRIP_PATTERNS:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


def pad_numbers(name):
    """glass1→Glass_01, box2→Box_02（边界：后面不能跟数字）"""
    def repl(m):
        word = m.group(1)
        num = m.group(2)
        return f"{word}_{int(num):02d}"
    name = re.sub(r'(?<=[a-zA-Z])([a-zA-Z]+)(\d{1,2})(?![0-9])', repl, name)
    return name


def invert_name(name):
    """倒装：StoneWall → Wall_Stone"""
    for material, category, prefix in INVERSION_MAP:
        pattern = rf'^(.*_){category}{material}$|^({category}){material}$|^(.*_){material}{category}$|^({material}){category}$'
        m = re.match(pattern, name, re.IGNORECASE)
        if m:
            target_attr = None
            rest = name
            for attr in sorted(ATTR_WORDS, key=len, reverse=True):
                if name.lower().startswith(attr.lower() + '_'):
                    target_attr = attr
                    rest = name[len(attr)+1:]
                    break
            
            prefix_word = prefix.capitalize()
            mat_word = material.capitalize()
            
            if rest.lower() == f'{category.lower()}{material.lower()}':
                new_name = f'{prefix_word}_{mat_word}' if target_attr is None else f'{target_attr}_{prefix_word}_{mat_word}'
            elif rest.lower() == f'{material.lower()}{category.lower()}':
                new_name = f'{prefix_word}_{mat_word}' if target_attr is None else f'{target_attr}_{prefix_word}_{mat_word}'
            elif rest.lower().startswith(f'{category.lower()}{material.lower()}'):
                suffix = rest[len(category)+len(material):]
                new_name = f'{prefix_word}_{mat_word}{suffix}' if target_attr is None else f'{target_attr}_{prefix_word}_{mat_word}{suffix}'
            elif rest.lower().startswith(f'{material.lower()}{category.lower()}'):
                suffix = rest[len(material)+len(category):]
                new_name = f'{prefix_word}_{mat_word}{suffix}' if target_attr is None else f'{target_attr}_{prefix_word}_{mat_word}{suffix}'
            else:
                continue
            
            if new_name != name:
                return new_name
    return name


def camel_case(name):
    """每个单词首字母大写，紧凑词（H2m, 2m, 3x3）内部不加_"""
    name = name.replace(' ', '_')
    name = re.sub(r'_+', '_', name)
    parts = name.split('_')
    new_parts = []
    for p in parts:
        if not p:
            continue
        if re.match(r'^\d', p):
            new_parts.append(p)
        else:
            new_parts.append(p[0].upper() + p[1:])
    return '_'.join(new_parts)


def split_compound(name):
    """拆分复合词（多次替换，不提前break）"""
    # 已知复合词拆分
    compounds = [
        ('BronzeOld', 'Bronze_Old'), ('BronzeNew', 'Bronze_New'),
        ('ItalianOld', 'Italian_Old'), ('ItalianNew', 'Italian_New'),
        ('SquareOld', 'Square_Old'), ('SquareNew', 'Square_New'),
        ('RoundOld', 'Round_Old'), ('RoundNew', 'Round_New'),
        ('PantileOld', 'Pantile_Old'),
        ('AsbestosOndulated', 'Asbestos_Ondulated'),
        ('WoodPlanks', 'Wood_Planks'),
        ('CorrugatedRusted', 'Corrugated_Rusted'),
        ('LightRust', 'Light_Rust'), ('MedRust', 'Med_Rust'), ('HeavyRust', 'Heavy_Rust'),
        ('Old2', 'Old_02'),
        ('BrickIndustrial', 'Brick_Industrial'),
        ('RidgeTille', 'Ridge_Tile'),
        ('Roofing_Slate', 'Roof_Slate'),
        ('Roofing_BronzeOld', 'Roof_Bronze_Old'),
        ('Roofing_BronzeNew', 'Roof_Bronze_New'),
        ('Roofing_Bronze', 'Roof_Bronze'),
        ('Roofing_ItalianOld', 'Roof_Italian_Old'),
        ('Roofing_ItalianNew', 'Roof_Italian_New'),
        ('Roofing_Italian', 'Roof_Italian'),
        ('Roofing_SquareOld', 'Roof_Square_Old'),
        ('Roofing_SquareNew', 'Roof_Square_New'),
        ('Roofing_Square', 'Roof_Square'),
        ('Roofing_RoundOld', 'Roof_Round_Old'),
        ('Roofing_RoundNew', 'Roof_Round_New'),
        ('Roofing_Round', 'Roof_Round'),
        ('Roofing_PantileOld', 'Roof_Pantile_Old'),
        ('Roofing_Pantile', 'Roof_Pantile'),
        ('Roofing_Wood', 'Roof_Wood'),
        ('Roofing_Asbestos', 'Roof_Asbestos'),
        ('Castle_Wall_Slates', 'Wall_Castle_Slate'),
        ('castle_wall_slates', 'Wall_Castle_Slate'),
        ('Concrete_Floor', 'Floor_Concrete'),
        ('concrete_floor', 'Floor_Concrete'),
        ('Rusty_Metal', 'Metal_Rusty'),
        ('rusty_metal', 'Metal_Rusty'),
        ('grey_roof_tiles', 'Roof_Grey_Tile'),
        ('ConcreteFenceSoviet', 'Fence_Concrete_Soviet'),
        ('SmallWoodenShingles', 'Roof_Shingle_Wood'),
    ]
    for old, new in compounds:
        if name == old or name.startswith(old + '_') or name == old.lower() or name.lower().startswith(old.lower() + '_'):
            name = new + name[len(old):]
    return name


def infer_number(name):
    """如果素材只有一个版本，加_01序号；已有序号的不重复加"""
    if re.search(r'_\d{2,}$', name):
        return name
    return name


def clean_texture_name(name):
    """贴图名称完整清理流水线"""
    original = name
    
    # 1. 先清除容量信息（必须在后缀匹配之前）
    name = strip_junk(name)
    
    # 2. 复合词拆分（在大小写处理之前）
    name = split_compound(name)
    
    # 3. 后缀标准化
    name, _ = apply_suffix(name)
    
    # 4. 数字补零
    name = pad_numbers(name)
    
    # 5. PascalCase
    name = camel_case(name)
    
    return name if name != original else original


def clean_material_name(name):
    """材质球名称清理 + Mat_ 前缀"""
    name = name.replace(' ', '_')
    if name.startswith('Mat_'):
        name = name[4:]
    name = camel_case(name)
    return 'Mat_' + name


def rename_file(filepath, new_basename, dry_run=True, rename_log=None):
    """重命名单个文件（含.meta），返回 (oldpath, newpath) 或 None"""
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


def process_dir(root_dir, dry_run=True):
    """处理整个目录树"""
    if not os.path.isdir(root_dir):
        print(f"  ❌ 路径不存在: {root_dir}")
        return [], []
    
    tex_exts = {'.tif','.tiff','.png','.jpg','.jpeg','.tga','.exr','.hdr','.psd'}
    renamed = []
    rename_log = [] if not dry_run else None
    
    total = 0
    
    for dirpath, dirs, files in os.walk(root_dir):
        for f in files:
            if f.endswith('.meta'):
                continue
            fp = os.path.join(dirpath, f)
            name, ext = os.path.splitext(f)
            ext_lower = ext.lower()
            
            if ext_lower in tex_exts:
                new_name = clean_texture_name(name)
            elif ext_lower == '.mat':
                new_name = clean_material_name(name)
            else:
                continue
            
            total += 1
            
            if new_name != name:
                r = rename_file(fp, new_name, dry_run, rename_log)
                if r:
                    renamed.append(r)
    
    if rename_log:
        log_path = os.path.join(root_dir, 'rename_log.txt')
        with open(log_path, 'w') as f:
            f.write(f"# 重命名日志 — {os.path.basename(root_dir)}\n")
            f.write("# 时间: 2026-06-03\n")
            f.write(f"# 共 {len(rename_log)} 条\n\n")
            for entry in rename_log:
                f.write(entry + '\n')
        print(f"\n  📝 rename_log.txt: {len(rename_log)} 条")
    
    return renamed, total


# ═══════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', default=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--dir', type=str, default='',
                       help='指定目录路径')
    args = parser.parse_args()
    dry_run = not args.execute
    
    if args.dir:
        target = args.dir
    else:
        target = os.path.join(BASE, "AssetScene", "SceneMaterials", "Materials_Standard")
    
    print(f"🔍 预览模式: {target}\n" if dry_run else f"⚠️ 执行模式: {target}\n")
    
    renamed, total = process_dir(target, dry_run)
    
    print(f"\n{'='*60}")
    print(f"📊 {len(renamed)}/{total} 个文件待重命名")
    if dry_run and renamed:
        print(f"   确认后执行: python3 scripts/rename-materials.py --execute --dir '{target}'")


if __name__ == '__main__':
    main()
