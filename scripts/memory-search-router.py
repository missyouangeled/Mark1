#!/usr/bin/env python3
"""
memory-search-router.py — 统一记忆搜索路由（L1→L2→L3→L4）

实现四层搜索路由，逐层尝试，找到置信度足够的结果就短路返回。

L1: MEMORY_INDEX.yaml 关键词匹配（置信度 ≥0.8 → 返回，<0.05s）
L2: QMD BM25 全文检索（置信度 ≥0.7 → 返回，0.2-0.5s）
L3: 返回提示走云端 memory_search（不在脚本内调云端 API）
L4: 读取 session-backup context-summary

用法：
  python3 scripts/memory-search-router.py "查询词"
  python3 scripts/memory-search-router.py --layer l1 "查询词"   # 单层搜索
  python3 scripts/memory-search-router.py --layer l2 "查询词"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import yaml
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
INDEX_PATH = Path("/mnt/data/openclaw/scratch/memory-index/MEMORY_INDEX.yaml")
SESSION_BACKUP_DIR = Path("/mnt/data/openclaw/session-backup")
CONTEXT_SUMMARY = "context-summary.md"

# 各层阈值
L1_CONFIDENCE_THRESHOLD = 0.8
L2_CONFIDENCE_THRESHOLD = 0.7
LAYER_TIMEOUT_S = 5


def tokenize_for_index(query: str) -> list[str]:
    """与 memory-index-builder.py 一致的 tokenize 逻辑。"""
    tokens: list[str] = []
    # 提取中文 2-4 字短语
    cn_words = re.findall(r"[\u4e00-\u9fff]{2,4}", query)
    en_words = re.findall(r"[a-zA-Z][a-zA-Z0-9_/-]{2,}", query.lower())

    stopwords = {
        "用户", "希望", "新增", "确认", "强调", "补充", "进一步",
        "默认", "优先", "可以", "不要", "必须", "应该", "已经",
        "当前", "后续", "以后", "如果", "或者", "以及", "并且",
        "这一", "这些", "这类", "这种", "但是", "因为", "所以",
        "全部", "所有", "每个", "任何", "还",
    }
    for w in cn_words:
        if w not in stopwords:
            tokens.append(w)
    for w in en_words:
        tokens.append(w)

    return tokens


def search_l1_index(query: str) -> dict | None:
    """L1: 在 MEMORY_INDEX.yaml 中做关键词匹配。"""
    if not INDEX_PATH.exists():
        return None

    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            idx = yaml.safe_load(f)
    except Exception:
        return None

    if not idx or "index" not in idx:
        return None

    index = idx["index"]
    tokens = tokenize_for_index(query)
    if not tokens:
        return None

    matches: list[dict] = []
    seen = set()
    for token in tokens:
        if token in index:
            for entry in index[token]:
                dedup_key = (entry["file"], entry["line"])
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    matches.append({
                        "file": entry["file"],
                        "line": entry["line"],
                        "snippet": entry.get("snippet", ""),
                        "keyword": token,
                    })

    if not matches:
        return None

    # 置信度 = min(1.0, 命中关键词数/总token数 × 1.0)
    kw_hit_ratio = len({m["keyword"] for m in matches}) / max(len(tokens), 1)
    # 匹配条目数因子（越多越确信）
    density = min(len(matches) / 3, 1.0)
    confidence = min(kw_hit_ratio * 0.6 + density * 0.4, 1.0)

    return {
        "layer": "L1",
        "confidence": round(confidence, 3),
        "matches": matches[:10],
        "short_circuit": confidence >= L1_CONFIDENCE_THRESHOLD,
    }


def search_l2_qmd(query: str) -> dict | None:
    """L2: QMD BM25 全文检索。"""
    try:
        result = subprocess.run(
            ["qmd", "search", query, "--top", "5"],
            capture_output=True, text=True,
            timeout=LAYER_TIMEOUT_S,
            cwd=str(WORKSPACE),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    # 解析 QMD 输出
    lines = result.stdout.strip().split("\n")
    matches: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 格式: qmd://path:lineno #hash 或 Title: ...
        m = re.match(r"qmd://(.+?):(\d+)\s+#\w+", line)
        if m:
            matches.append({
                "file": m.group(1),
                "line": int(m.group(2)),
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
        return None

    # 用最高分和命中数计算置信度
    top_score = max((m.get("score", 0) for m in matches), default=0)
    density = min(len(matches) / 3, 1.0)
    confidence = min(top_score * 0.7 + density * 0.3, 1.0)

    return {
        "layer": "L2",
        "confidence": round(confidence, 3),
        "matches": matches,
        "short_circuit": confidence >= L2_CONFIDENCE_THRESHOLD,
    }


def search_l3_cloud(query: str) -> dict:
    """L3: 返回提示走云端 memory_search（不在脚本内调 API）。"""
    return {
        "layer": "L3",
        "confidence": 0.0,
        "message": "本地搜索置信度不足，建议调用 memory_search 工具进行云端语义搜索",
        "action": "call_memory_search_tool",
        "short_circuit": False,
    }


def search_l4_backup(query: str) -> dict:
    """L4: 读取 session-backup context-summary。"""
    # 找到最新的 snapshot
    snapshots = sorted(
        SESSION_BACKUP_DIR.glob("snapshot-*"),
        key=lambda p: p.stat().st_mtime, reverse=True,
    ) if SESSION_BACKUP_DIR.exists() else []

    results: list[dict] = []
    for snap in snapshots[:1]:  # 只取最新一个
        summary_path = snap / CONTEXT_SUMMARY
        if not summary_path.exists():
            continue
        try:
            content = summary_path.read_text(encoding="utf-8")
            # 简单搜索：找包含查询词的行
            for i, line in enumerate(content.split("\n"), 1):
                if query.lower() in line.lower():
                    results.append({
                        "file": str(summary_path),
                        "line": i,
                        "snippet": line.strip()[:300],
                    })
        except Exception:
            continue

    confidence = min(len(results) / 3, 0.6) if results else 0.0

    return {
        "layer": "L4",
        "confidence": round(confidence, 3),
        "matches": results[:10],
        "source": str(snapshots[0]) if snapshots else None,
        "short_circuit": False,  # L4 不短路，仅作参考
    }


def route_search(query: str, max_layer: str = "L4") -> dict:
    """执行完整的 L1→L4 路由搜索。"""
    layers = ["L1", "L2", "L3", "L4"]
    start_idx = layers.index(max_layer) if max_layer in layers else 3

    results: list[dict] = []
    route_taken = None

    for i, layer_name in enumerate(layers):
        if i > start_idx:
            break

        t0 = time.time()

        if layer_name == "L1":
            l_result = search_l1_index(query)
        elif layer_name == "L2":
            l_result = search_l2_qmd(query)
        elif layer_name == "L3":
            l_result = search_l3_cloud(query)
        elif layer_name == "L4":
            l_result = search_l4_backup(query)

        elapsed = time.time() - t0

        if l_result:
            l_result["elapsed_ms"] = round(elapsed * 1000)
            results.append(l_result)

            if l_result.get("short_circuit"):
                route_taken = layer_name
                break

    return {
        "query": query,
        "route_taken": route_taken or layers[min(start_idx, 3)],
        "layers_searched": [r["layer"] for r in results],
        "layers": results,
        "recommendation": results[-1] if results else None,
    }


def main():
    parser = argparse.ArgumentParser(description="统一记忆搜索路由")
    parser.add_argument("query", nargs="+", help="搜索词")
    parser.add_argument("--layer", choices=["l1", "l2", "l3", "l4"],
                        help="指定单层搜索（跳过其他层）")
    parser.add_argument("--json", action="store_true", default=True,
                        help="JSON 输出（默认）")
    args = parser.parse_args()

    query = " ".join(args.query).strip()
    if not query:
        print(json.dumps({"error": "empty query"}, ensure_ascii=False))
        return 1

    if args.layer:
        # 单层模式
        layer_map = {"l1": search_l1_index, "l2": search_l2_qmd,
                     "l3": search_l3_cloud, "l4": search_l4_backup}
        fn = layer_map[args.layer]
        result = fn(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result and result.get("short_circuit") else 1

    # 全路由模式
    result = route_search(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["route_taken"] in ("L1", "L2"):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
