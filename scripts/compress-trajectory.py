#!/usr/bin/env python3
"""压缩 trajectory jsonl，删除旧 context.compiled 和 prompt.submitted 事件。

策略（保守）：
- 保留所有 lifecycle 事件（session.started, trace.metadata, session.ended, model.completed, trace.artifacts）
- context.compiled 和 prompt.submitted 只保留最近 KEEP_RECENT（默认 3）个

适用场景：
- trajectory 单文件超过 watcher 阈值（5MB）
- 系统稳定但 trajectory 累积
- gateway 进程未持有 trajectory fd（事件驱动关闭后）

风险：
- 删除后无法恢复未保留的事件 → 必须先备份
- 不影响当前主会话（gateway 用 jsonl 不依赖 trajectory）

用法：
  python3 scripts/compress-trajectory.py <session-id> [--keep 3] [--execute]
  默认 dry-run，加 --execute 才真写
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SESSIONS_DIR = Path.home() / ".openclaw/agents/main/sessions"
BACKUP_SUFFIX = ".pre-compress"

DROP_TYPES = {"context.compiled", "prompt.submitted"}


def compress(events: list, keep_recent: int = 3) -> list:
    """压缩事件列表。"""
    by_type = {}
    for e in events:
        by_type.setdefault(e["type"], []).append(e)

    keep = []
    for type_, evs in by_type.items():
        if type_ in DROP_TYPES:
            keep.extend(evs[-keep_recent:])
            print(f"  {type_}: 保留最近 {keep_recent} / {len(evs)}")
        else:
            keep.extend(evs)
            print(f"  {type_}: 保留全部 {len(evs)}")
    keep.sort(key=lambda e: e.get("seq", 0))
    return keep


def main():
    ap = argparse.ArgumentParser(description="压缩 trajectory jsonl")
    ap.add_argument("session_id", help="session UUID")
    ap.add_argument("--keep", type=int, default=3, help="context.compiled/prompt.submitted 保留最近 N 个（默认 3）")
    ap.add_argument("--execute", action="store_true", help="真写（默认 dry-run）")
    args = ap.parse_args()

    traj = SESSIONS_DIR / f"{args.session_id}.trajectory.jsonl"
    if not traj.exists():
        print(f"❌ trajectory 不存在: {traj}")
        sys.exit(1)

    orig_size = traj.stat().st_size
    events = [json.loads(l) for l in open(traj)]
    print(f"原: {orig_size/1024/1024:.2f} MB, {len(events)} 事件")

    keep = compress(events, args.keep)
    new_size = sum(len(json.dumps(e, ensure_ascii=False)) + 1 for e in keep)
    print(f"新: {new_size/1024/1024:.2f} MB, {len(keep)} 事件")
    print(f"减少: {(orig_size - new_size)/1024/1024:.2f} MB ({(orig_size - new_size)/orig_size*100:.0f}%)")

    if not args.execute:
        print("\n[DRY-RUN] 没真写。加 --execute 执行。")
        return

    # 备份
    backup = traj.with_suffix(traj.suffix + BACKUP_SUFFIX + "-" + __import__('datetime').datetime.now().strftime("%H%M"))
    import shutil
    shutil.copy2(traj, backup)
    print(f"备份: {backup.name}")

    # 写新文件：先写 .tmp 再 mv（避免半截状态）
    tmp = traj.with_suffix(traj.suffix + ".tmp")
    with open(tmp, "w") as f:
        for e in keep:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    tmp.replace(traj)

    actual = traj.stat().st_size
    print(f"\n✓ 压缩完成: {actual/1024/1024:.2f} MB")
    print(f"  备份保留: {backup}")
    print(f"  备份体积: {backup.stat().st_size/1024/1024:.2f} MB")


if __name__ == "__main__":
    main()
