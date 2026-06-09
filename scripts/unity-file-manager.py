#!/usr/bin/env python3
"""
unity-file-manager.py — 大型 Unity 工程文件管理器

三层架构：
  Layer 1 — Git 版本控制（回滚层）
  Layer 2 — JSON 索引数据库（查找层）
  Layer 3 — 操作工具链（执行层）

安全设计：
  - 全部变更操作默认 dry-run，必须加 --confirm 才真正执行
  - 任何修改前强制 git commit（自动），commit 失败则拒绝操作
  - 不提供 delete 命令
  - .meta 文件自动配对同步
  - 每次变更写入 journal（可审计/可回溯）
  - git reset --hard 秒级回滚

用法：
  python3 unity-file-manager.py index /path/to/Wall            # 建索引
  python3 unity-file-manager.py find --type prefab --name Gate  # 查文件
  python3 unity-file-manager.py snapshot /path/to/Wall          # 快照（git commit + 刷新索引）
  python3 unity-file-manager.py status /path/to/Wall            # 看当前状态
  python3 unity-file-manager.py verify /path/to/Wall            # 检查 .meta 一致性
  python3 unity-file-manager.py rollback /path/to/Wall          # 回滚到上次快照
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ── 项目类型适配器 ─────────────────────────────────────────────

# Unity: .meta 配对
UNITY_META_EXTS = {
    '.prefab', '.fbx', '.mat', '.png', '.jpg', '.jpeg',
    '.tif', '.tiff', '.tga', '.exr', '.hdr', '.psd',
    '.obj', '.dae', '.blend', '.cs', '.shader', '.anim',
    '.controller', '.asset', '.unity', '.mp3', '.wav',
}
# 可重命名的资产类型（用于批量改名）
RENAMEABLE_EXTS = {
    '.prefab', '.fbx', '.mat', '.png', '.jpg', '.jpeg',
    '.tif', '.tiff', '.tga', '.exr', '.hdr', '.psd',
}

# ── 工具函数 ────────────────────────────────────────────────────

_INDEX_FILENAME = '.unity-file-index.json'
_JOURNAL_FILENAME = '.unity-file-journal.jsonl'
_GITIGNORE_CONTENT = """\
# unity-file-manager
.unity-file-index.json
.unity-file-journal.jsonl
"""


def _git(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """安全执行 git 命令（list args 防注入）"""
    return subprocess.run(
        ['git'] + cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _ensure_git(target_dir: Path) -> bool:
    """确保目标目录是 git 仓库，不是则 init"""
    git_dir = target_dir / '.git'
    if git_dir.exists():
        return True
    r = _git(['init'], target_dir)
    if r.returncode != 0:
        print(f'❌ git init 失败: {r.stderr.strip()}')
        return False
    # 写入 .gitignore
    (target_dir / '.gitignore').write_text(_GITIGNORE_CONTENT, encoding='utf-8')
    print('✅ git init 完成')
    return True


def _git_has_changes(target_dir: Path) -> bool:
    """检查是否有未提交变更"""
    r = _git(['status', '--porcelain'], target_dir)
    return bool(r.stdout.strip())


def _git_commit(target_dir: Path, message: str) -> bool:
    """提交所有变更"""
    r = _git(['add', '-A'], target_dir)
    if r.returncode != 0:
        print(f'❌ git add 失败: {r.stderr.strip()}')
        return False
    r = _git(['commit', '-m', message], target_dir)
    if r.returncode == 0:
        print(f'✅ git commit: {message}')
        return True
    if 'nothing to commit' in (r.stdout + r.stderr):
        print('ℹ️  无变更，跳过 commit')
        return True
    print(f'❌ git commit 失败: {r.stderr.strip()}')
    return False


def _abs(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _file_hash(filepath: Path, algo: str = 'sha256') -> str:
    """快速文件哈希（用于变更检测）"""
    h = hashlib.new(algo)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ── Layer 2: 索引系统 ────────────────────────────────────────────

def build_index(root: Path) -> dict:
    """
    扫描目录，构建文件索引。
    返回:
      {
        "meta": { "root": "...", "scanned_at": "...", "file_count": N, "dir_count": N },
        "files": { "relative/path": { "name":..., "ext":..., "size":..., "type":...,
                   "meta_of": null|"相对路径", "meta_file": null|"相对路径" } },
        "by_type": { "prefab": ["路径1",...], "fbx": [...], ... },
        "by_dir": { "子目录名": ["路径1",...], ... }
      }
    """
    index = {
        'meta': {
            'root': str(root),
            'scanned_at': datetime.now(timezone.utc).isoformat(),
            'file_count': 0,
            'dir_count': 0,
        },
        'files': {},
        'by_type': defaultdict(list),
        'by_dir': defaultdict(list),
    }

    dirs_seen = set()
    for fp in sorted(root.rglob('*')):
        if fp.is_dir():
            dirs_seen.add(str(fp.relative_to(root)))
            continue
        rel = str(fp.relative_to(root)).replace('\\', '/')
        ext = fp.suffix.lower()
        ftype = ext.lstrip('.') if ext else 'unknown'
        is_meta = fp.name.endswith('.meta')

        entry = {
            'name': fp.name,
            'ext': ext,
            'size': fp.stat().st_size,
            'type': 'meta' if is_meta else ftype,
            'is_meta': is_meta,
            'meta_of': None,
            'meta_file': None,
        }

        # .meta 配对关系
        if is_meta:
            asset_rel = rel[:-5]  # 去掉 .meta
            entry['meta_of'] = asset_rel
        elif ext in UNITY_META_EXTS:
            meta_rel = rel + '.meta'
            if (root / meta_rel).exists():
                entry['meta_file'] = meta_rel

        index['files'][rel] = entry

        if not is_meta:
            index['by_type'][ftype].append(rel)

        # 按目录分组
        parent = str(Path(rel).parent) if Path(rel).parent != Path('.') else '(root)'
        index['by_dir'][parent].append(rel)

    index['meta']['file_count'] = len(index['files'])
    index['meta']['dir_count'] = len(dirs_seen) + 1  # +1 for root
    # 转换 defaultdict 为普通 dict（JSON 序列化友好）
    index['by_type'] = dict(index['by_type'])
    index['by_dir'] = dict(index['by_dir'])
    return index


def save_index(index: dict, root: Path) -> Path:
    idx_path = root / _INDEX_FILENAME
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    return idx_path


def load_index(root: Path) -> dict | None:
    idx_path = root / _INDEX_FILENAME
    if not idx_path.exists():
        return None
    return json.loads(idx_path.read_text(encoding='utf-8'))


# ── Layer 3: 操作命令 ────────────────────────────────────────────

def cmd_index(args):
    """构建/刷新索引"""
    root = _abs(args.path)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2
    print(f'🔍 扫描 {root} ...')
    t0 = time.time()
    index = build_index(root)
    idx_path = save_index(index, root)
    elapsed = time.time() - t0
    print(f'✅ 索引已保存: {idx_path}')
    print(f'   文件 {index["meta"]["file_count"]} 个  |  '
          f'目录 {index["meta"]["dir_count"]} 个  |  '
          f'耗时 {elapsed:.2f}s')
    return 0


def cmd_find(args):
    """从索引查询文件"""
    root = _abs(args.path)
    index = load_index(root)
    if index is None:
        print(f'❌ 索引不存在，请先运行: unity-file-manager.py index {args.path}')
        return 2

    results = list(index['files'].keys())

    # 过滤类型
    if args.type:
        ftype = args.type.lower().lstrip('.')
        if ftype in index.get('by_type', {}):
            results = index['by_type'][ftype]
        else:
            results = [f for f in results
                       if index['files'][f]['type'] == ftype]
    # 过滤名称
    if args.name:
        name_lower = args.name.lower()
        results = [f for f in results
                   if name_lower in index['files'][f]['name'].lower()]
    # 过滤目录
    if args.dir:
        dir_key = args.dir.replace('\\', '/').strip('/')
        if dir_key in index.get('by_dir', {}):
            results = index['by_dir'][dir_key]
        else:
            results = [f for f in results if f.startswith(dir_key + '/')]
    # 排除 .meta
    if not args.include_meta:
        results = [f for f in results if not f.endswith('.meta')]

    if not results:
        print('(无匹配文件)')
        return 0

    for rel in sorted(results):
        entry = index['files'][rel]
        meta_info = ''
        if entry.get('meta_file'):
            meta_info = ' [有.meta]'

        if args.long:
            size_kb = entry['size'] / 1024
            print(f'  {rel}  ({entry["type"]}, {size_kb:.1f}KB{meta_info})')
        else:
            print(f'  {rel}{meta_info}')

    print(f'\n共 {len(results)} 个文件')
    return 0


def cmd_snapshot(args):
    """快照：git commit + 刷新索引"""
    root = _abs(args.path)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2

    if not _ensure_git(root):
        return 3

    # 刷新索引
    index = build_index(root)
    save_index(index, root)

    # git commit
    msg = args.message or f'snapshot: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    if not _git_commit(root, msg):
        return 3

    print(f'📸 快照完成 ({index["meta"]["file_count"]} 文件)')
    return 0


def cmd_status(args):
    """查看当前状态"""
    root = _abs(args.path)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2

    # Git 状态
    git_dir = root / '.git'
    if git_dir.exists():
        r = _git(['log', '--oneline', '-5'], root)
        print('📋 最近快照:')
        print(r.stdout.strip() or '(无提交)')
        r2 = _git(['status', '--short'], root)
        if r2.stdout.strip():
            print('\n⚠️  未提交变更:')
            print(r2.stdout.strip()[:2000])
        else:
            print('✅ 工作区干净')
        print()

    # 索引状态
    index = load_index(root)
    if index:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(index['meta']['scanned_at'])
        print(f'📊 索引: {index["meta"]["file_count"]} 文件, {index["meta"]["dir_count"]} 目录')
        print(f'   上次扫描: {age.total_seconds():.0f}s 前')
    else:
        print('📊 索引: 未建立 (运行 index 命令)')

    # 目录概览
    print(f'\n📁 顶层目录:')
    for child in sorted(root.iterdir()):
        if child.name.startswith('.') or child.name.startswith('_'):
            continue
        if child.is_dir():
            count = sum(1 for _ in child.rglob('*') if _.is_file())
            print(f'   {child.name}/  ({count} 文件)')

    return 0


def cmd_verify(args):
    """检查 .meta 一致性"""
    root = _abs(args.path)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2

    issues = []
    ok_count = 0
    orphan_meta = []
    missing_meta = []

    for fp in sorted(root.rglob('*')):
        if not fp.is_file():
            continue
        rel = str(fp.relative_to(root)).replace('\\', '/')
        is_meta = fp.name.endswith('.meta')

        if is_meta:
            asset_path = root / rel[:-5]
            if not asset_path.exists():
                orphan_meta.append(rel)
        elif fp.suffix.lower() in UNITY_META_EXTS:
            meta_path = root / (rel + '.meta')
            if not meta_path.exists():
                missing_meta.append(rel)
            else:
                ok_count += 1

    # 检查重复文件名
    name_map = defaultdict(list)
    for fp in sorted(root.rglob('*')):
        if fp.is_file() and not fp.name.endswith('.meta'):
            name_map[fp.name].append(str(fp.relative_to(root)).replace('\\', '/'))
    dupes = {k: v for k, v in name_map.items() if len(v) > 1}

    if orphan_meta:
        print(f'⚠️  孤儿 .meta ({len(orphan_meta)} 个，对应资产不存在):')
        for m in orphan_meta[:20]:
            print(f'   {m}')
        if len(orphan_meta) > 20:
            print(f'   ... 还有 {len(orphan_meta) - 20} 个')
        print()

    if missing_meta:
        print(f'⚠️  缺 .meta 的资产 ({len(missing_meta)} 个):')
        for m in missing_meta[:20]:
            print(f'   {m}')
        if len(missing_meta) > 20:
            print(f'   ... 还有 {len(missing_meta) - 20} 个')
        print()

    if dupes:
        print(f'⚠️  同名文件 ({len(dupes)} 组):')
        for name, paths in list(dupes.items())[:10]:
            print(f'   {name}:')
            for p in paths:
                print(f'      {p}')
        print()

    if not orphan_meta and not missing_meta and not dupes:
        print(f'✅ 全部正常 ({ok_count} 个 .meta 配对完整)')
    else:
        print(f'ℹ️  正常配对: {ok_count}')
        return 1

    return 0


def cmd_rollback(args):
    """回滚到上一个快照"""
    root = _abs(args.path)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2

    git_dir = root / '.git'
    if not git_dir.exists():
        print('❌ 没有 git 仓库，无法回滚')
        return 3

    # 显示将要回滚到的状态
    r = _git(['log', '--oneline', '-3'], root)
    print('📋 提交历史:')
    print(r.stdout.strip())
    print()

    target = args.to or 'HEAD~1'
    if target == 'HEAD~1':
        r2 = _git(['diff', '--stat', 'HEAD~1', 'HEAD'], root)
        if r2.stdout.strip():
            print('📝 将撤销以下变更:')
            print(r2.stdout.strip()[:2000])
        print()

    if not args.confirm:
        print(f'💡 这是 dry-run。要执行回滚请加 --confirm')
        print(f'   将执行: git reset --hard {target}')
        return 0

    r = _git(['reset', '--hard', target], root)
    if r.returncode == 0:
        print(f'✅ 已回滚到 {target}')
        # 刷新索引
        index = build_index(root)
        save_index(index, root)
        return 0

    print(f'❌ 回滚失败: {r.stderr.strip()}')
    return 3


def cmd_info(args):
    """查看单个文件详情"""
    root = _abs(args.path)
    fp = root / args.file
    if not fp.exists():
        print(f'❌ 文件不存在: {fp}')
        return 2

    rel = str(fp.relative_to(root)).replace('\\', '/')
    stat = fp.stat()
    is_meta = fp.name.endswith('.meta')

    print(f'📄 {fp.name}')
    print(f'   路径: {rel}')
    print(f'   大小: {stat.st_size:,} 字节 ({stat.st_size / 1024:.1f} KB)')
    print(f'   修改: {datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")}')

    if is_meta:
        asset_rel = rel[:-5]
        asset_path = root / asset_rel
        print(f'   类型: .meta (对应资产)')
        print(f'   资产: {asset_rel} {"✅ 存在" if asset_path.exists() else "❌ 不存在"}')
    else:
        meta_rel = rel + '.meta'
        meta_path = root / meta_rel
        print(f'   类型: {fp.suffix}')
        print(f'   .meta: {"✅ 已配对" if meta_path.exists() else "⚠️ 缺失"}')

        # 如果是 .prefab 或 .mat，尝试显示内容摘要
        if fp.suffix.lower() in ('.prefab', '.mat'):
            try:
                content = fp.read_text(encoding='utf-8', errors='replace')[:2000]
                # 提取 GUID
                import re
                guids = re.findall(r'guid:\s*([a-f0-9]{32})', content, re.I)
                if guids:
                    print(f'   GUID: {guids[0]}')
                refs = re.findall(r'guid:\s*([a-f0-9]{32})', content, re.I)
                if len(refs) > 1:
                    print(f'   引用 GUID: {len(refs) - 1} 个')
            except Exception:
                pass

    return 0


# ── Plan / Apply 命令 ──────────────────────────────────────────

_PLAN_TYPE_DIR = "rename_dir"
_PLAN_TYPE_MOVE = "move"
_PLAN_TYPE_PREFIX = "rename_prefix"
_PLAN_TYPE_CUSTOM = "custom_rename"


def _load_rules(rules_path: str) -> dict:
    """加载规则 JSON 文件"""
    with open(rules_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _apply_directory_ops(
    rel_path: str, fname: str, directory_ops: list[dict],
    changes: list, conflict_map: dict,
) -> tuple[str, str]:
    """应用 directoryOps：修改目录路径，必要时 moveToParent"""
    parent = str(Path(rel_path).parent) if Path(rel_path).parent != Path('.') else ''
    new_parent = parent
    matched_op = None

    for op in directory_ops:
        from_dir = op["from"]
        to_dir = op["to"]

        # 精确目录名匹配
        if parent == from_dir or parent.startswith(from_dir + "/"):
            new_parent = parent.replace(from_dir, to_dir, 1)
            matched_op = op
            break
        # 匹配根目录（无父目录）情况
        if not parent and op.get("moveToParent"):
            # moveToParent: 文件从子目录移到父目录
            pass

    if matched_op:
        before_full = (parent + "/" if parent else "") + fname
        after_full = (new_parent + "/" if new_parent else "") + fname
        reason = f"目录重命名: {matched_op['from']}/ → {matched_op['to']}/"

        entry = {
            "before": {"path": before_full.rsplit("/", 1)[0] if "/" in before_full else "",
                       "name": fname},
            "after": {"path": after_full.rsplit("/", 1)[0] if "/" in after_full else "",
                      "name": fname},
            "type": _PLAN_TYPE_DIR,
            "reason": reason,
        }
        changes.append(entry)

        # 冲突检测 key
        key = after_full
        conflict_map.setdefault(key, []).append(before_full)

        return new_parent, fname

    return parent, fname


def _apply_rename_rules(
    rel_path: str, fname: str, rename_rules: list[dict],
    changes: list, conflict_map: dict,
) -> str:
    """应用 renameRules：在指定 scope 内做 pattern → replacement"""
    new_name = fname
    parent = str(Path(rel_path).parent) if Path(rel_path).parent != Path('.') else ''
    matched_rule = None

    for rule in rename_rules:
        scope = rule["scope"].rstrip("/")
        pattern = rule["pattern"]
        replacement = rule["replacement"]

        if rel_path.startswith(scope + "/") or rel_path == scope:
            if pattern in new_name:
                new_name = new_name.replace(pattern, replacement, 1)
                matched_rule = rule
                break

    if matched_rule:
        before_full = (parent + "/" if parent else "") + fname
        after_full = (parent + "/" if parent else "") + new_name
        reason = f"前缀替换: {matched_rule['pattern']} → {matched_rule['replacement']} (scope: {matched_rule['scope']})"

        entry = {
            "before": {"path": parent, "name": fname},
            "after": {"path": parent, "name": new_name},
            "type": _PLAN_TYPE_PREFIX,
            "reason": reason,
        }
        changes.append(entry)

        key = after_full
        conflict_map.setdefault(key, []).append(before_full)

        return new_name

    return fname


def _apply_custom_renames(
    rel_path: str, fname: str, custom_renames: dict,
    changes: list, conflict_map: dict,
) -> str:
    """应用 customRenames：精确名称映射"""
    name_no_ext = Path(fname).stem
    ext = Path(fname).suffix

    if name_no_ext in custom_renames:
        new_base = custom_renames[name_no_ext]
        new_name = new_base + ext
        parent = str(Path(rel_path).parent) if Path(rel_path).parent != Path('.') else ''
        before_full = (parent + "/" if parent else "") + fname
        after_full = (parent + "/" if parent else "") + new_name

        entry = {
            "before": {"path": parent, "name": fname},
            "after": {"path": parent, "name": new_name},
            "type": _PLAN_TYPE_CUSTOM,
            "reason": f"自定义重命名: {name_no_ext} → {new_base}",
        }
        changes.append(entry)

        key = after_full
        conflict_map.setdefault(key, []).append(before_full)

        return new_name

    return fname


def _apply_prefix(
    rel_path: str, fname: str, prefix: str,
    changes: list, conflict_map: dict,
) -> str:
    """应用前缀：给没有前缀的文件加前缀"""
    # 跳过目录操作类变更 — 已在之前处理
    # 只检查文件名是否已有 prefix
    if fname.startswith(prefix):
        return fname

    new_name = prefix + fname
    parent = str(Path(rel_path).parent) if Path(rel_path).parent != Path('.') else ''
    before_full = (parent + "/" if parent else "") + fname
    after_full = (parent + "/" if parent else "") + new_name

    entry = {
        "before": {"path": parent, "name": fname},
        "after": {"path": parent, "name": new_name},
        "type": _PLAN_TYPE_PREFIX,
        "reason": f"添加前缀: {prefix}",
    }
    changes.append(entry)

    key = after_full
    conflict_map.setdefault(key, []).append(before_full)

    return new_name


def _generate_plan(root: Path, rules: dict, changes: list, conflict_map: dict) -> dict:
    """遍历文件系统，应用所有规则，生成映射表"""
    prefix = rules.get("prefix", "")
    directory_ops = rules.get("directoryOps", [])
    rename_rules = rules.get("renameRules", [])
    custom_renames = rules.get("customRenames", {})

    total_files = 0
    skipped_meta = 0
    skipped_git = 0

    for fp in sorted(root.rglob('*')):
        if fp.is_dir():
            # 跳过 .git 目录
            if fp.name == '.git':
                continue
            continue

        # 跳过 .meta 文件和 .git 目录中的文件
        if fp.name.endswith('.meta'):
            skipped_meta += 1
            continue

        rel = str(fp.relative_to(root)).replace('\\', '/')
        if '.git/' in rel or rel.startswith('.git'):
            skipped_git += 1
            continue

        # 跳过非资产文件（JSON rules/config、.DS_Store、.gitignore 等）
        ext = fp.suffix.lower()
        skip_exts = {'.json', '.md', '.txt', '.gitignore', '.ds_store', '.log', '.tmp', '.bak'}
        if ext in skip_exts and ext not in UNITY_META_EXTS:
            continue

        total_files += 1
        fname = fp.name

        # 1. 应用目录操作（可能改变路径）
        new_parent, current_fname = _apply_directory_ops(
            rel, fname, directory_ops, changes, conflict_map,
        )

        # 2. 应用重命名规则
        current_fname = _apply_rename_rules(
            rel, current_fname, rename_rules, changes, conflict_map,
        )

        # 3. 应用自定义重命名
        current_fname = _apply_custom_renames(
            rel, current_fname, custom_renames, changes, conflict_map,
        )

        # 4. 应用前缀（最后一个，确保前面的 rename 不干扰）
        if prefix:
            current_fname = _apply_prefix(
                rel, current_fname, prefix, changes, conflict_map,
            )

    # 构建冲突列表
    conflicts_out = []
    for target, sources in conflict_map.items():
        if len(sources) > 1:
            conflicts_out.append({
                "target": target,
                "sources": sources,
            })

    return {
        "meta": {
            "root": str(root),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_files": total_files,
            "skipped_meta": skipped_meta,
            "skipped_git": skipped_git,
        },
        "rules": rules,
        "changes": changes,
        "conflicts": conflicts_out,
    }


def _fmt_plan_summary(plan: dict) -> str:
    """生成终端友好摘要"""
    meta = plan["meta"]
    changes = plan["changes"]
    conflicts = plan["conflicts"]
    root_name = Path(meta["root"]).name or meta["root"]

    total = meta["total_files"]
    changed = len(changes)
    # 去重：同一文件可能被多个规则命中
    unique_before_paths = set()
    for c in changes:
        bp = (c["before"]["path"] + "/" + c["before"]["name"]).strip("/")
        unique_before_paths.add(bp)
    unique_changed = len(unique_before_paths)
    unchanged = total - unique_changed

    lines = []
    lines.append(f"📋 映射表 — {root_name} 重命名计划")
    lines.append(f"   根目录: {meta['root']}")
    lines.append(f"   📊 总文件 {total} | 将变更 {unique_changed} | 不变 {unchanged}")
    lines.append(f"   ⚠️ 冲突 {len(conflicts)} 项")
    lines.append("")

    # 按类型聚合
    by_type = defaultdict(list)
    for c in changes:
        by_type[c["type"]].append(c)

    # 目录操作
    if by_type.get(_PLAN_TYPE_DIR):
        lines.append(f"📁 目录操作 ({len(by_type[_PLAN_TYPE_DIR])} 项)")
        # 按目录聚合
        dir_summary = defaultdict(list)
        for c in by_type[_PLAN_TYPE_DIR]:
            old_dir = c["before"]["path"]
            new_dir = c["after"]["path"]
            key = f"{old_dir}/ → {new_dir}/"
            dir_summary[key].append(c)
        for key, items in sorted(dir_summary.items()):
            lines.append(f"   {key} [影响 {len(items)} 文件]")
        lines.append("")

    # 前缀替换
    if by_type.get(_PLAN_TYPE_PREFIX):
        lines.append(f"🔤 前缀替换 ({len(by_type[_PLAN_TYPE_PREFIX])} 组)")
        prefix_summary = defaultdict(list)
        for c in by_type[_PLAN_TYPE_PREFIX]:
            # 提取 pattern → replacement 从 reason
            reason = c.get("reason", "")
            key = reason
            prefix_summary[key].append(c)
        for key, items in sorted(prefix_summary.items(), key=lambda x: -len(x[1])):
            lines.append(f"   {key} [{len(items)} 文件]")
        lines.append("")

    # 自定义重命名
    if by_type.get(_PLAN_TYPE_CUSTOM):
        lines.append(f"✏️ 精确重命名 ({len(by_type[_PLAN_TYPE_CUSTOM])} 项)")
        for c in by_type[_PLAN_TYPE_CUSTOM]:
            before = c["before"]["name"]
            after = c["after"]["name"]
            lines.append(f"   {before} → {after}")
        lines.append("")

    # 冲突
    if conflicts:
        lines.append(f"⚠️ 冲突 ({len(conflicts)} 项)")
        for conflict in conflicts[:10]:
            lines.append(f"   {conflict['target']} ← {', '.join(conflict['sources'][:3])}")
        if len(conflicts) > 10:
            lines.append(f"   ... 还有 {len(conflicts) - 10} 项")
        lines.append("")

    lines.append(f"💡 下一步: unity-file-manager.py apply <plan.json> [--confirm]")

    return "\n".join(lines)


def cmd_plan(args):
    """生成重命名映射表"""
    root = _abs(args.directory)
    if not root.is_dir():
        print(f'❌ 目录不存在: {root}')
        return 2

    if not args.rules:
        print(f'❌ 需要 --rules 指定规则文件')
        return 2

    rules_path = Path(args.rules)
    if not rules_path.exists():
        print(f'❌ 规则文件不存在: {rules_path}')
        return 2

    rules = _load_rules(str(rules_path))

    output_path = args.output
    if not output_path:
        scratch = Path("/mnt/data/openclaw/scratch/ufm-plans")
        scratch.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        output_path = str(scratch / f"plan-{root.name}-{ts}.json")

    changes = []
    conflict_map = {}

    plan = _generate_plan(root, rules, changes, conflict_map)

    # 写入输出文件
    Path(output_path).write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    # 打印终端摘要
    print(_fmt_plan_summary(plan))
    print(f"\n📄 完整映射表: {output_path}")
    return 0


def _run_apply_dry(plan: dict):
    """Dry-run 模式：打印每条变更，不执行"""
    changes = plan.get("changes", [])
    if not changes:
        print("(无变更)")
        return

    for i, c in enumerate(changes, 1):
        before = f"{c['before']['path']}/{c['before']['name']}" if c['before']['path'] else c['before']['name']
        after = f"{c['after']['path']}/{c['after']['name']}" if c['after']['path'] else c['after']['name']
        icon = {"rename_dir": "📁", "move": "📦", "rename_prefix": "🔤", "custom_rename": "✏️"}.get(c["type"], "❓")
        print(f"  {i:>4}. {icon} {before}")
        print(f"       → {after}   [{c['type']}]")


def _run_apply_confirm(plan: dict) -> dict:
    """确认执行模式：真正执行变更"""
    root = Path(plan["meta"]["root"])
    changes = plan.get("changes", [])

    if not changes:
        return {"executed": 0, "failed": 0, "errors": []}

    # 1. 自动 git commit（失败则拒绝）
    if not _ensure_git(root):
        return {"executed": 0, "failed": -1, "errors": ["git init 失败"]}

    r = _git(["add", "-A"], root)
    if r.returncode != 0:
        return {"executed": 0, "failed": -1, "errors": [f"git add 失败: {r.stderr.strip()}"]}

    r = _git(["commit", "-m", f"ufm-apply: pre-rename snapshot {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"], root)
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        return {"executed": 0, "failed": -1, "errors": [f"git commit 失败: {r.stderr.strip()}"]}

    t0 = time.time()
    stats = {"rename_dir": 0, "rename_prefix": 0, "custom_rename": 0, "move": 0, "meta_synced": 0}
    errors = []

    # 2. 按类型分组执行
    # 目录操作 → 先处理
    dir_changes = [c for c in changes if c["type"] == _PLAN_TYPE_DIR]
    file_changes = [c for c in changes if c["type"] != _PLAN_TYPE_DIR]

    # 先创建目标目录 + 执行目录级移动
    for c in dir_changes:
        try:
            old_dir = root / c["before"]["path"]
            new_dir = root / c["after"]["path"]
            if not new_dir.exists():
                new_dir.mkdir(parents=True, exist_ok=True)

            old_path = old_dir / c["before"]["name"]
            new_path = new_dir / c["after"]["name"]

            # 目录操作实际是 rename_dir，在 os.walk 之前已改变路径
            # 这里是 move 类型：文件从旧目录移到新目录
            if old_path.exists():
                shutil.move(str(old_path), str(new_path))
                stats["move"] += 1

                # 同步 .meta
                old_meta = root / (str(c["before"]["path"]) + "/" + c["before"]["name"] + ".meta")
                if old_meta.exists():
                    new_meta = root / (str(c["after"]["path"]) + "/" + c["after"]["name"] + ".meta")
                    shutil.move(str(old_meta), str(new_meta))
                    stats["meta_synced"] += 1
        except Exception as e:
            errors.append(f"{c['before']['name']}: {e}")

    # 然后执行文件级重命名
    for c in file_changes:
        try:
            old_path = root / (c["before"]["path"] + "/" + c["before"]["name"])
            new_path = root / (c["after"]["path"] + "/" + c["after"]["name"])

            if old_path.exists():
                os.rename(str(old_path), str(new_path))
                stats[c["type"]] = stats.get(c["type"], 0) + 1

                # 同步 .meta
                old_meta = root / (str(c["before"]["path"]) + "/" + c["before"]["name"] + ".meta")
                if old_meta.exists():
                    new_meta = root / (str(c["after"]["path"]) + "/" + c["after"]["name"] + ".meta")
                    os.rename(str(old_meta), str(new_meta))
                    stats["meta_synced"] += 1
        except Exception as e:
            errors.append(f"{c['before']['name']}: {e}")

    elapsed = time.time() - t0
    total = sum(v for k, v in stats.items() if k != "meta_synced")

    # 3. 写入 journal
    journal = root / _JOURNAL_FILENAME
    journal_entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "action": "apply",
        "stats": stats,
        "total": total,
        "errors": errors,
        "elapsed_s": round(elapsed, 2),
    }
    with open(journal, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(journal_entry, ensure_ascii=False) + "\n")

    return {
        "executed": total,
        "failed": len(errors),
        "errors": errors,
        "stats": stats,
        "elapsed": elapsed,
    }


def cmd_apply(args):
    """执行重命名映射表"""
    plan_path = Path(args.plan_file)
    if not plan_path.exists():
        print(f'❌ 映射表文件不存在: {plan_path}')
        return 2

    try:
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        print(f'❌ JSON 解析失败: {e}')
        return 2

    # 结构验证
    if "meta" not in plan or "changes" not in plan:
        print(f'❌ 映射表结构无效，缺少 meta 或 changes')
        return 2

    if "root" not in plan["meta"]:
        print(f'❌ 映射表结构无效，缺少 meta.root')
        return 2

    root = Path(plan["meta"]["root"])
    if not root.is_dir():
        print(f'❌ 根目录不存在: {root}')
        return 2

    conflicts = plan.get("conflicts", [])
    if conflicts:
        print(f'⚠️ 映射表包含 {len(conflicts)} 个冲突项，请先解决后重试:')
        for conflict in conflicts[:5]:
            print(f'   {conflict["target"]} ← {", ".join(conflict["sources"][:3])}')
        if len(conflicts) > 5:
            print(f'   ... 还有 {len(conflicts) - 5} 项')
        print(f'\n💡 手动编辑映射表解决冲突后重新 apply')
        return 3

    if args.confirm:
        print("🚀 执行中...")
        result = _run_apply_confirm(plan)

        if result.get("failed") == -1:
            print(f'❌ 前置条件失败: {result.get("errors", ["未知"])[0]}')
            return 4

        stats = result.get("stats", {})
        total = result["executed"]

        dir_ops = stats.get("rename_dir", 0) + stats.get("move", 0)
        renames = stats.get("rename_prefix", 0) + stats.get("custom_rename", 0)
        meta_sync = stats.get("meta_synced", 0)
        elapsed = result.get("elapsed", 0)

        print(f"✅ 已执行 {dir_ops}/{dir_ops or total} 项目录操作" if dir_ops > 0 else f"✅ 目录操作: 0 项")
        print(f"✅ 已执行 {renames}/{renames or total} 项重命名" if renames > 0 else f"✅ 重命名: 0 项")
        print(f"✅ .meta 同步: {meta_sync} 配对")
        print(f"📸 快照: git commit 已创建 (可 rollback)")
        print(f"⏱️ 耗时: {elapsed:.1f}s")

        if result["errors"]:
            print(f"\n⚠️ {len(result['errors'])} 个错误:")
            for e in result["errors"][:10]:
                print(f"   {e}")
            if len(result["errors"]) > 10:
                print(f"   ... 还有 {len(result['errors']) - 10} 个")
    else:
        print("💡 Dry-run 模式（加 --confirm 真正执行）\n")
        _run_apply_dry(plan)

    return 0


def cmd_export(args):
    """导出索引为可读报告（JSON/Markdown）"""
    root = _abs(args.path)
    index = load_index(root)
    if index is None:
        print(f'❌ 索引不存在，请先运行: index {args.path}')
        return 2

    fmt = args.format or 'json'
    if fmt == 'json':
        out = args.output or str(root / '.unity-file-report.json')
        Path(out).write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'✅ JSON 报告: {out}')
    elif fmt == 'md':
        out = args.output or str(root / '.unity-file-report.md')
        lines = [
            f'# 文件索引报告',
            f'',
            f'- 根目录: `{index["meta"]["root"]}`',
            f'- 扫描时间: {index["meta"]["scanned_at"]}',
            f'- 文件数: {index["meta"]["file_count"]}',
            f'- 目录数: {index["meta"]["dir_count"]}',
            f'',
        ]
        # 按类型汇总
        lines.append('## 按类型')
        for ftype, files in sorted(index.get('by_type', {}).items()):
            lines.append(f'- **{ftype}**: {len(files)} 个')
        lines.append('')
        # 按目录汇总
        lines.append('## 按目录')
        for d, files in sorted(index.get('by_dir', {}).items()):
            lines.append(f'- **{d}/**: {len(files)} 个文件')
        lines.append('')
        # 完整文件列表
        lines.append('## 完整文件列表')
        for rel in sorted(index['files'].keys()):
            entry = index['files'][rel]
            meta_flag = ' [.meta]' if entry.get('meta_file') else ''
            lines.append(f'- `{rel}` ({entry["type"]}, {entry["size"]:,}B{meta_flag})')

        Path(out).write_text('\n'.join(lines), encoding='utf-8')
        print(f'✅ Markdown 报告: {out}')
    return 0


# ── CLI ──────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='Unity 大型工程文件管理器 — 索引/查找/快照/回滚/校验',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest='command', help='子命令')

    # index
    p_idx = sub.add_parser('index', help='扫描目录，构建文件索引')
    p_idx.add_argument('path', help='目标目录')
    p_idx.set_defaults(func=cmd_index)

    # find
    p_find = sub.add_parser('find', help='从索引查询文件')
    p_find.add_argument('path', help='目标目录（需要有索引）')
    p_find.add_argument('--type', '-t', help='文件类型 (prefab/fbx/mat/png/...)')
    p_find.add_argument('--name', '-n', help='文件名关键词（模糊匹配）')
    p_find.add_argument('--dir', '-d', help='限定子目录')
    p_find.add_argument('--include-meta', action='store_true', help='包含 .meta 文件')
    p_find.add_argument('--long', '-l', action='store_true', help='显示详细信息')
    p_find.set_defaults(func=cmd_find)

    # snapshot
    p_snap = sub.add_parser('snapshot', help='快照：git init(如需要) + commit + 刷新索引')
    p_snap.add_argument('path', help='目标目录')
    p_snap.add_argument('--message', '-m', help='提交信息')
    p_snap.set_defaults(func=cmd_snapshot)

    # status
    p_stat = sub.add_parser('status', help='当前状态一览')
    p_stat.add_argument('path', help='目标目录')
    p_stat.set_defaults(func=cmd_status)

    # verify
    p_ver = sub.add_parser('verify', help='检查 .meta 一致性')
    p_ver.add_argument('path', help='目标目录')
    p_ver.set_defaults(func=cmd_verify)

    # rollback
    p_rb = sub.add_parser('rollback', help='回滚到上一个快照（默认 dry-run，加 --confirm 执行）')
    p_rb.add_argument('path', help='目标目录')
    p_rb.add_argument('--to', help='回滚目标 (默认 HEAD~1)')
    p_rb.add_argument('--confirm', action='store_true', help='确认执行回滚')
    p_rb.set_defaults(func=cmd_rollback)

    # info
    p_inf = sub.add_parser('info', help='查看单个文件详情')
    p_inf.add_argument('path', help='目标目录')
    p_inf.add_argument('file', help='文件路径（相对于目标目录）')
    p_inf.set_defaults(func=cmd_info)

    # plan
    p_plan = sub.add_parser('plan', help='生成重命名映射表（dry-run，不改文件）')
    p_plan.add_argument('directory', help='目标 Unity 项目目录')
    p_plan.add_argument('--rules', '-r', required=True, help='规则文件路径（JSON 格式）')
    p_plan.add_argument('--output', '-o', help='映射表输出路径（默认自动生成到 scratch 目录）')
    p_plan.set_defaults(func=cmd_plan)

    # apply
    p_apply = sub.add_parser('apply', help='执行重命名映射表')
    p_apply.add_argument('plan_file', help='plan 命令生成的映射表 JSON 文件')
    p_apply.add_argument('--confirm', action='store_true', help='真正执行（否则 dry-run）')
    p_apply.add_argument('--dry-run', action='store_true', help='显式 dry-run 模式（默认）')
    p_apply.set_defaults(func=cmd_apply)

    # export
    p_exp = sub.add_parser('export', help='导出报告')
    p_exp.add_argument('path', help='目标目录')
    p_exp.add_argument('--format', '-f', choices=['json', 'md'], default='json', help='输出格式')
    p_exp.add_argument('--output', '-o', help='输出文件路径')
    p_exp.set_defaults(func=cmd_export)

    args = ap.parse_args()
    if not args.command:
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
