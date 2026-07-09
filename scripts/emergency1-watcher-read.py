#!/usr/bin/env python3
"""读 watcher alerts.json，输出未读摘要；是否 mark read 由调用方显式决定。

默认：只读不改。
加 --mark：输出后把 unread 置回 False。

这样可以保证：只有真正完成转发后，调用方才标记已读，避免注入失败却把告警吃掉。
"""
import json
import sys
from pathlib import Path


def mark_read(path: Path) -> None:
    if not path.exists():
        return
    d = json.loads(path.read_text())
    d["unread"] = False
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2))
    tmp.replace(path)


def main():
    if len(sys.argv) < 2:
        print("ERR: usage: emergency1-watcher-read.py <alerts.json> [--mark]")
        sys.exit(1)

    alerts_path = Path(sys.argv[1])
    do_mark = "--mark" in sys.argv

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
        level = it.get("level", "?")
        unique.append((level, msg))
        levels[level] = levels.get(level, 0) + 1

    summary = "; ".join([f"{k}={v}" for k, v in levels.items()])
    print(f"UNREAD_SUMMARY={summary}")
    for level, msg in unique[:3]:
        print(f"WARN: [{level}] {msg}")

    if do_mark:
        mark_read(alerts_path)


if __name__ == "__main__":
    main()