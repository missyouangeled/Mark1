#!/usr/bin/env python3
"""
query-cache.py — 轻量 TTL 缓存层

为 memory_search / infos-handle / broker 重复查询提供本地 TTL 缓存。
不依赖 Redis，JSON 文件存储，适合单机低频调用。

默认 TTL: 60s，最大条目: 200

用法：
  python3 scripts/query-cache.py get <namespace> <key>       → stdout: 缓存值或空(NOT_FOUND)
  python3 scripts/query-cache.py set <namespace> <key> <ttl>  → stdin 读值
  python3 scripts/query-cache.py stats                        → 缓存统计
  python3 scripts/query-cache.py purge                        → 清空所有缓存
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_TTL = 60
MAX_ENTRIES = 200

STATE_HOME = os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
CACHE_DIR = Path(STATE_HOME) / "openclaw" / "cache"
CACHE_PATH = CACHE_DIR / "query-cache.json"


def _load() -> dict:
    if not CACHE_PATH.exists():
        return {"entries": {}}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": {}}


def _save(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def _key(namespace: str, query: str) -> str:
    return f"{namespace}:{hashlib.md5(query.encode()).hexdigest()[:12]}"


def _cleanup(entries: dict, now: float) -> dict:
    """删除过期条目 + 按条目数裁剪。"""
    clean = {k: v for k, v in entries.items() if v.get("expiresAt", 0) > now}
    if len(clean) > MAX_ENTRIES:
        sorted_items = sorted(clean.items(), key=lambda x: x[1].get("ts", 0))
        clean = dict(sorted_items[-MAX_ENTRIES:])
    return clean


def get(namespace: str, query: str) -> str | None:
    data = _load()
    now = time.time()
    k = _key(namespace, query)
    entry = data["entries"].get(k)
    if entry and entry.get("expiresAt", 0) > now:
        return entry.get("value")
    # 清理过期
    data["entries"] = _cleanup(data["entries"], now)
    _save(data)
    return None


def set(namespace: str, query: str, value: str, ttl: int = DEFAULT_TTL) -> None:
    data = _load()
    now = time.time()
    data["entries"] = _cleanup(data["entries"], now)
    k = _key(namespace, query)
    data["entries"][k] = {
        "ts": now,
        "expiresAt": now + ttl,
        "value": value,
    }
    _save(data)


def stats() -> dict:
    data = _load()
    now = time.time()
    entries = data.get("entries", {})
    total = len(entries)
    active = sum(1 for v in entries.values() if v.get("expiresAt", 0) > now)
    return {"total": total, "active": active, "expired": total - active}


def purge() -> None:
    _save({"entries": {}})


def main():
    parser = argparse.ArgumentParser(description="TTL 查询缓存")
    sub = parser.add_subparsers(dest="action", required=True)

    get_p = sub.add_parser("get")
    get_p.add_argument("namespace")
    get_p.add_argument("key", nargs="+")

    set_p = sub.add_parser("set")
    set_p.add_argument("namespace")
    set_p.add_argument("ttl", type=int, nargs="?", default=DEFAULT_TTL)
    set_p.add_argument("key", nargs="+")

    sub.add_parser("stats")
    sub.add_parser("purge")

    args = parser.parse_args()

    if args.action == "get":
        ns = args.namespace
        query = " ".join(args.key)
        val = get(ns, query)
        if val is not None:
            print(val, end="")
            return 0
        else:
            print("NOT_FOUND")
            return 1

    elif args.action == "set":
        ns = args.namespace
        query = " ".join(args.key)
        ttl = args.ttl
        value = sys.stdin.read()
        set(ns, query, value, ttl)
        return 0

    elif args.action == "stats":
        s = stats()
        print(json.dumps(s, ensure_ascii=False))
        return 0

    elif args.action == "purge":
        purge()
        print("purged")
        return 0


if __name__ == "__main__":
    sys.exit(main())
