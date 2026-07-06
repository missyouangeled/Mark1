#!/usr/bin/env python3
"""读 watcher alerts.json 输出 UNREAD_SUMMARY + WARN 行 + mark read。

被救命 1 v4 cron 调用：
1. 读 alerts.json，输出未读告警摘要
2. 立即把 unread 设回 False（避免下次 watcher raise_alert 又重置 True 后无人接收）

注意：watcher 自己 raise_alert 会把 unread=True 重新设回，所以 mark read 必须在
紧急通知发出后立刻做。
"""
import json
import sys
from pathlib import Path


def mark_read(path: Path) -> None:
    if not path.exists():
        return
    try:
        d = json.loads(path.read_text())
        d["unread"] = False
        # 原子写：先写 tmp 再 rename
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
        tmp.replace(path)
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        print("ERR: usage: emergency1-watcher-read.py <alerts.json> [--no-mark]")
        sys.exit(1)

    alerts_path = Path(sys.argv[1])
    mark = "--no-mark" not in sys.argv

    try:
        d = json.loads(alerts_path.read_text())
    except Exception as e:
        print(f"ERR: {e}")
        sys.exit(1)

    if not d.get("unread"):
        sys.exit(0)

    items = d.get("items", [])
    levels = {}
    seen = set()
    unique = []
    for it in items:
        msg = it.get("message", "")[:120]
        if msg in seen:
            continue
        seen.add(msg)
        unique.append((it.get("level", "?"), msg))
        levels[it.get("level", "?")] = levels.get(it.get("level", "?"), 0) + 1

    summary = "; ".join([f"{k}={v}" for k, v in levels.items()])
    print(f"UNREAD_SUMMARY={summary}")
    for level, msg in unique[:3]:
        print(f"WARN: [{level}] {msg}")

    # 标记已读（在输出之后，让 watcher 任何后续 raise_alert 也不会再次 unread 我们看过的内容）
    if mark:
        mark_read(alerts_path)


if __name__ == "__main__":
    main()