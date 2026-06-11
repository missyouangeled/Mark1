#!/usr/bin/env python3
"""
会话状态快照备份 — 在数据盘独立保存近期对话与记忆状态
适用机器：公司（Linux）/ 通用

在数据盘 /mnt/data/openclaw/session-backup/ 下保存：
- 今天的每日记录副本 + transcript
- MEMORY.md 副本
- SOUL.md + USER.md 副本
- session-state.json（会话目录大小/修改时间快照）
- 上下文摘要（AI 可读的恢复指南）
- 备份日志

用途：
- Gateway 重启 / session 压缩 / 意外清理后快速恢复上下文
- 独立于 workspace 仓库，不受 git 操作影响
- 默认保留 14 天

用法：
  python3 scripts/openclaw-session-backup.py                 # 执行一次快照
  python3 scripts/openclaw-session-backup.py --quiet         # 静默模式（systemd timer）
  python3 scripts/openclaw-session-backup.py --restore-last  # 查看最近备份
  python3 scripts/openclaw-session-backup.py --clean 14      # 清理 14 天前的备份
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
SESSIONS_DIR = Path.home() / ".openclaw/agents/main/sessions"
RETENTION_DAYS = 7
MANIFEST_FILE = BACKUP_ROOT / "backup-manifest.json"

# 磁盘安全检查阈值：workspace 所在盘余量低于此值（GB），只写数据盘
MIN_ROOT_FREE_GB = 2.0


def get_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_timestamp_str() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H%M%S")


def _get_free_gb(path: Path) -> float:
    """获取路径所在磁盘分区的可用空间（GB）"""
    try:
        stat = os.statvfs(str(path))
        free_bytes = stat.f_frsize * stat.f_bavail
        return free_bytes / (1024 ** 3)
    except Exception:
        return float("inf")


def _can_write_workspace_disk() -> bool:
    """工作区所在盘余量 >= 2GB 才允许写入备份副本"""
    free = _get_free_gb(WORKSPACE)
    return free >= MIN_ROOT_FREE_GB


def _build_session_state() -> dict:
    """扫描 ~/.openclaw/agents/main/sessions/ 目录，生成 session-state.json"""
    state = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sessions": {},
        "trajectories": {},
        "summary": {"total_sessions": 0, "total_mb": 0},
    }

    if not SESSIONS_DIR.exists():
        return state

    total_bytes = 0

    for f in sorted(SESSIONS_DIR.glob("*.jsonl")):
        fname = f.name
        if fname == "sessions.json":
            continue
        is_meta_file = any(
            marker in fname for marker in (".checkpoint.", ".trajectory", ".reset.")
        )
        if is_meta_file:
            try:
                size = f.stat().st_size
                state["trajectories"][fname] = {
                    "size_bytes": size,
                    "size_mb": round(size / (1024 ** 2), 2),
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                }
                total_bytes += size
            except OSError:
                pass
            continue

        # 主会话文件：文件名即 sessionKey
        session_key = fname.replace(".jsonl", "")
        try:
            size = f.stat().st_size
            entry = {
                "size_bytes": size,
                "size_mb": round(size / (1024 ** 2), 2),
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }

            # 查找关联的 checkpoint/trajectory
            for sf in SESSIONS_DIR.glob(f"{session_key}.*"):
                if sf.name == fname:
                    continue
                try:
                    ss = sf.stat().st_size
                    entry.setdefault("extras", {})[sf.name] = {
                        "size_bytes": ss,
                        "size_mb": round(ss / (1024 ** 2), 2),
                    }
                    total_bytes += ss
                except OSError:
                    pass

            state["sessions"][session_key] = entry
            total_bytes += size
        except OSError:
            pass

    state["summary"]["total_sessions"] = len(state["sessions"])
    state["summary"]["total_mb"] = round(total_bytes / (1024 ** 2), 2)

    return state


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

    workspace_disk_ok = _can_write_workspace_disk()

    # 1. 今天 + 昨天的每日记录
    for day_offset in [0, 1]:
        day = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        src = MEMORY_DIR / f"{day}.md"
        if src.exists():
            dst = snapshot_dir / f"daily-{day}.md"
            shutil.copy2(src, dst)
            result["files"].append(str(dst))

    # 1b. Transcript 文件：最近 2 天完整复制，2～7 天仅保留 daily.md 摘要
    for day_offset in range(7):  # 检查过去 7 天
        day = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        src = MEMORY_DIR / f"{day}-transcript.md"
        if not src.exists():
            continue
        if day_offset <= 1:
            # 最近 2 天：完整复制
            dst = snapshot_dir / f"daily-{day}-transcript.md"
            shutil.copy2(src, dst)
            result["files"].append(str(dst))
        # 2~7 天：不额外复制 transcript（已有 daily.md 摘要，且会被清理逻辑处理）

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

    # 4. 会话状态快照
    session_state = _build_session_state()
    state_file = snapshot_dir / "session-state.json"
    state_file.write_text(json.dumps(session_state, ensure_ascii=False, indent=2), encoding="utf-8")
    result["files"].append(str(state_file))

    # 5. 上下文摘要 — 增强版（含 transcript 最后 50 行）
    context_summary = build_context_summary()
    summary_file = snapshot_dir / "context-summary.md"
    summary_file.write_text(context_summary, encoding="utf-8")
    result["files"].append(str(summary_file))

    # 6. 磁盘安全检查：若 workspace 盘余量不足，不写根盘副本
    if not workspace_disk_ok:
        result["errors"].append(
            f"工作区磁盘余量不足 ({_get_free_gb(WORKSPACE):.1f}GB < {MIN_ROOT_FREE_GB}GB)，"
            f"已跳过往根盘写副本，仅保存到数据盘 {BACKUP_ROOT}"
        )

    # 7. 更新 manifest
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
    """从现有文件构建当前会话上下文摘要 — AI 可读的恢复指南

    包含：
    - 今日摘要（daily.md）
    - 今日 transcript 尾巴（最后 200 行）
    - 昨日摘要（daily.md 的「重要事项」段）
    - 昨日 transcript 尾巴（最后 300 行）
    """
    now = datetime.now()
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    summary = f"""# 🔄 会话上下文快照 — AI 恢复指南

## ⚠️ 如果你是刚醒来的 AI 模型，请先读这里

在你开始回复点点之前：
1. 先读完本文件的全部内容（特别是「最近规则」和「今日摘要」）
2. 然后读本目录下的 `MEMORY.md`（备份副本）
3. 然后读 `daily-{today}.md`（今日记录）和 `daily-{today}-transcript.md`（今日对话记录）
4. 然后读「昨日摘要」和「昨日对话尾巴」了解跨天断层内容
5. 然后再开始回复——不要一张嘴就说"早上好"如果今天已经聊了很久

## 生成时间
{now.strftime('%Y-%m-%d %H:%M:%S %Z')}

## 今日摘要
"""

    # 最近的核心记忆条目
    try:
        mem = MEMORY_FILE.read_text(encoding="utf-8")
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
    today_file = MEMORY_DIR / f"{today}.md"
    if today_file.exists():
        summary += f"## 今日记录\n摘要已备份至 `daily-{today}.md`\n\n"

    # 从 daily.md 提取今日摘要正文（含「今日摘要」+「重要事项」区块）
    today_md = MEMORY_DIR / f"{today}.md"
    if today_md.exists():
        try:
            md_full = today_md.read_text(encoding="utf-8")
            import re
            m = re.search(r'(## 今日摘要.*?)(?=\n## |\Z)', md_full, re.DOTALL)
            if m:
                excerpt = m.group(1).strip()
                if len(excerpt) > 800:
                    excerpt = excerpt[:800] + "\n...(已截断)"
                summary += "## 今日摘要（来自 daily.md）\n"
                summary += excerpt + "\n\n"
        except Exception:
            pass

    # 从 transcript 提取最后 200 行（覆盖约最近 1 小时）
    transcript_file = MEMORY_DIR / f"{today}-transcript.md"
    if transcript_file.exists():
        try:
            full = transcript_file.read_text(encoding="utf-8")
            lines = full.split("\n")
            total = len(lines)
            tail_count = 200 if total >= 200 else total
            tail_lines = lines[-tail_count:] if total >= tail_count else lines
            summary += f"## 今日对话摘要（第 {total - tail_count + 1}-{total} 行 / 共 {total} 行）\n"
            summary += "```\n"
            summary += "\n".join(tail_lines)
            summary += "\n```\n\n"
        except Exception:
            pass

    # ── 🆕 昨日摘要（daily.md 的「重要事项」段）──
    yesterday_md = MEMORY_DIR / f"{yesterday}.md"
    if yesterday_md.exists():
        try:
            yd_full = yesterday_md.read_text(encoding="utf-8")
            import re
            # 提取「重要事项」区块（如果存在）
            m = re.search(r'(## 重要事项.*?)(?=\n## |\Z)', yd_full, re.DOTALL)
            if m:
                excerpt = m.group(1).strip()
                if len(excerpt) > 600:
                    excerpt = excerpt[:600] + "\n...(已截断)"
                summary += "## 昨日重要事项（跨天恢复用）\n"
                summary += excerpt + "\n\n"
            else:
                # 若无「重要事项」段，取昨日全文的前 500 字符作为摘要
                preview = yd_full[:500].strip()
                if len(yd_full) > 500:
                    preview += "\n...(已截断)"
                summary += f"## 昨日记录（{yesterday}）\n"
                summary += preview + "\n\n"
        except Exception:
            pass

    # ── 🆕 昨日 transcript 尾巴（最后 300 行）──
    yesterday_transcript = MEMORY_DIR / f"{yesterday}-transcript.md"
    if yesterday_transcript.exists():
        try:
            full = yesterday_transcript.read_text(encoding="utf-8")
            lines = full.split("\n")
            total = len(lines)
            tail_count = 300 if total >= 300 else total
            tail_lines = lines[-tail_count:] if total >= tail_count else lines
            summary += f"## 昨日对话尾巴（第 {total - tail_count + 1}-{total} 行 / 共 {total} 行）\n"
            summary += "```\n"
            summary += "\n".join(tail_lines)
            summary += "\n```\n\n"
        except Exception:
            pass

    summary += "## 恢复提示\n"
    summary += "- 主会话中断后，先读取本文件的「最近规则」部分\n"
    summary += "- 再读 MEMORY.md 的最新备份了解偏好\n"
    summary += "- 最后读今日和昨日的 daily 文件了解最近对话\n"
    summary += "- 「昨日重要事项」和「昨日对话尾巴」帮助你在跨天醒来时无缝接上\n"

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
    parser.add_argument("--quiet", action="store_true", help="静默模式（systemd timer 用）")
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
    if not args.quiet:
        print(f"📸 创建会话快照...")

    result = create_snapshot()

    if not args.quiet:
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
