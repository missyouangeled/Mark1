#!/usr/bin/env python3
"""
会话状态快照备份 — 在数据盘独立保存近期对话与记忆状态
适用机器：公司（Linux）/ 通用

在数据盘 /mnt/data/openclaw/session-backup/ 下保存：
- 今天的每日记录副本
- MEMORY.md 副本
- 当前对话上下文摘要（从最近消息提取）
- 备份日志

用途：
- Gateway 重启 / session 压缩 / 意外清理后快速恢复上下文
- 独立于 workspace 仓库，不受 git 操作影响
- 默认保留 7 天

用法：
  python3 scripts/openclaw-session-backup.py                 # 执行一次快照
  python3 scripts/openclaw-session-backup.py --restore-last   # 查看最近备份
  python3 scripts/openclaw-session-backup.py --clean 7        # 清理 7 天前的备份
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKUP_ROOT = Path("/mnt/data/openclaw/session-backup")
WORKSPACE = Path.home() / ".openclaw/workspace"
MEMORY_DIR = WORKSPACE / "memory/daily"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
SOUL_FILE = WORKSPACE / "SOUL.md"
USER_FILE = WORKSPACE / "USER.md"
RETENTION_DAYS = 7
MANIFEST_FILE = BACKUP_ROOT / "backup-manifest.json"


def get_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def create_snapshot() -> dict:
    """创建一次快照"""
    ts = get_timestamp_str()
    date = get_date_str()
    snapshot_dir = BACKUP_ROOT / f"snapshot-{ts}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": ts,
        "date": date,
        "path": str(snapshot_dir),
        "files": [],
        "errors": [],
    }

    # 1. 今天 + 昨天的每日记录
    for day_offset in [0, 1]:
        day = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        src = MEMORY_DIR / f"{day}.md"
        if src.exists():
            dst = snapshot_dir / f"daily-{day}.md"
            shutil.copy2(src, dst)
            result["files"].append(str(dst))

    # 2. MEMORY.md
    if MEMORY_FILE.exists():
        dst = snapshot_dir / "MEMORY.md"
        shutil.copy2(MEMORY_FILE, dst)
        result["files"].append(str(dst))

    # 3. SOUL.md + USER.md
    for f in [SOUL_FILE, USER_FILE]:
        if f.exists():
            dst = snapshot_dir / f.name
            shutil.copy2(f, dst)
            result["files"].append(str(dst))

    # 4. 上下文摘要 — 从最近聊天中提取关键信息
    context_summary = build_context_summary()
    summary_file = snapshot_dir / "context-summary.md"
    summary_file.write_text(context_summary, encoding="utf-8")
    result["files"].append(str(summary_file))

    # 5. 更新 manifest
    manifest = load_manifest()
    manifest["snapshots"].append({
        "timestamp": ts,
        "date": date,
        "path": str(snapshot_dir),
        "fileCount": len(result["files"]),
    })
    # 只保留最近 30 条
    manifest["snapshots"] = manifest["snapshots"][-30:]
    save_manifest(manifest)

    result["manifestUpdated"] = True
    return result


def build_context_summary() -> str:
    """从现有文件构建当前会话上下文摘要"""
    summary = f"# 会话上下文快照\n\n## 生成时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n\n"

    # 最近的核心记忆条目
    try:
        mem = MEMORY_FILE.read_text(encoding="utf-8")
        # 提取最近一条规则/方法论
        lines = mem.split("\n")
        recent_rules = []
        capture = False
        for line in lines:
            if "2026-06-09" in line or "2026-06-08" in line:
                capture = True
            if capture and line.strip():
                recent_rules.append(line)
            if len(recent_rules) > 15:
                break
        if recent_rules:
            summary += "## 最近规则/偏好更新\n"
            summary += "\n".join(recent_rules) + "\n\n"
    except Exception:
        pass

    # 今日工作记录
    today_file = MEMORY_DIR / f"{get_date_str()}.md"
    if today_file.exists():
        summary += f"## 今日记录\n摘要已备份至 `daily-{get_date_str()}.md`\n\n"

    summary += "## 恢复提示\n"
    summary += "- 主会话中断后，先读取本文件的「最近规则」部分\n"
    summary += "- 再读 MEMORY.md 的最新备份了解偏好\n"
    summary += "- 最后读今日和昨日的 daily 文件了解最近对话\n"

    return summary


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text())
        except Exception:
            pass
    return {"snapshots": [], "created": get_timestamp_str()}


def save_manifest(manifest: dict):
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))


def restore_last() -> dict:
    """返回最近一次快照的信息"""
    manifest = load_manifest()
    snapshots = manifest.get("snapshots", [])
    if not snapshots:
        return {"found": False, "message": "暂无快照"}

    last = snapshots[-1]
    snap_path = Path(last["path"])
    files = list(snap_path.glob("*")) if snap_path.exists() else []

    return {
        "found": True,
        "snapshot": last,
        "files": [str(f.relative_to(snap_path)) for f in files],
        "path": str(snap_path),
    }


def clean_old(days: int = RETENTION_DAYS):
    """清理旧快照"""
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0

    for d in BACKUP_ROOT.iterdir():
        if d.is_dir() and d.name.startswith("snapshot-"):
            try:
                ts_str = d.name.replace("snapshot-", "")
                ts = datetime.strptime(ts_str, "%Y-%m-%dT%H%M%S")
                if ts < cutoff:
                    shutil.rmtree(d)
                    removed += 1
            except (ValueError, OSError):
                pass

    # 更新 manifest
    manifest = load_manifest()
    manifest["snapshots"] = [
        s for s in manifest.get("snapshots", [])
        if Path(s["path"]).exists()
    ]
    save_manifest(manifest)

    return {"removed": removed, "retentionDays": days}


# ── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="会话状态快照备份")
    parser.add_argument("--restore-last", action="store_true", help="查看最近备份")
    parser.add_argument("--clean", type=int, nargs="?", const=RETENTION_DAYS,
                        help=f"清理旧快照（默认保留 {RETENTION_DAYS} 天）")
    args = parser.parse_args()

    if args.restore_last:
        info = restore_last()
        if info["found"]:
            print(f"📦 最近快照: {info['snapshot']['timestamp']}")
            print(f"📁 路径: {info['path']}")
            print(f"📄 文件: {', '.join(info['files'])}")
        else:
            print("📭 暂无快照")
        return 0

    if args.clean is not None:
        print(f"🧹 清理 {args.clean} 天前的快照...")
        result = clean_old(days=args.clean)
        print(f"   已清理 {result['removed']} 个旧快照")
        return 0

    # 创建快照
    print(f"📸 创建会话快照...")
    result = create_snapshot()
    print(f"   {result['timestamp']}")
    print(f"   {len(result['files'])} 个文件 → {result['path']}")
    for f in result["files"]:
        print(f"     ✓ {Path(f).name}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"     ⚠ {e}")
    print("✅ 完成")


if __name__ == "__main__":
    sys.exit(main())
