#!/usr/bin/env python3
"""
wall-rename-v3.py — Wall 目录 V3 规则重命名（基于新 unity-file-manager 流程）

规则（与 V3 Props 一致）：
  1. 前缀: .prefab/.fbx/贴图 → Wall_, .mat → Mat_
  2. 删除 Type01/Type02 等类型标记
  3. #后缀变体保留（去#变_）：#BrickIndustrial6 → _BrickIndustrial_06
  4. PascalCase 分割（H1m → H_01m）
  5. 数字规范化：1m→01m, 2m→02m, 0M5→00M75
  6. _x/_X → _X, _xx01 → _Xx_01

安全：
  - dry-run 默认，加 --confirm 才执行
  - 执行前自动 snapshot（git commit）
  - rename-conflict-check 预检
  - .meta 自动同步
"""

import json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

WALL_ROOT = Path("/media/missyouangeled/WD_BLACK/Project_amend_01/Assets/AssetScene/SceneModels/Wall")
MANAGER = Path("/home/missyouangeled/.openclaw/workspace/scripts/unity-file-manager.py")

# ── V3 命名规则 ──────────────────────────────────────────────────

META_EXTS = {'.prefab', '.fbx', '.mat', '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.tga', '.exr', '.hdr', '.psd'}

def split_camel(s: str) -> str:
    """PascalCase 拆分：WithPost → With_Post。不拆带单位数字（H1m、0M75 保持不动）。"""
    # 只在 小写-大写 之间插入 _
    s = re.sub(r'([a-z])([A-Z])', r'\1_\2', s)
    # 数字后紧跟大写字母：仅当后面还是字母时才拆分（跳过 0M75 这样的单位模式）
    s = re.sub(r'(\d)([A-Z])(?=[a-zA-Z])', r'\1_\2', s)
    return s


def normalize_meters(s: str) -> str:
    """规范化高度/宽度表示：H1m→H_1m, 2m→_2m（不补零）"""
    # H1m, H2m6 等 → H_1m, H_2m6
    s = re.sub(
        r'([A-Z])(\d+)([Mm])(\d*)',
        lambda m: f"{m.group(1)}_{m.group(2)}{m.group(3)}{m.group(4)}",
        s, flags=re.I
    )
    # _2m_/_2M_ → _2m_/_2M_  或 _0M5 → _0M5（不加前导零）
    s = re.sub(
        r'(?<=_)(\d+)([Mm])(\d*)(?=_|$)',
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}",
        s
    )
    return s


def extract_variant(name: str) -> tuple[str, str]:
    """提取 # 变体后缀：#BrickIndustrial6_x → variant=Brick_Industrial_06_X"""
    m = re.search(r'#(\w+)$', name)
    if m:
        base = name[:m.start()]
        variant = m.group(1)
        variant = split_camel(variant)
        # 数字补零
        variant = re.sub(
            r'([A-Za-z]+)(\d+)(_|$)',
            lambda m2: f'{m2.group(1)}_{int(m2.group(2)):02d}{m2.group(3)}',
            variant
        )
        variant = re.sub(
            r'([A-Za-z]+)(\d+)$',
            lambda m2: f'{m2.group(1)}_{int(m2.group(2)):02d}',
            variant
        )
        # _x → _X, _xx → _Xx
        variant = re.sub(r'_x$', '_X', variant, flags=re.I)
        variant = re.sub(r'_xx$', '_Xx', variant, flags=re.I)
        return base, variant
    return name, ''


def apply_v3_rules(filepath: Path, rel_root: Path) -> str | None:
    """
    对单个文件应用 V3 规则，返回新的相对路径。
    返回 None 表示不需要改名。
    """
    rel = str(filepath.relative_to(rel_root)).replace('\\', '/')
    parent = str(Path(rel).parent) if Path(rel).parent != Path('.') else ''
    name = filepath.stem
    ext = filepath.suffix.lower()
    is_meta = filepath.name.endswith('.meta')

    # .meta 文件跟随主文件，不单独处理
    if is_meta:
        return None

    # 只处理需要前缀的文件类型
    if ext not in META_EXTS:
        return None

    prefix = 'Mat_' if ext == '.mat' else 'Wall_'
    original_name = name

    # ── Step 1: 去掉 # 后缀 → 保留变体信息
    name, variant = extract_variant(name)

    # ── Step 2: 去掉 Type01/Type02/Type_/SceneStatic 等前缀
    name = re.sub(r'_Type\d*_?', '_', name, flags=re.I)
    name = re.sub(r'^Type\d*_?', '', name, flags=re.I)
    name = re.sub(r'SceneStatic_?', '', name, flags=re.I)
    # 清理多余的 _
    name = re.sub(r'_+', '_', name).strip('_')

    # ── Step 3: PascalCase 拆分
    name = split_camel(name)

    # ── Step 4: 数字规范化
    name = normalize_meters(name)

    # ── Step 4.5: 后缀规范化
    # _xx## → _Xx_## (如 _xx01 → _Xx_01)
    name = re.sub(r'_xx(\d+)$', lambda m: f'_Xx_{int(m.group(1)):02d}', name, flags=re.I)
    name = re.sub(r'_xx(\d+)_', lambda m: f'_Xx_{int(m.group(1)):02d}_', name, flags=re.I)
    # _x$ → _X (独立 X 后缀在末尾)
    name = re.sub(r'_x$', '_X', name, flags=re.I)
    # _x_ → _X_ (独立 X 后缀在中间)
    name = re.sub(r'_x_', '_X_', name, flags=re.I)

    # ── Step 4.6: 末尾/独立编号补零（Industrial6 → Industrial_06, Bricks01 → Bricks_01）
    name = re.sub(r'_([A-Za-z]+)(\d+)_', lambda m: f'_{m.group(1)}_{int(m.group(2)):02d}_', name)
    name = re.sub(r'_([A-Za-z]+)(\d+)$', lambda m: f'_{m.group(1)}_{int(m.group(2)):02d}', name)
    name = re.sub(r'^([A-Za-z]+)(\d+)$', lambda m: f'{m.group(1)}_{int(m.group(2)):02d}', name)

    # 清理多重下划线
    name = re.sub(r'_+', '_', name)
    name = name.strip('_')

    # ── Step 5: 拼装变体
    if variant:
        name += '_' + variant

    # ── Step 6: 加前缀
    prefix = 'Mat_' if ext == '.mat' else 'Wall_'
    name_lower = name.lower()
    has_wall = name_lower.startswith('wall_')
    has_mat = name_lower.startswith('mat_')

    if prefix == 'Mat_':
        # .mat: 去掉已有的 Mat_（如果有），保留 Wall_（那是资产名的一部分）
        if has_mat:
            name = re.sub(r'^Mat_', '', name, flags=re.I)
        name = 'Mat_' + name
    else:
        # 非 .mat: 去掉错误的 Mat_ 前缀，保留或加 Wall_
        if has_mat:
            name = re.sub(r'^Mat_', '', name, flags=re.I)
        if not name.lower().startswith('wall_'):
            name = 'Wall_' + name

    # ── Step 6.5: 确保首字母大写（wall_ → Wall_）
    name = re.sub(r'^wall_', 'Wall_', name, flags=re.I)
    name = re.sub(r'^mat_', 'Mat_', name, flags=re.I)

    # ── 最终组装
    new_name = name + ext
    if parent:
        new_rel = parent + '/' + new_name
    else:
        new_rel = new_name

    if new_rel != rel:
        return new_rel
    return None


# ── 主流程 ────────────────────────────────────────────────────────

def main():
    confirm = '--confirm' in sys.argv
    wall = WALL_ROOT.resolve()

    if not wall.is_dir():
        print(f"❌ 目录不存在: {wall}")
        return 1

    print("🔍 扫描文件...")
    mappings = []  # (old_rel, new_rel, file_type)

    for fp in sorted(wall.rglob('*')):
        if not fp.is_file():
            continue
        new_rel = apply_v3_rules(fp, wall)
        if new_rel:
            rel = str(fp.relative_to(wall)).replace('\\', '/')
            ext = fp.suffix.lower().lstrip('.')
            mappings.append((rel, new_rel, ext))

    if not mappings:
        print("✅ 所有文件已符合 V3 规则，无需改名")
        return 0

    # ══════════ 冲突检测 ══════════
    target_count = defaultdict(list)
    for old_rel, new_rel, ftype in mappings:
        target_count[new_rel].append((old_rel, ftype))

    conflicts = {k: v for k, v in target_count.items() if len(v) > 1}
    if conflicts:
        print(f"\n⚠️  {len(conflicts)} 个目标名冲突:")
        for target, sources in sorted(conflicts.items()):
            print(f"\n  目标: {target}")
            for src, ftype in sources:
                print(f"    ← {src} ({ftype})")
        print("\n💡 冲突文件需要手动处理（如保留 # 变体后缀）。请检查后再试。")

    # ══════════ 输出映射表 ══════════
    report = {
        'meta': {
            'root': str(wall),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'total_mappings': len(mappings),
            'conflict_count': len(conflicts),
            'rules': 'V3 — Wall_/Mat_ 前缀 + 去Type## + #变体保留 + PascalCase + 数字规范化',
        },
        'mappings': [
            {
                'old': old,
                'new': new,
                'type': ftype,
                'conflict': new in conflicts,
            }
            for old, new, ftype in sorted(mappings)
        ],
    }

    # 映射表放在目标文件夹下（改哪个文件夹就放哪个文件夹里）
    out_dir = wall
    md_path = out_dir / 'wall-rename-v3-mapping.md'
    lines = [
        f'# Wall 重命名映射表 (V3)',
        f'',
        f'- **根目录**: `{wall}`',
        f'- **生成时间**: {report["meta"]["generated_at"]}',
        f'- **总映射数**: {len(mappings)} 项',
        f'- **冲突数**: {len(conflicts)} 组',
        f'',
        f'## 规则摘要',
        f'',
        f'| # | 规则 |',
        f'|---|------|',
        f'| 1 | `.prefab`/`.fbx`/贴图 → `Wall_` 前缀（已有 `Wall` 则不重复添加） |',
        f'| 2 | `.mat` → `Mat_` 前缀（保留 `Wall` 在资产名中） |',
        f'| 3 | 删除 `Type01`/`Type02`/`SceneStatic` 标记 |',
        f'| 4 | `#` 后缀变体保留（`#BrickIndustrial6` → `_BrickIndustrial_06`） |',
        f'| 5 | PascalCase 拆分 + 数字规范化（不补零） |',
        f'| 6 | `.meta` 跟随主文件同步 |',
        f'',
        f'## 全部映射',
        f'',
        f'| 子目录 | 原名 | 新名 |',
        f'|--------|------|------|',
    ]

    for old, new, ftype in sorted(mappings):
        parts = old.rsplit('/', 1)
        folder = parts[0] if len(parts) > 1 else ''
        orig_name = parts[-1]
        new_name = new.rsplit('/', 1)[-1]
        conflict_mark = ' ⚠️' if new in conflicts else ''
        lines.append(f'| {folder}/ | {orig_name} | {new_name}{conflict_mark} |')

    md_path.write_text('\n'.join(lines), encoding='utf-8')

    print(f"\n📊 统计:")
    print(f"   需要改名: {len(mappings)} 个文件")
    if conflicts:
        print(f"   ⚠️  目标名冲突: {len(conflicts)} 组")

    # 按类型汇总
    type_counts = defaultdict(int)
    for _, _, ftype in mappings:
        type_counts[ftype] += 1
    for ftype, count in sorted(type_counts.items()):
        print(f"   {ftype}: {count}")

    print(f"\n📄 映射表: {md_path}")

    # 展示全部项
    print(f"\n📋 全部 {len(mappings)} 项:")
    for old, new, ftype in sorted(mappings):
        cf = ' ⚠️' if new in conflicts else ''
        print(f"   {old}  →  {new}{cf}")

    if not conflicts and confirm:
        print("\n⚡ 执行改名...")
        # 1. snapshot
        subprocess.run(['python3', str(MANAGER), 'snapshot', str(wall),
                       '-m', 'V3重命名前快照'], check=True)

        renamed = 0
        errors = []
        for old_rel, new_rel, ftype in sorted(mappings):
            old_path = wall / old_rel
            new_path = wall / new_rel

            # 确保目标目录存在
            new_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                old_path.rename(new_path)
                renamed += 1

                # 同步 .meta
                old_meta = wall / (old_rel + '.meta')
                new_meta = wall / (new_rel + '.meta')
                if old_meta.exists():
                    new_meta.parent.mkdir(parents=True, exist_ok=True)
                    old_meta.rename(new_meta)
            except Exception as e:
                errors.append((old_rel, str(e)))

        # 2. 刷新索引
        subprocess.run(['python3', str(MANAGER), 'index', str(wall)], check=True)

        # 3. snapshot
        subprocess.run(['python3', str(MANAGER), 'snapshot', str(wall),
                       '-m', 'V3重命名后快照'], check=True)

        # 4. verify
        subprocess.run(['python3', str(MANAGER), 'verify', str(wall)], check=False)

        print(f"\n✅ 改名完成: {renamed} 个文件")
        if errors:
            print(f"❌ 错误: {len(errors)} 个")
            for f, e in errors[:10]:
                print(f"   {f}: {e}")
    elif not confirm:
        print(f"\n💡 这是 dry-run。要执行改名请加 --confirm")
    else:
        print(f"\n❌ 有冲突，跳过执行。请手动处理冲突后再试。")

    return 0


if __name__ == '__main__':
    sys.exit(main())
