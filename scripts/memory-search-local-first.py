#!/usr/bin/env python3
"""
memory-search-local-first.py — 本地预搜短路器（L1 grep + L2 QMD BM25）

在调用 memory_search（云端 github-copilot，4-10s）之前，先用本地搜索：
  L1: grep MEMORY.md + memory/*.md（置信度 >=0.7 → 短路）
  L2: QMD BM25 全文检索 memory/（置信度 >=0.7 → 短路）
  L3: 返回 exit 1，走云端 memory_search

用法：
  python3 scripts/memory-search-local-first.py "搜索词"
  → stdout: JSON 结果，含 shortCircuited=true/false 和 results
  → exit 0: 已短路（直接可用）  exit 1: 需云端搜索

集成规则（见 AGENTS.md）：
  每次调用 memory_search 前，先跑本脚本：
  - exit 0 → 直接使用结果，跳过 memory_search
  - exit 1 → 继续调用 memory_search
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MEMORY_ROOT = WORKSPACE / "memory"
MEMORY_MD = WORKSPACE / "MEMORY.md"

# 短路阈值
SHORT_CIRCUIT_THRESHOLD = 0.70   # 综合分 >= 0.7 才短路
MIN_MATCH_LINES = 2              # 至少命中 2 行
EXACT_BONUS = 0.65             # 精确关键词匹配加权
PARTIAL_BONUS = 0.2             # 部分匹配加权
DENSITY_BONUS = 0.15            # 高密度段落加权

# 需要搜索的文件
SEARCH_FILES = [MEMORY_MD] + sorted(
    MEMORY_ROOT.glob("*.md") if MEMORY_ROOT.exists() else [],
    key=lambda p: p.name,
)


def tokenize_query(query: str) -> list[str]:
    """提取搜索词中的关键词，含中文分词（滑动窗口）。"""
    # 按空格和中文字符边界拆
    tokens = re.findall(r"(?:[\u4e00-\u9fff]+|[a-zA-Z0-9_]+)", query.lower())
    result: list[str] = []
    for token in tokens:
        if len(token) >= 2:
            result.append(token)
        # 中文长 token 生成 2-char 滑动窗口子词
        if re.match(r"^[\u4e00-\u9fff]+$", token) and len(token) >= 4:
            for i in range(len(token) - 1):
                sub = token[i:i + 2]
                if sub not in result:
                    result.append(sub)
    return result


def score_line(line: str, tokens: list[str]) -> float:
    """单行评分。"""
    line_lower = line.lower()
    hits = 0
    for token in tokens:
        if token in line_lower:
            if re.search(rf"\b{re.escape(token)}\b", line_lower):
                hits += EXACT_BONUS
            else:
                hits += PARTIAL_BONUS * 0.5
    # 密度加分：token 命中的比例
    density = hits / max(len(tokens), 1)
    return min(hits + density * DENSITY_BONUS, 1.0)


def search_local(query: str) -> dict:
    """在本地文件中搜索，返回结果。"""
    tokens = tokenize_query(query)
    if not tokens:
        return {"shortCircuited": False, "results": [], "confidence": 0.0,
                "reason": "no extractable tokens"}

    all_matches: list[tuple[float, str, str, int]] = []  # score, file, line, lineno
    seen = set()

    for fpath in SEARCH_FILES:
        if not fpath.exists():
            continue
        try:
            lines = fpath.read_text(encoding="utf-8").split("\n")
        except Exception:
            continue

        rel = str(fpath.relative_to(WORKSPACE))
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("# ") or stripped.startswith("```"):
                continue
            score = score_line(stripped, tokens)
            if score > 0:
                dedup = (rel, stripped[:80])
                if dedup not in seen:
                    seen.add(dedup)
                    all_matches.append((score, rel, stripped[:300], i))

    all_matches.sort(key=lambda x: x[0], reverse=True)

    # 计算综合置信度
    match_count = len(all_matches)
    if match_count == 0:
        return {"shortCircuited": False, "results": [], "confidence": 0.0,
                "reason": "no matches"}

    top_score = all_matches[0][0]
    # 综合置信度 = 最高分 × 0.4 + 命中数因子 × 0.6
    redundancy = min(match_count / 5, 1.0)
    confidence = min(top_score * 0.4 + redundancy * 0.6, 1.0)

    if match_count < MIN_MATCH_LINES:
        return {"shortCircuited": False, "results": [], "confidence": confidence,
                "reason": f"only {match_count} matches (need >= {MIN_MATCH_LINES})"}

    if confidence < SHORT_CIRCUIT_THRESHOLD:
        return {"shortCircuited": False, "results": [], "confidence": confidence,
                "reason": f"confidence {confidence:.2f} < {SHORT_CIRCUIT_THRESHOLD}"}

    top = all_matches[:MAX_TOP_RESULTS]
    return {
        "shortCircuited": True,
        "confidence": round(confidence, 3),
        "layer": "L1-grep",
        "results": [
            {"file": f, "line": l, "lineno": n, "score": round(s, 3)}
            for s, f, l, n in top
        ],
    }


def search_qmd(query: str) -> dict:
    """L2: QMD BM25 全文检索 memory/ 目录。
    
    先 tokenize query，再用空格分隔的"索引真实关键词"传给 QMD，
    过滤滑动窗口产生的 phantom token（如"工规""工规则"）。
    """
    # Tokenize query，用 QMD 实际索引中的 token 过滤 phantom
    tokens = tokenize_query(query)
    valid_tokens: list[str] = []
    index_path = Path("/mnt/data/openclaw/scratch/memory-index/MEMORY_INDEX.json")
    if index_path.exists():
        try:
            import json
            with open(index_path, "r", encoding="utf-8") as f:
                idx = json.load(f)
            index_keys = set(idx.get("index", {}).keys()) if idx else set()
            valid_tokens = [t for t in tokens if t in index_keys and len(t) <= 3]
        except Exception:
            pass
    if not valid_tokens:
        manual_tokens = query.replace("，", " ").replace(" ", " ").strip().split()
        valid_tokens = [t for t in manual_tokens if len(t) >= 2] or [query]
    search_query = " ".join(valid_tokens[:6])

    try:
        result = subprocess.run(
            ["qmd", "search", search_query, "--top", "5"],
            capture_output=True, text=True,
            timeout=5,
            cwd=str(WORKSPACE),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"shortCircuited": False, "results": [], "confidence": 0.0,
                "layer": "L2-qmd", "reason": "qmd not available or timed out"}

    if result.returncode != 0 or not result.stdout.strip():
        return {"shortCircuited": False, "results": [], "confidence": 0.0,
                "layer": "L2-qmd", "reason": "no BM25 matches"}

    # 解析 QMD 输出
    lines = result.stdout.strip().split("\n")
    matches: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"qmd://(.+?):(\d+)\s+#\w+", line)
        if m:
            matches.append({
                "file": m.group(1),
                "lineno": int(m.group(2)),
                "raw": line,
            })
            continue
        m_title = re.match(r"Title:\s*(.+)", line)
        if m_title and matches:
            matches[-1]["title"] = m_title.group(1)
            continue
        m_score = re.match(r"Score:\s*(\d+)%", line)
        if m_score and matches:
            matches[-1]["score"] = int(m_score.group(1)) / 100.0

    if not matches:
        return {"shortCircuited": False, "results": [], "confidence": 0.0,
                "layer": "L2-qmd", "reason": "no parsed matches"}

    # 用最高分和命中数计算置信度
    top_score = max((m.get("score", 0) for m in matches), default=0)
    density = min(len(matches) / 3, 1.0)
    confidence = min(top_score * 0.7 + density * 0.3, 1.0)

    if confidence < SHORT_CIRCUIT_THRESHOLD:
        return {"shortCircuited": False, "results": [], "confidence": round(confidence, 3),
                "layer": "L2-qmd", "reason": f"confidence {confidence:.2f} < {SHORT_CIRCUIT_THRESHOLD}"}

    return {
        "shortCircuited": True,
        "confidence": round(confidence, 3),
        "layer": "L2-qmd",
        "results": [
            {
                "file": m.get("file", ""),
                "lineno": m.get("lineno", 0),
                "score": round(m.get("score", 0), 3),
                "title": m.get("title", ""),
                "snippet": m.get("raw", "")[:200],
            }
            for m in matches
        ],
    }


MAX_TOP_RESULTS = 8

# ── 内联缓存 ──
CACHE_DIR = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "openclaw" / "cache"
CACHE_PATH = CACHE_DIR / "query-cache.json"


def _cache_get(namespace: str, query: str) -> str | None:
    try:
        if not CACHE_PATH.exists():
            return None
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        k = f"{namespace}:{hashlib.md5(query.encode()).hexdigest()[:12]}"
        entry = (data.get("entries") or {}).get(k)
        if entry and entry.get("expiresAt", 0) > time.time():
            return entry.get("value")
    except Exception:
        pass
    return None


def _cache_set(namespace: str, query: str, value: str, ttl: int = 60) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {"entries": {}}
        if CACHE_PATH.exists():
            try:
                data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        now = time.time()
        k = f"{namespace}:{hashlib.md5(query.encode()).hexdigest()[:12]}"
        data.setdefault("entries", {})[k] = {
            "ts": now,
            "expiresAt": now + ttl,
            "value": value,
        }
        # 裁剪到 200 条
        entries = data.get("entries", {})
        if len(entries) > 200:
            sorted_items = sorted(entries.items(), key=lambda x: x[1].get("ts", 0))
            data["entries"] = dict(sorted_items[-200:])
        tmp = CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(CACHE_PATH)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="本地 memory 预搜短路")
    parser.add_argument("query", nargs="+", help="搜索词")
    parser.add_argument("--threshold", type=float, default=SHORT_CIRCUIT_THRESHOLD,
                        help=f"短路阈值 (默认 {SHORT_CIRCUIT_THRESHOLD})")
    parser.add_argument("--print-json", action="store_true", default=True)
    parser.add_argument("--no-cache", action="store_true", help="跳过缓存")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        print(json.dumps({"shortCircuited": False, "results": [], "confidence": 0.0,
                          "reason": "empty query"}, ensure_ascii=False))
        return 1

    # 查缓存（TTL 60s）
    if not args.no_cache:
        cached = _cache_get("memory-search", query)
        if cached:
            try:
                cached_result = json.loads(cached)
                if isinstance(cached_result, dict) and cached_result.get("shortCircuited") is not None:
                    if args.print_json:
                        print(json.dumps(cached_result, ensure_ascii=False, indent=2))
                    return 0 if cached_result["shortCircuited"] else 1
            except Exception:
                pass

    result = search_local(query)

    # L1 grep 未短路 → 尝试 L2 QMD BM25
    if not result["shortCircuited"]:
        qmd_result = search_qmd(query)
        if qmd_result["shortCircuited"]:
            result = qmd_result

    result_str = json.dumps(result, ensure_ascii=False)

    # 写缓存
    _cache_set("memory-search", query, result_str, ttl=60)

    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["shortCircuited"] else 1


if __name__ == "__main__":
    sys.exit(main())
